from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_RUNNER_PATH = REPO_ROOT / "scripts" / "run_tests.py"


def load_script_runner():
    spec = importlib.util.spec_from_file_location("collective_script_runner", SCRIPT_RUNNER_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_security_runner_saves_safety_json_report(monkeypatch):
    runner_module = load_script_runner()
    calls: list[list[str]] = []

    def fake_call(command):
        calls.append(command)
        return 0

    monkeypatch.setattr(subprocess, "call", fake_call)

    results = runner_module.TestRunner().run_security_checks()

    assert results == {"bandit": 0, "safety": 0}
    assert [
        "safety",
        "check",
        "-r",
        "requirements.txt",
        "-r",
        "requirements-dev.txt",
        "-r",
        "requirements-security.txt",
        "-r",
        "requirements-semgrep.txt",
        "--json",
        "--save-json",
        "safety-report.json",
    ] in calls
