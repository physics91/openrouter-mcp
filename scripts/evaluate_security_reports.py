#!/usr/bin/env python3
"""Fail-closed evaluator for CI security scanner reports."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

DEFAULT_SEMGREP_AUTO_BASELINE = Path("semgrep-auto-baseline.json")

EXPECTED_STATUS_KEYS = (
    "safety",
    "npm-audit",
    "retire",
    "pip-audit",
    "pip-audit-security",
    "pip-audit-semgrep",
    "osv-package-lock",
    "osv-requirements",
    "bandit",
    "semgrep-auto",
    "semgrep-owasp",
)


class SecurityReportError(ValueError):
    """Raised when a security report is missing, malformed, or has findings."""


FindingKey = tuple[str, str, str]
ScannerEvaluation = tuple[int, int, bool, list[str]]


def _load_json_path(path: Path, label: str) -> Any:
    if not path.is_file():
        raise SecurityReportError(f"Missing report: {label}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SecurityReportError(f"Invalid JSON in {label}: {exc}") from exc


def _load_json(report_dir: Path, filename: str) -> Any:
    return _load_json_path(report_dir / filename, filename)


def _require_dict(value: Any, filename: str, field: str | None = None) -> dict[str, Any]:
    if not isinstance(value, dict):
        if field:
            raise SecurityReportError(f"{filename} missing object field: {field}")
        raise SecurityReportError(f"{filename} must be a JSON object")
    return value


def _require_list(value: Any, field: str, filename: str) -> list[Any]:
    if not isinstance(value, list):
        raise SecurityReportError(f"{filename} missing list field: {field}")
    return value


def _require_str(value: Any, field: str, filename: str) -> str:
    if not isinstance(value, str) or not value:
        raise SecurityReportError(f"{filename} missing string field: {field}")
    return value


def _require_int(value: Any, field: str, filename: str) -> int:
    if not isinstance(value, int):
        raise SecurityReportError(f"{filename} missing integer field: {field}")
    return value


def _load_status(report_dir: Path) -> dict[str, int]:
    data = _require_dict(_load_json(report_dir, "security-status.json"), "security-status.json")
    status: dict[str, int] = {}
    for key in EXPECTED_STATUS_KEYS:
        if key not in data:
            raise SecurityReportError(f"security-status.json missing status: {key}")
        status[key] = _require_int(data[key], key, "security-status.json")
    return status


def _scanner_result(count: int, has_tool_errors: bool = False) -> ScannerEvaluation:
    return count, count, has_tool_errors, []


def _count_safety(report_dir: Path) -> ScannerEvaluation:
    data = _require_dict(_load_json(report_dir, "safety-report.json"), "safety-report.json")
    report_meta = data.get("report_meta")
    if not isinstance(report_meta, dict):
        raise SecurityReportError("safety-report.json missing object field: report_meta")
    return _scanner_result(
        _require_int(
            report_meta.get("vulnerabilities_found"),
            "report_meta.vulnerabilities_found",
            "safety-report.json",
        )
    )


def _count_npm_audit(report_dir: Path) -> ScannerEvaluation:
    filename = "npm-audit-report.json"
    data = _require_dict(_load_json(report_dir, filename), filename)
    metadata = _require_dict(data.get("metadata"), filename, "metadata")
    vulnerabilities = _require_dict(
        metadata.get("vulnerabilities"), filename, "metadata.vulnerabilities"
    )
    total = _require_int(vulnerabilities.get("total"), "metadata.vulnerabilities.total", filename)
    return _scanner_result(total)


def _count_retire(report_dir: Path) -> ScannerEvaluation:
    filename = "retire-report.json"
    data = _require_dict(_load_json(report_dir, filename), filename)
    findings = _require_list(data.get("data"), "data", filename)
    errors = _require_list(data.get("errors"), "errors", filename)
    count = 0
    for finding_index, finding in enumerate(findings):
        finding_dict = _require_dict(finding, filename, f"data[{finding_index}]")
        results = _require_list(
            finding_dict.get("results"),
            f"data[{finding_index}].results",
            filename,
        )
        for result_index, result in enumerate(results):
            result_dict = _require_dict(
                result,
                filename,
                f"data[{finding_index}].results[{result_index}]",
            )
            vulnerabilities = _require_list(
                result_dict.get("vulnerabilities"),
                f"data[{finding_index}].results[{result_index}].vulnerabilities",
                filename,
            )
            count += len(vulnerabilities)
    return _scanner_result(count, bool(errors))


def _count_pip_audit(report_dir: Path, filename: str) -> ScannerEvaluation:
    data = _require_dict(_load_json(report_dir, filename), filename)
    dependencies = _require_list(data.get("dependencies"), "dependencies", filename)
    count = 0
    for index, dependency in enumerate(dependencies):
        if not isinstance(dependency, dict):
            raise SecurityReportError(f"{filename} dependency #{index} must be an object")
        vulns = _require_list(
            dependency.get("vulns"),
            f"dependencies[{index}].vulns",
            filename,
        )
        count += len(vulns)
    return _scanner_result(count)


def _count_osv(report_dir: Path, filename: str) -> ScannerEvaluation:
    data = _require_dict(_load_json(report_dir, filename), filename)
    results = _require_list(data.get("results"), "results", filename)
    count = 0
    for result_index, result in enumerate(results):
        result_dict = _require_dict(result, filename, f"results[{result_index}]")
        packages = _require_list(
            result_dict.get("packages"),
            f"results[{result_index}].packages",
            filename,
        )
        for package_index, package in enumerate(packages):
            package_dict = _require_dict(
                package,
                filename,
                f"results[{result_index}].packages[{package_index}]",
            )
            vulnerabilities = _require_list(
                package_dict.get("vulnerabilities"),
                f"results[{result_index}].packages[{package_index}].vulnerabilities",
                filename,
            )
            count += len(vulnerabilities)
    return _scanner_result(count)


def _count_bandit(report_dir: Path) -> ScannerEvaluation:
    data = _require_dict(_load_json(report_dir, "bandit-report.json"), "bandit-report.json")
    errors = _require_list(data.get("errors"), "errors", "bandit-report.json")
    return _scanner_result(
        len(_require_list(data.get("results"), "results", "bandit-report.json")),
        bool(errors),
    )


def _count_semgrep(report_dir: Path, filename: str) -> ScannerEvaluation:
    data = _require_dict(_load_json(report_dir, filename), filename)
    errors = _require_list(data.get("errors"), "errors", filename)
    return _scanner_result(
        len(_require_list(data.get("results"), "results", filename)), bool(errors)
    )


def _normalize_source_span(source_root: Path, result: dict[str, Any], filename: str) -> str:
    result_path = _require_str(result.get("path"), "path", filename)
    start = _require_dict(result.get("start"), filename, "start")
    end = _require_dict(result.get("end"), filename, "end")
    start_line = _require_int(start.get("line"), "start.line", filename)
    end_line = _require_int(end.get("line"), "end.line", filename)
    if start_line < 1 or end_line < start_line:
        raise SecurityReportError(f"{filename} has invalid source span for {result_path}")

    root = source_root.resolve()
    source_path = (root / result_path).resolve()
    try:
        source_path.relative_to(root)
    except ValueError as exc:
        raise SecurityReportError(f"{filename} path escapes source root: {result_path}") from exc

    if not source_path.is_file():
        raise SecurityReportError(f"{filename} source file missing: {result_path}")

    source_lines = source_path.read_text(encoding="utf-8").splitlines()
    if end_line > len(source_lines):
        raise SecurityReportError(f"{filename} source span out of range: {result_path}")

    return "\n".join(
        line.strip() for line in source_lines[start_line - 1 : end_line] if line.strip()
    )


def _semgrep_result_key(
    source_root: Path,
    result: Any,
    filename: str,
) -> tuple[FindingKey, str]:
    result_dict = _require_dict(result, filename)
    check_id = _require_str(result_dict.get("check_id"), "check_id", filename)
    result_path = _require_str(result_dict.get("path"), "path", filename)
    start = _require_dict(result_dict.get("start"), filename, "start")
    line = _require_int(start.get("line"), "start.line", filename)
    normalized_span = _normalize_source_span(source_root, result_dict, filename)
    digest = hashlib.sha256(normalized_span.encode("utf-8")).hexdigest()
    return (check_id, result_path, digest), f"{result_path}:{line} {check_id}"


def _load_semgrep_auto_baseline(path: Path) -> Counter[FindingKey]:
    data = _require_dict(_load_json_path(path, str(path)), str(path))
    findings = _require_list(data.get("findings"), "findings", str(path))
    baseline: Counter[FindingKey] = Counter()
    for index, finding in enumerate(findings):
        finding_dict = _require_dict(finding, f"{path} findings[{index}]")
        key = (
            _require_str(finding_dict.get("check_id"), f"findings[{index}].check_id", str(path)),
            _require_str(finding_dict.get("path"), f"findings[{index}].path", str(path)),
            _require_str(
                finding_dict.get("source_sha256"),
                f"findings[{index}].source_sha256",
                str(path),
            ),
        )
        baseline[key] += 1
    return baseline


def _count_semgrep_auto(
    report_dir: Path,
    baseline_path: Path,
    source_root: Path,
) -> ScannerEvaluation:
    filename = "semgrep-auto-report.json"
    data = _require_dict(_load_json(report_dir, filename), filename)
    errors = _require_list(data.get("errors"), "errors", filename)
    results = _require_list(data.get("results"), "results", filename)
    baseline = _load_semgrep_auto_baseline(baseline_path)

    current: Counter[FindingKey] = Counter()
    labels: dict[FindingKey, str] = {}
    for result in results:
        key, label = _semgrep_result_key(source_root, result, filename)
        current[key] += 1
        labels[key] = label

    new_findings = current - baseline
    stale_baseline = baseline - current

    details: list[str] = [
        "semgrep-auto: "
        f"total_findings={sum(current.values())} "
        f"baselined={sum((current & baseline).values())} "
        f"new={sum(new_findings.values())} "
        f"stale_baseline={sum(stale_baseline.values())}"
    ]
    details.extend(
        f"semgrep-auto: new finding outside baseline: {labels.get(key, key[1])}"
        for key, count in new_findings.items()
        for _ in range(count)
    )
    details.extend(
        f"semgrep-auto: stale baseline entry: {key[1]} {key[0]}"
        for key, count in stale_baseline.items()
        for _ in range(count)
    )

    blocking_count = sum(new_findings.values()) + sum(stale_baseline.values())
    return blocking_count, len(results), bool(errors), details


def evaluate_reports(
    report_dir: Path,
    semgrep_auto_baseline: Path = DEFAULT_SEMGREP_AUTO_BASELINE,
    source_root: Path = Path("."),
) -> tuple[bool, list[str]]:
    """Evaluate reports and return `(ok, messages)`."""
    messages: list[str] = []
    try:
        status = _load_status(report_dir)
        scanners: dict[str, ScannerEvaluation] = {
            "safety": _count_safety(report_dir),
            "npm-audit": _count_npm_audit(report_dir),
            "retire": _count_retire(report_dir),
            "pip-audit": _count_pip_audit(report_dir, "pip-audit-report.json"),
            "pip-audit-security": _count_pip_audit(report_dir, "pip-audit-security-report.json"),
            "pip-audit-semgrep": _count_pip_audit(report_dir, "pip-audit-semgrep-report.json"),
            "osv-package-lock": _count_osv(report_dir, "osv-package-lock-report.json"),
            "osv-requirements": _count_osv(report_dir, "osv-requirements-report.json"),
            "bandit": _count_bandit(report_dir),
            "semgrep-auto": _count_semgrep_auto(
                report_dir,
                semgrep_auto_baseline,
                source_root,
            ),
            "semgrep-owasp": _count_semgrep(report_dir, "semgrep-owasp-report.json"),
        }
    except SecurityReportError as exc:
        return False, [str(exc)]

    ok = True
    for scanner, (
        blocking_count,
        parsed_count,
        has_tool_errors,
        details,
    ) in scanners.items():
        scanner_status = status[scanner]
        messages.append(
            f"{scanner}: exit={scanner_status} findings={parsed_count} "
            f"blocking_findings={blocking_count} tool_errors={int(has_tool_errors)}"
        )
        messages.extend(details)
        if has_tool_errors:
            ok = False
            messages.append(f"{scanner}: scanner reported execution errors")
        if blocking_count:
            ok = False
            messages.append(f"{scanner}: findings detected")
        if scanner_status != 0 and parsed_count == 0 and not has_tool_errors:
            ok = False
            messages.append(f"{scanner}: unexpected nonzero exit without parsed findings or errors")

    return ok, messages


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=Path("."),
        help="Directory containing security report JSON files",
    )
    parser.add_argument(
        "--semgrep-auto-baseline",
        type=Path,
        default=DEFAULT_SEMGREP_AUTO_BASELINE,
        help="JSON baseline for existing Semgrep auto findings",
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        default=Path("."),
        help="Repository root used to hash Semgrep source spans",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    ok, messages = evaluate_reports(
        args.report_dir,
        semgrep_auto_baseline=args.semgrep_auto_baseline,
        source_root=args.source_root,
    )
    for message in messages:
        print(message)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
