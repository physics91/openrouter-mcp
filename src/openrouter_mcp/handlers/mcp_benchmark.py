#!/usr/bin/env python3
"""
MCP Benchmark Tools for OpenRouter

FastMCP 도구들을 제공하여 Claude Desktop과 다른 MCP 클라이언트에서
벤치마킹 기능을 사용할 수 있게 합니다.
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Annotated, Any, Dict, List, Literal, Optional, Tuple

from pydantic import Field

from ..config.constants import BenchmarkDefaults, CacheConfig, EnvVars, ModelDefaults

# Import shared MCP instance from registry to prevent duplicate registration
from ..mcp_registry import mcp
from ..models.cache import ModelCache
from ..utils.async_utils import maybe_await
from ..utils.env import get_required_env
from .benchmark import (
    BenchmarkError,
    BenchmarkReportExporter,
    EnhancedBenchmarkHandler,
    ModelPerformanceAnalyzer,
)

logger = logging.getLogger(__name__)

# 지원 메트릭 정의
SUPPORTED_CATEGORY_METRICS = {"overall", "speed", "cost", "quality"}


@dataclass
class ReportMetrics:
    """BenchmarkReportExporter와 호환되는 최소 메트릭 뷰."""

    avg_response_time: float = 0.0
    avg_cost: float = 0.0
    quality_score: float = 0.0
    throughput: float = 0.0


@dataclass
class ReportResult:
    """BenchmarkReportExporter와 호환되는 결과 뷰."""

    model_id: str
    success: bool
    response: str
    metrics: Optional[ReportMetrics] = None


def _to_float(value: Any, default: float) -> float:
    """안전한 float 변환 헬퍼."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _extract_response_time_seconds(model: Dict[str, Any]) -> Optional[float]:
    """모델 메타데이터에서 응답시간(초)을 추출."""
    seconds_keys = ("avg_response_time", "response_time", "latency")
    millis_keys = ("avg_response_time_ms", "response_time_ms", "latency_ms")

    for key in seconds_keys:
        if key in model:
            return _to_float(model.get(key), 0.0)

    for key in millis_keys:
        if key in model:
            return _to_float(model.get(key), 0.0) / 1000.0

    benchmark_meta = model.get("benchmark", {})
    if isinstance(benchmark_meta, dict):
        if "avg_response_time" in benchmark_meta:
            return _to_float(benchmark_meta.get("avg_response_time"), 0.0)
        if "avg_response_time_ms" in benchmark_meta:
            return _to_float(benchmark_meta.get("avg_response_time_ms"), 0.0) / 1000.0

    return None


def _extract_prompt_price(model: Dict[str, Any]) -> Optional[float]:
    """모델 메타데이터에서 프롬프트 단가를 추출."""
    pricing = model.get("pricing", {})
    if not isinstance(pricing, dict):
        return None
    if "prompt" not in pricing:
        return None
    return _to_float(pricing.get("prompt"), 0.0)


def _selection_score(model: Dict[str, Any], metric: str) -> float:
    """카테고리별 사전 모델 선택 점수 계산."""
    quality_score = _to_float(model.get("quality_score"), 0.0)
    response_time = _extract_response_time_seconds(model)
    prompt_price = _extract_prompt_price(model)

    if metric == "quality":
        return quality_score

    if metric == "speed":
        if response_time is None:
            return quality_score
        return -response_time

    if metric == "cost":
        if prompt_price is None:
            return quality_score
        return quality_score / max(prompt_price, 0.0001)

    # overall
    speed_component = 0.0
    if response_time is not None:
        speed_component = 1.0 / (1.0 + response_time)
    cost_component = 0.0
    if prompt_price is not None:
        cost_component = 1.0 / (1.0 + (prompt_price * 1000))
    return (quality_score * 0.5) + (speed_component * 0.3) + (cost_component * 0.2)


# 글로벌 벤치마크 핸들러
_benchmark_handler: Optional[EnhancedBenchmarkHandler] = None
_model_cache: Optional[ModelCache] = None
_benchmark_handler_factory: Optional[object] = None


