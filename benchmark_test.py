#!/usr/bin/env python3
"""
OpenRouter MCP 벤치마크 시스템 테스트 스크립트
"""

import os
import asyncio
import sys
from datetime import datetime

# 환경변수 설정 (실제 API 키는 사용하지 않음)
os.environ['OPENROUTER_API_KEY'] = 'test-api-key-for-demo'

# MCP 벤치마크 시스템 import
from src.openrouter_mcp.handlers.mcp_benchmark import get_benchmark_handler
from src.openrouter_mcp.handlers.benchmark import (
    BenchmarkReportExporter, ModelPerformanceAnalyzer,
    EnhancedBenchmarkResult, EnhancedBenchmarkMetrics, BenchmarkResult
)

async def test_benchmark_system():
    """벤치마크 시스템 테스트"""
    print("=" * 60)
    print("OpenRouter MCP 벤치마크 시스템 테스트")
    print("=" * 60)
    
    try:
        # 1. 핸들러 초기화
        print("\n1. 벤치마크 핸들러 초기화...")
        handler = await get_benchmark_handler()
        print(f"   핸들러 타입: {type(handler).__name__}")
        print(f"   결과 디렉토리: {handler.results_dir}")
        
        # 2. 모의 벤치마크 결과 생성
        print("\n2. 모의 벤치마크 결과 생성...")
        benchmark_results = []
        for i in range(3):
            result = BenchmarkResult(
                model_id="test-model",
                prompt="Hello, world!",
                response=f"Response {i+1}: Hello! How can I help you?",
                response_time_ms=1500 + (i * 200),
                tokens_used=50 + (i * 10),
                cost=0.001 + (i * 0.0002),
                timestamp=datetime.now(),
                prompt_tokens=25,
                completion_tokens=25 + (i * 5),
                quality_score=8.0 + (i * 0.2),
                throughput_tokens_per_second=30.0 + (i * 5)
            )
            benchmark_results.append(result)
        
        # 3. Enhanced 결과 생성
        print("\n3. Enhanced 벤치마크 결과 생성...")
        enhanced_result = handler._create_enhanced_result("test-model", benchmark_results, "Hello, world!")
        print(f"   모델 ID: {enhanced_result.model_id}")
        print(f"   성공 여부: {enhanced_result.success}")
        print(f"   응답 길이: {len(enhanced_result.response) if enhanced_result.response else 0}")
        
        if enhanced_result.metrics:
            print(f"   평균 응답 시간: {enhanced_result.metrics.avg_response_time:.2f}초")
            print(f"   평균 비용: ${enhanced_result.metrics.avg_cost:.6f}")
            print(f"   품질 점수: {enhanced_result.metrics.quality_score:.1f}")
            print(f"   처리량: {enhanced_result.metrics.throughput:.1f} tokens/s")
        
        # 4. 결과 저장 테스트
        print("\n4. 결과 저장 테스트...")
        results = {"test-model": enhanced_result}
        filename = f"test_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        await handler.save_results(results, filename)
        print(f"   결과 저장 완료: {filename}")
        
        # 5. 보고서 내보내기 테스트
        print("\n5. 보고서 내보내기 테스트...")
        exporter = BenchmarkReportExporter()
        
        # Markdown 보고서
        md_path = f"benchmarks/test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        await exporter.export_markdown(results, md_path)
        print(f"   Markdown 보고서: {md_path}")
        
        # CSV 보고서
        csv_path = f"benchmarks/test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        await exporter.export_csv(results, csv_path)
        print(f"   CSV 보고서: {csv_path}")
        
        # 6. 성능 분석기 테스트
        print("\n6. 성능 분석기 테스트...")
        analyzer = ModelPerformanceAnalyzer()
        results_list = [enhanced_result]
        
        ranking = analyzer.rank_models(results_list)
        print(f"   랭킹 결과: {len(ranking)}개 모델")
        
        comparison = analyzer.compare_models(results_list)
        if comparison:
            print(f"   분석 완료 - 성공한 모델: {comparison.get('successful_models', 0)}")
        
        print("\n" + "=" * 60)
        print("모든 테스트 완료! 벤치마크 시스템이 정상적으로 작동합니다.")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_benchmark_system())
    sys.exit(0 if success else 1)