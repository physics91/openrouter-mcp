#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

CONVENTIONAL_PATTERN = re.compile(
    r"^(feat|fix|docs|style|refactor|test|chore|ci|build|perf|revert)"
    r"(\([a-z0-9._/-]+\))?!?: [a-z].{0,71}$"
)
KOREAN_PATTERN = re.compile(r"[\u3131-\u318E\uAC00-\uD7A3]")
AUTO_GENERATED_PREFIXES = ("Merge ", 'Revert "')


def validate_commit_message(message: str) -> tuple[bool, str]:
    if not message:
        return False, "Commit message is empty"

    if message.startswith(AUTO_GENERATED_PREFIXES):
        return True, ""

    if KOREAN_PATTERN.search(message):
        return False, "Commit message subject must be English-only."

    if not CONVENTIONAL_PATTERN.fullmatch(message):
        return (
            False,
            "Invalid commit message format. Expected: "
            "type(scope): subject (Conventional Commits).",
        )

    if message.endswith("."):
        return False, "Commit message subject must not end with a period."

    return True, ""


def _read_first_line(commit_msg_file: Path) -> str:
    for raw_line in commit_msg_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line:
            return line
    return ""


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: validate_commit_msg.py <commit-msg-file>", file=sys.stderr)
        return 1

    commit_msg_file = Path(sys.argv[1])
    if not commit_msg_file.exists():
        print(f"Commit message file not found: {commit_msg_file}", file=sys.stderr)
        return 1

    message = _read_first_line(commit_msg_file)
    is_valid, error_message = validate_commit_message(message)
    if not is_valid:
        print(error_message, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
