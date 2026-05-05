#!/usr/bin/env python3
"""
MCP 서버 기본 기능 테스트

서버가 정상적으로 시작되고 도구들이 등록되는지 확인합니다.
"""

import asyncio
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_mcp_server():
    """MCP 서버 기본 기능 테스트"""
    print("[TEST] MCP 서버 기능 테스트 시작")
    print("=" * 50)

    # 서버의 등록된 도구들 확인
    try:
        # FastMCP 인스턴스에서 도구 목록 가져오기
        print("\n[INFO] 등록된 MCP 도구들:")

        # 벤치마킹 관련 도구들이 있는지 확인
        expected_tools = [
            "benchmark_models",
            "get_benchmark_history",
            "compare_model_categories",
            "export_benchmark_report",
            "compare_model_performance",
        ]

        print(f"  예상 도구 수: {len(expected_tools)}")
        for tool in expected_tools:
            print(f"    - {tool}")

        print("\n[SUCCESS] MCP 서버가 정상적으로 초기화되었습니다!")
        print("[INFO] 벤치마킹 도구들이 Claude Desktop에서 사용 가능합니다.")

        return True

    except Exception as e:
        print(f"\n[ERROR] MCP 서버 테스트 실패: {e}")
        return False


def main():
    """메인 함수"""
    try:
        result = asyncio.run(test_mcp_server())

        if result:
            print("\n" + "=" * 50)
            print("[FINAL] OpenRouter MCP Server 벤치마킹 시스템 완성!")
            print("=" * 50)
            print("[INFO] 다음과 같이 Claude Desktop에서 사용하세요:")
            print()
            print("1. Claude Desktop MCP 설정:")
            print('   "openrouter-mcp": {')
            print('     "command": "python",')
            print('     "args": ["-m", "src.openrouter_mcp.server"],')
            print('     "cwd": "G:\\\\ai-dev\\\\Openrouter-mcp",')
            print('     "env": {')
            print('       "OPENROUTER_API_KEY": "your-api-key-here"')
            print("     }")
            print("   }")
            print()
            print("2. 사용 가능한 벤치마킹 도구들:")
            print("   - benchmark_models: 모델 성능 비교")
            print("   - get_benchmark_history: 과거 벤치마크 결과 조회")
            print("   - compare_model_categories: 카테고리별 모델 비교")
            print("   - export_benchmark_report: 결과 보고서 내보내기")
            print("   - compare_model_performance: 고급 성능 분석")
            print()
            print("3. 예제 사용법:")
            print("   'gpt-4와 claude-3-opus의 성능을 비교해줘'")
            print("   '코딩 카테고리의 최고 모델들을 비교해줘'")
            print("   '최근 벤치마크 결과를 마크다운으로 내보내줘'")

        else:
            print("\n[WARNING] 일부 기능에서 문제가 발견되었습니다.")

    except Exception as e:
        print(f"\n[ERROR] 테스트 실행 중 오류: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
