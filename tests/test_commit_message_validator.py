from __future__ import annotations

import subprocess
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "validate_commit_msg.py"


def _run_validator(message: str) -> subprocess.CompletedProcess[str]:
    tmp_path = Path(__file__).resolve().parent / ".tmp_commit_msg.txt"
    tmp_path.write_text(f"{message}\n", encoding="utf-8")
    try:
        return subprocess.run(
            [sys.executable, str(SCRIPT_PATH), str(tmp_path)],
            check=False,
            capture_output=True,
            text=True,
        )
    finally:
        tmp_path.unlink(missing_ok=True)


def test_accepts_valid_conventional_commit_message() -> None:
    result = _run_validator("feat(cli): add commit message validator")
    assert result.returncode == 0


def test_rejects_message_with_disallowed_type() -> None:
    result = _run_validator("unknown: test")
    assert result.returncode == 1
    assert "Invalid commit message format" in result.stderr


def test_rejects_message_ending_with_period() -> None:
    result = _run_validator("fix: handle edge case.")
    assert result.returncode == 1
    assert "must not end with a period" in result.stderr


def test_rejects_message_with_korean_characters() -> None:
    result = _run_validator("feat: 커밋 메시지 검증 추가")
    assert result.returncode == 1
    assert "must be English-only" in result.stderr


def test_allows_merge_and_revert_messages() -> None:
    merge_result = _run_validator("Merge branch 'feature/x'")
    revert_result = _run_validator('Revert "feat: add validator"')
    assert merge_result.returncode == 0
    assert revert_result.returncode == 0
