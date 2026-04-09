from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CLI_PATH = REPO_ROOT / "bin" / "openrouter-mcp.js"
SECURE_CREDENTIALS_PATH = REPO_ROOT / "bin" / "secure-credentials.js"
START_RUNTIME_PATH = REPO_ROOT / "bin" / "start-runtime.js"
NODE_BINARY = shutil.which("node") or "node"


def _run_node_script(
    script: str, *, cwd: Path, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [NODE_BINARY, "-e", script],
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


@pytest.mark.unit
def test_start_command_does_not_write_wrapper_logs_to_stdout() -> None:
    env = os.environ.copy()
    env["OPENROUTER_API_KEY"] = "sk-or-test-key-123"
    env["NO_COLOR"] = "1"
    env["FORCE_COLOR"] = "0"

    process = subprocess.Popen(
        [NODE_BINARY, str(CLI_PATH), "start"],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        time.sleep(1.2)
        process.send_signal(signal.SIGTERM)
        stdout, stderr = process.communicate(timeout=5)
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=5)

    assert stdout == ""
    assert stderr is not None


@pytest.mark.unit
def test_resolve_api_key_for_start_fails_when_no_credentials_are_available(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["HOME"] = str(tmp_path / "home")
    env["NO_COLOR"] = "1"
    env["FORCE_COLOR"] = "0"

    script = f"""
const runtime = require({json.dumps(str(START_RUNTIME_PATH))});

(async () => {{
  try {{
    await runtime.resolveApiKeyForStart({{
      env: {{}},
      secureCredentials: {{
        getApiKey: async () => ({{ key: null, source: null }}),
      }},
      stderr: {{ write() {{}} }},
    }});
    console.log(JSON.stringify({{ ok: true }}));
  }} catch (error) {{
    console.log(JSON.stringify({{ ok: false, message: error.message }}));
  }}
}})().catch((error) => {{
  console.error(error);
  process.exit(1);
}});
"""

    result = _run_node_script(script, cwd=tmp_path, env=env)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout.strip())
    assert payload == {
        "ok": False,
        "message": "OpenRouter API key is required to start the MCP server. Run 'openrouter-mcp init' first or set OPENROUTER_API_KEY.",
    }


@pytest.mark.unit
def test_delete_credentials_preserves_non_secret_configuration(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    home = tmp_path / "home"
    home.mkdir()

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["NO_COLOR"] = "1"
    env["FORCE_COLOR"] = "0"

    script = f"""
const fs = require("fs");
const path = require("path");
const secure = require({json.dumps(str(SECURE_CREDENTIALS_PATH))});

const cwd = process.cwd();
const home = process.env.HOME;
const envPath = path.join(cwd, ".env");
const claudeCodePath = path.join(home, ".claude.json");
const claudeDesktopPath = path.join(home, ".config", "claude", "claude_desktop_config.json");

fs.mkdirSync(path.dirname(claudeDesktopPath), {{ recursive: true }});

fs.writeFileSync(
  envPath,
  [
    "OPENROUTER_API_KEY=sk-or-test",
    "OPENROUTER_APP_NAME=test-app",
    "OPENROUTER_HTTP_REFERER=https://example.com",
  ].join("\\n"),
);

const serverConfig = {{
  type: "stdio",
  command: "npx",
  args: ["@physics91/openrouter-mcp", "start"],
  env: {{
    OPENROUTER_API_KEY: "sk-or-test",
    LOG_LEVEL: "info",
  }},
}};

fs.writeFileSync(claudeCodePath, JSON.stringify({{ mcpServers: {{ openrouter: serverConfig }} }}, null, 2));
fs.writeFileSync(
  claudeDesktopPath,
  JSON.stringify({{ mcpServers: {{ openrouter: serverConfig }} }}, null, 2),
);

(async () => {{
  await secure.deleteAllCredentials();

  console.log(
    JSON.stringify({{
      envExists: fs.existsSync(envPath),
      envContent: fs.existsSync(envPath) ? fs.readFileSync(envPath, "utf8") : null,
      claudeCode: JSON.parse(fs.readFileSync(claudeCodePath, "utf8")),
      claudeDesktop: JSON.parse(fs.readFileSync(claudeDesktopPath, "utf8")),
    }})
  );
}})().catch((error) => {{
  console.error(error);
  process.exit(1);
}});
"""

    result = _run_node_script(script, cwd=workspace, env=env)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout.strip().splitlines()[-1])

    assert payload["envExists"] is True
    assert "OPENROUTER_API_KEY=" not in payload["envContent"]
    assert "OPENROUTER_APP_NAME=test-app" in payload["envContent"]
    assert "OPENROUTER_HTTP_REFERER=https://example.com" in payload["envContent"]

    claude_code_server = payload["claudeCode"]["mcpServers"]["openrouter"]
    claude_desktop_server = payload["claudeDesktop"]["mcpServers"]["openrouter"]

    assert claude_code_server["command"] == "npx"
    assert claude_code_server["args"] == ["@physics91/openrouter-mcp", "start"]
    assert claude_code_server["env"] == {"LOG_LEVEL": "info"}

    assert claude_desktop_server["command"] == "npx"
    assert claude_desktop_server["args"] == ["@physics91/openrouter-mcp", "start"]
    assert claude_desktop_server["env"] == {"LOG_LEVEL": "info"}