async def get_benchmark_handler() -> EnhancedBenchmarkHandler:
    """벤치마크 핸들러 싱글톤 인스턴스 반환"""
    global _benchmark_handler, _model_cache, _benchmark_handler_factory

    try:
        api_key = get_required_env(
            EnvVars.API_KEY,
            error_message=f"{EnvVars.API_KEY} 환경변수가 설정되지 않았습니다",
        )
    except ValueError:
        _benchmark_handler = None
        _model_cache = None
        _benchmark_handler_factory = None
        raise

    handler_factory = EnhancedBenchmarkHandler
    if _benchmark_handler is not None:
        if _benchmark_handler_factory is handler_factory:
            return _benchmark_handler
        _benchmark_handler = None
        _model_cache = None
        _benchmark_handler_factory = None

    if _benchmark_handler is None:
        # 모델 캐시 초기화
        if _model_cache is None:
            _model_cache = ModelCache(ttl_hours=CacheConfig.BENCHMARK_CACHE_TTL_HOURS)

        _benchmark_handler = handler_factory(
            api_key=api_key,
            model_cache=_model_cache,
            results_dir=BenchmarkDefaults.DEFAULT_RESULTS_DIR,
        )
        _benchmark_handler_factory = handler_factory

    return _benchmark_handler


async def benchmark_models(
    models: Annotated[
        List[str],
        Field(
            description="List of model IDs to benchmark (e.g. ['openai/gpt-4', 'anthropic/claude-3-opus'])"
        ),
    ],
    prompt: Annotated[
        str, Field(description="Test prompt for benchmarking")
    ] = BenchmarkDefaults.DEFAULT_PROMPT,
    runs: Annotated[
        int, Field(description="Number of runs per model for statistical accuracy")
    ] = BenchmarkDefaults.DEFAULT_MCP_RUNS,
    delay_seconds: Annotated[
        float, Field(description="Delay between API calls in seconds")
    ] = BenchmarkDefaults.DEFAULT_DELAY_SECONDS,
    save_results: Annotated[bool, Field(description="Whether to save results to a file")] = True,
    include_prompts_in_logs: Annotated[
        bool, Field(description="PRIVACY WARNING: enables logging of prompt content")
    ] = False,
) -> Dict[str, Any]:
    """Run performance benchmarks across multiple models.

    Executes the same prompt against each model multiple times, collecting
    response time, cost, quality, and throughput metrics with statistical ranking.
    """
    try:
        handler = await get_benchmark_handler()

        logger.info(f"{len(models)}개 모델 벤치마킹 시작: {models}")

        # SECURITY: Only log prompt content if explicitly consented
        if include_prompts_in_logs:
            logger.warning(
                "PRIVACY WARNING: Logging prompt content is enabled. "
                "Prompts may contain sensitive or personal information."
            )
            logger.info(f"프롬프트: {prompt[:50]}...")
        else:
            logger.info(f"프롬프트 길이: {len(prompt)} 문자 (내용은 로깅하지 않음)")

        logger.info(f"실행 횟수: {runs}회, 지연: {delay_seconds}초")

        # 벤치마크 실행
        results = await maybe_await(
            handler.benchmark_models(
                model_ids=models,
                prompt=prompt,
                runs=runs,
                delay_between_requests=delay_seconds,
            )
        )

        # 결과를 딕셔너리로 변환
        benchmark_data: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "config": {
                "models": models,
                "prompt": prompt,
                "runs": runs,
                "delay_seconds": delay_seconds,
                "privacy_mode": not include_prompts_in_logs,
            },
            "results": {},
        }

        for model_id, result in results.items():
            benchmark_data["results"][model_id] = {
                "success": result.success,
                "error_message": result.error_message,
                "metrics": result.metrics.__dict__ if result.metrics else None,
                # SECURITY: Only include response content if explicitly allowed
                "response": (
                    (
                        result.response[:200] + "..."
                        if result.response and len(result.response) > 200
                        else result.response
                    )
                    if include_prompts_in_logs
                    else f"<REDACTED: {len(result.response) if result.response else 0} chars>"
                ),
            }

        # 성능 랭킹 계산
        successful_results = {k: v for k, v in results.items() if v.success}
        if successful_results:
            analyzer = ModelPerformanceAnalyzer()
            ranking = analyzer.rank_models(list(successful_results.values()))

            benchmark_data["ranking"] = [
                {
                    "model_id": result.model_id,
                    "overall_score": score,
                    "speed_score": result.metrics.speed_score if result.metrics else 0,
                    "cost_score": result.metrics.cost_score if result.metrics else 0,
                    "quality_score": (result.metrics.quality_score if result.metrics else 0),
                    "throughput_score": (result.metrics.throughput_score if result.metrics else 0),
                }
                for result, score in ranking
            ]

        # 결과 저장
        if save_results:
            filename = f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            await handler.save_results(results, filename)
            benchmark_data["saved_file"] = filename

        logger.info(f"벤치마킹 완료: {len(successful_results)}/{len(models)} 성공")
        return benchmark_data

    except Exception as e:
        logger.error(f"벤치마킹 중 오류 발생: {e}")
        raise BenchmarkError(f"벤치마킹 실패: {str(e)}") from e


