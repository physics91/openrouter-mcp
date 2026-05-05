#!/usr/bin/env python3
"""
OpenRouter MCP Server 벤치마킹 예제 스크립트

이 스크립트는 OpenRouter MCP Server의 벤치마킹 기능을 시연합니다.
다양한 AI 모델의 성능을 비교하고 분석하는 방법을 보여줍니다.
"""

import asyncio
import os
import json
import logging
from datetime import datetime
from typing import List, Dict, Any

# 벤치마킹 관련 import
from src.openrouter_mcp.handlers.mcp_benchmark import (
    get_benchmark_handler,
    benchmark_models,
    get_benchmark_history,
    compare_model_categories,
    export_benchmark_report,
    compare_model_performance
)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def example_1_basic_benchmarking():
    """예제 1: 기본 벤치마킹"""
    print("🚀 예제 1: 기본 벤치마킹")
    print("=" * 50)
    
    # 테스트할 모델들 (빠른 무료 모델들)
    models = [
        "openai/gpt-3.5-turbo",
        "anthropic/claude-3-haiku", 
        "google/gemini-flash-1.5",
        "meta-llama/llama-3.1-8b-instruct:free"
    ]
    
    prompt = "Python에서 'Hello, World!'를 출력하는 방법을 설명해주세요."
    
    try:
        result = await benchmark_models(
            models=models,
            prompt=prompt,
            runs=2,  # 빠른 테스트를 위해 2회만
            delay_seconds=0.5,
            save_results=True
        )
        
        print(f"✅ 벤치마크 완료!")
        print(f"📊 테스트된 모델: {len(result['results'])}")
        print(f"⏱️ 총 소요 시간: {result.get('summary', {}).get('total_time', 'N/A')}")
        
        # 결과 요약 출력
        if 'ranking' in result:
            print("\n🏆 모델 랭킹:")
            for rank_info in result['ranking'][:3]:  # 상위 3개만
                print(f"  {rank_info['rank']}. {rank_info['model_id']} "
                      f"(점수: {rank_info['overall_score']:.2f})")
        
        return result.get('saved_file')
        
    except Exception as e:
        print(f"❌ 기본 벤치마킹 실패: {e}")
        return None


async def example_2_category_comparison():
    """예제 2: 카테고리별 모델 비교"""
    print("\n🎯 예제 2: 카테고리별 모델 비교")
    print("=" * 50)
    
    try:
        result = await compare_model_categories(
            categories=["chat", "code"],
            top_n=2,
            metric="quality"
        )
        
        print(f"✅ 카테고리 비교 완료!")
        print(f"📊 비교된 카테고리: {result['config']['categories']}")
        
        # 카테고리별 정보 출력
        if 'category_info' in result:
            print("\n📋 카테고리별 정보:")
            for category, info in result['category_info'].items():
                print(f"  - {category}: {info['total_models']}개 모델 중 "
                      f"{len(info['selected_models'])}개 선택")
        
        # 카테고리별 결과 출력
        if 'results' in result:
            print("\n🏆 카테고리별 최고 모델:")
            for category, models in result['results'].items():
                print(f"  {category.upper()}:")
                for model in models:
                    if model.get('success'):
                        metrics = model.get('metrics', {})
                        print(f"    - {model['model_id']}: "
                              f"품질 {metrics.get('quality_score', 0):.1f}, "
                              f"비용 ${metrics.get('avg_cost', 0):.6f}")
        
        return True
        
    except Exception as e:
        print(f"❌ 카테고리 비교 실패: {e}")
        return False


async def example_3_performance_analysis():
    """예제 3: 고급 성능 분석"""
    print("\n📈 예제 3: 고급 성능 분석")
    print("=" * 50)
    
    # 분석할 모델들
    models = [
        "openai/gpt-3.5-turbo",
        "anthropic/claude-3-haiku"
    ]
    
    # 사용 사례별 가중치 설정
    use_cases = {
        "speed_focused": {
            "speed": 0.5,
            "cost": 0.3,
            "quality": 0.2
        },
        "quality_focused": {
            "speed": 0.1,
            "cost": 0.2,
            "quality": 0.7
        },
        "balanced": {
            "speed": 0.25,
            "cost": 0.25,
            "quality": 0.25,
            "throughput": 0.25
        }
    }
    
    try:
        print("⚖️ 다양한 가중치로 모델 성능 비교 중...")
        
        for use_case, weights in use_cases.items():
            print(f"\n📋 {use_case.replace('_', ' ').title()} 시나리오:")
            
            result = await compare_model_performance(
                models=models,
                weights=weights,
                include_cost_analysis=True
            )
            
            if result.get('success'):
                ranking = result.get('ranking', [])
                print(f"  🏆 1위: {ranking[0]['model_id']} (점수: {ranking[0]['weighted_score']:.3f})")
                if len(ranking) > 1:
                    print(f"  🥈 2위: {ranking[1]['model_id']} (점수: {ranking[1]['weighted_score']:.3f})")
                
                # 추천사항 출력
                recommendations = result.get('recommendations', [])
                for rec in recommendations[:1]:  # 첫 번째 추천만
                    print(f"  💡 {rec['type']}: {rec['model']} - {rec['reason']}")
            else:
                print(f"  ❌ {use_case} 분석 실패: {result.get('error', 'Unknown error')}")
        
        return True
        
    except Exception as e:
        print(f"❌ 성능 분석 실패: {e}")
        return False


