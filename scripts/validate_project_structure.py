#!/usr/bin/env python3
"""
프로젝트 구조 검증 스크립트

이 스크립트는 OpenRouter MCP 프로젝트의 파일/디렉토리 구조가 
가이드라인을 준수하는지 자동으로 검증합니다.
"""

import os
import sys
import glob
import re
from pathlib import Path
from typing import List, Tuple

# Windows 인코딩 문제 해결
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

class ProjectStructureValidator:
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root).resolve()
        self.violations = []
        self.warnings = []
        
    def check_root_directory_cleanliness(self) -> None:
        """루트 디렉토리 정리 상태 검증"""
        print("🔍 루트 디렉토리 정리 상태 검사...")
        
        # 루트에 있으면 안 되는 파일 패턴들
        forbidden_patterns = [
            "test_*.py",
            "*_test.py", 
            "*_results_*.json",
            "*_report_*.json",
            "*_report_*.md",
            "debug_*.py",
            "quick_*.py",
            "benchmark_*.json"
        ]
        
        for pattern in forbidden_patterns:
            matches = list(self.project_root.glob(pattern))
            if matches:
                for match in matches:
                    self.violations.append(f"❌ 루트에 금지된 파일: {match.name}")
                    
    def check_api_key_security(self) -> None:
        """API 키 하드코딩 보안 검사"""
        print("🔒 API 키 보안 검사...")
        
        # 위험한 API 키 패턴
        api_key_patterns = [
            r'sk-or-v1-[a-f0-9]{64}',  # OpenRouter API 키
            r'sk-[a-zA-Z0-9]{48,}',    # OpenAI 스타일 키
            r'OPENROUTER_API_KEY\s*=\s*["\']sk-',  # 환경변수 하드코딩
        ]
        
        python_files = list(self.project_root.rglob("*.py"))
        for file_path in python_files:
            if ".git" in str(file_path):
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                for pattern in api_key_patterns:
                    if re.search(pattern, content):
                        self.violations.append(f"🚨 API 키 하드코딩 발견: {file_path.relative_to(self.project_root)}")
                        
            except (UnicodeDecodeError, PermissionError):
                continue
                
    def check_test_file_organization(self) -> None:
        """테스트 파일 구조 검증"""
        print("🧪 테스트 파일 구조 검사...")
        
        tests_dir = self.project_root / "tests"
        if not tests_dir.exists():
            self.violations.append("❌ tests/ 디렉토리가 존재하지 않습니다")
            return
            
        # tests/ 디렉토리 내 구조 검증
        test_files = list(tests_dir.rglob("*.py"))
        if len(test_files) < 3:
            self.warnings.append("⚠️ tests/ 디렉토리에 테스트 파일이 부족할 수 있습니다")
            
    def check_documentation_structure(self) -> None:
        """문서 구조 검증"""
        print("📚 문서 구조 검사...")
        
        docs_dir = self.project_root / "docs"
        if not docs_dir.exists():
            self.violations.append("❌ docs/ 디렉토리가 존재하지 않습니다")
            return
            
        # 필수 문서들
        required_docs = ["README.md", "INSTALLATION.md", "API.md"]
        for doc in required_docs:
            if not (docs_dir / doc).exists():
                self.warnings.append(f"⚠️ 권장 문서 누락: docs/{doc}")
                
        # 보고서 디렉토리 확인
        reports_dir = docs_dir / "reports"
        if reports_dir.exists():
            report_files = list(reports_dir.glob("*.md"))
            print(f"✅ 보고서 디렉토리: {len(report_files)}개 보고서 파일")
        else:
            self.warnings.append("⚠️ docs/reports/ 디렉토리가 없습니다")
            
    def check_gitignore_patterns(self) -> None:
        """gitignore 패턴 검증"""
        print("🙈 .gitignore 패턴 검사...")
        
        gitignore_path = self.project_root / ".gitignore"
        if not gitignore_path.exists():
            self.violations.append("❌ .gitignore 파일이 없습니다")
            return
            
        with open(gitignore_path, 'r') as f:
            gitignore_content = f.read()
            
        # 필수 패턴들
        required_patterns = [
            "*_cache.json",
            "*_results_*.json", 
            "benchmark_*.json",
            ".env"
        ]
        
        for pattern in required_patterns:
            if pattern not in gitignore_content:
                self.warnings.append(f"⚠️ .gitignore에 권장 패턴 누락: {pattern}")
                
    def count_file_statistics(self) -> dict:
        """파일 통계 수집"""
        stats = {
            'root_files': len(list(self.project_root.glob("*"))),
            'root_py_files': len(list(self.project_root.glob("*.py"))),
            'root_md_files': len(list(self.project_root.glob("*.md"))),
            'test_files': len(list((self.project_root / "tests").rglob("*.py"))) if (self.project_root / "tests").exists() else 0,
            'doc_files': len(list((self.project_root / "docs").rglob("*.md"))) if (self.project_root / "docs").exists() else 0,
        }
        return stats
        
    def run_validation(self) -> bool:
        """전체 검증 실행"""
        print(f"🚀 OpenRouter MCP 프로젝트 구조 검증 시작")
        print(f"📁 프로젝트 경로: {self.project_root}")
        print("=" * 60)
        
        # 모든 검증 실행
        self.check_root_directory_cleanliness()
        self.check_api_key_security()
        self.check_test_file_organization()
        self.check_documentation_structure()
        self.check_gitignore_patterns()
        
        # 통계 출력
        stats = self.count_file_statistics()
        print(f"\n📊 프로젝트 통계:")
        print(f"   • 루트 파일 수: {stats['root_files']}")
        print(f"   • 루트 Python 파일: {stats['root_py_files']}")
        print(f"   • 루트 문서 파일: {stats['root_md_files']}")
        print(f"   • 테스트 파일: {stats['test_files']}")
        print(f"   • 문서 파일: {stats['doc_files']}")
        
        # 결과 요약
        print(f"\n📋 검증 결과:")
        
        if self.violations:
            print(f"❌ 위반사항 ({len(self.violations)}개):")
            for violation in self.violations:
                print(f"   {violation}")
        else:
            print("✅ 구조 위반사항 없음")
            
        if self.warnings:
            print(f"\n⚠️ 개선 권장사항 ({len(self.warnings)}개):")
            for warning in self.warnings:
                print(f"   {warning}")
                
        # 최종 판정
        is_valid = len(self.violations) == 0
        
        print("\n" + "=" * 60)
        if is_valid:
            print("🎉 프로젝트 구조 검증 통과!")
        else:
            print("💥 프로젝트 구조 개선이 필요합니다.")
            
        return is_valid

def main():
    """메인 실행 함수"""
    validator = ProjectStructureValidator()
    success = validator.run_validation()
    
    # 종료 코드 설정 (CI/CD에서 활용 가능)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()