async def get_benchmark_history(
    limit: Annotated[int, Field(description="Maximum number of results to return")] = 10,
    days_back: Annotated[int, Field(description="Number of days to look back")] = 30,
    model_filter: Annotated[
        Optional[str], Field(description="Filter results by model ID substring match")
    ] = None,
) -> Dict[str, Any]:
    """Retrieve past benchmark results from the results directory.

    Returns a chronologically sorted list of benchmark runs with summary
    statistics including models tested, success rates, and best performers.
    """
    try:
        handler = await get_benchmark_handler()

        # 결과 디렉토리에서 파일 목록 가져오기
        results_dir = handler.results_dir
        if not os.path.exists(results_dir):
            return {
                "history": [],
                "total_files": 0,
                "message": "벤치마크 기록이 없습니다.",
            }

        # 최근 파일들 찾기
        cutoff_date = datetime.now() - timedelta(days=days_back)

        # 블로킹 I/O를 executor에서 실행
        loop = asyncio.get_running_loop()
        history = await loop.run_in_executor(
            None,
            _read_benchmark_files,
            results_dir,
            cutoff_date,
            limit,
            model_filter,
        )

        return {
            "history": history,
            "total_files": len(history),
            "filter_applied": model_filter is not None,
            "period_days": days_back,
            "message": "벤치마크 기록이 없습니다." if not history else None,
        }

    except Exception as e:
        logger.error(f"벤치마크 기록 조회 중 오류: {e}")
        raise BenchmarkError(f"기록 조회 실패: {str(e)}") from e


