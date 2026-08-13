"""Regression tests for the canonical local test runner."""

from __future__ import annotations

import sys
from collections.abc import Callable

import pytest

import run_tests


def _capture_commands(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    commands: list[list[str]] = []

    def fake_run_command(command: list[str], env: dict | None = None) -> int:
        commands.append(command)
        return 0

    monkeypatch.setattr(run_tests, "run_command", fake_run_command)
    return commands


def _set_npm_available(monkeypatch: pytest.MonkeyPatch) -> None:
    original_which: Callable[[str], str | None] = run_tests.shutil.which
    monkeypatch.setattr(
        run_tests.shutil,
        "which",
        lambda executable: (
            "/usr/bin/npm" if executable == "npm" else original_which(executable)
        ),
    )


@pytest.mark.unit
def test_all_excludes_real_api_and_installs_node_dependencies_first(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["run_tests.py", "all", "-v"])
    _set_npm_available(monkeypatch)
    commands = _capture_commands(monkeypatch)

    assert run_tests.main() == 0

    assert commands[0] == ["npm", "install", "--no-audit", "--no-fund"]
    pytest_command = commands[1]
    marker_index = pytest_command.index("-m", 3)
    assert pytest_command[marker_index + 1] == "not real_api"
    assert "--ignore=tests/test_real_world_integration.py" in pytest_command


@pytest.mark.unit
def test_assurance_installs_node_dependencies_before_pytest_and_security(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["run_tests.py", "assurance", "-v"])
    monkeypatch.setattr(run_tests.importlib.util, "find_spec", lambda name: object())
    _set_npm_available(monkeypatch)
    commands = _capture_commands(monkeypatch)

    assert run_tests.main() == 0

    assert commands[0] == ["npm", "install", "--no-audit", "--no-fund"]
    assert commands[1][0:3] == [sys.executable, "-m", "pytest"]
    assert commands[2] == ["npm", "run", "test:security"]
