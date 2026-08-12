from unittest.mock import Mock, call

import pytest

import src.openrouter_mcp.cli.mcp_manager as manager_module
from src.openrouter_mcp.cli.mcp_manager import (
    MCPConfigError,
    MCPManager,
    MCPServerAlreadyExistsError,
    MCPServerConfig,
    MCPServerNotFoundError,
)

pytestmark = pytest.mark.unit


def _make_manager(servers=None):
    manager = object.__new__(MCPManager)
    manager.config = {"mcpServers": dict(servers or {})}
    return manager


def test_store_server_config_preserves_mutation_save_and_log_order(
    monkeypatch,
    tmp_path,
):
    manager = _make_manager()
    raw_cwd = str(tmp_path / "missing" / ".." / "project")
    expected_cwd = str((tmp_path / "project").resolve())
    config = MCPServerConfig(name="example", command="python", cwd=raw_cwd)
    payload = {"command": "serialized"}
    events = []

    def to_dict():
        events.append(("to_dict", config.cwd))
        return payload

    def save_config():
        events.append(("save", manager.config["mcpServers"]["example"]))

    def log_info(message):
        events.append(("log", message))

    monkeypatch.setattr(config, "to_dict", to_dict)
    monkeypatch.setattr(manager, "_save_config", save_config)
    monkeypatch.setattr(manager_module.logger, "info", log_info)

    manager._store_server_config(config, action="Added")

    assert config.cwd == expected_cwd
    assert manager.config["mcpServers"]["example"] is payload
    assert events == [
        ("to_dict", expected_cwd),
        ("save", payload),
        ("log", "Added MCP server: example"),
    ]


@pytest.mark.parametrize("cwd", [None, ""])
def test_store_server_config_preserves_falsey_cwd(monkeypatch, cwd):
    manager = _make_manager()
    config = MCPServerConfig(name="example", command="python", cwd=cwd)
    observed = []

    def to_dict():
        observed.append(config.cwd)
        return {"command": "python"}

    monkeypatch.setattr(config, "to_dict", to_dict)
    monkeypatch.setattr(manager, "_save_config", Mock())
    monkeypatch.setattr(manager_module.logger, "info", Mock())

    manager._store_server_config(config, action="Updated")

    assert observed == [cwd]
    assert config.cwd is cwd


def test_store_server_config_preserves_to_dict_failure_state(
    monkeypatch,
    tmp_path,
):
    old_payload = {"command": "old"}
    manager = _make_manager({"example": old_payload})
    config = MCPServerConfig(
        name="example",
        command="python",
        cwd=str(tmp_path / "project"),
    )
    save_config = Mock()
    log_info = Mock()
    monkeypatch.setattr(
        config,
        "to_dict",
        Mock(side_effect=RuntimeError("serialization failed")),
    )
    monkeypatch.setattr(manager, "_save_config", save_config)
    monkeypatch.setattr(manager_module.logger, "info", log_info)

    with pytest.raises(RuntimeError, match="serialization failed"):
        manager._store_server_config(config, action="Updated")

    assert config.cwd == str((tmp_path / "project").resolve())
    assert manager.config["mcpServers"]["example"] is old_payload
    save_config.assert_not_called()
    log_info.assert_not_called()


def test_store_server_config_preserves_save_failure_partial_state(monkeypatch):
    old_payload = {"command": "old"}
    new_payload = {"command": "new"}
    manager = _make_manager({"example": old_payload})
    config = MCPServerConfig(name="example", command="python")
    log_info = Mock()
    monkeypatch.setattr(config, "to_dict", Mock(return_value=new_payload))
    monkeypatch.setattr(
        manager,
        "_save_config",
        Mock(side_effect=MCPConfigError("save failed")),
    )
    monkeypatch.setattr(manager_module.logger, "info", log_info)

    with pytest.raises(MCPConfigError, match="save failed"):
        manager._store_server_config(config, action="Updated")

    assert manager.config["mcpServers"]["example"] is new_payload
    log_info.assert_not_called()


def test_add_server_preserves_duplicate_check_before_storage(monkeypatch):
    manager = _make_manager({"example": {"command": "old"}})
    config = MCPServerConfig(name="example", command="python", cwd="~/project")
    store_server = Mock()
    monkeypatch.setattr(
        manager,
        "_store_server_config",
        store_server,
        raising=False,
    )

    with pytest.raises(MCPServerAlreadyExistsError):
        manager.add_server(config)

    assert config.cwd == "~/project"
    store_server.assert_not_called()

    manager.add_server(config, force=True)

    assert store_server.call_args_list == [call(config, action="Added")]


def test_update_server_preserves_existence_check_before_storage(monkeypatch):
    manager = _make_manager()
    config = MCPServerConfig(name="example", command="python", cwd="~/project")
    store_server = Mock()
    monkeypatch.setattr(
        manager,
        "_store_server_config",
        store_server,
        raising=False,
    )

    with pytest.raises(MCPServerNotFoundError):
        manager.update_server(config)

    assert config.cwd == "~/project"
    store_server.assert_not_called()

    manager.config["mcpServers"]["example"] = {"command": "old"}
    manager.update_server(config)

    assert store_server.call_args_list == [call(config, action="Updated")]