async def compare_model_categories(
    categories: Annotated[
        Optional[List[str]], Field(description="Categories to compare (None for all categories)")
    ] = None,
    top_n: Annotated[int, Field(description="Number of top models to select per category")] = 3,
    metric: Annotated[
        Literal["overall", "speed", "cost", "quality"], Field(description="Comparison metric")
    ] = "overall",
) -> Dict[str, Any]:
    """Compare top-performing models across categories.

    Selects the best models from each category based on the chosen metric,
    runs benchmarks on all of them, and returns a cross-category ranking.
    """
    # Defensive: also validates when called directly outside MCP schema validation
    normalized_metric = metric.lower().strip()
    if normalized_metric not in SUPPORTED_CATEGORY_METRICS:
        supported = ", ".join(sorted(SUPPORTED_CATEGORY_METRICS))
        raise BenchmarkError(f"지원하지 않는 metric: {metric}. 지원 값: {supported}")

    try:
        handler = await get_benchmark_handler()
        cache = handler.model_cache

        # 모든 모델 가져오기
        models = await maybe_await(cache.get_models())

        # 카테고리별로 모델 그룹화
        category_models: Dict[str, List[Dict[str, Any]]] = {}
        for model in models:
            category = model.get("category", "unknown")
            if category not in category_models:
                category_models[category] = []
            category_models[category].append(model)

        # 카테고리 필터링
        if categories:
            category_models = {
                cat: models for cat, models in category_models.items() if cat in categories
            }

        # 각 카테고리에서 상위 모델 선택
        selected_models: List[Dict[str, Any]] = []
        category_info: Dict[str, Dict[str, Any]] = {}

        for category, cat_models in category_models.items():
            if not cat_models:
                continue

            # 메트릭에 따라 정렬
            sorted_models = sorted(
                cat_models,
                key=lambda x: _selection_score(x, normalized_metric),
                reverse=True,
            )[:top_n]

            selected_models.extend(sorted_models)
            category_info[category] = {
                "total_models": len(cat_models),
                "selected_models": [m["id"] for m in sorted_models],
            }

        if not selected_models:
            return {
                "message": "비교할 모델이 없습니다.",
                "categories": categories or [],
                "available_categories": list(category_models.keys()),
            }

        # 선택된 모델들로 벤치마크 실행
        model_ids = [model["id"] for model in selected_models]

        # 카테고리별 대표 프롬프트 사용
        prompt = _get_category_prompt(
            categories[0] if categories and len(categories) == 1 else "chat"
        )

        logger.info(f"카테고리별 비교 시작: {len(model_ids)}개 모델")

        results = await maybe_await(
            handler.benchmark_models(
                model_ids=model_ids,
                prompt=prompt,
                runs=BenchmarkDefaults.CATEGORY_COMPARE_RUNS,
                delay_between_requests=BenchmarkDefaults.CATEGORY_COMPARE_DELAY,
            )
        )

        # 결과 분석
        successful_results = {k: v for k, v in results.items() if v.success}

        comparison_data: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "config": {
                "categories": categories or list(category_models.keys()),
                "top_n": top_n,
                "metric": normalized_metric,
                "prompt": prompt,
            },
            "category_info": category_info,
            "results": {},
        }

        # 카테고리별로 결과 그룹화
        for model_id, result in successful_results.items():
            # 해당 모델의 카테고리 찾기
            model_category = "unknown"
            for model in selected_models:
                if model["id"] == model_id:
                    model_category = model.get("category", "unknown")
                    break

            if model_category not in comparison_data["results"]:
                comparison_data["results"][model_category] = []

            comparison_data["results"][model_category].append(
                {
                    "model_id": model_id,
                    "success": result.success,
                    "metrics": (
                        {
                            "avg_response_time": result.metrics.avg_response_time,
                            "avg_cost": result.metrics.avg_cost,
                            "quality_score": result.metrics.quality_score,
                            "throughput": result.metrics.throughput,
                        }
                        if result.metrics
                        else None
                    ),
                    # SECURITY: Don't include response content by default - privacy risk
                    "response_length": len(result.response) if result.response else 0,
                }
            )

        # 전체 랭킹 계산
        if successful_results:
            analyzer = ModelPerformanceAnalyzer()
            ranking = analyzer.rank_models(list(successful_results.values()))

            comparison_data["overall_ranking"] = [
                {
                    "model_id": result.model_id,
                    "category": next(
                        (
                            m.get("category", "unknown")
                            for m in selected_models
                            if m["id"] == result.model_id
                        ),
                        "unknown",
                    ),
                    "overall_score": score,
                    "speed_score": result.metrics.speed_score if result.metrics else 0,
                    "cost_score": result.metrics.cost_score if result.metrics else 0,
                    "quality_score": (result.metrics.quality_score if result.metrics else 0),
                }
                for result, score in ranking[:10]  # 상위 10개만
            ]

        logger.info(f"카테고리별 비교 완료: {len(successful_results)} 모델 성공")
        return comparison_data

    except Exception as e:
        logger.error(f"카테고리별 모델 비교 중 오류: {e}")
        raise BenchmarkError(f"카테고리 비교 실패: {str(e)}") from e


