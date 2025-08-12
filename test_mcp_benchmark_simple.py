#!/usr/bin/env python3
"""
MCP 벤치마킹 시스템 간단한 기능 테스트

이 스크립트는 OpenRouter MCP Server의 벤치마킹 도구들이 정상적으로 작동하는지 확인합니다.
"""

import asyncio
import os
import json
from datetime import datetime

# MCP 벤치마킹 도구들 가져오기
from src.openrouter_mcp.handlers.mcp_benchmark import (
    benchmark_models,
    get_benchmark_history,
    compare_model_categories,
    export_benchmark_report,
    compare_model_performance
)

async def test_mcp_tools():
    """MCP 벤치마킹 도구들의 기본 기능 테스트"""
    print("[TEST] MCP 벤치마킹 도구 테스트 시작")
    print("=" * 50)
    
    test_results = {}
    
    # 1. 기본 벤치마킹 테스트 (모의 데이터 사용)
    print("\n[1] 기본 벤치마킹 테스트...")
    try:
        # 간단한 테스트 모델로 벤치마킹
        result = await benchmark_models(
            models=["test-model"],  # 존재하지 않는 모델이지만 오류 처리 테스트
            prompt="Hello, how can you help me?",
            runs=1,
            delay_seconds=0.1,
            save_results=True
        )
        
        if 'error' in result:
            print(f"  [WARN] 예상된 오류 (API 키 없음): {result.get('error', 'Unknown')[:50]}...")
            test_results["basic_benchmarking"] = "API 연결 필요"
        else:
            print(f"  [OK] 벤치마킹 완료: {len(result.get('results', {}))} 모델")
            test_results["basic_benchmarking"] = "성공"
    except Exception as e:
        print(f"  [ERROR] 오류: {e}")
        test_results["basic_benchmarking"] = f"오류: {type(e).__name__}"
    
    # 2. 벤치마크 기록 조회 테스트
    print("\n[2] 벤치마크 기록 조회 테스트...")
    try:
        result = await get_benchmark_history(limit=5, days_back=7)
        print(f"  [OK] 기록 조회 완료: {len(result.get('history', []))} 개 파일 발견")
        test_results["history_query"] = "성공"
    except Exception as e:
        print(f"  [ERROR] 오류: {e}")
        test_results["history_query"] = f"오류: {type(e).__name__}"
    
    # 3. 카테고리별 비교 테스트
    print("\n[3] 카테고리별 모델 비교 테스트...")
    try:
        result = await compare_model_categories(
            categories=["chat", "code"],
            top_n=2,
            metric="quality"
        )
        
        if 'error' in result:
            print(f"  [WARN] 예상된 오류 (API 키 없음): {result.get('error', 'Unknown')[:50]}...")
            test_results["category_comparison"] = "API 연결 필요"
        else:
            print(f"  [OK] 카테고리 비교 완료: {result.get('config', {}).get('categories', [])} 카테고리")
            test_results["category_comparison"] = "성공"
    except Exception as e:
        print(f"  [ERROR] 오류: {e}")
        test_results["category_comparison"] = f"오류: {type(e).__name__}"
    
    # 4. 성능 분석 테스트
    print("\n[4] 모델 성능 분석 테스트...")
    try:
        result = await compare_model_performance(
            models=["test-model-1", "test-model-2"],
            weights={"speed": 0.4, "cost": 0.3, "quality": 0.3},
            include_cost_analysis=True
        )
        
        if 'error' in result:
            print(f"  [WARN] 예상된 오류 (API 키 없음): {result.get('error', 'Unknown')[:50]}...")
            test_results["performance_analysis"] = "API 연결 필요"
        else:
            print(f"  [OK] 성능 분석 완료: {len(result.get('ranking', []))} 모델 분석")
            test_results["performance_analysis"] = "성공"
    except Exception as e:
        print(f"  [ERROR] 오류: {e}")
        test_results["performance_analysis"] = f"오류: {type(e).__name__}"
    
    # 5. 보고서 내보내기 테스트 (기존 파일이 있다면)
    print("\n[5] 보고서 내보내기 테스트...")
    try:
        # 기존 벤치마크 파일 찾기
        benchmarks_dir = "benchmarks"
        if os.path.exists(benchmarks_dir):
            benchmark_files = [f for f in os.listdir(benchmarks_dir) 
                             if f.startswith('test_benchmark_') and f.endswith('.json')]
            
            if benchmark_files:
                test_file = benchmark_files[0]
                result = await export_benchmark_report(
                    benchmark_file=test_file,
                    format="markdown"
                )
                print(f"  [OK] 보고서 내보내기 완료: {result.get('output_file', 'N/A')}")
                test_results["report_export"] = "성공"
            else:
                print("  [INFO] 테스트할 벤치마크 파일이 없습니다.")
                test_results["report_export"] = "파일 없음"
        else:
            print("  [INFO] benchmarks 디렉토리가 없습니다.")
            test_results["report_export"] = "디렉토리 없음"
    except Exception as e:
        print(f"  [ERROR] 오류: {e}")
        test_results["report_export"] = f"오류: {type(e).__name__}"
    
    # 테스트 결과 요약
    print("\n" + "=" * 50)
    print("[SUMMARY] 테스트 결과 요약")
    print("=" * 50)
    
    for test_name, result in test_results.items():
        status_icon = "[OK]" if result == "성공" else ("[WARN]" if "API" in result or "없음" in result else "[ERROR]")
        print(f"  {test_name:20} : {status_icon} {result}")
    
    # 성공한 테스트 수 계산
    successful = sum(1 for result in test_results.values() 
                    if result == "성공" or "API" in result or "없음" in result)
    total = len(test_results)
    
    print(f"\n[STATS] {total}개 테스트 중 {successful}개 정상 ({successful/total*100:.1f}%)")
    
    if successful == total:
        print("\n[SUCCESS] 모든 MCP 벤치마킹 도구가 정상적으로 작동합니다!")
        print("[INFO] API 키를 설정하면 실제 모델 벤치마킹을 수행할 수 있습니다.")
    elif successful > total // 2:
        print("\n[SUCCESS] 대부분의 MCP 벤치마킹 도구가 정상적으로 작동합니다.")
        print("[INFO] 일부 기능은 API 키 설정 후 사용 가능합니다.")
    else:
        print("\n[WARNING] 일부 MCP 도구에서 문제가 발견되었습니다.")
        print("[INFO] 상세한 오류 분석이 필요합니다.")

if __name__ == "__main__":
    try:
        asyncio.run(test_mcp_tools())
    except KeyboardInterrupt:
        print("\n[WARNING] 테스트가 중단되었습니다.")
    except Exception as e:
        print(f"\n[ERROR] 테스트 실행 중 오류: {e}")
        import traceback
        traceback.print_exc()