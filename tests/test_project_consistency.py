#!/usr/bin/env python3
"""Project consistency checks for docs and package metadata."""

import json
import re
import subprocess
from pathlib import Path

import pytest

from tests.test_tool_expectations import ALL_REGISTERED_TOOL_NAMES

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parent.parent
USER_FACING_EXAMPLE_FILES = (
    # Security-detection fixtures intentionally keep fake key-shaped values.
    "src/openrouter_mcp/cli/mcp_manager.py",
    "tests/test_mcp_cli_integration.py",
)
SECURITY_METADATA_DOCS = (
    "SECURITY.md",
    "docs/SECURITY.md",
    "docs/SECURITY_BEST_PRACTICES.md",
)


def _read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _load_package_json() -> dict:
    return json.loads(_read_text("package.json"))


def _tracked_markdown_docs() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "*.md"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    return [ROOT / relative_path for relative_path in result.stdout.splitlines()]


def _normalize_shell_continuations(command_text: str) -> str:
    command_text = re.sub(r"\\\s*\n\s*", " ", command_text)
    return re.sub(r"\|\s*\n\s*", "| ", command_text)


def _contains_elevated_pipe_to_shell(command_text: str) -> bool:
    elevated_shell_pipe = re.compile(
        r"\b(?:curl|wget)\b[^\n|]*\|\s*"
        r"sudo\b(?:\s+(?:-[A-Za-z]+|--[A-Za-z][\w-]*(?:=\S+)?))*\s+"
        r"(?:bash|sh)\b",
        re.IGNORECASE,
    )

    return bool(elevated_shell_pipe.search(_normalize_shell_continuations(command_text)))


def _iter_markdown_fenced_blocks(path: Path) -> list[tuple[str, list[tuple[int, str]]]]:
    blocks = []
    in_block = False
    language = ""
    block_lines: list[tuple[int, str]] = []

    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("```"):
            if in_block:
                blocks.append((language, block_lines))
                in_block = False
                language = ""
                block_lines = []
            else:
                in_block = True
                parts = stripped[3:].strip().split(maxsplit=1)
                language = parts[0].lower() if parts else ""
            continue

        if in_block:
            block_lines.append((line_number, line))

    return blocks


def _contains_secret_env_file_reference(line: str) -> bool:
    env_file_reference = re.compile(r"(?<![\w.-])\.env(?:\.[A-Za-z0-9_.-]+)?(?![\w.-])")
    return any(match.group(0) != ".env.example" for match in env_file_reference.finditer(line))


def _dockerfile_line_bakes_openrouter_secret(line: str) -> bool:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return False

    if re.match(r"^(?:COPY|ADD)\b", stripped, re.IGNORECASE):
        return _contains_secret_env_file_reference(stripped)

    return bool(re.match(r"^(?:ENV|ARG)\s+OPENROUTER_API_KEY(?:\s|=|$)", stripped, re.IGNORECASE))


