#!/usr/bin/env python3
"""
Benchmark handler cleanup - MCP 도구 제거
"""

# benchmark.py 파일에서 MCP 관련 코드를 제거하고 순수한 벤치마킹 로직만 유지하는 스크립트

import os
import re

def cleanup_benchmark_file():
    """benchmark.py에서 MCP 관련 코드 제거"""
    benchmark_file = "G:/ai-dev/Openrouter-mcp/src/openrouter_mcp/handlers/benchmark.py"
    
    # 원본 파일 읽기
    with open(benchmark_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # MCP 관련 import 제거
    content = re.sub(r'from fastmcp import Context\n', '', content)
    content = re.sub(r'from \.\.server import mcp\n', '', content)
    
    # MCP 도구들 제거 (950번째 줄 이후 모든 내용)
    lines = content.split('\n')
    clean_lines = []
    
    for i, line in enumerate(lines):
        if i >= 949:  # 950번째 줄부터 제거
            if '# MCP Tool functions' in line or '@mcp.tool()' in line:
                break
        clean_lines.append(line)
    
    # 파일 끝에 주석 추가
    clean_lines.append('')
    clean_lines.append('# MCP 도구들은 mcp_benchmark.py에서 관리됩니다.')
    
    # 파일 저장
    with open(benchmark_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(clean_lines))
    
    print("benchmark.py 파일에서 MCP 관련 코드가 제거되었습니다.")

if __name__ == "__main__":
    cleanup_benchmark_file()