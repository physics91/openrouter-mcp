import json
from unittest.mock import Mock

import pytest

from src.openrouter_mcp.cli import mcp_manager as manager_module
from src.openrouter_mcp.cli.mcp_manager import MCPConfigError, MCPManager

pytestmark = pytest.mark.unit


def _manager(config_path):
    manager = object.__new__(MCPManager)
    manager.config_path = config_path
    manager.config = {"mcpServers": {}}
    return manager


def _assert_wrapped(error, expected_message, cause):
    assert str(error.value) == expected_message
    assert error.value.__cause__ is cause


def test_load_config_preserves_json_error_as_direct_cause(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text("{}", encoding="utf-8")
    manager = _manager(config_path)
    cause = json.JSONDecodeError("bad json", "", 0)
    monkeypatch.setattr(manager_module.json, "load", Mock(side_effect=cause))

    with pytest.raises(MCPConfigError) as error:
        manager._load_config()

    _assert_wrapped(
        error,
        "Invalid configuration file: bad json: line 1 column 1 (char 0)",
        cause,
    )


def test_load_config_preserves_generic_error_as_direct_cause(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text("{}", encoding="utf-8")
    manager = _manager(config_path)
    cause = OSError("read failed")
    monkeypatch.setattr(manager_module.json, "load", Mock(side_effect=cause))

    with pytest.raises(MCPConfigError) as error:
        manager._load_config()

    _assert_wrapped(error, "Failed to load configuration: read failed", cause)


def test_save_config_preserves_write_error_as_direct_cause(monkeypatch, tmp_path):
    manager = _manager(tmp_path / "config.json")
    cause = OSError("write failed")
    monkeypatch.setattr("builtins.open", Mock(side_effect=cause))

    with pytest.raises(MCPConfigError) as error:
        manager._save_config()

    _assert_wrapped(error, "Failed to save configuration: write failed", cause)


def test_restore_config_preserves_restore_error_after_rollback(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    backup_path = tmp_path / "backup.json"
    current_backup = tmp_path / "current.backup"
    for path in (config_path, backup_path, current_backup):
        path.write_text('{"mcpServers": {}}', encoding="utf-8")
    manager = _manager(config_path)
    cause = OSError("restore failed")
    monkeypatch.setattr(manager, "backup_config", Mock(return_value=current_backup))
    monkeypatch.setattr(
        manager_module.shutil,
        "copy2",
        Mock(side_effect=[cause, None]),
    )

    with pytest.raises(MCPConfigError) as error:
        manager.restore_config(backup_path)

    _assert_wrapped(error, "Failed to restore, rolled back: restore failed", cause)


def test_restore_config_preserves_json_error_as_direct_cause(monkeypatch, tmp_path):
    backup_path = tmp_path / "backup.json"
    backup_path.write_text("{}", encoding="utf-8")
    manager = _manager(tmp_path / "config.json")
    cause = json.JSONDecodeError("bad json", "", 0)
    monkeypatch.setattr(manager_module.json, "load", Mock(side_effect=cause))

    with pytest.raises(MCPConfigError) as error:
        manager.restore_config(backup_path)

    _assert_wrapped(error, "Invalid backup file: not valid JSON", cause)


def test_restore_config_preserves_outer_error_as_direct_cause(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    backup_path = tmp_path / "backup.json"
    config_path.write_text('{"mcpServers": {}}', encoding="utf-8")
    backup_path.write_text('{"mcpServers": {}}', encoding="utf-8")
    manager = _manager(config_path)
    cause = OSError("backup failed")
    monkeypatch.setattr(manager, "backup_config", Mock(side_effect=cause))

    with pytest.raises(MCPConfigError) as error:
        manager.restore_config(backup_path)

    _assert_wrapped(error, "Failed to restore configuration: backup failed", cause)