def _env_file_setup_findings(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    findings = []
    try:
        display_path = path.relative_to(ROOT)
    except ValueError:
        display_path = path

    for language, block_lines in _iter_markdown_fenced_blocks(path):
        if language not in {"env", "dotenv", "bash", "sh", "shell"} or not block_lines:
            continue

        block_text = "\n".join(line for _, line in block_lines)
        if "OPENROUTER_API_KEY=REPLACE_WITH_OPENROUTER_API_KEY" not in block_text:
            continue

        start_line = block_lines[0][0]
        end_line = block_lines[-1][0]
        context_start = max(0, start_line - 9)
        context_end = min(len(lines), end_line + 8)
        context = "\n".join(lines[context_start:context_end])

        if ".env" not in context:
            continue

        missing = []
        if "chmod 600 .env" not in context:
            missing.append("chmod 600 .env")
        if not re.search(r"\bplain\s?text\b|평문", context, re.IGNORECASE):
            missing.append("plaintext warning")
        if not re.search(
            r"\b(?:do not|don't|never)\b.{0,100}\b(?:commit|share|paste)\b|커밋|공유",
            context,
            re.IGNORECASE,
        ):
            missing.append("non-commit/share warning")

        if missing:
            findings.append(f"{display_path}:{start_line}: missing {', '.join(missing)}")

    return findings


def test_package_metadata_has_no_placeholders() -> None:
    package = _load_package_json()

    values_to_check = [
        package["author"],
        package["homepage"],
        package["repository"]["url"],
        package["bugs"]["url"],
    ]

    placeholder_markers = ("Your Name", "your.email@example.com", "yourusername")
    offenders = [
        value for value in values_to_check if any(marker in value for marker in placeholder_markers)
    ]

    assert not offenders, f"Placeholder package metadata remains: {offenders}"


def test_api_docs_cover_all_registered_tools() -> None:
    api_doc = _read_text("docs/API.md")
    missing = [name for name in ALL_REGISTERED_TOOL_NAMES if name not in api_doc]

    assert not missing, f"API docs are missing registered tools: {missing}"


def test_api_docs_use_raw_mcp_name_field() -> None:
    api_doc = _read_text("docs/API.md")

    assert '"method": "tools/call"' in api_doc
    assert '"params": {' in api_doc
    assert '"name": "chat_with_model"' in api_doc
    assert '"name": "chat_with_vision"' in api_doc
    assert '"name": "compare_model_performance"' in api_doc
    assert '"tool":' not in api_doc


def test_docs_describe_runtime_thrift_response_metadata() -> None:
    api_doc = _read_text("docs/API.md")
    faq_doc = _read_text("docs/FAQ.md")

    assert "thrift_metrics" in api_doc
    assert "thrift_summary" in api_doc
    assert "routing_metrics.thrift_feedback" in api_doc
    assert "constraints_applied" in api_doc
    assert "constraints_unmet" in api_doc
    assert "filtered_candidates" in api_doc
    assert "performance_weights" in api_doc
    assert "preference_matches" in api_doc
    assert "preferred_provider" in api_doc
    assert "preferred_model_family" in api_doc
    assert "max_cost" in api_doc
    assert "min_context_length" in api_doc
    assert "adaptive_model_selection" in api_doc
    assert "lookback_days" in api_doc
    assert "bucket_summary" in api_doc
    assert "prompt_savings_breakdown" in api_doc
    assert "recent_reuse_prompt_tokens" in api_doc
    assert "request_savings_breakdown" in api_doc
    assert "cache_efficiency" in api_doc
    assert "cache_hit_requests" in api_doc
    assert "cache_write_requests" in api_doc
    assert "cache_hit_request_rate_pct" in api_doc
    assert "cache_write_request_rate_pct" in api_doc
    assert "cache_efficiency_by_provider" in api_doc
    assert "cache_efficiency_by_model" in api_doc
    assert "cache_hotspots" in api_doc
    assert "cache_deadspots" in api_doc
    assert '"reason"' in api_doc
    assert "persisted daily rollups" in api_doc
    assert "local calendar day" in api_doc
    assert "chat_with_model" in api_doc
    assert "chat_with_vision" in api_doc
    assert "free_chat" in api_doc
    assert "get_usage_stats" in api_doc
    assert "thrift_summary" in faq_doc


def test_troubleshooting_covers_runtime_thrift_interpretation() -> None:
    troubleshooting_doc = _read_text("docs/TROUBLESHOOTING.md")

    assert "thrift_summary" in troubleshooting_doc
    assert "routing_metrics.thrift_feedback" in troubleshooting_doc
    assert "constraints_applied" in troubleshooting_doc
    assert "constraints_unmet" in troubleshooting_doc
    assert "filtered_candidates" in troubleshooting_doc
    assert "performance_weights" in troubleshooting_doc
    assert "preference_matches" in troubleshooting_doc
    assert "preferred_provider" in troubleshooting_doc
    assert "preferred_model_family" in troubleshooting_doc
    assert "Adaptive Router Keeps Picking Cache Deadspots" in troubleshooting_doc
    assert "source" in troubleshooting_doc
    assert "penalty" in troubleshooting_doc
    assert "lookback_days" in troubleshooting_doc
    assert "bucket_summary" in troubleshooting_doc
    assert "saved_cost_usd" in troubleshooting_doc
    assert "effective_cost_reduction_pct" in troubleshooting_doc
    assert "prompt_savings_breakdown" in troubleshooting_doc
    assert "recent_reuse_prompt_tokens" in troubleshooting_doc
    assert "request_savings_breakdown" in troubleshooting_doc
    assert "cache_efficiency" in troubleshooting_doc
    assert "cache_hit_request_rate_pct" in troubleshooting_doc
    assert "cache_write_request_rate_pct" in troubleshooting_doc
    assert "cache_efficiency_by_provider" in troubleshooting_doc
    assert "cache_hotspots" in troubleshooting_doc
    assert "cache_deadspots" in troubleshooting_doc
    assert "reason" in troubleshooting_doc
    assert "local calendar day" in troubleshooting_doc
    assert "get_usage_stats" in troubleshooting_doc


def test_korean_usage_guide_covers_runtime_thrift_summary() -> None:
    usage_guide = _read_text("docs/USAGE_GUIDE_KR.md")

    assert "get_usage_stats" in usage_guide
    assert "thrift_summary" in usage_guide
    assert "saved_cost_usd" in usage_guide
    assert "prompt_savings_breakdown" in usage_guide
    assert "recent_reuse_prompt_tokens" in usage_guide
    assert "request_savings_breakdown" in usage_guide
    assert "cache_efficiency" in usage_guide
    assert "cache_hit_request_rate_pct" in usage_guide
    assert "cache_write_request_rate_pct" in usage_guide
    assert "cache_efficiency_by_provider" in usage_guide
    assert "cache_hotspots" in usage_guide
    assert "cache_deadspots" in usage_guide
    assert "reason" in usage_guide
    assert "로컬 날짜" in usage_guide


def test_docs_show_usage_stats_request_and_response_examples() -> None:
    api_doc = _read_text("docs/API.md")
    usage_guide = _read_text("docs/USAGE_GUIDE_KR.md")

    assert '"name": "get_usage_stats"' in api_doc
    assert "Example MCP Response" in api_doc
    assert "Claude 출력 예시" in usage_guide
    assert "이번 달 OpenRouter 사용량" in usage_guide


@pytest.mark.parametrize(
    ("relative_path", "banned_snippet"),
    [
        (
            "docs/MULTIMODAL_GUIDE.md",
            '{"data": "/path/to/image.jpg", "type": "path"}',
        ),
        (
            "docs/MULTIMODAL_GUIDE.md",
            "Try downloading and using file path instead",
        ),
        (
            "docs/USAGE_GUIDE_KR.md",
            '"OPENROUTER_API_KEY": "sk-or-v1-your-key-here"',
        ),
        (
            "docs/USAGE_GUIDE_KR.md",
            'img = ImageInput(data="/path/to/image.jpg", type="path")',
        ),
        (
            "docs/INSTALLATION.md",
            "OPENROUTER_API_KEY=sk-or-v1-your-key-here",
        ),
        (
            "docs/FAQ.md",
            '{"data": "/path/to/image.jpg", "type": "path"}',
        ),
        (
            "docs/CLAUDE_CODE_SETUP_KR.md",
            '"OPENROUTER_API_KEY":',
        ),
        (
            "docs/CLAUDE_CODE_GUIDE.md",
            '"OPENROUTER_API_KEY":',
        ),
    ],
)
def test_docs_do_not_contain_removed_or_insecure_examples(
    relative_path: str, banned_snippet: str
) -> None:
    content = _read_text(relative_path)

    assert banned_snippet not in content, f"{relative_path} still contains: {banned_snippet}"


def test_changelog_has_no_placeholder_repo_links() -> None:
    changelog = _read_text("CHANGELOG.md")

    assert "yourusername/openrouter-mcp" not in changelog


def test_tracked_markdown_docs_avoid_openrouter_key_shaped_placeholders() -> None:
    offenders = []

    for path in _tracked_markdown_docs():
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "sk-or-v1-" in line:
                relative_path = path.relative_to(ROOT)
                offenders.append(f"{relative_path}:{line_number} contains sk-or-v1-")

    assert not offenders, "OpenRouter-key-shaped placeholders remain:\n" + "\n".join(offenders)


def test_tracked_markdown_docs_use_safe_openrouter_key_examples() -> None:
    offenders = []
    assignment_pattern = re.compile(r"\b(?:export|set)?\s*OPENROUTER_API_KEY=")

    for path in _tracked_markdown_docs():
        relative_path = path.relative_to(ROOT)
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if "OPENROUTER_API_KEY=" not in stripped or "grep" in stripped:
                continue
            if stripped == "OPENROUTER_API_KEY=REPLACE_WITH_OPENROUTER_API_KEY":
                continue
            if stripped.startswith("export OPENROUTER_API_KEY=$("):
                continue
            if assignment_pattern.search(stripped):
                offenders.append(f"{relative_path}:{line_number}: {stripped}")

    assert not offenders, "Unsafe OpenRouter API key examples remain:\n" + "\n".join(offenders)


def test_tracked_markdown_docs_avoid_inline_api_key_placeholder_literals() -> None:
    unsafe_patterns = (
        (
            re.compile(r"\bplaceholder(?:-here)?\b", re.IGNORECASE),
            "use an explicit replacement token or runtime environment value",
        ),
        (
            re.compile(r"os\.environ\[\s*['\"]OPENROUTER_API_KEY['\"]\s*\]\s*="),
            "read OPENROUTER_API_KEY from the caller environment instead of assigning it",
        ),
    )
    offenders = []

    for path in _tracked_markdown_docs():
        relative_path = path.relative_to(ROOT)
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for pattern, guidance in unsafe_patterns:
                if pattern.search(line):
                    offenders.append(f"{relative_path}:{line_number}: {guidance}")
                    break

    assert not offenders, "Inline API key placeholder guidance remains:\n" + "\n".join(offenders)


def test_user_facing_source_examples_avoid_key_shaped_inline_assignments() -> None:
    patterns = (
        re.compile(r"OPENROUTER_API_KEY\s*=\s*[\"']?sk-"),
        re.compile(r"\{EnvVars\.API_KEY\}\s*=\s*[\"']?sk-"),
    )
    offenders = []

    for relative_path in USER_FACING_EXAMPLE_FILES:
        for line_number, line in enumerate(_read_text(relative_path).splitlines(), 1):
            if any(pattern.search(line) for pattern in patterns):
                offenders.append(f"{relative_path}:{line_number}: {line.strip()}")

    assert not offenders, "Unsafe source API key examples remain:\n" + "\n".join(offenders)


def test_tracked_markdown_docs_use_non_disclosing_security_diagnostics() -> None:
    unsafe_env_grep = re.compile(r"env\s*\|\s*grep\s+OPENROUTER")
    unsafe_secret_grep = re.compile(r"grep\s+-[^\n]*r[^\n]*[\"']sk-or-[\"']")
    offenders = []

    for path in _tracked_markdown_docs():
        relative_path = path.relative_to(ROOT)
        lines = path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            line_number = index + 1
            if unsafe_env_grep.search(line):
                offenders.append(f"{relative_path}:{line_number}: prints OPENROUTER values")
            if unsafe_secret_grep.search(line):
                offenders.append(f"{relative_path}:{line_number}: prints matching secret lines")
            if "audit.log" in line.lower() and "share" in line.lower():
                nearby = "\n".join(lines[max(0, index - 2) : index + 3]).lower()
                if "review" not in nearby and "redact" not in nearby:
                    offenders.append(
                        f"{relative_path}:{line_number}: shares audit.log without review/redaction"
                    )

    assert not offenders, "Unsafe security diagnostics remain:\n" + "\n".join(offenders)


def test_tracked_markdown_docs_avoid_unverified_security_email() -> None:
    offenders = []

    for path in _tracked_markdown_docs():
        relative_path = path.relative_to(ROOT)
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "security@openrouter-mcp.com" in line:
                offenders.append(f"{relative_path}:{line_number}: {line.strip()}")

    assert not offenders, "Unverified security email remains:\n" + "\n".join(offenders)


def test_security_doc_review_dates_are_ordered() -> None:
    date_pattern = re.compile(
        r"\*\*(Last Updated|Next Review)(?::)?\*\*:?\s*([0-9]{4}-[0-9]{2}-[0-9]{2})"
    )
    offenders = []

    for relative_path in SECURITY_METADATA_DOCS:
        metadata = dict(date_pattern.findall(_read_text(relative_path)))
        last_updated = metadata.get("Last Updated")
        next_review = metadata.get("Next Review")
        if last_updated and next_review and next_review < last_updated:
            offenders.append(
                f"{relative_path}: Next Review {next_review} is before Last Updated {last_updated}"
            )

    assert not offenders, "Security doc review dates are inconsistent:\n" + "\n".join(offenders)


def test_tracked_markdown_docs_avoid_security_contact_placeholders() -> None:
    placeholder = re.compile(r"Security Contact.*\[To be configured\]", re.IGNORECASE)
    offenders = []

    for path in _tracked_markdown_docs():
        relative_path = path.relative_to(ROOT)
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if placeholder.search(line):
                offenders.append(f"{relative_path}:{line_number}: {line.strip()}")

    assert not offenders, "Security contact placeholder remains:\n" + "\n".join(offenders)


def test_tracked_markdown_docs_avoid_tls_verification_bypass() -> None:
    bypass_patterns = (
        re.compile(r"NODE_TLS_REJECT_UNAUTHORIZED\s*=\s*0"),
        re.compile(r"npm\s+config\s+set\s+strict-ssl\s+false"),
        re.compile(r"strict-ssl\s*=\s*false"),
    )
    offenders = []

    for path in _tracked_markdown_docs():
        relative_path = path.relative_to(ROOT)
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if any(pattern.search(line) for pattern in bypass_patterns):
                offenders.append(f"{relative_path}:{line_number}: {line.strip()}")

    assert not offenders, "TLS verification bypass guidance remains:\n" + "\n".join(offenders)


def test_tracked_markdown_docs_avoid_sudo_npm_global_install_guidance() -> None:
    elevated_global_install = re.compile(
        r"\bsudo\s+npm\b(?=.*\b(?:install|i)\b)(?=.*(?:^|\s)(?:-g|--global)(?:\s|=|$))"
    )
    offenders = []

    for path in _tracked_markdown_docs():
        relative_path = path.relative_to(ROOT)
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if elevated_global_install.search(line):
                offenders.append(
                    f"{relative_path}:{line_number}: use npx or a user-owned Node/npm setup"
                )

    assert not offenders, "Elevated npm global install guidance remains:\n" + "\n".join(offenders)


@pytest.mark.parametrize(
    "command_text",
    [
        "curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -",
        "wget -qO- https://example.invalid/install.sh | sudo --preserve-env bash -s",
        "curl -fsSL https://example.invalid/install.sh \\\n  | sudo sh -",
        "wget -qO- https://example.invalid/install.sh |\n  sudo --preserve-env=PATH bash -s",
    ],
)
def test_detects_elevated_pipe_to_shell_examples(command_text: str) -> None:
    assert _contains_elevated_pipe_to_shell(command_text)


@pytest.mark.parametrize(
    "command_text",
    [
        (
            "curl -fsSL https://deb.nodesource.com/setup_18.x -o nodesource_setup.sh\n"
            "sudo -E bash nodesource_setup.sh"
        ),
        "sudo apt install nodejs -y",
        '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"',
        "curl -fsSL https://example.invalid/install.sh | bash -",
    ],
)
def test_allows_non_elevated_or_downloaded_install_examples(command_text: str) -> None:
    assert not _contains_elevated_pipe_to_shell(command_text)


def test_tracked_markdown_docs_avoid_elevated_pipe_to_shell_guidance() -> None:
    offenders = []

    for path in _tracked_markdown_docs():
        relative_path = path.relative_to(ROOT)
        lines = path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            if not re.search(r"\b(?:curl|wget)\b", line):
                continue
            window = "\n".join(lines[index : index + 3])
            if _contains_elevated_pipe_to_shell(window):
                offenders.append(
                    f"{relative_path}:{index + 1}: download first or use package/version manager"
                )

    assert not offenders, "Elevated pipe-to-shell guidance remains:\n" + "\n".join(offenders)


def test_tracked_markdown_docs_avoid_eol_node_install_guidance() -> None:
    eol_install_patterns = (
        (
            re.compile(r"setup_(?:16|18|20)\.x"),
            "use setup_lts.x or another supported Node.js LTS installer",
        ),
        (
            re.compile(r"FROM\s+node:(?:16|18|20)(?:[-\s]|$)", re.IGNORECASE),
            "use a supported Node.js LTS base image",
        ),
    )
    offenders = []

    for path in _tracked_markdown_docs():
        relative_path = path.relative_to(ROOT)
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for pattern, guidance in eol_install_patterns:
                if pattern.search(line):
                    offenders.append(f"{relative_path}:{line_number}: {guidance}")

    assert not offenders, "EOL Node.js install guidance remains:\n" + "\n".join(offenders)


@pytest.mark.parametrize(
    "line",
    [
        "COPY .env .env",
        "copy --chown=node .env.local /app/.env",
        'ADD [".env.production", "/app/.env"]',
        "ENV OPENROUTER_API_KEY=REPLACE_WITH_OPENROUTER_API_KEY",
        "ENV OPENROUTER_API_KEY REPLACE_WITH_OPENROUTER_API_KEY",
        "ARG OPENROUTER_API_KEY",
    ],
)
def test_detects_dockerfile_secret_baking_examples(line: str) -> None:
    assert _dockerfile_line_bakes_openrouter_secret(line)


@pytest.mark.parametrize(
    "line",
    [
        "COPY .env.example .env.example",
        "RUN --mount=type=secret,id=OPENROUTER_API_KEY true",
        "RUN npm install -g @physics91/openrouter-mcp",
        "# COPY .env .env",
    ],
)
def test_allows_safe_dockerfile_secret_handling_examples(line: str) -> None:
    assert not _dockerfile_line_bakes_openrouter_secret(line)


def test_tracked_markdown_dockerfile_blocks_avoid_secret_baking() -> None:
    offenders = []

    for path in _tracked_markdown_docs():
        relative_path = path.relative_to(ROOT)
        for language, block_lines in _iter_markdown_fenced_blocks(path):
            if language not in {"dockerfile", "docker"}:
                continue
            for line_number, line in block_lines:
                if _dockerfile_line_bakes_openrouter_secret(line):
                    offenders.append(
                        f"{relative_path}:{line_number}: use docker run --env-file instead"
                    )

    assert not offenders, "Dockerfile examples bake OpenRouter secrets:\n" + "\n".join(offenders)


def test_tracked_markdown_env_file_examples_include_permissions_and_warnings() -> None:
    offenders = []

    for path in _tracked_markdown_docs():
        offenders.extend(_env_file_setup_findings(path))

    assert not offenders, "Unsafe .env file examples remain:\n" + "\n".join(offenders)


def test_detects_env_file_examples_without_permissions_or_warnings(tmp_path: Path) -> None:
    doc_path = tmp_path / "doc.md"
    doc_path.write_text(
        """Create a `.env` file:

```env
OPENROUTER_API_KEY=REPLACE_WITH_OPENROUTER_API_KEY
```
""",
        encoding="utf-8",
    )

    findings = _env_file_setup_findings(doc_path)

    assert findings
    assert "chmod 600 .env" in findings[0]
    assert "plaintext warning" in findings[0]
    assert "non-commit/share warning" in findings[0]


def test_allows_env_file_examples_with_permissions_and_warnings(tmp_path: Path) -> None:
    doc_path = tmp_path / "doc.md"
    doc_path.write_text(
        """Create a `.env` file:

```env
OPENROUTER_API_KEY=REPLACE_WITH_OPENROUTER_API_KEY
```

`.env` is plaintext. Do not commit, paste, or share it.
```bash
chmod 600 .env
```
""",
        encoding="utf-8",
    )

    assert not _env_file_setup_findings(doc_path)


def test_ignores_generic_non_env_file_environment_examples(tmp_path: Path) -> None:
    doc_path = tmp_path / "doc.md"
    doc_path.write_text(
        """Set a temporary environment variable:

```bash
OPENROUTER_API_KEY=REPLACE_WITH_OPENROUTER_API_KEY
```
""",
        encoding="utf-8",
    )

    assert not _env_file_setup_findings(doc_path)


def test_tracked_markdown_docs_avoid_public_sensitive_log_sharing() -> None:
    sharing = re.compile(r"\b(share|send|paste|attach|post)\b", re.IGNORECASE)
    artifact = re.compile(r"\b(logs?|output|diagnostics?|dump|audit)\b", re.IGNORECASE)
    public_issue = re.compile(r"github issue", re.IGNORECASE)
    safety_terms = re.compile(
        r"\b(review|redact|sanitize|sanitized|non-sensitive)\b", re.IGNORECASE
    )
    offenders = []

    for path in _tracked_markdown_docs():
        relative_path = path.relative_to(ROOT)
        lines = path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            line_number = index + 1
            nearby = "\n".join(lines[max(0, index - 2) : index + 3])
            if "security-audit" in nearby and sharing.search(nearby) and artifact.search(nearby):
                if not safety_terms.search(nearby):
                    offenders.append(
                        f"{relative_path}:{line_number}: shares security-audit diagnostics unsafely"
                    )
            if public_issue.search(nearby) and artifact.search(nearby):
                if not safety_terms.search(nearby):
                    offenders.append(
                        f"{relative_path}:{line_number}: sends sensitive diagnostics to public issue"
                    )

    assert not offenders, "Unsafe public diagnostic sharing remains:\n" + "\n".join(offenders)
