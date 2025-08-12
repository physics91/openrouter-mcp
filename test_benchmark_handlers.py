#!/usr/bin/env python3
"""
벤치마킹 핸들러 직접 테스트

MCP 도구가 아닌 핸들러를 직접 테스트하여 벤치마킹 시스템의 작동 여부를 확인합니다.
"""

import asyncio
import os
import json
from datetime import datetime

# 직접 핸들러 클래스들 가져오기
from src.openrouter_mcp.handlers.mcp_benchmark import get_benchmark_handler
from src.openrouter_mcp.handlers.benchmark import (
    BenchmarkResult,
    BenchmarkMetrics,
    BenchmarkHandler
)

async def test_benchmark_handlers():
    """벤치마킹 핸들러들의 직접 테스트"""
    print("[TEST] 벤치마킹 핸들러 직접 테스트 시작")
    print("=" * 50)
    
    test_results = {}
    
    # 1. 벤치마크 핸들러 생성 테스트
    print("\n[1] 벤치마크 핸들러 생성 테스트...")
    try:
        handler = await get_benchmark_handler()
        print("  [OK] 벤치마크 핸들러 생성 성공")
        test_results["handler_creation"] = "성공"
    except Exception as e:
        print(f"  [ERROR] 핸들러 생성 실패: {e}")
        test_results["handler_creation"] = f"오류: {type(e).__name__}"
        return test_results
    
    # 2. 모의 벤치마크 결과 생성 테스트
    print("\n[2] 모의 벤치마크 결과 생성 테스트...")
    try:
        # 모의 데이터로 벤치마크 결과 생성
        mock_metrics = BenchmarkMetrics()
        mock_metrics.avg_response_time_ms = 1500
        mock_metrics.min_response_time_ms = 1000
        mock_metrics.max_response_time_ms = 2000
        mock_metrics.avg_cost = 0.001
        mock_metrics.min_cost = 0.0008
        mock_metrics.max_cost = 0.0012
        mock_metrics.avg_prompt_tokens = 25.0
        mock_metrics.avg_completion_tokens = 30.0
        mock_metrics.avg_total_tokens = 55.0
        mock_metrics.quality_score = 8.5
        mock_metrics.throughput_tokens_per_sec = 45.0
        mock_metrics.success_rate = 1.0
        
        mock_result = BenchmarkResult(
            model_id="test-model",
            success=True,
            response="This is a test response for benchmarking.",
            error_message=None,
            timestamp=datetime.now().isoformat(),
            metrics=mock_metrics
        )
        
        print("  [OK] 모의 벤치마크 결과 생성 성공")
        print(f"    - 모델 ID: {mock_result.model_id}")
        print(f"    - 성공 여부: {mock_result.success}")
        print(f"    - 평균 응답시간: {mock_result.metrics.avg_response_time_ms}ms")
        print(f"    - 평균 비용: ${mock_result.metrics.avg_cost}")
        print(f"    - 품질 점수: {mock_result.metrics.quality_score}")
        
        test_results["mock_result_creation"] = "성공"
        
    except Exception as e:
        print(f"  [ERROR] 모의 결과 생성 실패: {e}")
        test_results["mock_result_creation"] = f"오류: {type(e).__name__}"
        return test_results
    
    # 3. 보고서 익스포터 테스트
    print("\n[3] 보고서 익스포터 테스트...")
    try:
        exporter = BenchmarkReportExporter()
        
        # 모의 벤치마크 결과 사전 생성
        mock_results = {
            "test-model": mock_result
        }
        
        # 임시 파일에 마크다운 보고서 내보내기
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as tmp_file:
            temp_path = tmp_file.name
            
        await exporter.export_markdown(mock_results, temp_path)
        
        # 생성된 파일 확인
        if os.path.exists(temp_path):
            with open(temp_path, 'r', encoding='utf-8') as f:
                content = f.read()
                print(f"  [OK] 마크다운 보고서 생성 성공: {len(content)} 문자")
                
            # 임시 파일 삭제
            os.unlink(temp_path)
            test_results["report_exporter"] = "성공"
        else:
            print("  [ERROR] 보고서 파일이 생성되지 않았습니다.")
            test_results["report_exporter"] = "파일 생성 실패"
            
    except Exception as e:
        print(f"  [ERROR] 보고서 익스포터 실패: {e}")
        test_results["report_exporter"] = f"오류: {type(e).__name__}"
    
    # 4. 모델 성능 분석기 테스트
    print("\n[4] 모델 성능 분석기 테스트...")
    try:
        analyzer = ModelPerformanceAnalyzer()
        
        # 모의 결과로 성능 분석
        mock_results_multi = {
            "model-1": EnhancedBenchmarkResult(
                model_id="model-1",
                success=True,
                response="Response from model 1",
                error_message=None,
                timestamp=datetime.now(),
                metrics=EnhancedBenchmarkMetrics(
                    avg_response_time=1.2,
                    min_response_time=1.0,
                    max_response_time=1.5,
                    avg_cost=0.0008,
                    min_cost=0.0006,
                    max_cost=0.001,
                    avg_prompt_tokens=25.0,
                    avg_completion_tokens=35.0,
                    avg_total_tokens=60.0,
                    quality_score=9.0,
                    throughput=50.0,
                    success_rate=1.0,
                    speed_score=0.9,
                    cost_score=0.95,
                    throughput_score=0.5
                )
            ),
            "model-2": EnhancedBenchmarkResult(
                model_id="model-2", 
                success=True,
                response="Response from model 2",
                error_message=None,
                timestamp=datetime.now(),
                metrics=EnhancedBenchmarkMetrics(
                    avg_response_time=2.0,
                    min_response_time=1.8,
                    max_response_time=2.2,
                    avg_cost=0.0015,
                    min_cost=0.0012,
                    max_cost=0.0018,
                    avg_prompt_tokens=25.0,
                    avg_completion_tokens=40.0,
                    avg_total_tokens=65.0,
                    quality_score=8.5,
                    throughput=32.0,
                    success_rate=1.0,
                    speed_score=0.6,
                    cost_score=0.75,
                    throughput_score=0.32
                )
            )
        }
        
        # 가중치 기반 분석
        weights = {"speed": 0.3, "cost": 0.4, "quality": 0.3}
        ranking = analyzer.calculate_weighted_scores(mock_results_multi, weights)
        
        print(f"  [OK] 성능 분석 완료: {len(ranking)} 모델 분석")
        for i, item in enumerate(ranking, 1):
            print(f"    {i}. {item['model_id']}: {item['weighted_score']:.3f} 점")
            
        test_results["performance_analyzer"] = "성공"
        
    except Exception as e:
        print(f"  [ERROR] 성능 분석기 실패: {e}")
        test_results["performance_analyzer"] = f"오류: {type(e).__name__}"
    
    # 5. 벤치마크 결과 저장 및 로드 테스트
    print("\n[5] 벤치마크 결과 저장/로드 테스트...")
    try:
        # 결과 저장
        results_to_save = {"test-model": mock_result}
        filename = f"test_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        if not os.path.exists("benchmarks"):
            os.makedirs("benchmarks")
        
        file_path = os.path.join("benchmarks", filename)
        
        # JSON 직렬화를 위해 결과를 딕셔너리로 변환
        serializable_results = {}
        for model_id, result in results_to_save.items():
            serializable_results[model_id] = {
                "model_id": result.model_id,
                "success": result.success,
                "response": result.response,
                "error_message": result.error_message,
                "timestamp": result.timestamp.isoformat(),
                "metrics": {
                    "avg_response_time": result.metrics.avg_response_time,
                    "min_response_time": result.metrics.min_response_time,
                    "max_response_time": result.metrics.max_response_time,
                    "avg_cost": result.metrics.avg_cost,
                    "min_cost": result.metrics.min_cost,
                    "max_cost": result.metrics.max_cost,
                    "avg_prompt_tokens": result.metrics.avg_prompt_tokens,
                    "avg_completion_tokens": result.metrics.avg_completion_tokens,
                    "avg_total_tokens": result.metrics.avg_total_tokens,
                    "quality_score": result.metrics.quality_score,
                    "throughput": result.metrics.throughput,
                    "success_rate": result.metrics.success_rate,
                    "speed_score": result.metrics.speed_score,
                    "cost_score": result.metrics.cost_score,
                    "throughput_score": result.metrics.throughput_score
                }
            }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "results": serializable_results
            }, f, indent=2, ensure_ascii=False)
        
        print(f"  [OK] 벤치마크 결과 저장 성공: {filename}")
        
        # 저장된 파일 확인
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                loaded_data = json.load(f)
                print(f"  [OK] 벤치마크 결과 로드 성공: {len(loaded_data['results'])} 모델")
                
        test_results["save_load"] = "성공"
        
    except Exception as e:
        print(f"  [ERROR] 저장/로드 실패: {e}")
        test_results["save_load"] = f"오류: {type(e).__name__}"
    
    # 테스트 결과 요약
    print("\n" + "=" * 50)
    print("[SUMMARY] 핸들러 테스트 결과 요약")
    print("=" * 50)
    
    for test_name, result in test_results.items():
        status_icon = "[OK]" if result == "성공" else "[ERROR]"
        print(f"  {test_name:25} : {status_icon} {result}")
    
    # 성공한 테스트 수 계산
    successful = sum(1 for result in test_results.values() if result == "성공")
    total = len(test_results)
    
    print(f"\n[STATS] {total}개 테스트 중 {successful}개 성공 ({successful/total*100:.1f}%)")
    
    if successful == total:
        print("\n[SUCCESS] 모든 벤치마킹 핸들러가 정상적으로 작동합니다!")
        print("[INFO] MCP 도구들도 정상적으로 작동할 것입니다.")
    elif successful > total // 2:
        print("\n[SUCCESS] 대부분의 벤치마킹 핸들러가 정상적으로 작동합니다.")
        print("[INFO] 일부 기능은 추가 디버깅이 필요할 수 있습니다.")
    else:
        print("\n[WARNING] 여러 핸들러에서 문제가 발견되었습니다.")
        print("[INFO] 상세한 디버깅이 필요합니다.")
    
    return test_results

if __name__ == "__main__":
    try:
        asyncio.run(test_benchmark_handlers())
    except KeyboardInterrupt:
        print("\n[WARNING] 테스트가 중단되었습니다.")
    except Exception as e:
        print(f"\n[ERROR] 테스트 실행 중 오류: {e}")
        import traceback
        traceback.print_exc()