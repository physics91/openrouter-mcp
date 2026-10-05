#!/usr/bin/env python3
"""
MCP 벤치마크 도구 테스트
"""

import json
import os
import tempfile
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.openrouter_mcp.handlers import mcp_benchmark
from src.openrouter_mcp.handlers.benchmark import (
    BenchmarkError,
    BenchmarkMetrics,
    BenchmarkResult,
    EnhancedBenchmarkMetrics,
    EnhancedBenchmarkResult,
)
from src.openrouter_mcp.handlers.mcp_benchmark import (
    _build_performance_comparison_data,
    _serialize_category_benchmark_result,
    benchmark_models,
    compare_model_categories,
    compare_model_performance,
    export_benchmark_report,
    get_benchmark_handler,
    get_benchmark_history,
)

pytestmark = pytest.mark.unit


def test_build_performance_comparison_data_preserves_pipeline_order_and_identity():
    events = []
    benchmark_result = Mock()
    successful_results = {"model-a": benchmark_result}
    models = ["model-a"]
    weights = {"speed": 0.6, "quality": 0.4}
    ranking = [(benchmark_result, 0.75)]
    serialized_ranking = [{"rank": 1}]
    detailed_metrics = {"model-a": {"quality": 0.8}}
    cost_analysis = {"most_cost_efficient": "model-a"}
    performance_analysis = {"quality": {"avg": 0.8}}
    recommendations = [{"model": "model-a"}]
    analyzer = Mock()

    def rank(results, received_weights):
        events.append("rank")
        assert results == [benchmark_result]
        assert results[0] is benchmark_result
        assert received_weights is weights
        return ranking

    analyzer.rank_models_with_weights.side_effect = rank

    class FrozenTimestamp:
        def isoformat(self):
            events.append("isoformat")
            return "2026-08-12T12:34:56"

    class FrozenDatetime:
        @classmethod
        def now(cls):
            events.append("now")
            return FrozenTimestamp()

    def create_analyzer():
        events.append("analyzer")
        return analyzer

    def serialize_ranking(received_ranking):
        events.append("serialize-ranking")
        assert received_ranking is ranking
        return serialized_ranking

    def serialize_metrics(results):
        events.append("serialize-metrics")
        assert results is successful_results
        return detailed_metrics

    def analyze_cost(results):
        events.append("cost")
        assert results is successful_results
        return cost_analysis

    def analyze_performance(results):
        events.append("performance")
        assert results is successful_results
        return performance_analysis

    def generate_recommendations(received_ranking, received_weights):
        events.append("recommendations")
        assert received_ranking is ranking
        assert received_weights is weights
        return recommendations

    with patch.object(
        mcp_benchmark,
        "ModelPerformanceAnalyzer",
        side_effect=create_analyzer,
    ), patch.object(
        mcp_benchmark,
        "datetime",
        FrozenDatetime,
    ), patch.object(
        mcp_benchmark,
        "_serialize_weighted_performance_ranking",
        side_effect=serialize_ranking,
    ), patch.object(
        mcp_benchmark,
        "_serialize_detailed_performance_metrics",
        side_effect=serialize_metrics,
    ), patch.object(
        mcp_benchmark,
        "_analyze_cost_efficiency",
        side_effect=analyze_cost,
    ), patch.object(
        mcp_benchmark,
        "_analyze_performance_distribution",
        side_effect=analyze_performance,
    ), patch.object(
        mcp_benchmark,
        "_generate_recommendations",
        side_effect=generate_recommendations,
    ):
        result = _build_performance_comparison_data(
            successful_results,
            models,
            weights,
            include_cost_analysis=True,
        )

    assert list(result) == [
        "timestamp",
        "config",
        "ranking",
        "detailed_metrics",
        "analysis",
        "recommendations",
    ]
    assert result == {
        "timestamp": "2026-08-12T12:34:56",
        "config": {
            "models": models,
            "weights": weights,
            "include_cost_analysis": True,
        },
        "ranking": serialized_ranking,
        "detailed_metrics": detailed_metrics,
        "analysis": {
            "cost_efficiency": cost_analysis,
            "performance_distribution": performance_analysis,
        },
        "recommendations": recommendations,
    }
    assert result["config"]["models"] is models
    assert result["config"]["weights"] is weights
    assert events == [
        "analyzer",
        "rank",
        "now",
        "isoformat",
        "serialize-ranking",
        "serialize-metrics",
        "cost",
        "performance",
        "recommendations",
    ]