async def export_benchmark_report(
    benchmark_file: Annotated[str, Field(description="Benchmark result filename to export")],
    format: Annotated[
        Literal["markdown", "csv", "json"], Field(description="Export format")
    ] = "markdown",
    output_file: Annotated[
        Optional[str], Field(description="Output filename (auto-generated if omitted)")
    ] = None,
) -> Dict[str, Any]:
    """Export benchmark results to markdown, CSV, or JSON format.

    Reads a previously saved benchmark result file and converts it into
    a human-readable report in the specified format.
    """
    try:
        handler = await get_benchmark_handler()

        # 결과 파일 경로
        results_path = os.path.join(handler.results_dir, benchmark_file)

        if not os.path.exists(results_path):
            raise BenchmarkError(f"벤치마크 파일을 찾을 수 없습니다: {benchmark_file}")

        # 결과 로드
        with open(results_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # BenchmarkResult 객체들로 변환
        results = {}
        for model_id, result_data in data.get("results", {}).items():
            if result_data.get("success") and result_data.get("metrics"):
                metrics_data = result_data.get("metrics", {})
                report_metrics = ReportMetrics(
                    avg_response_time=_to_float(metrics_data.get("avg_response_time"), 0.0),
                    avg_cost=_to_float(metrics_data.get("avg_cost"), 0.0),
                    quality_score=_to_float(metrics_data.get("quality_score"), 0.0),
                    throughput=_to_float(metrics_data.get("throughput"), 0.0),
                )
                results[model_id] = ReportResult(
                    model_id=model_id,
                    success=True,
                    response=result_data.get("response", ""),
                    metrics=report_metrics,
                )

        if not results:
            return {
                "error": "내보낼 성공한 벤치마크 결과가 없습니다.",
                "file": benchmark_file,
            }

        # 출력 파일명 생성
        if output_file is None:
            base_name = benchmark_file.replace(".json", "")
            output_file = f"{base_name}_report.{format}"

        # 리포트 내보내기
        exporter = BenchmarkReportExporter()
        output_path = os.path.join(handler.results_dir, output_file)

        if format == "markdown":
            await exporter.export_markdown(results, output_path)
        elif format == "csv":
            await exporter.export_csv(results, output_path)
        elif format == "json":
            await exporter.export_json(results, output_path)
        else:
            # Defensive: also validates when called directly outside MCP schema validation
            raise BenchmarkError(f"Unsupported format: {format}. Use markdown, csv, or json.")

        return {
            "message": f"{format.upper()} 보고서가 성공적으로 생성되었습니다.",
            "input_file": benchmark_file,
            "output_file": output_file,
            "output_path": output_path,
            "format": format,
            "models_included": list(results.keys()),
        }

    except Exception as e:
        logger.error(f"벤치마크 보고서 내보내기 중 오류: {e}")
        raise BenchmarkError(f"보고서 내보내기 실패: {str(e)}") from e


async def export_benchmark_batch(
    models: Annotated[
        List[str],
        Field(description="List of model IDs to export for deferred benchmark execution"),
    ],
    prompt: Annotated[
        str, Field(description="Benchmark prompt to queue for offline execution")
    ] = BenchmarkDefaults.DEFAULT_PROMPT,
    runs: Annotated[
        int, Field(description="Number of deferred runs to enqueue per model")
    ] = BenchmarkDefaults.DEFAULT_MCP_RUNS,
    delay_seconds: Annotated[
        float, Field(description="Advisory delay metadata between requests")
    ] = BenchmarkDefaults.DEFAULT_DELAY_SECONDS,
    temperature: Annotated[
        float, Field(description="Sampling temperature for queued requests")
    ] = ModelDefaults.TEMPERATURE,
    max_tokens: Annotated[
        int, Field(description="Maximum completion tokens for queued requests")
    ] = BenchmarkDefaults.DEFAULT_MAX_TOKENS,
    sla_window_hours: Annotated[
        int, Field(description="Desired completion window for the deferred batch")
    ] = 24,
    target_spend_usd: Annotated[
        Optional[float], Field(description="Optional target spend cap for the batch")
    ] = None,
) -> Dict[str, Any]:
    """Export benchmark requests into grouped JSONL files for deferred execution."""
    try:
        handler = await get_benchmark_handler()
        export = await handler.export_benchmark_batch(
            model_ids=models,
            prompt=prompt,
            runs=runs,
            temperature=temperature,
            max_tokens=max_tokens,
            delay_between_requests=delay_seconds,
            sla_window_hours=sla_window_hours,
            target_spend_usd=target_spend_usd,
        )
        return {
            "message": "Deferred benchmark batch exported successfully.",
            **export,
        }
    except Exception as e:
        logger.error(f"벤치마크 배치 내보내기 중 오류: {e}")
        raise BenchmarkError(f"배치 내보내기 실패: {str(e)}") from e


async def compare_model_performance(
    models: Annotated[List[str], Field(description="List of model IDs to compare")],
    weights: Annotated[
        Optional[Dict[str, float]],
        Field(
            description="Metric weights, e.g. {'speed': 0.2, 'cost': 0.3, 'quality': 0.4, 'throughput': 0.1}"
        ),
    ] = None,
    include_cost_analysis: Annotated[
        bool, Field(description="Whether to include detailed cost efficiency analysis")
    ] = True,
) -> Dict[str, Any]:
    """Run weighted performance comparison across models.

    Benchmarks the given models and ranks them using custom metric weights,
    providing detailed per-model metrics, cost efficiency analysis, and
    actionable recommendations.
    """
    try:
        handler = await get_benchmark_handler()

        # 기본 가중치 설정
        if weights is None:
            weights = {"speed": 0.2, "cost": 0.3, "quality": 0.4, "throughput": 0.1}

        # 가중치 정규화
        total_weight = sum(weights.values())
        if total_weight > 0:
            weights = {k: v / total_weight for k, v in weights.items()}

        logger.info(f"고급 성능 비교 시작: {models}")
        logger.info(f"가중치: {weights}")

        # 벤치마크 실행
        results = await maybe_await(
            handler.benchmark_models(
                model_ids=models,
                prompt=BenchmarkDefaults.PERFORMANCE_COMPARE_PROMPT,
                runs=BenchmarkDefaults.PERFORMANCE_COMPARE_RUNS,
                delay_between_requests=BenchmarkDefaults.PERFORMANCE_COMPARE_DELAY,
            )
        )

        successful_results = {k: v for k, v in results.items() if v.success}

        if not successful_results:
            return {"error": "성공한 벤치마크 결과가 없습니다.", "models": models}

        # 성능 분석기로 상세 분석
        analyzer = ModelPerformanceAnalyzer()

        # 가중치 적용한 랭킹
        ranking = analyzer.rank_models_with_weights(list(successful_results.values()), weights)

        # 결과 구성
        comparison_data: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "config": {
                "models": models,
                "weights": weights,
                "include_cost_analysis": include_cost_analysis,
            },
            "ranking": [],
            "detailed_metrics": {},
            "analysis": {},
        }

        # 랭킹 결과 추가
        for i, (result, weighted_score) in enumerate(ranking):
            comparison_data["ranking"].append(
                {
                    "rank": i + 1,
                    "model_id": result.model_id,
                    "weighted_score": round(weighted_score, 3),
                    "individual_scores": (
                        {
                            "speed": result.metrics.speed_score,
                            "cost": result.metrics.cost_score,
                            "quality": result.metrics.quality_score,
                            "throughput": result.metrics.throughput_score,
                        }
                        if result.metrics
                        else {}
                    ),
                }
            )

        # 상세 메트릭 추가
        for model_id, result in successful_results.items():
            if result.metrics:
                metrics_data = {
                    "response_time": {
                        "avg": result.metrics.avg_response_time,
                        "min": result.metrics.min_response_time,
                        "max": result.metrics.max_response_time,
                    },
                    "tokens": {
                        "avg_prompt": result.metrics.avg_prompt_tokens,
                        "avg_completion": result.metrics.avg_completion_tokens,
                        "avg_total": result.metrics.avg_total_tokens,
                    },
                    "cost": {
                        "avg": result.metrics.avg_cost,
                        "min": result.metrics.min_cost,
                        "max": result.metrics.max_cost,
                    },
                    "quality": result.metrics.quality_score,
                    "throughput": result.metrics.throughput,
                    "success_rate": result.metrics.success_rate,
                }

                comparison_data["detailed_metrics"][model_id] = metrics_data

        # 비용 분석 추가
        if include_cost_analysis:
            cost_analysis = _analyze_cost_efficiency(successful_results)
            comparison_data["analysis"]["cost_efficiency"] = cost_analysis

        # 성능 분포 분석
        performance_analysis = _analyze_performance_distribution(successful_results)
        comparison_data["analysis"]["performance_distribution"] = performance_analysis

        # 추천 사항
        recommendations = _generate_recommendations(ranking, weights)
        comparison_data["recommendations"] = recommendations

        logger.info(f"고급 성능 비교 완료: {len(successful_results)} 모델 분석")
        return comparison_data

    except Exception as e:
        logger.error(f"고급 성능 비교 중 오류: {e}")
        raise BenchmarkError(f"성능 비교 실패: {str(e)}") from e