async def example_4_benchmark_history():
    """예제 4: 벤치마크 기록 조회"""
    print("\n📚 예제 4: 벤치마크 기록 조회")
    print("=" * 50)
    
    try:
        result = await get_benchmark_history(
            limit=5,
            days_back=7
        )
        
        history = result.get('history', [])
        
        if history:
            print(f"✅ {len(history)}개의 벤치마크 기록 발견")
            
            print("\n📋 최근 벤치마크 기록:")
            for i, record in enumerate(history, 1):
                print(f"  {i}. {record['filename']}")
                print(f"     - 시간: {record['timestamp']}")
                print(f"     - 모델: {', '.join(record['models_tested'])}")
                print(f"     - 성공률: {record['success_rate']}")
                if record['summary'].get('avg_response_time'):
                    print(f"     - 평균 응답시간: {record['summary']['avg_response_time']:.2f}초")
                print()
        else:
            print("ℹ️ 벤치마크 기록이 없습니다.")
        
        return len(history)
        
    except Exception as e:
        print(f"❌ 기록 조회 실패: {e}")
        return 0


async def example_5_export_reports(benchmark_file: str):
    """예제 5: 보고서 내보내기"""
    print("\n📄 예제 5: 보고서 내보내기")
    print("=" * 50)
    
    if not benchmark_file:
        print("ℹ️ 내보낼 벤치마크 파일이 없습니다.")
        return False
    
    formats = ["markdown", "csv", "json"]
    
    try:
        for fmt in formats:
            print(f"📝 {fmt.upper()} 형식으로 내보내는 중...")
            
            result = await export_benchmark_report(
                benchmark_file=benchmark_file,
                format=fmt
            )
            
            if result.get('message'):
                print(f"  ✅ {result['message']}")
                print(f"     📁 파일: {result.get('output_file', 'N/A')}")
            else:
                print(f"  ❌ {fmt} 내보내기 실패")
        
        return True
        
    except Exception as e:
        print(f"❌ 보고서 내보내기 실패: {e}")
        return False


async def example_6_real_world_scenario():
    """예제 6: 실제 사용 사례 시나리오"""
    print("\n🌍 예제 6: 실제 사용 사례 - 최적의 코딩 어시스턴트 찾기")
    print("=" * 50)
    
    # 코딩 관련 프롬프트
    coding_prompt = """
    다음 Python 함수를 최적화해주세요:

    def fibonacci(n):
        if n <= 1:
            return n
        return fibonacci(n-1) + fibonacci(n-2)

    시간 복잡도를 개선하고, 코드를 더 효율적으로 만들어주세요.
    """
    
    # 코딩에 특화된 모델들
    coding_models = [
        "openai/gpt-3.5-turbo",  # 범용 모델
        "anthropic/claude-3-haiku",  # 빠른 응답
    ]
    
    try:
        print("💻 코딩 어시스턴트 성능 테스트 중...")
        
        result = await benchmark_models(
            models=coding_models,
            prompt=coding_prompt,
            runs=2,
            delay_seconds=1.0,
            save_results=True
        )
        
        if result.get('results'):
            print("✅ 코딩 테스트 완료!")
            
            # 코딩 관련 분석
            print("\n🔍 코딩 능력 분석:")
            
            for model_id, model_result in result['results'].items():
                if model_result.get('success'):
                    metrics = model_result.get('metrics', {})
                    response_preview = model_result.get('response_preview', '')
                    
                    # 코드 포함 여부 확인
                    has_code = '```' in response_preview or 'def ' in response_preview
                    
                    print(f"\n📊 {model_id}:")
                    print(f"  - 응답 시간: {metrics.get('avg_response_time', 0):.2f}초")
                    print(f"  - 비용: ${metrics.get('avg_cost', 0):.6f}")
                    print(f"  - 품질 점수: {metrics.get('quality_score', 0):.1f}")
                    print(f"  - 코드 포함: {'✅' if has_code else '❌'}")
                    print(f"  - 응답 미리보기: {response_preview[:100]}...")
        
        # 추가 분석: 코딩 전용 성능 비교
        print("\n⚖️ 코딩 최적화 가중치 분석:")
        
        coding_weights = {
            "speed": 0.3,      # 빠른 개발을 위한 응답 속도
            "cost": 0.2,       # 비용 효율성
            "quality": 0.5     # 코드 품질이 가장 중요
        }
        
        performance_result = await compare_model_performance(
            models=coding_models,
            weights=coding_weights,
            include_cost_analysis=True
        )
        
        if performance_result.get('success'):
            ranking = performance_result.get('ranking', [])
            print(f"🏆 최적의 코딩 어시스턴트: {ranking[0]['model_id']}")
            print(f"   종합 점수: {ranking[0]['weighted_score']:.3f}")
            
            recommendations = performance_result.get('recommendations', [])
            for rec in recommendations:
                if rec['type'] in ['best_overall', 'highest_quality']:
                    print(f"💡 추천: {rec['model']} - {rec['reason']}")
        
        return True
        
    except Exception as e:
        print(f"❌ 실제 사용 사례 테스트 실패: {e}")
        return False


