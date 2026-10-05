"""Runtime dependency checks reject vulnerable/unsupported installed versions."""

import importlib.util
from importlib.metadata import PackageNotFoundError
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.security]

spec = importlib.util.spec_from_file_location(
    "runtime_requirements",
    Path(__file__).resolve().parents[1] / "bin" / "check-requirements.py",
)
assert spec and spec.loader
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


def test_rejects_old_missing_and_prerelease_dependencies(tmp_path, monkeypatch):
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(
        "fastmcp==3.2.4\nmcp>=1.30.0,<2\nPillow>=12.3.0\nhttpx>=0.28.1\n",
        encoding="utf-8",
    )
    versions = {"fastmcp": "3.0.2", "mcp": "1.30.0rc1", "httpx": "0.28.1"}

    def installed(name):
        if name not in versions:
            raise PackageNotFoundError(name)
        return versions[name]

    monkeypatch.setattr(checker, "version", installed)
    problems = checker.check_requirements(requirements)
    assert len(problems) == 3
    assert any("fastmcp 3.0.2" in problem for problem in problems)
    assert any("mcp 1.30.0rc1" in problem for problem in problems)
    assert "Missing Pillow" in problems


def test_accepts_supported_versions_and_respects_environment_markers(
    tmp_path, monkeypatch
):
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(
        "# versions\nfastmcp==3.2.4\nmcp>=1.30.0,<2\n"
        "absent-package>=1; python_version < '2'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        checker, "version", {"fastmcp": "3.2.4", "mcp": "1.30.0"}.__getitem__
    )
    assert checker.check_requirements(requirements) == []