# 유틸리티 함수들


def _read_benchmark_files(
    results_dir: str,
    cutoff_date: datetime,
    limit: int,
    model_filter: Optional[str],
) -> List[Dict[str, Any]]:
    """벤치마크 결과 파일들을 읽어 히스토리 목록을 반환하는 동기 헬퍼.

    ``get_benchmark_history`` 에서 ``run_in_executor`` 를 통해 호출되어
    블로킹 I/O(os.listdir, os.path, open) 가 이벤트 루프를 차단하지 않도록 합니다.
    """
    recent_files = []

    for filename in os.listdir(results_dir):
        if not filename.endswith(".json"):
            continue

        filepath = os.path.join(results_dir, filename)
        file_time = datetime.fromtimestamp(os.path.getctime(filepath))

        if file_time >= cutoff_date:
            recent_files.append((filename, filepath, file_time))

    # 시간순 정렬 (최신 먼저)
    recent_files.sort(key=lambda x: x[2], reverse=True)
    recent_files = recent_files[:limit]

    history: List[Dict[str, Any]] = []
    for filename, filepath, file_time in recent_files:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 모델 필터 적용
            if model_filter:
                models_in_file = list(data.get("results", {}).keys())
                if not any(model_filter.lower() in model.lower() for model in models_in_file):
                    continue

            # 요약 정보 생성
            results = data.get("results", {})
            successful = sum(1 for r in results.values() if r.get("success", False))
            total = len(results)

            history.append(
                {
                    "filename": filename,
                    "timestamp": file_time.isoformat(),
                    "models_tested": list(results.keys()),
                    "success_rate": f"{successful}/{total}",
                    "config": data.get("config", {}),
                    "summary": {
                        "total_models": total,
                        "successful_models": successful,
                        "avg_response_time": _calculate_avg_response_time(results),
                        "best_model": _get_best_model(results),
                    },
                }
            )

        except (json.JSONDecodeError, OSError, KeyError) as e:
            logger.warning(f"파일 {filename} 읽기 실패: {e}")
            continue

    return history