async def main():
    """메인 실행 함수"""
    print("🎉 OpenRouter MCP Server 벤치마킹 예제 시작!")
    print("=" * 60)
    
    # API 키 확인
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("❌ OPENROUTER_API_KEY 환경변수가 설정되지 않았습니다.")
        print("   다음 명령으로 API 키를 설정하세요:")
        print("   export OPENROUTER_API_KEY='your-api-key-here'")
        return
    
    print(f"✅ API 키 확인 완료: {api_key[:8]}...")
    print()
    
    # 예제 실행
    examples = [
        ("기본 벤치마킹", example_1_basic_benchmarking),
        ("카테고리별 비교", example_2_category_comparison),
        ("고급 성능 분석", example_3_performance_analysis),
        ("벤치마크 기록 조회", example_4_benchmark_history),
        ("실제 사용 사례", example_6_real_world_scenario),
    ]
    
    results = {}
    benchmark_file = None
    
    for name, example_func in examples:
        try:
            print(f"\n{'='*20} {name} {'='*20}")
            
            if example_func == example_1_basic_benchmarking:
                # 첫 번째 예제에서 벤치마크 파일 경로 받기
                benchmark_file = await example_func()
                results[name] = benchmark_file is not None
            elif example_func == example_4_benchmark_history:
                # 기록 조회에서 개수 받기
                count = await example_func()
                results[name] = count > 0
            else:
                # 나머지 예제들
                result = await example_func()
                results[name] = result
        
        except Exception as e:
            print(f"❌ {name} 실행 중 오류: {e}")
            results[name] = False
        
        # 예제 간 잠시 대기
        await asyncio.sleep(1)
    
    # 보고서 내보내기 예제 (벤치마크 파일이 있을 때만)
    if benchmark_file:
        try:
            print(f"\n{'='*20} 보고서 내보내기 {'='*20}")
            export_result = await example_5_export_reports(benchmark_file)
            results["보고서 내보내기"] = export_result
        except Exception as e:
            print(f"❌ 보고서 내보내기 실행 중 오류: {e}")
            results["보고서 내보내기"] = False
    
    # 최종 결과 요약
    print("\n" + "="*60)
    print("🎯 예제 실행 결과 요약")
    print("="*60)
    
    successful = sum(1 for success in results.values() if success)
    total = len(results)
    
    for name, success in results.items():
        status = "✅ 성공" if success else "❌ 실패"
        print(f"  {name:20} : {status}")
    
    print(f"\n📊 총 {total}개 예제 중 {successful}개 성공 ({successful/total*100:.1f}%)")
    
    if successful > 0:
        print("\n🎉 벤치마킹 예제 완료!")
        print("💡 Claude Desktop이나 다른 MCP 클라이언트에서 벤치마킹 도구를 사용해보세요:")
        print("   - benchmark_models")
        print("   - get_benchmark_history") 
        print("   - compare_model_categories")
        print("   - export_benchmark_report")
        print("   - compare_model_performance")
    else:
        print("\n😞 모든 예제가 실패했습니다.")
        print("API 키와 인터넷 연결을 확인해주세요.")


if __name__ == "__main__":
    # 예제 실행
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️ 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\n❌ 예제 실행 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()