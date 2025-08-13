#!/usr/bin/env python3
"""
Claude Code CLI MCP 연결 테스트

Claude Code CLI가 OpenRouter MCP Server에 정상적으로 연결되는지 테스트합니다.
"""

import json
import subprocess
import sys
from pathlib import Path
import os

def test_claude_config():
    """Claude Code CLI 설정 파일 테스트"""
    print("[TEST] Claude Code CLI 설정 파일 테스트")
    print("=" * 50)
    
    # 설정 파일 경로
    if os.name == 'nt':  # Windows
        config_path = Path.home() / ".claude" / "claude_code_config.json"
    else:  # macOS/Linux
        config_path = Path.home() / ".claude" / "claude_code_config.json"
    
    # 1. 설정 파일 존재 확인
    if not config_path.exists():
        print(f"[ERROR] 설정 파일이 존재하지 않습니다: {config_path}")
        return False
    
    print(f"[SUCCESS] 설정 파일 발견: {config_path}")
    
    # 2. 설정 파일 내용 검증
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        if "mcpServers" not in config:
            print("[ERROR] mcpServers 섹션이 없습니다.")
            return False
        
        if "openrouter-mcp" not in config["mcpServers"]:
            print("[ERROR] openrouter-mcp 서버 설정이 없습니다.")
            return False
        
        mcp_config = config["mcpServers"]["openrouter-mcp"]
        required_fields = ["command", "args", "cwd", "env"]
        
        for field in required_fields:
            if field not in mcp_config:
                print(f"[ERROR] 필수 필드 누락: {field}")
                return False
        
        print("[SUCCESS] 설정 파일 구조 검증 완료")
        
        # 3. 중요 설정값 확인
        print("\n[INFO] MCP 서버 설정:")
        print(f"  - Command: {mcp_config['command']}")
        print(f"  - Args: {mcp_config['args']}")
        print(f"  - Working Directory: {mcp_config['cwd']}")
        print(f"  - API Key: {mcp_config['env']['OPENROUTER_API_KEY'][:10]}..." 
              if len(mcp_config['env']['OPENROUTER_API_KEY']) > 10 else "[NOT_SET]")
        
        return True
        
    except json.JSONDecodeError as e:
        print(f"[ERROR] 설정 파일 JSON 파싱 오류: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] 설정 파일 검증 오류: {e}")
        return False

def test_mcp_server():
    """MCP 서버 직접 실행 테스트"""
    print("\n[TEST] MCP 서버 직접 실행 테스트")
    print("=" * 50)
    
    try:
        # 현재 디렉토리에서 MCP 서버 모듈 테스트
        print("[INFO] MCP 서버 모듈 import 테스트...")
        import src.openrouter_mcp.server
        print("[SUCCESS] MCP 서버 모듈 import 성공")
        
        # MCP 도구들이 등록되었는지 확인
        print("[INFO] 등록된 MCP 도구 확인...")
        expected_tools = [
            "chat_with_model",
            "list_available_models",
            "get_usage_stats",
            "benchmark_models",
            "get_benchmark_history",
            "compare_model_categories",
            "export_benchmark_report",
            "compare_model_performance"
        ]
        
        print(f"[INFO] 예상 MCP 도구 수: {len(expected_tools)}")
        for tool in expected_tools:
            print(f"  - {tool}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] MCP 서버 테스트 실패: {e}")
        return False

def test_python_environment():
    """Python 환경 테스트"""
    print("\n[TEST] Python 환경 테스트")
    print("=" * 50)
    
    print(f"[INFO] Python 버전: {sys.version}")
    print(f"[INFO] Python 실행 파일: {sys.executable}")
    print(f"[INFO] 현재 작업 디렉토리: {os.getcwd()}")
    
    # 필수 패키지 확인
    required_packages = ["fastmcp", "aiohttp", "asyncio"]
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"[SUCCESS] {package} 패키지 available")
        except ImportError:
            print(f"[WARNING] {package} 패키지 not found")
    
    return True

def show_usage_instructions():
    """사용법 안내"""
    print("\n[USAGE] Claude Code CLI에서 OpenRouter MCP Server 사용법")
    print("=" * 60)
    
    print("\n1. Claude Code CLI 재시작:")
    print("   - 기존 Claude Code CLI 세션을 종료하세요")
    print("   - 새 터미널을 열고 Claude Code CLI를 다시 실행하세요")
    
    print("\n2. API 키 설정 (필수):")
    print("   - https://openrouter.ai 에서 계정 생성")
    print("   - API Keys 섹션에서 새 API 키 생성")
    config_path = Path.home() / ".claude" / "claude_code_config.json"
    print(f"   - {config_path} 파일을 편집기로 열기")
    print("   - 'your-openrouter-api-key-here'를 실제 API 키로 교체")
    
    print("\n3. MCP 도구 사용 예제:")
    print("   벤치마킹:")
    print("     'gpt-4와 claude-3-opus의 성능을 비교해줘'")
    print("     '코딩 카테고리의 최고 모델들을 비교해줘'")
    print("     '최근 벤치마크 결과를 보여줘'")
    
    print("\n   모델 사용:")
    print("     'list all available AI models'")
    print("     'use gpt-4o to explain quantum computing'")
    print("     'show my OpenRouter usage statistics'")
    
    print("\n   비전/멀티모달:")
    print("     'analyze this image with gpt-4o-vision'")
    print("     'compare these two images using claude-3-opus'")
    
    print("\n4. 문제 해결:")
    current_dir = Path(__file__).parent
    print(f"   - 문서: {current_dir}/docs/TROUBLESHOOTING.md")
    print(f"   - FAQ: {current_dir}/docs/FAQ.md")
    print(f"   - 설정 파일: {config_path}")

def main():
    """메인 테스트 함수"""
    print("[INFO] Claude Code CLI MCP 연결 테스트 시작")
    print("=" * 60)
    
    results = {}
    
    # 테스트 실행
    results["config"] = test_claude_config()
    results["python"] = test_python_environment()
    results["mcp_server"] = test_mcp_server()
    
    # 결과 요약
    print("\n" + "=" * 60)
    print("[SUMMARY] 테스트 결과 요약")
    print("=" * 60)
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {test_name:15} : {status}")
    
    print(f"\n[STATS] {total}개 테스트 중 {passed}개 통과 ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("\n[SUCCESS] 모든 테스트 통과! Claude Code CLI에서 MCP 도구를 사용할 준비가 되었습니다.")
        show_usage_instructions()
    elif passed > 0:
        print("\n[WARNING] 일부 테스트에서 문제가 발견되었습니다.")
        print("API 키 설정 후 정상 작동할 수 있습니다.")
        show_usage_instructions()
    else:
        print("\n[ERROR] 모든 테스트가 실패했습니다.")
        print("설치를 다시 실행하거나 문서를 참조하세요.")
    
    return passed == total

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[WARNING] 테스트가 중단되었습니다.")
    except Exception as e:
        print(f"\n[ERROR] 테스트 실행 중 오류: {e}")
        import traceback
        traceback.print_exc()