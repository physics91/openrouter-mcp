import hashlib
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "evaluate_security_reports.py"
AUTO_SOURCE = "danger(command)\n"
AUTO_RESULT = {
    "check_id": "test.semgrep-auto",
    "path": "demo.py",
    "start": {"line": 1},
    "end": {"line": 1},
}


def auto_baseline_entry():
    return {
        "check_id": AUTO_RESULT["check_id"],
        "path": AUTO_RESULT["path"],
        "line": 1,
        "source_sha256": hashlib.sha256(AUTO_SOURCE.strip().encode("utf-8")).hexdigest(),
    }


def write_reports(
    report_dir,
    *,
    baseline_auto=False,
    finding_scanner=None,
    malformed=None,
    missing=None,
    schema_missing=None,
    stale_auto_baseline=False,
    tool_error=None,
    bad_status=None
):
    (report_dir / "demo.py").write_text(AUTO_SOURCE, encoding="utf-8")

    status = {
        "safety": 0,
        "pip-audit": 0,
        "osv-package-lock": 0,
        "osv-requirements": 0,
        "bandit": 0,
        "semgrep-auto": 0,
        "semgrep-owasp": 0,
    }
    if bad_status:
        status[bad_status] = 2

    reports = {
        "security-status.json": status,
        "safety-report.json": {"report_meta": {"vulnerabilities_found": 0}},
        "pip-audit-report.json": {
            "dependencies": [{"name": "demo", "version": "1.0", "vulns": []}]
        },
        "osv-package-lock-report.json": {"results": []},
        "osv-requirements-report.json": {"results": []},
        "bandit-report.json": {"errors": [], "results": []},
        "semgrep-auto-report.json": {"errors": [], "results": []},
        "semgrep-owasp-report.json": {"errors": [], "results": []},
        "semgrep-auto-baseline.json": {"findings": []},
    }

    if finding_scanner == "safety":
        reports["safety-report.json"]["report_meta"]["vulnerabilities_found"] = 1
    elif finding_scanner == "pip-audit":
        reports["pip-audit-report.json"]["dependencies"][0]["vulns"] = [{"id": "TEST"}]
    elif finding_scanner == "osv-package-lock":
        reports["osv-package-lock-report.json"]["results"] = [
            {"packages": [{"vulnerabilities": [{"id": "GHSA-test"}]}]}
        ]
    elif finding_scanner == "osv-requirements":
        reports["osv-requirements-report.json"]["results"] = [
            {"packages": [{"vulnerabilities": [{"id": "GHSA-test"}]}]}
        ]
    elif finding_scanner == "bandit":
        reports["bandit-report.json"]["results"] = [{"test_id": "B000"}]
    elif finding_scanner == "semgrep-auto":
        reports["semgrep-auto-report.json"]["results"] = [AUTO_RESULT]
    elif finding_scanner == "semgrep-owasp":
        reports["semgrep-owasp-report.json"]["results"] = [{"check_id": "test"}]

    if baseline_auto:
        reports["semgrep-auto-report.json"]["results"] = [AUTO_RESULT]
        reports["semgrep-auto-baseline.json"]["findings"] = [auto_baseline_entry()]
    elif stale_auto_baseline:
        reports["semgrep-auto-baseline.json"]["findings"] = [auto_baseline_entry()]

    if tool_error == "bandit":
        reports["bandit-report.json"]["errors"] = [{"filename": "bad.py"}]
    elif tool_error == "semgrep-auto":
        reports["semgrep-auto-report.json"]["errors"] = [{"message": "bad config"}]
    elif tool_error == "semgrep-owasp":
        reports["semgrep-owasp-report.json"]["errors"] = [{"message": "bad config"}]

    if schema_missing == "safety":
        reports["safety-report.json"].pop("report_meta")
    elif schema_missing == "pip-audit":
        reports["pip-audit-report.json"].pop("dependencies")
    elif schema_missing == "osv-package-lock":
        reports["osv-package-lock-report.json"].pop("results")
    elif schema_missing == "osv-requirements":
        reports["osv-requirements-report.json"].pop("results")
    elif schema_missing == "bandit":
        reports["bandit-report.json"].pop("results")
    elif schema_missing == "semgrep-auto":
        reports["semgrep-auto-report.json"].pop("results")
    elif schema_missing == "semgrep-owasp":
        reports["semgrep-owasp-report.json"].pop("results")
    elif schema_missing == "status":
        reports["security-status.json"].pop("safety")

    for filename, data in reports.items():
        if filename == missing:
            continue
        path = report_dir / filename
        if filename == malformed:
            path.write_text("{not-json", encoding="utf-8")
        else:
            path.write_text(json.dumps(data), encoding="utf-8")