def test_build_performance_comparison_data_skips_cost_analysis():
    benchmark_result = Mock()
    successful_results = {"model-a": benchmark_result}
    ranking = [(benchmark_result, 0.75)]
    analyzer = Mock()
    analyzer.rank_models_with_weights.return_value = ranking

    with patch.object(
        mcp_benchmark,
        "ModelPerformanceAnalyzer",
        return_value=analyzer,
    ), patch.object(
        mcp_benchmark,
        "_serialize_weighted_performance_ranking",
        return_value=[],
    ), patch.object(
        mcp_benchmark,
        "_serialize_detailed_performance_metrics",
        return_value={},
    ), patch.object(
        mcp_benchmark,
        "_analyze_cost_efficiency",
    ) as analyze_cost, patch.object(
        mcp_benchmark,
        "_analyze_performance_distribution",
        return_value={"distribution": True},
    ), patch.object(
        mcp_benchmark,
        "_generate_recommendations",
        return_value=[],
    ):
        result = _build_performance_comparison_data(
            successful_results,
            ["model-a"],
            {"quality": 1.0},
            include_cost_analysis=False,
        )

    analyze_cost.assert_not_called()
    assert result["analysis"] == {"performance_distribution": {"distribution": True}}


@pytest.mark.asyncio
async def test_compare_model_performance_delegates_only_successful_results():
    models = ["model-a", "model-b"]
    input_weights = {"speed": 2.0}
    normalized_weights = {"speed": 1.0}
    successful = Mock(success=True)
    failed = Mock(success=False)
    raw_results = {"model-a": successful, "model-b": failed}
    expected = {"comparison": True}
    handler = Mock()
    events = []

    async def benchmark(**kwargs):
        events.append("benchmark")
        return raw_results

    handler.benchmark_models = Mock(side_effect=benchmark)

    def build(results, received_models, received_weights, include_cost_analysis):
        events.append("build")
        assert list(results) == ["model-a"]
        assert results["model-a"] is successful
        assert received_models is models
        assert received_weights is normalized_weights
        assert include_cost_analysis is False
        return expected

    def log(message):
        events.append(f"log:{message}")

    with patch.object(
        mcp_benchmark,
        "get_benchmark_handler",
        new=AsyncMock(return_value=handler),
    ), patch.object(
        mcp_benchmark,
        "_normalize_performance_weights",
        return_value=normalized_weights,
    ), patch.object(
        mcp_benchmark,
        "_build_performance_comparison_data",
        side_effect=build,
    ) as build_comparison, patch.object(
        mcp_benchmark.logger,
        "info",
        side_effect=log,
    ):
        result = await compare_model_performance(
            models,
            input_weights,
            include_cost_analysis=False,
        )

    assert result is expected
    build_comparison.assert_called_once()
    assert events == [
        f"log:고급 성능 비교 시작: {models}",
        f"log:가중치: {normalized_weights}",
        "benchmark",
        "build",
        "log:고급 성능 비교 완료: 1 모델 분석",
    ]


@pytest.mark.asyncio
async def test_compare_model_performance_preserves_all_failed_early_return():
    models = ["model-a"]
    handler = Mock()
    handler.benchmark_models = AsyncMock(
        return_value={"model-a": Mock(success=False, error_message="Provider failed")}
    )

    with patch.object(
        mcp_benchmark,
        "get_benchmark_handler",
        new=AsyncMock(return_value=handler),
    ), patch.object(
        mcp_benchmark,
        "_build_performance_comparison_data",
    ) as build_comparison:
        result = await compare_model_performance(models)

    build_comparison.assert_not_called()
    assert result == {
        "error": "성공한 벤치마크 결과가 없습니다.",
        "models": models,
        "benchmark_status": "failed",
        "failed_models": {"model-a": "Provider failed"},
    }
    assert result["models"] is models


