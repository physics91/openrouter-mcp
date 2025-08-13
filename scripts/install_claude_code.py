#!/usr/bin/env python3
"""
OpenRouter MCP Server - Claude Code CLI 자동 설치 스크립트

이 스크립트는 OpenRouter MCP Server를 Claude Code CLI에 자동으로 설정합니다.
"""

import os
import json
import shutil
from pathlib import Path

def get_claude_config_path():
    """Claude Code CLI 설정 파일 경로 반환"""
    if os.name == 'nt':  # Windows
        return Path.home() / ".claude" / "claude_code_config.json"
    else:  # macOS/Linux
        return Path.home() / ".claude" / "claude_code_config.json"

def ensure_claude_dir():
    """Claude 설정 디렉토리 생성"""
    config_path = get_claude_config_path()
    config_dir = config_path.parent
    
    if not config_dir.exists():
        config_dir.mkdir(parents=True, exist_ok=True)
        print(f"✅ Claude 설정 디렉토리 생성: {config_dir}")
    else:
        print(f"📁 Claude 설정 디렉토리 존재: {config_dir}")
    
    return config_path

def load_existing_config(config_path):
    """기존 Claude Code CLI 설정 로드"""
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                print("📋 기존 Claude Code CLI 설정 발견")
                return config
        except (json.JSONDecodeError, Exception) as e:
            print(f"⚠️ 기존 설정 파일 읽기 실패: {e}")
            print("새로운 설정으로 덮어씁니다.")
    
    return {"mcpServers": {}}

def get_api_key():
    """OpenRouter API 키 입력받기"""
    print("\n🔑 OpenRouter API 키 설정")
    print("=" * 50)
    print("1. https://openrouter.ai 에서 계정을 생성하세요")
    print("2. 'API Keys' 섹션에서 새 API 키를 생성하세요")
    print("3. 아래에 API 키를 입력하세요")
    print()
    
    # 환경변수에서 먼저 확인
    env_key = os.getenv("OPENROUTER_API_KEY")
    if env_key:
        use_env = input(f"환경변수에서 API 키를 발견했습니다: {env_key[:8]}...\n이 키를 사용하시겠습니까? (y/N): ").lower()
        if use_env == 'y':
            return env_key
    
    while True:
        api_key = input("OpenRouter API 키를 입력하세요: ").strip()
        if api_key:
            if api_key.startswith('sk-or-'):
                return api_key
            else:
                print("⚠️ OpenRouter API 키는 'sk-or-'로 시작해야 합니다.")
        else:
            print("⚠️ API 키를 입력해주세요.")

def create_mcp_config(api_key):
    """MCP 서버 설정 생성"""
    current_dir = Path(__file__).parent.absolute()
    
    return {
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

def save_config(config_path, config):
    """설정 파일 저장"""
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print(f"✅ Claude Code CLI 설정 저장: {config_path}")
        return True
    except Exception as e:
        print(f"❌ 설정 저장 실패: {e}")
        return False

def test_mcp_server():
    """MCP 서버 동작 테스트"""
    try:
        import src.openrouter_mcp.server
        print("✅ OpenRouter MCP Server 모듈 import 성공")
        return True
    except Exception as e:
        print(f"❌ MCP 서버 테스트 실패: {e}")
        return False

def main():
    """메인 설치 함수"""
    print("🚀 OpenRouter MCP Server - Claude Code CLI 설치")
    print("=" * 60)
    
    # 1. MCP 서버 모듈 테스트
    print("\n1️⃣ MCP 서버 모듈 테스트...")
    if not test_mcp_server():
        print("❌ MCP 서버 모듈을 로드할 수 없습니다.")
        print("현재 디렉토리에서 실행했는지 확인하세요.")
        return False
    
    # 2. Claude 설정 디렉토리 확인/생성
    print("\n2️⃣ Claude Code CLI 설정 디렉토리 확인...")
    config_path = ensure_claude_dir()
    
    # 3. 기존 설정 로드
    print("\n3️⃣ 기존 Claude Code CLI 설정 확인...")
    config = load_existing_config(config_path)
    
    # 4. API 키 입력
    print("\n4️⃣ OpenRouter API 키 설정...")
    api_key = get_api_key()
    
    # 5. MCP 서버 설정 추가
    print("\n5️⃣ OpenRouter MCP Server 설정 추가...")
    mcp_config = create_mcp_config(api_key)
    config["mcpServers"]["openrouter-mcp"] = mcp_config
    
    # 6. 설정 파일 저장
    print("\n6️⃣ Claude Code CLI 설정 파일 저장...")
    if not save_config(config_path, config):
        return False
    
    # 7. 설치 완료 안내
    print("\n" + "=" * 60)
    print("🎉 OpenRouter MCP Server 설치 완료!")
    print("=" * 60)
    print()
    print("다음 단계:")
    print("1. Claude Code CLI를 재시작하세요")
    print("2. 다음 명령으로 MCP 도구들을 사용하세요:")
    print()
    print("📊 벤치마킹 도구:")
    print("  - 'gpt-4와 claude-3-opus의 성능을 비교해줘'")
    print("  - '코딩 카테고리의 최고 모델들을 비교해줘'")
    print("  - '최근 벤치마크 결과를 보여줘'")
    print()
    print("🤖 모델 사용:")
    print("  - 'list available models'")
    print("  - 'use gpt-4o to explain quantum computing'")
    print("  - 'show usage statistics'")
    print()
    print("📚 도움말:")
    print(f"  - 설정 파일: {config_path}")
    print(f"  - 문서: {Path(__file__).parent}/docs/INDEX.md")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        if not success:
            print("\n❌ 설치가 완료되지 않았습니다.")
            exit(1)
    except KeyboardInterrupt:
        print("\n⚠️ 설치가 중단되었습니다.")
        exit(1)
    except Exception as e:
        print(f"\n❌ 설치 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        exit(1)