def run_evaluator(report_dir):
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--report-dir",
            str(report_dir),
            "--semgrep-auto-baseline",
            str(report_dir / "semgrep-auto-baseline.json"),
            "--source-root",
            str(report_dir),
        ],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def test_evaluator_passes_zero_reports(tmp_path):
    write_reports(tmp_path)

    result = run_evaluator(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr


def test_evaluator_fails_on_each_scanner_finding(tmp_path):
    for scanner in [
        "safety",
        "pip-audit",
        "osv-package-lock",
        "osv-requirements",
        "bandit",
        "semgrep-auto",
        "semgrep-owasp",
    ]:
        case_dir = tmp_path / scanner
        case_dir.mkdir()
        write_reports(case_dir, finding_scanner=scanner)

        result = run_evaluator(case_dir)

        assert result.returncode == 1, scanner


def test_evaluator_passes_baselined_semgrep_auto_finding(tmp_path):
    write_reports(tmp_path, baseline_auto=True)

    result = run_evaluator(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "baselined=1" in result.stdout


def test_evaluator_fails_on_stale_semgrep_auto_baseline(tmp_path):
    write_reports(tmp_path, stale_auto_baseline=True)

    result = run_evaluator(tmp_path)

    assert result.returncode == 1
    assert "stale baseline" in result.stdout


def test_evaluator_fails_on_missing_report(tmp_path):
    write_reports(tmp_path, missing="bandit-report.json")

    result = run_evaluator(tmp_path)

    assert result.returncode == 1
    assert "Missing report" in result.stdout


def test_evaluator_fails_on_malformed_json(tmp_path):
    write_reports(tmp_path, malformed="safety-report.json")

    result = run_evaluator(tmp_path)

    assert result.returncode == 1
    assert "Invalid JSON" in result.stdout


def test_evaluator_fails_on_missing_semgrep_auto_baseline(tmp_path):
    write_reports(tmp_path, missing="semgrep-auto-baseline.json")

    result = run_evaluator(tmp_path)

    assert result.returncode == 1
    assert "semgrep-auto-baseline.json" in result.stdout


def test_evaluator_fails_on_missing_schema_key(tmp_path):
    write_reports(tmp_path, schema_missing="pip-audit")

    result = run_evaluator(tmp_path)

    assert result.returncode == 1
    assert "missing list field" in result.stdout


def test_evaluator_fails_on_missing_status_entry(tmp_path):
    write_reports(tmp_path, schema_missing="status")

    result = run_evaluator(tmp_path)

    assert result.returncode == 1
    assert "missing status" in result.stdout


def test_evaluator_fails_on_unexpected_nonzero_status(tmp_path):
    write_reports(tmp_path, bad_status="safety")

    result = run_evaluator(tmp_path)

    assert result.returncode == 1
    assert "unexpected nonzero exit" in result.stdout


def test_evaluator_fails_on_tool_error_with_zero_findings(tmp_path):
    write_reports(tmp_path, tool_error="semgrep-owasp")

    result = run_evaluator(tmp_path)

    assert result.returncode == 1
    assert "scanner reported execution errors" in result.stdout