class TestMCPBenchmarkTools:
    """MCP 벤치마크 도구 테스트 클래스"""

    @pytest.fixture
    def mock_env(self):
        """환경변수 모킹"""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-api-key"}):
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
            throughput_score=0.85,
        )

        result = EnhancedBenchmarkResult(
            model_id="test-model",
            success=True,
            response="테스트 응답입니다.",
            error_message=None,
            metrics=metrics,
            timestamp=datetime.now(),
        )

        return result

    def test_serialize_category_benchmark_result_omits_response_content(self):
        response = "sensitive-benchmark-response"
        result = EnhancedBenchmarkResult(
            model_id="test-model",
            success=True,
            response=response,
            error_message=None,
            metrics=EnhancedBenchmarkMetrics(
                avg_response_time=1.25,
                avg_cost=0.002,
                quality_score=0.9,
                throughput=42.0,
            ),
            timestamp=datetime.now(),
        )

        serialized = _serialize_category_benchmark_result("test-model", result)

        assert serialized == {
            "model_id": "test-model",
            "success": True,
            "metrics": {
                "avg_response_time": 1.25,
                "avg_cost": 0.002,
                "quality_score": 0.9,
                "throughput": 42.0,
            },
            "response_length": len(response),
        }
        assert "response" not in serialized
        assert response not in serialized.values()

    def test_serialize_category_benchmark_result_handles_missing_payloads(self):
        result = EnhancedBenchmarkResult(
            model_id="failed-model",
            success=False,
            response=None,
            error_message="failed",
            metrics=None,
            timestamp=datetime.now(),
        )

        assert _serialize_category_benchmark_result("failed-model", result) == {
            "model_id": "failed-model",
            "success": False,
            "metrics": None,
            "response_length": 0,
        }

    def test_serialize_benchmark_result_redacts_response_by_default(self):
        response = "sensitive-benchmark-response"
        metrics = EnhancedBenchmarkMetrics(
            avg_response_time=1.25,
            avg_cost=0.002,
            quality_score=0.9,
            throughput=42.0,
        )
        result = EnhancedBenchmarkResult(
            model_id="test-model",
            success=True,
            response=response,
            error_message=None,
            metrics=metrics,
            timestamp=datetime.now(),
        )

        serialized = mcp_benchmark._serialize_benchmark_result(
            result, include_response_content=False
        )

        assert serialized == {
            "success": True,
            "error_message": None,
            "metrics": metrics.__dict__,
            "response": f"<REDACTED: {len(response)} chars>",
        }
        assert response not in repr(serialized)

    def test_serialize_benchmark_result_preserves_response_boundaries(self):
        def make_result(response):
            return EnhancedBenchmarkResult(
                model_id="test-model",
                success=True,
                response=response,
                error_message=None,
                metrics=None,
                timestamp=datetime.now(),
            )

        short_response = "short response"
        assert (
            mcp_benchmark._serialize_benchmark_result(
                make_result(short_response), include_response_content=True
            )["response"]
            == short_response
        )

        response_at_limit = "x" * 200
        assert (
            mcp_benchmark._serialize_benchmark_result(
                make_result(response_at_limit), include_response_content=True
            )["response"]
            == response_at_limit
        )

        response_over_limit = "x" * 201
        assert (
            mcp_benchmark._serialize_benchmark_result(
                make_result(response_over_limit), include_response_content=True
            )["response"]
            == f"{'x' * 200}..."
        )

        for response, exposed_response in ((None, None), ("", "")):
            result = make_result(response)
            assert (
                mcp_benchmark._serialize_benchmark_result(
                    result, include_response_content=False
                )["response"]
                == "<REDACTED: 0 chars>"
            )
            assert (
                mcp_benchmark._serialize_benchmark_result(
                    result, include_response_content=True
                )["response"]
                == exposed_response
            )

    def test_serialize_benchmark_ranking_preserves_contract(self):
        result_with_metrics = EnhancedBenchmarkResult(
            model_id="ranked-model",
            success=True,
            response="response",
            error_message=None,
            metrics=EnhancedBenchmarkMetrics(
                speed_score=0.81,
                cost_score=0.72,
                quality_score=0.93,
                throughput_score=0.64,
            ),
            timestamp=datetime.now(),
        )
        result_without_metrics = EnhancedBenchmarkResult(
            model_id="no-metrics-model",
            success=True,
            response="response",
            error_message=None,
            metrics=None,
            timestamp=datetime.now(),
        )

        serialized = mcp_benchmark._serialize_benchmark_ranking(
            [(result_with_metrics, 0.87654), (result_without_metrics, 0.12345)]
        )

        assert serialized == [
            {
                "model_id": "ranked-model",
                "overall_score": 0.87654,
                "speed_score": 0.81,
                "cost_score": 0.72,
                "quality_score": 0.93,
                "throughput_score": 0.64,
            },
            {
                "model_id": "no-metrics-model",
                "overall_score": 0.12345,
                "speed_score": 0,
                "cost_score": 0,
                "quality_score": None,
                "throughput_score": 0,
            },
        ]

    def test_serialize_weighted_performance_ranking_preserves_contract(self):
        ranked_result = EnhancedBenchmarkResult(
            model_id="ranked-model",
            success=True,
            response="response",
            error_message=None,
            metrics=EnhancedBenchmarkMetrics(
                avg_response_time=1.25,
                avg_cost=0.002,
                quality_score=0.91,
                throughput=42.0,
                speed_score=0.81,
                cost_score=0.72,
                throughput_score=0.63,
            ),
            timestamp=datetime.now(),
        )
        result_without_metrics = EnhancedBenchmarkResult(
            model_id="no-metrics-model",
            success=True,
            response="response",
            error_message=None,
            metrics=None,
            timestamp=datetime.now(),
        )

        serialized = mcp_benchmark._serialize_weighted_performance_ranking(
            [(ranked_result, 0.87654), (result_without_metrics, 0.12345)]
        )

        assert serialized == [
            {
                "rank": 1,
                "model_id": "ranked-model",
                "weighted_score": 0.877,
                "individual_scores": {
                    "speed": 0.81,
                    "cost": 0.72,
                    "quality": 0.91,
                    "throughput": 0.63,
                },
            },
            {
                "rank": 2,
                "model_id": "no-metrics-model",
                "weighted_score": 0.123,
                "individual_scores": {},
            },
        ]

    def test_serialize_detailed_performance_metrics_preserves_contract(self):
        result_with_metrics = EnhancedBenchmarkResult(
            model_id="payload-model-id",
            success=True,
            response="response",
            error_message=None,
            metrics=EnhancedBenchmarkMetrics(
                avg_response_time=1.1,
                min_response_time=0.9,
                max_response_time=1.3,
                avg_cost=0.004,
                min_cost=0.002,
                max_cost=0.006,
                avg_prompt_tokens=11.0,
                avg_completion_tokens=22.0,
                avg_total_tokens=33.0,
                quality_score=0.88,
                throughput=44.0,
                success_rate=0.75,
            ),
            timestamp=datetime.now(),
        )
        result_without_metrics = EnhancedBenchmarkResult(
            model_id="no-metrics-model",
            success=True,
            response="response",
            error_message=None,
            metrics=None,
            timestamp=datetime.now(),
        )

        serialized = mcp_benchmark._serialize_detailed_performance_metrics(
            {
                "input-model-key": result_with_metrics,
                "omitted-model-key": result_without_metrics,
            }
        )

        assert serialized == {
            "input-model-key": {
                "response_time": {"avg": 1.1, "min": 0.9, "max": 1.3},
                "tokens": {
                    "avg_prompt": 11.0,
                    "avg_completion": 22.0,
                    "avg_total": 33.0,
                },
                "cost": {"avg": 0.004, "min": 0.002, "max": 0.006},
                "quality": 0.88,
                "throughput": 44.0,
                "success_rate": 0.75,
            }
        }

    def test_normalize_performance_weights_preserves_contract(self):
        assert mcp_benchmark._normalize_performance_weights(None) == {
            "speed": 0.3,
            "cost": 0.5,
            "throughput": 0.2,
        }

        positive_weights = {"speed": 1.0, "quality": 3.0}
        normalized = mcp_benchmark._normalize_performance_weights(positive_weights)
        assert normalized == {"speed": 0.25, "quality": 0.75}
        assert normalized is not positive_weights
        assert positive_weights == {"speed": 1.0, "quality": 3.0}

        for weights in (
            {"speed": 1.0, "cost": -1.0},
            {"speed": -2.0},
            {"speed": float("nan")},
        ):
            with pytest.raises(ValueError, match="Weights"):
                mcp_benchmark._normalize_performance_weights(weights)

    @pytest.mark.asyncio
    async def test_get_benchmark_handler(self, mock_env):
        """벤치마크 핸들러 싱글톤 테스트"""
        with patch(
            "src.openrouter_mcp.handlers.mcp_benchmark.EnhancedBenchmarkHandler"
        ) as mock_handler_class:
            with patch(
                "src.openrouter_mcp.handlers.mcp_benchmark.ModelCache"
            ) as mock_cache_class:
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
            "claude-3-haiku": mock_benchmark_result,
        }

        with patch(
            "src.openrouter_mcp.handlers.mcp_benchmark.get_benchmark_handler"
        ) as mock_get_handler:
            mock_handler = AsyncMock()
            mock_handler.benchmark_models.return_value = mock_results
            mock_handler.save_results = AsyncMock()
            mock_get_handler.return_value = mock_handler

            with patch(
                "src.openrouter_mcp.handlers.mcp_benchmark.ModelPerformanceAnalyzer"
            ) as mock_analyzer_class:
                mock_analyzer = Mock()
                mock_analyzer.rank_models.return_value = [(mock_benchmark_result, 0.85)]
                mock_analyzer_class.return_value = mock_analyzer

                result = await benchmark_models(
                    models=models, prompt=prompt, runs=2, delay_seconds=0.5
                )

                # 결과 검증
                assert "timestamp" in result
                assert "config" in result
                assert "results" in result
                assert "ranking" in result
                assert len(result["results"]) == 2
                assert result["config"]["models"] == models
                assert result["config"]["prompt"] == prompt
                assert {
                    model_id: payload["response"]
                    for model_id, payload in result["results"].items()
                } == {
                    "gpt-3.5-turbo": "<REDACTED: 10 chars>",
                    "claude-3-haiku": "<REDACTED: 10 chars>",
                }
                assert result["ranking"] == [
                    {
                        "model_id": "test-model",
                        "overall_score": 0.85,
                        "speed_score": 0.8,
                        "cost_score": 0.9,
                        "quality_score": 8.5,
                        "throughput_score": 0.85,
                    }
                ]

                # 핸들러 호출 검증
                mock_handler.benchmark_models.assert_called_once_with(
                    model_ids=models, prompt=prompt, runs=2, delay_between_requests=0.5
                )

    @pytest.mark.asyncio
    async def test_benchmark_models_no_success(self, mock_env):
        """모델 벤치마킹 실패 테스트"""
        models = ["invalid-model"]

        # 실패한 결과
        failed_result = BenchmarkResult.from_enhanced_result(
            model_id="invalid-model",
            success=False,
            response=None,
            error_message="Model not found",
        )

        mock_results = {"invalid-model": failed_result}

        with patch(
            "src.openrouter_mcp.handlers.mcp_benchmark.get_benchmark_handler"
        ) as mock_get_handler:
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
        with patch(
            "src.openrouter_mcp.handlers.mcp_benchmark.get_benchmark_handler"
        ) as mock_get_handler:
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
            "config": {"models": ["gpt-3.5-turbo"], "prompt": "테스트"},
            "results": {
                "gpt-3.5-turbo": {
                    "success": True,
                    "metrics": {"avg_response_time": 1.5, "quality_score": 8.0},
                }
            },
        }

        test_file = os.path.join(temp_dir, "test_benchmark.json")
        with open(test_file, "w", encoding="utf-8") as f:
            json.dump(test_data, f)

        with patch(
            "src.openrouter_mcp.handlers.mcp_benchmark.get_benchmark_handler"
        ) as mock_get_handler:
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
            {"id": "dall-e", "category": "image", "quality_score": 7.5},
        ]

        with patch(
            "src.openrouter_mcp.handlers.mcp_benchmark.get_benchmark_handler"
        ) as mock_get_handler:
            mock_handler = AsyncMock()
            mock_cache = Mock()
            mock_cache.get_models.return_value = mock_models
            mock_handler.model_cache = mock_cache

            # 벤치마크 결과 모킹
            mock_handler.benchmark_models.return_value = {
                "gpt-4": BenchmarkResult.from_enhanced_result(
                    model_id="gpt-4",
                    success=True,
                    response="Response",
                    error_message=None,
                    metrics=BenchmarkMetrics(
                        avg_response_time_ms=1.0,
                        avg_tokens_used=1.0,
                        avg_cost=1.0,
                        total_cost=100,
                        success_rate=50,
                        sample_count=150,
                        avg_quality_score=0.001,
                        avg_throughput=0.001,
                        avg_prompt_tokens=0.001,
                        avg_completion_tokens=9.0,
                        cost_per_quality_point=150.0,
                        avg_total_tokens=1.0,
                        avg_response_length=0.9,
                        avg_input_cost_per_1k_tokens=0.8,
                        avg_output_cost_per_1k_tokens=0.85,
                    ),
                )
            }

            mock_get_handler.return_value = mock_handler

            with patch(
                "src.openrouter_mcp.handlers.mcp_benchmark.ModelPerformanceAnalyzer"
            ) as mock_analyzer_class:
                mock_analyzer = Mock()
                mock_analyzer.rank_models.return_value = [
                    (
                        BenchmarkResult.from_enhanced_result(
                            model_id="gpt-4",
                            success=True,
                            response="Response",
                            error_message=None,
                            metrics=None,
                        ),
                        0.9,
                    )
                ]
                mock_analyzer_class.return_value = mock_analyzer

                result = await compare_model_categories(categories=["chat"], top_n=2)

                assert "config" in result
                assert "category_info" in result
                assert "results" in result
                assert result["config"]["categories"] == ["chat"]
                assert "chat" in result["category_info"]
                assert result["overall_ranking"] == [
                    {
                        "model_id": "gpt-4",
                        "category": "chat",
                        "overall_score": 0.9,
                        "speed_score": 0,
                        "cost_score": 0,
                        "quality_score": None,
                    }
                ]

    @pytest.mark.asyncio
    async def test_compare_model_categories_speed_prefers_lower_latency(self, mock_env):
        """speed 메트릭은 더 낮은 지연 시간을 우선 선택해야 함"""
        mock_models = [
            {
                "id": "quality-high-but-slow",
                "category": "chat",
                "quality_score": 9.8,
                "avg_response_time": 3.0,
            },
            {
                "id": "quality-lower-but-fast",
                "category": "chat",
                "quality_score": 7.0,
                "avg_response_time": 0.4,
            },
        ]

        def _make_result(model_id: str) -> BenchmarkResult:
            return BenchmarkResult.from_enhanced_result(
                model_id=model_id,
                success=True,
                response="ok",
                error_message=None,
                metrics=BenchmarkMetrics(
                    avg_response_time_ms=500.0,
                    avg_tokens_used=100.0,
                    avg_cost=0.001,
                    total_cost=0.001,
                    success_rate=1.0,
                    sample_count=1,
                    avg_quality_score=0.8,
                    avg_throughput=100.0,
                ),
            )

        with patch(
            "src.openrouter_mcp.handlers.mcp_benchmark.get_benchmark_handler"
        ) as mock_get_handler:
            mock_handler = AsyncMock()
            mock_cache = Mock()
            mock_cache.get_models.return_value = mock_models
            mock_handler.model_cache = mock_cache

            async def _benchmark_models_side_effect(
                model_ids, prompt, runs, delay_between_requests
            ):
                return {model_id: _make_result(model_id) for model_id in model_ids}

            mock_handler.benchmark_models.side_effect = _benchmark_models_side_effect
            mock_get_handler.return_value = mock_handler

            with patch(
                "src.openrouter_mcp.handlers.mcp_benchmark.ModelPerformanceAnalyzer"
            ) as mock_analyzer_class:
                mock_analyzer = Mock()
                mock_analyzer.rank_models.return_value = []
                mock_analyzer_class.return_value = mock_analyzer

                result = await compare_model_categories(
                    categories=["chat"],
                    top_n=1,
                    metric="speed",
                )

                assert result["category_info"]["chat"]["selected_models"] == [
                    "quality-lower-but-fast"
                ]

    @pytest.mark.asyncio
    async def test_compare_model_categories_rejects_invalid_metric(self, mock_env):
        """지원하지 않는 metric 값은 명시적으로 오류를 반환해야 함"""
        with pytest.raises(BenchmarkError) as exc_info:
            await compare_model_categories(metric="not-a-metric")

        assert "지원하지 않는 metric" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_export_benchmark_report_not_found(self, mock_env, temp_dir):
        """존재하지 않는 벤치마크 파일 내보내기 테스트"""
        with patch(
            "src.openrouter_mcp.handlers.mcp_benchmark.get_benchmark_handler"
        ) as mock_get_handler:
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
                        "throughput": 100.0,
                    },
                    "response": "테스트 응답",
                }
            }
        }

        input_file = "test_benchmark.json"
        input_path = os.path.join(temp_dir, input_file)
        with open(input_path, "w", encoding="utf-8") as f:
            json.dump(benchmark_data, f)

        with patch(
            "src.openrouter_mcp.handlers.mcp_benchmark.get_benchmark_handler"
        ) as mock_get_handler:
            mock_handler = Mock()
            mock_handler.results_dir = temp_dir
            mock_get_handler.return_value = mock_handler

            with patch(
                "src.openrouter_mcp.handlers.mcp_benchmark.BenchmarkReportExporter"
            ) as mock_exporter_class:
                mock_exporter = AsyncMock()
                mock_exporter_class.return_value = mock_exporter

                result = await export_benchmark_report(
                    benchmark_file=input_file, format="markdown"
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
        weights = {"speed": 0.3, "cost": 0.3, "throughput": 0.4}

        mock_results = {
            "gpt-4": mock_benchmark_result,
            "claude-3": mock_benchmark_result,
        }

        with patch(
            "src.openrouter_mcp.handlers.mcp_benchmark.get_benchmark_handler"
        ) as mock_get_handler:
            mock_handler = AsyncMock()
            mock_handler.benchmark_models.return_value = mock_results
            mock_get_handler.return_value = mock_handler

            with patch(
                "src.openrouter_mcp.handlers.mcp_benchmark.ModelPerformanceAnalyzer"
            ) as mock_analyzer_class:
                mock_analyzer = Mock()
                mock_analyzer.rank_models_with_weights.return_value = [
                    (mock_benchmark_result, 0.85)
                ]
                mock_analyzer_class.return_value = mock_analyzer

                result = await compare_model_performance(
                    models=models, weights=weights, include_cost_analysis=True
                )

                assert "config" in result
                assert "ranking" in result
                assert "detailed_metrics" in result
                assert "analysis" in result
                assert "recommendations" in result
                assert result["ranking"] == [
                    {
                        "rank": 1,
                        "model_id": "test-model",
                        "weighted_score": 0.85,
                        "individual_scores": {
                            "speed": 0.8,
                            "cost": 0.9,
                            "quality": 8.5,
                            "throughput": 0.85,
                        },
                    }
                ]
                assert result["detailed_metrics"] == {
                    model_id: {
                        "response_time": {"avg": 1.5, "min": 0.0, "max": 0.0},
                        "tokens": {
                            "avg_prompt": 100.0,
                            "avg_completion": 50.0,
                            "avg_total": 150.0,
                        },
                        "cost": {"avg": 0.001, "min": 0.0, "max": 0.0},
                        "quality": 8.5,
                        "throughput": 100.0,
                        "success_rate": 1.0,
                    }
                    for model_id in models
                }

                # 가중치 정규화 검증
                total_weight = sum(result["config"]["weights"].values())
                assert abs(total_weight - 1.0) < 0.001  # 부동소수점 오차 고려

    @pytest.mark.asyncio
    async def test_compare_model_performance_no_weights(
        self, mock_env, mock_benchmark_result
    ):
        """가중치 없는 모델 성능 비교 테스트"""
        models = ["gpt-4"]

        mock_results = {"gpt-4": mock_benchmark_result}

        with patch(
            "src.openrouter_mcp.handlers.mcp_benchmark.get_benchmark_handler"
        ) as mock_get_handler:
            mock_handler = AsyncMock()
            mock_handler.benchmark_models.return_value = mock_results
            mock_get_handler.return_value = mock_handler

            with patch(
                "src.openrouter_mcp.handlers.mcp_benchmark.ModelPerformanceAnalyzer"
            ) as mock_analyzer_class:
                mock_analyzer = Mock()
                mock_analyzer.rank_models_with_weights.return_value = [
                    (mock_benchmark_result, 0.85)
                ]
                mock_analyzer_class.return_value = mock_analyzer

                result = await compare_model_performance(models=models)

                # 기본 가중치가 사용되었는지 확인
                expected_weights = {
                    "speed": 0.3,
                    "cost": 0.5,
                    "throughput": 0.2,
                }
                assert result["config"]["weights"] == expected_weights

    def test_utility_functions(self):
        """유틸리티 함수들 테스트"""
        from src.openrouter_mcp.handlers.mcp_benchmark import (
            _calculate_avg_response_time,
            _calculate_std,
            _get_best_model,
            _get_category_prompt,
        )

        # _calculate_avg_response_time 테스트
        results = {
            "model1": {"success": True, "metrics": {"avg_response_time": 1.5}},
            "model2": {"success": True, "metrics": {"avg_response_time": 2.0}},
            "model3": {"success": False, "metrics": {"avg_response_time": 3.0}},
        }

        avg_time = _calculate_avg_response_time(results)
        assert avg_time == 1.75  # (1.5 + 2.0) / 2

        # _get_best_model 테스트
        results_with_quality = {
            "model1": {"success": True, "metrics": {"quality_score": 8.0}},
            "model2": {"success": True, "metrics": {"quality_score": 9.5}},
        }

        best_model = _get_best_model(results_with_quality)
        assert best_model is None  # Unmarked legacy quality scores are not evaluations

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

    def test_build_benchmark_history_entry_preserves_summary_contract(self):
        file_time = datetime(2025, 1, 2, 3, 4, 5)
        config = {"runs": 3}
        data = {
            "config": config,
            "results": {
                "model-b": {
                    "success": True,
                    "metrics": {"avg_response_time": 2.0, "quality_score": 0.7},
                },
                "model-a": {
                    "success": False,
                    "metrics": {"avg_response_time": 0.5, "quality_score": 0.9},
                },
                "model-c": {
                    "success": True,
                    "metrics": {"avg_response_time": 4.0, "quality_score": 0.8},
                },
            },
        }
        original = json.loads(json.dumps(data))

        entry = mcp_benchmark._build_benchmark_history_entry(
            "benchmark.json", file_time, data
        )

        assert entry == {
            "filename": "benchmark.json",
            "timestamp": "2025-01-02T03:04:05",
            "models_tested": ["model-b", "model-a", "model-c"],
            "success_rate": "2/3",
            "config": {"runs": 3},
            "summary": {
                "total_models": 3,
                "successful_models": 2,
                "avg_response_time": 3.0,
                "best_model": None,
            },
        }
        assert entry["config"] is config
        assert data == original

    def test_build_benchmark_history_entry_handles_missing_results(self):
        assert mcp_benchmark._build_benchmark_history_entry(
            "empty.json", datetime(2025, 1, 1), {}
        ) == {
            "filename": "empty.json",
            "timestamp": "2025-01-01T00:00:00",
            "models_tested": [],
            "success_rate": "0/0",
            "config": {},
            "summary": {
                "total_models": 0,
                "successful_models": 0,
                "avg_response_time": None,
                "best_model": None,
            },
        }

    def test_build_benchmark_history_entry_preserves_malformed_result_error(self):
        with pytest.raises(AttributeError):
            mcp_benchmark._build_benchmark_history_entry(
                "invalid.json",
                datetime(2025, 1, 1),
                {"results": {"model": None}},
            )

    @pytest.mark.asyncio
    async def test_error_handling(self, mock_env):
        """에러 핸들링 테스트"""
        # API 키가 없을 때
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(Exception) as exc_info:
                await get_benchmark_handler()
            assert "OPENROUTER_API_KEY" in str(exc_info.value)

        # 벤치마크 실행 중 예외 발생
        with patch(
            "src.openrouter_mcp.handlers.mcp_benchmark.get_benchmark_handler"
        ) as mock_get_handler:
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
            "results": {"gpt-4": {"success": True}, "gpt-3.5-turbo": {"success": True}},
            "config": {},
        }

        # Claude 모델이 포함된 파일
        claude_data = {
            "results": {
                "claude-3-opus": {"success": True},
                "claude-3-sonnet": {"success": True},
            },
            "config": {},
        }

        gpt_file = os.path.join(temp_dir, "gpt_benchmark.json")
        claude_file = os.path.join(temp_dir, "claude_benchmark.json")

        with open(gpt_file, "w", encoding="utf-8") as f:
            json.dump(gpt_data, f)
        with open(claude_file, "w", encoding="utf-8") as f:
            json.dump(claude_data, f)

        with patch(
            "src.openrouter_mcp.handlers.mcp_benchmark.get_benchmark_handler"
        ) as mock_get_handler:
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
