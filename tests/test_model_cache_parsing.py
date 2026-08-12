import json
from datetime import datetime
from unittest.mock import patch

import pytest

from src.openrouter_mcp.models import cache as cache_module
from src.openrouter_mcp.models.cache import ModelCache, _parse_model_cache_data

pytestmark = pytest.mark.unit


def test_parse_model_cache_data_preserves_models_and_timestamp():
    models = [{"id": "model-a"}]
    timestamp = "2026-08-12T12:34:56.123456"

    parsed_models, updated_at = _parse_model_cache_data(
        {"models": models, "updated_at": timestamp}
    )

    assert parsed_models is models
    assert updated_at == datetime.fromisoformat(timestamp)


def test_parse_model_cache_data_uses_existing_missing_defaults():
    parsed_models, updated_at = _parse_model_cache_data({})

    assert parsed_models == []
    assert updated_at is None


@pytest.mark.parametrize("updated_at", [None, "", 0, False])
def test_parse_model_cache_data_keeps_falsey_timestamp_as_none(updated_at):
    models = []

    parsed_models, parsed_updated_at = _parse_model_cache_data(
        {"models": models, "updated_at": updated_at}
    )

    assert parsed_models is models
    assert parsed_updated_at is None


def test_parse_model_cache_data_propagates_invalid_timestamp():
    with pytest.raises(ValueError):
        _parse_model_cache_data({"models": [], "updated_at": "not-a-timestamp"})


def test_load_from_file_cache_delegates_loaded_payload(tmp_path):
    cache_path = tmp_path / "models.json"
    cache = ModelCache(cache_file=str(cache_path))
    payload = {"models": [{"id": "stored"}], "updated_at": "stored-at"}
    cache_path.write_text(json.dumps(payload), encoding="utf-8")
    models = [{"id": "parsed"}]
    updated_at = datetime(2026, 8, 12, 12, 34, 56)

    with patch.object(
        cache_module,
        "_parse_model_cache_data",
        return_value=(models, updated_at),
    ) as parse:
        parsed_models, parsed_updated_at = cache._load_from_file_cache_sync()

    assert parsed_models is models
    assert parsed_updated_at is updated_at
    parse.assert_called_once_with(payload)


def test_load_from_file_cache_absorbs_parser_failure(tmp_path):
    cache_path = tmp_path / "models.json"
    cache = ModelCache(cache_file=str(cache_path))
    cache_path.write_text("{}", encoding="utf-8")

    with patch.object(
        cache_module,
        "_parse_model_cache_data",
        side_effect=TypeError("invalid cache payload"),
    ) as parse, patch.object(cache_module.logger, "error") as log:
        result = cache._load_from_file_cache_sync()

    assert result == ([], None)
    parse.assert_called_once_with({})
    log.assert_called_once_with(
        "Failed to load models from file cache: invalid cache payload"
    )
