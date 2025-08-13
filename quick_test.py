#!/usr/bin/env python3
"""
OpenRouter API 빠른 테스트
"""

import asyncio
import os
from src.openrouter_mcp.client.openrouter import OpenRouterClient

async def quick_test():
    """OpenRouter API 빠른 연결 테스트"""
    print("[TEST] OpenRouter API 연결 테스트")
    
    # API 키 설정
    api_key = "placeholder"
    
    try:
        # OpenRouter 클라이언트 생성
        client = OpenRouterClient(api_key=api_key)
        
        print("[INFO] OpenRouter 클라이언트 생성 성공")
        
        # 모델 목록 가져오기 테스트
        print("[INFO] 모델 목록 조회 중...")
        models = await client.list_models()
        
        if models:
            print(f"[SUCCESS] {len(models)}개 모델 발견!")
            print("[INFO] 인기 모델 예시:")
            
            # 몇 개 인기 모델 표시
            popular_models = []
            for model in models[:10]:  # 처음 10개만 확인
                if any(keyword in model.get('id', '').lower() for keyword in ['gpt-4', 'claude', 'gemini']):
                    popular_models.append(model.get('id', 'Unknown'))
            
            for i, model in enumerate(popular_models[:5], 1):
                print(f"  {i}. {model}")
            
            print(f"\n[SUCCESS] OpenRouter API 연결 성공! 총 {len(models)}개 모델 사용 가능")
            return True
        else:
            print("[ERROR] 모델 목록을 가져올 수 없습니다")
            return False
            
    except Exception as e:
        print(f"[ERROR] API 테스트 실패: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(quick_test())
    if success:
        print("\n[FINAL] 모든 설정이 완료되었습니다!")
        print("Claude Desktop과 Claude Code CLI에서 OpenRouter MCP 도구를 사용할 수 있습니다.")
    else:
        print("\n[WARNING] API 연결에 문제가 있을 수 있습니다.")
        print("인터넷 연결과 API 키를 확인해보세요.")