#!/usr/bin/env python3
"""
OpenRouter MCP Server - Claude Code CLI 자동 설치 스크립트 (Simple)
"""

import os
import json
from pathlib import Path

def main():
    """메인 설치 함수"""
    print("[INFO] OpenRouter MCP Server - Claude Code CLI 설치 시작")
    print("=" * 60)
    
    # 1. MCP 서버 모듈 테스트
    print("\n[1] MCP 서버 모듈 테스트...")
    try:
        import src.openrouter_mcp.server
        print("[SUCCESS] OpenRouter MCP Server 모듈 import 성공")
    except Exception as e:
        print(f"[ERROR] MCP 서버 테스트 실패: {e}")
        return False
    
    # 2. Claude 설정 디렉토리 확인/생성
    print("\n[2] Claude Code CLI 설정 디렉토리 확인...")
    if os.name == 'nt':  # Windows
        config_path = Path.home() / ".claude" / "claude_code_config.json"
    else:  # macOS/Linux
        config_path = Path.home() / ".claude" / "claude_code_config.json"
    
    config_dir = config_path.parent
    if not config_dir.exists():
        config_dir.mkdir(parents=True, exist_ok=True)
        print(f"[SUCCESS] Claude 설정 디렉토리 생성: {config_dir}")
    else:
        print(f"[INFO] Claude 설정 디렉토리 존재: {config_dir}")
    
    # 3. 기존 설정 로드
    print("\n[3] 기존 Claude Code CLI 설정 확인...")
    config = {"mcpServers": {}}
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                print("[INFO] 기존 Claude Code CLI 설정 발견")
        except Exception as e:
            print(f"[WARNING] 기존 설정 파일 읽기 실패: {e}")
            print("[INFO] 새로운 설정으로 덮어씁니다.")
            config = {"mcpServers": {}}
    
    # 4. API 키 설정 (환경변수 또는 기본값)
    print("\n[4] OpenRouter API 키 설정...")
    api_key = os.getenv("OPENROUTER_API_KEY", "your-openrouter-api-key-here")
    if api_key == "your-openrouter-api-key-here":
        print("[WARNING] OPENROUTER_API_KEY 환경변수가 설정되지 않았습니다.")
        print("[INFO] 기본값을 사용합니다. 나중에 설정 파일에서 수정하세요.")
    else:
        print(f"[SUCCESS] 환경변수에서 API 키 발견: {api_key[:8]}...")
    
    # 5. MCP 서버 설정 생성
    print("\n[5] OpenRouter MCP Server 설정 추가...")
    current_dir = Path(__file__).parent.absolute()
    
    mcp_config = {
        "command": "python",
        "args": ["-m", "src.openrouter_mcp.server"],
        "cwd": str(current_dir),
        "env": {
            "OPENROUTER_API_KEY": api_key,
            "OPENROUTER_APP_NAME": "claude-code-mcp",
            "OPENROUTER_HTTP_REFERER": "https://localhost:3000",
            "HOST": "localhost",
            "PORT": "8000",
            "LOG_LEVEL": "info"
        }
    }
    
    config["mcpServers"]["openrouter-mcp"] = mcp_config
    
    # 6. 설정 파일 저장
    print("\n[6] Claude Code CLI 설정 파일 저장...")
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print(f"[SUCCESS] Claude Code CLI 설정 저장: {config_path}")
    except Exception as e:
        print(f"[ERROR] 설정 저장 실패: {e}")
        return False
    
    # 7. 설치 완료 안내
    print("\n" + "=" * 60)
    print("[SUCCESS] OpenRouter MCP Server 설치 완료!")
    print("=" * 60)
    print()
    print("다음 단계:")
    print("1. Claude Code CLI를 재시작하세요")
    print("2. 다음 명령으로 MCP 도구들을 사용하세요:")
    print()
    print("벤치마킹 도구:")
    print("  - 'gpt-4와 claude-3-opus의 성능을 비교해줘'")
    print("  - '코딩 카테고리의 최고 모델들을 비교해줘'")
    print("  - '최근 벤치마크 결과를 보여줘'")
    print()
    print("모델 사용:")
    print("  - 'list available models'")
    print("  - 'use gpt-4o to explain quantum computing'")
    print("  - 'show usage statistics'")
    print()
    print("도움말:")
    print(f"  - 설정 파일: {config_path}")
    print(f"  - 문서: {Path(__file__).parent}/docs/INDEX.md")
    
    if api_key == "your-openrouter-api-key-here":
        print()
        print("[IMPORTANT] API 키 설정 필요:")
        print("1. https://openrouter.ai 에서 계정을 생성하세요")
        print("2. 'API Keys' 섹션에서 새 API 키를 생성하세요")
        print(f"3. {config_path} 파일을 열어서")
        print("   'your-openrouter-api-key-here'를 실제 API 키로 교체하세요")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        if not success:
            print("\n[ERROR] 설치가 완료되지 않았습니다.")
    except KeyboardInterrupt:
        print("\n[WARNING] 설치가 중단되었습니다.")
    except Exception as e:
        print(f"\n[ERROR] 설치 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()