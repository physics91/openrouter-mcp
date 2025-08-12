#!/usr/bin/env python3
"""
간단한 MCP 벤치마크 도구 테스트
"""

import json
import os
import tempfile
import pytest
from unittest.mock import Mock, AsyncMock, patch

from src.openrouter_mcp.handlers.benchmark import BenchmarkResult, BenchmarkMetrics


class TestMCPBenchmarkSimple:
    """간단한 MCP 벤치마크 테스트"""
    
    @pytest.fixture
    def sample_metrics(self):
        """샘플 메트릭 생성"""
        return BenchmarkMetrics(
            avg_response_time_ms=1500.0,
            avg_tokens_used=150.0,
            avg_cost=0.001,
            total_cost=0.003,
            success_rate=1.0,
            sample_count=3,
            avg_quality_score=8.5,
            avg_throughput=100.0,
            avg_prompt_tokens=100.0,
            avg_completion_tokens=50.0,
            cost_per_quality_point=0.00012
        )
    
    @pytest.fixture
    def sample_result(self, sample_metrics):
        """샘플 벤치마크 결과 생성"""
        return BenchmarkResult(
            model_id="test-model",
            success=True,
            response="테스트 응답입니다.",
            error_message=None,
            metrics=sample_metrics
        )
    
    def test_benchmark_metrics_creation(self, sample_metrics):
        """벤치마크 메트릭 생성 테스트"""
        assert sample_metrics.avg_response_time_ms == 1500.0
        assert sample_metrics.avg_cost == 0.001
        assert sample_metrics.success_rate == 1.0
        assert sample_metrics.avg_quality_score == 8.5
    
    def test_benchmark_result_creation(self, sample_result):
        """벤치마크 결과 생성 테스트"""
        assert sample_result.model_id == "test-model"
        assert sample_result.success is True
        assert sample_result.response == "테스트 응답입니다."
        assert sample_result.metrics is not None
        assert sample_result.metrics.avg_cost == 0.001
    
    def test_utility_functions(self):
        """유틸리티 함수들 테스트"""
        from src.openrouter_mcp.handlers.mcp_benchmark import (
            _calculate_avg_response_time,
            _get_best_model,
            _get_category_prompt,
            _calculate_std
        )
        
        # _calculate_avg_response_time 테스트
        results = {
            "model1": {
                "success": True,
                "metrics": {"avg_response_time": 1.5}
            },
            "model2": {
                "success": True,
                "metrics": {"avg_response_time": 2.0}
            },
            "model3": {
                "success": False,
                "metrics": {"avg_response_time": 3.0}
            }
        }
        
        avg_time = _calculate_avg_response_time(results)
        assert avg_time == 1.75  # (1.5 + 2.0) / 2
        
        # _get_best_model 테스트
        results_with_quality = {
            "model1": {
                "success": True,
                "metrics": {"quality_score": 8.0}
            },
            "model2": {
                "success": True,
                "metrics": {"quality_score": 9.5}
            }
        }
        
        best_model = _get_best_model(results_with_quality)
        assert best_model == "model2"
        
        # _get_category_prompt 테스트
        chat_prompt = _get_category_prompt("chat")
        code_prompt = _get_category_prompt("code")
        unknown_prompt = _get_category_prompt("unknown_category")
        
        assert "안녕하세요" in chat_prompt
        assert "파이썬" in code_prompt
        assert chat_prompt == unknown_prompt  # 기본값
        
        # _calculate_std 테스트
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        std = _calculate_std(values)
        assert abs(std - 1.5811) < 0.001  # 표준편차 계산 검증
        
        # 단일 값에 대한 표준편차
        single_value = _calculate_std([1.0])
        assert single_value == 0
    
    @pytest.mark.asyncio
    async def test_get_benchmark_handler_env_error(self):
        """환경변수 오류 테스트"""
        from src.openrouter_mcp.handlers.mcp_benchmark import get_benchmark_handler
        
        # API 키가 없을 때
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(Exception) as exc_info:
                await get_benchmark_handler()
            assert "OPENROUTER_API_KEY" in str(exc_info.value)
    
    def test_performance_analysis_functions(self):
        """성능 분석 함수 테스트"""
        from src.openrouter_mcp.handlers.mcp_benchmark import (
            _analyze_cost_efficiency,
            _analyze_performance_distribution,
            _generate_recommendations
        )
        
        # 모킹된 결과 생성
        mock_result1 = Mock()
        mock_result1.success = True
        mock_result1.metrics.avg_cost = 0.001
        mock_result1.metrics.quality_score = 8.0
        
        mock_result2 = Mock()
        mock_result2.success = True
        mock_result2.metrics.avg_cost = 0.002
        mock_result2.metrics.quality_score = 9.0
        
        results = {
            "model1": mock_result1,
            "model2": mock_result2
        }
        
        # 비용 효율성 분석 테스트
        cost_analysis = _analyze_cost_efficiency(results)
        assert "most_cost_efficient" in cost_analysis
        assert "avg_cost" in cost_analysis
        
        # 성능 분포 분석 테스트
        mock_result1.metrics.avg_response_time = 1.5
        mock_result1.metrics.throughput = 100.0
        mock_result2.metrics.avg_response_time = 2.0
        mock_result2.metrics.throughput = 80.0
        
        perf_analysis = _analyze_performance_distribution(results)
        assert "response_time" in perf_analysis
        assert "quality" in perf_analysis
        assert "throughput" in perf_analysis
        
        # 추천사항 생성 테스트
        ranking = [(mock_result1, 0.8), (mock_result2, 0.9)]
        weights = {"speed": 0.3, "cost": 0.3, "quality": 0.4}
        mock_result1.model_id = "model1"
        mock_result2.model_id = "model2"
        
        recommendations = _generate_recommendations(ranking, weights)
        assert len(recommendations) >= 1
        assert recommendations[0]["type"] == "best_overall"
        assert recommendations[0]["model"] == "model1"  # ranking의 첫 번째
    
    def test_category_prompts(self):
        """카테고리별 프롬프트 테스트"""
        from src.openrouter_mcp.handlers.mcp_benchmark import _get_category_prompt
        
        # 각 카테고리별 프롬프트 테스트
        categories = ["chat", "code", "reasoning", "multimodal", "image", "unknown"]
        
        for category in categories:
            prompt = _get_category_prompt(category)
            assert isinstance(prompt, str)
            assert len(prompt) > 10  # 의미 있는 길이
        
        # 기본값 테스트 (unknown이면 chat과 같아야 함)
        chat_prompt = _get_category_prompt("chat")
        unknown_prompt = _get_category_prompt("unknown_category")
        assert chat_prompt == unknown_prompt
    
    def test_math_utilities(self):
        """수학 유틸리티 테스트"""
        from src.openrouter_mcp.handlers.mcp_benchmark import _calculate_std
        
        # 정상적인 경우
        values = [2, 4, 4, 4, 5, 5, 7, 9]
        std_dev = _calculate_std(values)
        assert std_dev > 0
        
        # 빈 리스트
        empty_std = _calculate_std([])
        assert empty_std == 0
        
        # 단일 값
        single_std = _calculate_std([5])
        assert single_std == 0
        
        # 모든 값이 동일
        same_values = [3, 3, 3, 3]
        same_std = _calculate_std(same_values)
        assert same_std == 0
    
    def test_json_serialization(self):
        """JSON 직렬화 테스트"""
        # 벤치마크 결과가 JSON으로 직렬화 가능한지 테스트
        test_data = {
            "timestamp": "2024-01-01T12:00:00",
            "config": {
                "models": ["gpt-4", "claude-3"],
                "prompt": "테스트 프롬프트",
                "runs": 3
            },
            "results": {
                "gpt-4": {
                    "success": True,
                    "metrics": {
                        "avg_response_time": 1.5,
                        "avg_cost": 0.001,
                        "quality_score": 8.5
                    },
                    "response": "테스트 응답"
                }
            }
        }
        
        # JSON 직렬화/역직렬화 테스트
        json_str = json.dumps(test_data, ensure_ascii=False)
        loaded_data = json.loads(json_str)
        
        assert loaded_data["config"]["models"] == ["gpt-4", "claude-3"]
        assert loaded_data["results"]["gpt-4"]["success"] is True
        assert loaded_data["results"]["gpt-4"]["metrics"]["quality_score"] == 8.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])