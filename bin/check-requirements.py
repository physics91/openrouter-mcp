#!/usr/bin/env python3
"""Check installed runtime versions without importing the server or its plugins."""

import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


def check_requirements(requirements_path: Path) -> list[str]:
    try:
        from packaging.requirements import Requirement
    except ImportError:
        return ["Missing packaging; install the runtime requirements first"]

    problems = []
    for line in requirements_path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        requirement = Requirement(line)
        if requirement.marker and not requirement.marker.evaluate():
            continue
        try:
            installed = version(requirement.name)
        except PackageNotFoundError:
            problems.append(f"Missing {requirement.name}")
            continue
        if not requirement.specifier.contains(installed, prereleases=False):
            problems.append(
                f"{requirement.name} {installed} does not satisfy {requirement.specifier}"
            )
    return problems


def main() -> int:
    requirements_path = Path(__file__).resolve().parent.parent / "requirements.txt"
    problems = check_requirements(requirements_path)
    if problems:
        print(
            "Runtime dependency check failed:\n" + "\n".join(problems), file=sys.stderr
        )
        return 1
    print("Runtime dependency versions satisfy requirements.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