def _calculate_avg_response_time(results: Dict[str, Any]) -> Optional[float]:
    """결과들의 평균 응답 시간 계산"""
    times = []
    for result in results.values():
        if result.get("success") and result.get("metrics"):
            times.append(result["metrics"].get("avg_response_time", 0))

    return sum(times) / len(times) if times else None


def _get_best_model(results: Dict[str, Any]) -> Optional[str]:
    """최고 품질 점수 모델 찾기"""
    best_model = None
    best_score = 0

    for model_id, result in results.items():
        if result.get("success") and result.get("metrics"):
            quality_score = result["metrics"].get("quality_score", 0)
            if quality_score > best_score:
                best_score = quality_score
                best_model = model_id

    return best_model


def _get_category_prompt(category: str) -> str:
    """카테고리별 적합한 프롬프트 반환"""
    prompts = {
        "chat": "안녕하세요! 오늘 날씨가 좋네요. 어떻게 지내세요?",
        "code": "파이썬에서 리스트를 역순으로 정렬하는 방법을 보여주세요.",
        "reasoning": "다음 논리 문제를 풀어주세요: 모든 A는 B이고, 모든 B는 C입니다. X가 A라면, X는 C인가요?",
        "multimodal": "이미지를 분석하고 설명하는 방법에 대해 알려주세요.",
        "image": "이미지 생성을 위한 좋은 프롬프트 작성 팁을 알려주세요.",
    }

    return prompts.get(category, prompts["chat"])


def _analyze_cost_efficiency(results: Dict[str, Any]) -> Dict[str, Any]:
    """비용 효율성 분석"""
    cost_data = []

    for model_id, result in results.items():
        if result.success and result.metrics:
            quality_per_cost = result.metrics.quality_score / max(result.metrics.avg_cost, 0.0001)
            cost_data.append(
                {
                    "model_id": model_id,
                    "avg_cost": result.metrics.avg_cost,
                    "quality_score": result.metrics.quality_score,
                    "quality_per_cost": quality_per_cost,
                }
            )

    if not cost_data:
        return {}

    # 비용 효율성 순으로 정렬
    cost_data.sort(key=lambda x: x["quality_per_cost"], reverse=True)

    return {
        "most_cost_efficient": cost_data[0]["model_id"] if cost_data else None,
        "least_cost_efficient": cost_data[-1]["model_id"] if cost_data else None,
        "avg_cost": sum(item["avg_cost"] for item in cost_data) / len(cost_data),
        "cost_range": {
            "min": min(item["avg_cost"] for item in cost_data),
            "max": max(item["avg_cost"] for item in cost_data),
        },
        "efficiency_ranking": [
            {
                "model": item["model_id"],
                "efficiency": round(item["quality_per_cost"], 3),
            }
            for item in cost_data[:5]  # 상위 5개만
        ],
    }


