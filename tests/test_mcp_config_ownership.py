import pytest

from src.openrouter_mcp.cli.mcp_manager import MCPManager, MCPServerConfig

pytestmark = pytest.mark.unit


def test_server_config_copies_mutable_fields_at_mapping_boundaries():
    source_args = ["server.py"]
    source_env = {"MODE": "test"}

    config = MCPServerConfig.from_dict(
        "test-server",
        {"command": "python", "args": source_args, "env": source_env},
    )

    assert config.args == source_args
    assert config.args is not source_args
    assert config.env == source_env
    assert config.env is not source_env

    serialized = config.to_dict()

    assert serialized["args"] == config.args
    assert serialized["args"] is not config.args
    assert serialized["env"] == config.env
    assert serialized["env"] is not config.env


def test_manager_server_configs_do_not_leak_mutable_state(tmp_path):
    manager = MCPManager(tmp_path / ".claude.json")
    config = MCPServerConfig(
        name="test-server",
        command="python",
        args=["server.py"],
        env={"MODE": "test"},
    )

    manager.add_server(config)
    config.args.append("--changed")
    config.env["MODE"] = "changed"

    stored = manager.config["mcpServers"]["test-server"]
    assert stored["args"] == ["server.py"]
    assert stored["env"] == {"MODE": "test"}

    loaded = manager.get_server("test-server")
    loaded.args.append("--loaded-change")
    loaded.env["MODE"] = "loaded-change"

    assert stored["args"] == ["server.py"]
    assert stored["env"] == {"MODE": "test"}


@pytest.mark.parametrize(
    ("raw_args", "raw_env"),
    [(None, None), (("server.py",), "MODE=test")],
)
def test_server_config_preserves_non_mutable_raw_field_contract(raw_args, raw_env):
    config = MCPServerConfig.from_dict(
        "test-server",
        {"command": "python", "args": raw_args, "env": raw_env},
    )

    assert config.args is raw_args
    assert config.env is raw_env

    serialized = config.to_dict()
    assert serialized["args"] is raw_args
    if raw_env:
        assert serialized["env"] is raw_env
    else:
        assert "env" not in serialized
