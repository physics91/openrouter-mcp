"""Exercise filesystem security boundaries through the actual Node/stdio server."""

import asyncio
import json
import os
import shutil
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

pytestmark = [pytest.mark.security, pytest.mark.integration]


@pytest.mark.asyncio
async def test_report_export_confines_files_through_real_stdio(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    server_dir = tmp_path / "server"
    results_dir = server_dir / ".cache" / "benchmarks"
    results_dir.mkdir(parents=True)
    # The launcher runs in its installed package directory. Stage the exact
    # shipped code there so the real launcher can only write temporary data.
    for directory in ("bin", "src"):
        shutil.copytree(
            repo / directory,
            server_dir / directory,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
    for filename in ("package.json", "requirements.txt"):
        shutil.copy2(repo / filename, server_dir / filename)
    payload = {
        "results": {
            "audit-model": {
                "success": True,
                "response": "security-regression-marker",
                "metrics": {"avg_cost": 0.0, "quality_score": 1.0},
            }
        }
    }
    valid_input = results_dir / "result.json"
    valid_input.write_text(json.dumps(payload), encoding="utf-8")
    outside_input = tmp_path / "outside.json"
    outside_input.write_text(json.dumps(payload), encoding="utf-8")
    outside_output = tmp_path / "protected.txt"
    outside_output.write_text("must remain unchanged", encoding="utf-8")

    environment = {
        "PATH": os.pathsep.join([str(Path(sys.executable).parent), os.environ["PATH"]]),
        "PYTHONDONTWRITEBYTECODE": "1",
        "NODE_PATH": str(repo / "node_modules"),
        "OPENROUTER_API_KEY": "security-regression-placeholder",
        "OPENROUTER_BASE_URL": "http://127.0.0.1:9",
        "FASTMCP_CHECK_FOR_UPDATES": "off",
    }
    params = StdioServerParameters(
        command=shutil.which("node") or "node",
        args=[str(server_dir / "bin" / "openrouter-mcp.js"), "start"],
        cwd=str(server_dir),
        env=environment,
    )

    async def exercise():
        with (tmp_path / "server.log").open("w", encoding="utf-8") as log:
            async with (
                stdio_client(params, errlog=log) as (read, write),
                ClientSession(read, write) as session,
            ):
                await session.initialize()

                async def export(input_name, output_name):
                    return await session.call_tool(
                        "export_benchmark_report",
                        {
                            "benchmark_file": input_name,
                            "output_file": output_name,
                            "format": "json",
                        },
                    )

                valid = await export("result.json", "report.json")
                assert not valid.isError
                assert "security-regression-marker" in (
                    results_dir / "report.json"
                ).read_text(encoding="utf-8")

                for invalid in (
                    "../../../outside.json",
                    str(outside_input),
                    r"..\outside.json",
                    r"C:\outside.json",
                    "subdir/result.json",
                ):
                    assert (await export(invalid, "report.json")).isError

                for invalid in (
                    "../../../protected.txt",
                    str(outside_output),
                    r"..\protected.txt",
                    r"C:protected.txt",
                    "",
                    ".",
                ):
                    assert (await export("result.json", invalid)).isError

                if os.name != "nt":
                    (results_dir / "linked-input.json").symlink_to(outside_input)
                    (results_dir / "linked-output.json").symlink_to(outside_output)
                    assert (await export("linked-input.json", "report.json")).isError
                    assert (await export("result.json", "linked-output.json")).isError

                    os.link(outside_output, results_dir / "hardlink.json")
                    assert not (await export("result.json", "hardlink.json")).isError

                assert (
                    outside_output.read_text(encoding="utf-8")
                    == "must remain unchanged"
                )

    await asyncio.wait_for(exercise(), timeout=40)