def _analyze_performance_distribution(results: Dict[str, Any]) -> Dict[str, Any]:
    """성능 분포 분석"""
    response_times = []
    quality_scores = []
    throughputs = []

    for result in results.values():
        if result.success and result.metrics:
            response_times.append(result.metrics.avg_response_time)
            quality_scores.append(result.metrics.quality_score)
            throughputs.append(result.metrics.throughput)

    if not response_times:
        return {}

    return {
        "response_time": {
            "avg": sum(response_times) / len(response_times),
            "min": min(response_times),
            "max": max(response_times),
            "std": _calculate_std(response_times),
        },
        "quality": {
            "avg": sum(quality_scores) / len(quality_scores),
            "min": min(quality_scores),
            "max": max(quality_scores),
            "std": _calculate_std(quality_scores),
        },
        "throughput": {
            "avg": sum(throughputs) / len(throughputs),
            "min": min(throughputs),
            "max": max(throughputs),
            "std": _calculate_std(throughputs),
        },
    }


def _calculate_std(values: List[float]) -> float:
    """표준편차 계산"""
    if len(values) < 2:
        return 0

    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
    return float(variance**0.5)


def _generate_recommendations(
    ranking: List[Tuple[Any, float]], weights: Dict[str, float]
) -> List[Dict[str, Any]]:
    """성능 분석 기반 추천사항 생성"""
    recommendations: List[Dict[str, Any]] = []

    if not ranking:
        return recommendations

    # 최고 모델
    best_model = ranking[0][0]
    recommendations.append(
        {
            "type": "best_overall",
            "model": best_model.model_id,
            "reason": f"가중치 기반 종합 점수가 가장 높음 (점수: {ranking[0][1]:.3f})",
            "use_case": "종합적인 성능이 필요한 작업에 최적",
        }
    )

    # 가장 중요한 가중치에 따른 추천
    primary_metric = max(weights.items(), key=lambda x: x[1])

    if primary_metric[0] == "speed":
        fastest_model = min(
            ranking,
            key=lambda x: (x[0].metrics.avg_response_time if x[0].metrics else float("inf")),
        )
        recommendations.append(
            {
                "type": "fastest",
                "model": fastest_model[0].model_id,
                "reason": f"평균 응답 시간이 가장 빠름 ({fastest_model[0].metrics.avg_response_time:.2f}초)",
                "use_case": "빠른 응답이 필요한 실시간 애플리케이션에 적합",
            }
        )

    elif primary_metric[0] == "cost":
        cheapest_model = min(
            ranking,
            key=lambda x: x[0].metrics.avg_cost if x[0].metrics else float("inf"),
        )
        recommendations.append(
            {
                "type": "most_economical",
                "model": cheapest_model[0].model_id,
                "reason": f"평균 비용이 가장 저렴함 (${cheapest_model[0].metrics.avg_cost:.6f})",
                "use_case": "대량 처리나 예산 제약이 있는 프로젝트에 적합",
            }
        )

    elif primary_metric[0] == "quality":
        highest_quality = max(
            ranking, key=lambda x: x[0].metrics.quality_score if x[0].metrics else 0
        )
        recommendations.append(
            {
                "type": "highest_quality",
                "model": highest_quality[0].model_id,
                "reason": f"품질 점수가 가장 높음 ({highest_quality[0].metrics.quality_score:.1f}점)",
                "use_case": "고품질 응답이 중요한 중요한 업무에 최적",
            }
        )

    return recommendations


_benchmark_models_tool = mcp.tool(benchmark_models)
_get_benchmark_history_tool = mcp.tool(get_benchmark_history)
_compare_model_categories_tool = mcp.tool(compare_model_categories)
_export_benchmark_report_tool = mcp.tool(export_benchmark_report)
_export_benchmark_batch_tool = mcp.tool(export_benchmark_batch)
_compare_model_performance_tool = mcp.tool(compare_model_performance)

logger.info("MCP 벤치마크 도구가 등록되었습니다.")
