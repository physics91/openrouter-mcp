#!/usr/bin/env python3
"""
MCP 벤치마크 도구 테스트
"""

import json
import os
import tempfile
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

from src.openrouter_mcp.handlers import mcp_benchmark
from src.openrouter_mcp.handlers.benchmark import (
    BenchmarkResult, BenchmarkMetrics, EnhancedBenchmarkResult, 
    EnhancedBenchmarkMetrics, BenchmarkReportExporter, ModelPerformanceAnalyzer
)
from src.openrouter_mcp.handlers.mcp_benchmark import (
    get_benchmark_handler, benchmark_models, get_benchmark_history,
    compare_model_categories, export_benchmark_report, compare_model_performance
)


class TestMCPBenchmarkTools:
    """MCP 벤치마크 도구 테스트 클래스"""
    
    @pytest.fixture
    def mock_env(self):
        """환경변수 모킹"""
        with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'test-api-key'}):
            yield
    
    @pytest.fixture
    def temp_dir(self):
        """임시 디렉토리 생성"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def mock_benchmark_result(self):
        """모킹된 벤치마크 결과"""
        metrics = EnhancedBenchmarkMetrics(
            avg_response_time=1.5,  # 초 단위
            avg_cost=0.001,
            quality_score=8.5,
            throughput=100.0,
            success_rate=1.0,
            avg_prompt_tokens=100.0,
            avg_completion_tokens=50.0,
            avg_total_tokens=150.0,
            speed_score=0.8,
            cost_score=0.9,
            throughput_score=0.85
        )
        
        result = EnhancedBenchmarkResult(
            model_id="test-model",
            success=True,
            response="테스트 응답입니다.",
            error_message=None,
            metrics=metrics,
            timestamp=datetime.now()
        )
        
        return result
    
    @pytest.mark.asyncio
    async def test_get_benchmark_handler(self, mock_env):
        """벤치마크 핸들러 싱글톤 테스트"""
        with patch('src.openrouter_mcp.handlers.mcp_benchmark.EnhancedBenchmarkHandler') as mock_handler_class:
            with patch('src.openrouter_mcp.handlers.mcp_benchmark.ModelCache') as mock_cache_class:
                mock_handler = Mock()
                mock_handler_class.return_value = mock_handler
                mock_cache_class.return_value = Mock()
                
                # 첫 번째 호출
                handler1 = await mcp_benchmark.get_benchmark_handler()
                
                # 두 번째 호출 (싱글톤이므로 같은 인스턴스)
                handler2 = await mcp_benchmark.get_benchmark_handler()
                
                assert handler1 is handler2
                mock_handler_class.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_benchmark_models_success(self, mock_env, mock_benchmark_result):
        """모델 벤치마킹 성공 테스트"""
        models = ["gpt-3.5-turbo", "claude-3-haiku"]
        prompt = "테스트 프롬프트"
        
        # 모킹된 핸들러 결과
        mock_results = {
            "gpt-3.5-turbo": mock_benchmark_result,
            "claude-3-haiku": mock_benchmark_result
        }
        
        with patch('src.openrouter_mcp.handlers.mcp_benchmark.get_benchmark_handler') as mock_get_handler:
            mock_handler = AsyncMock()
            mock_handler.benchmark_models.return_value = mock_results
            mock_handler.save_results = AsyncMock()
            mock_get_handler.return_value = mock_handler
            
            with patch('src.openrouter_mcp.handlers.mcp_benchmark.ModelPerformanceAnalyzer') as mock_analyzer_class:
                mock_analyzer = Mock()
                mock_analyzer.rank_models.return_value = [(mock_benchmark_result, 0.85)]
                mock_analyzer_class.return_value = mock_analyzer
                
                result = await benchmark_models(
                    models=models,
                    prompt=prompt,
                    runs=2,
                    delay_seconds=0.5
                )
                
                # 결과 검증
                assert "timestamp" in result
                assert "config" in result
                assert "results" in result
                assert "ranking" in result
                assert len(result["results"]) == 2
                assert result["config"]["models"] == models
                assert result["config"]["prompt"] == prompt
                
                # 핸들러 호출 검증
                mock_handler.benchmark_models.assert_called_once_with(
                    model_ids=models,
                    prompt=prompt,
                    runs=2,
                    delay_between_requests=0.5
                )
    
    @pytest.mark.asyncio
    async def test_benchmark_models_no_success(self, mock_env):
        """모델 벤치마킹 실패 테스트"""
        models = ["invalid-model"]
        
        # 실패한 결과
        failed_result = BenchmarkResult(
            model_id="invalid-model",
            success=False,
            response=None,
            error_message="Model not found"
        )
        
        mock_results = {"invalid-model": failed_result}
        
        with patch('src.openrouter_mcp.handlers.mcp_benchmark.get_benchmark_handler') as mock_get_handler:
            mock_handler = AsyncMock()
            mock_handler.benchmark_models.return_value = mock_results
            mock_get_handler.return_value = mock_handler
            
            result = await benchmark_models(models=models)
            
            assert "results" in result
            assert result["results"]["invalid-model"]["success"] is False
            assert "ranking" not in result  # 성공한 결과가 없으므로 랭킹 없음
    
    @pytest.mark.asyncio
    async def test_get_benchmark_history_empty(self, mock_env, temp_dir):
        """빈 벤치마크 기록 테스트"""
        with patch('src.openrouter_mcp.handlers.mcp_benchmark.get_benchmark_handler') as mock_get_handler:
            mock_handler = Mock()
            mock_handler.results_dir = temp_dir
            mock_get_handler.return_value = mock_handler
            
            result = await get_benchmark_history()
            
            assert result["history"] == []
            assert result["total_files"] == 0
            assert "벤치마크 기록이 없습니다" in result["message"]
    
    @pytest.mark.asyncio
    async def test_get_benchmark_history_with_files(self, mock_env, temp_dir):
        """벤치마크 기록 파일이 있을 때 테스트"""
        # 테스트 결과 파일 생성
        test_data = {
            "timestamp": "2024-01-01T12:00:00",
            "config": {
                "models": ["gpt-3.5-turbo"],
                "prompt": "테스트"
            },
            "results": {
                "gpt-3.5-turbo": {
                    "success": True,
                    "metrics": {
                        "avg_response_time": 1.5,
                        "quality_score": 8.0
                    }
                }
            }
        }
        
        test_file = os.path.join(temp_dir, "test_benchmark.json")
        with open(test_file, 'w', encoding='utf-8') as f:
            json.dump(test_data, f)
        
        with patch('src.openrouter_mcp.handlers.mcp_benchmark.get_benchmark_handler') as mock_get_handler:
            mock_handler = Mock()
            mock_handler.results_dir = temp_dir
            mock_get_handler.return_value = mock_handler
            
            result = await get_benchmark_history(limit=5)
            
            assert len(result["history"]) == 1
            assert result["total_files"] == 1
            assert result["history"][0]["models_tested"] == ["gpt-3.5-turbo"]
            assert result["history"][0]["success_rate"] == "1/1"
    
    @pytest.mark.asyncio
    async def test_compare_model_categories(self, mock_env):
        """모델 카테고리 비교 테스트"""
        # 모킹된 모델 데이터
        mock_models = [
            {"id": "gpt-4", "category": "chat", "quality_score": 9.0},
            {"id": "claude-3", "category": "chat", "quality_score": 8.5},
            {"id": "codellama", "category": "code", "quality_score": 8.0},
            {"id": "dall-e", "category": "image", "quality_score": 7.5}
        ]
        
        with patch('src.openrouter_mcp.handlers.mcp_benchmark.get_benchmark_handler') as mock_get_handler:
            mock_handler = AsyncMock()
            mock_cache = Mock()
            mock_cache.get_models.return_value = mock_models
            mock_handler.model_cache = mock_cache
            
            # 벤치마크 결과 모킹
            mock_handler.benchmark_models.return_value = {
                "gpt-4": BenchmarkResult("gpt-4", True, "Response", None, 
                                       BenchmarkMetrics(1.0, 1.0, 1.0, 100, 50, 150, 0.001, 0.001, 0.001, 9.0, 150.0, 1.0, 0.9, 0.8, 0.85))
            }
            
            mock_get_handler.return_value = mock_handler
            
            with patch('src.openrouter_mcp.handlers.mcp_benchmark.ModelPerformanceAnalyzer') as mock_analyzer_class:
                mock_analyzer = Mock()
                mock_analyzer.rank_models.return_value = [(BenchmarkResult("gpt-4", True, "Response", None, None), 0.9)]
                mock_analyzer_class.return_value = mock_analyzer
                
                result = await compare_model_categories(
                    categories=["chat"],
                    top_n=2
                )
                
                assert "config" in result
                assert "category_info" in result
                assert "results" in result
                assert result["config"]["categories"] == ["chat"]
                assert "chat" in result["category_info"]
    
    @pytest.mark.asyncio
    async def test_export_benchmark_report_not_found(self, mock_env, temp_dir):
        """존재하지 않는 벤치마크 파일 내보내기 테스트"""
        with patch('src.openrouter_mcp.handlers.mcp_benchmark.get_benchmark_handler') as mock_get_handler:
            mock_handler = Mock()
            mock_handler.results_dir = temp_dir
            mock_get_handler.return_value = mock_handler
            
            with pytest.raises(Exception) as exc_info:
                await export_benchmark_report("nonexistent.json")
            
            assert "찾을 수 없습니다" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_export_benchmark_report_markdown(self, mock_env, temp_dir):
        """벤치마크 보고서 Markdown 내보내기 테스트"""
        # 테스트 벤치마크 파일 생성
        benchmark_data = {
            "results": {
                "gpt-3.5-turbo": {
                    "success": True,
                    "metrics": {
                        "avg_response_time": 1.5,
                        "avg_cost": 0.001,
                        "quality_score": 8.0,
                        "throughput": 100.0
                    },
                    "response": "테스트 응답"
                }
            }
        }
        
        input_file = "test_benchmark.json"
        input_path = os.path.join(temp_dir, input_file)
        with open(input_path, 'w', encoding='utf-8') as f:
            json.dump(benchmark_data, f)
        
        with patch('src.openrouter_mcp.handlers.mcp_benchmark.get_benchmark_handler') as mock_get_handler:
            mock_handler = Mock()
            mock_handler.results_dir = temp_dir
            mock_get_handler.return_value = mock_handler
            
            with patch('src.openrouter_mcp.handlers.mcp_benchmark.BenchmarkReportExporter') as mock_exporter_class:
                mock_exporter = AsyncMock()
                mock_exporter_class.return_value = mock_exporter
                
                result = await export_benchmark_report(
                    benchmark_file=input_file,
                    format="markdown"
                )
                
                assert result["format"] == "markdown"
                assert result["input_file"] == input_file
                assert "output_file" in result
                assert result["models_included"] == ["gpt-3.5-turbo"]
                
                # 내보내기 메서드 호출 검증
                mock_exporter.export_markdown.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_compare_model_performance(self, mock_env, mock_benchmark_result):
        """고급 모델 성능 비교 테스트"""
        models = ["gpt-4", "claude-3"]
        weights = {"speed": 0.3, "cost": 0.3, "quality": 0.4}
        
        mock_results = {
            "gpt-4": mock_benchmark_result,
            "claude-3": mock_benchmark_result
        }
        
        with patch('src.openrouter_mcp.handlers.mcp_benchmark.get_benchmark_handler') as mock_get_handler:
            mock_handler = AsyncMock()
            mock_handler.benchmark_models.return_value = mock_results
            mock_get_handler.return_value = mock_handler
            
            with patch('src.openrouter_mcp.handlers.mcp_benchmark.ModelPerformanceAnalyzer') as mock_analyzer_class:
                mock_analyzer = Mock()
                mock_analyzer.rank_models_with_weights.return_value = [(mock_benchmark_result, 0.85)]
                mock_analyzer_class.return_value = mock_analyzer
                
                result = await compare_model_performance(
                    models=models,
                    weights=weights,
                    include_cost_analysis=True
                )
                
                assert "config" in result
                assert "ranking" in result
                assert "detailed_metrics" in result
                assert "analysis" in result
                assert "recommendations" in result
                
                # 가중치 정규화 검증
                total_weight = sum(result["config"]["weights"].values())
                assert abs(total_weight - 1.0) < 0.001  # 부동소수점 오차 고려
    
    @pytest.mark.asyncio
    async def test_compare_model_performance_no_weights(self, mock_env, mock_benchmark_result):
        """가중치 없는 모델 성능 비교 테스트"""
        models = ["gpt-4"]
        
        mock_results = {"gpt-4": mock_benchmark_result}
        
        with patch('src.openrouter_mcp.handlers.mcp_benchmark.get_benchmark_handler') as mock_get_handler:
            mock_handler = AsyncMock()
            mock_handler.benchmark_models.return_value = mock_results
            mock_get_handler.return_value = mock_handler
            
            with patch('src.openrouter_mcp.handlers.mcp_benchmark.ModelPerformanceAnalyzer') as mock_analyzer_class:
                mock_analyzer = Mock()
                mock_analyzer.rank_models_with_weights.return_value = [(mock_benchmark_result, 0.85)]
                mock_analyzer_class.return_value = mock_analyzer
                
                result = await compare_model_performance(models=models)
                
                # 기본 가중치가 사용되었는지 확인
                expected_weights = {"speed": 0.2, "cost": 0.3, "quality": 0.4, "throughput": 0.1}
                assert result["config"]["weights"] == expected_weights
    
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
    async def test_error_handling(self, mock_env):
        """에러 핸들링 테스트"""
        # API 키가 없을 때
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(Exception) as exc_info:
                await get_benchmark_handler()
            assert "OPENROUTER_API_KEY" in str(exc_info.value)
        
        # 벤치마크 실행 중 예외 발생
        with patch('src.openrouter_mcp.handlers.mcp_benchmark.get_benchmark_handler') as mock_get_handler:
            mock_handler = AsyncMock()
            mock_handler.benchmark_models.side_effect = Exception("API Error")
            mock_get_handler.return_value = mock_handler
            
            with pytest.raises(Exception) as exc_info:
                await benchmark_models(models=["test-model"])
            assert "벤치마킹 실패" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_model_filter_in_history(self, mock_env, temp_dir):
        """벤치마크 기록에서 모델 필터링 테스트"""
        # GPT 모델이 포함된 파일
        gpt_data = {
            "results": {
                "gpt-4": {"success": True},
                "gpt-3.5-turbo": {"success": True}
            },
            "config": {}
        }
        
        # Claude 모델이 포함된 파일
        claude_data = {
            "results": {
                "claude-3-opus": {"success": True},
                "claude-3-sonnet": {"success": True}
            },
            "config": {}
        }
        
        gpt_file = os.path.join(temp_dir, "gpt_benchmark.json")
        claude_file = os.path.join(temp_dir, "claude_benchmark.json")
        
        with open(gpt_file, 'w', encoding='utf-8') as f:
            json.dump(gpt_data, f)
        with open(claude_file, 'w', encoding='utf-8') as f:
            json.dump(claude_data, f)
        
        with patch('src.openrouter_mcp.handlers.mcp_benchmark.get_benchmark_handler') as mock_get_handler:
            mock_handler = Mock()
            mock_handler.results_dir = temp_dir
            mock_get_handler.return_value = mock_handler
            
            # GPT 모델만 필터링
            result = await get_benchmark_history(model_filter="gpt")
            
            assert result["filter_applied"] is True
            assert len(result["history"]) == 1
            assert "gpt-4" in result["history"][0]["models_tested"]
            
            # 모든 모델 (필터 없음)
            result_all = await get_benchmark_history()
            
            assert result_all["filter_applied"] is False
            assert len(result_all["history"]) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])