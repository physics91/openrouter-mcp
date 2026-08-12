from unittest.mock import AsyncMock, Mock, call

import pytest

import src.openrouter_mcp.collective_intelligence.lifecycle_manager as lifecycle_module
from src.openrouter_mcp.collective_intelligence.lifecycle_manager import (
    CollectiveIntelligenceLifecycleManager,
)

pytestmark = pytest.mark.unit


def _make_manager(provider=None, operational_config=None):
    manager = object.__new__(CollectiveIntelligenceLifecycleManager)
    manager._model_provider = provider
    manager._operational_config = operational_config
    return manager


def test_require_model_provider_preserves_identity():
    provider = Mock()
    manager = _make_manager(provider)

    assert manager._require_model_provider() is provider


def test_require_model_provider_preserves_unconfigured_error():
    manager = _make_manager()

    with pytest.raises(
        RuntimeError,
        match=r"^LifecycleManager not configured\. Call configure\(\) first\.$",
    ):
        manager._require_model_provider()


@pytest.mark.asyncio
async def test_consensus_getter_uses_required_provider_and_preserves_config(
    monkeypatch,
):
    provider = Mock()
    operational_config = Mock()
    consensus_config = Mock()
    engine = Mock()
    constructor = Mock(return_value=engine)
    require_provider = Mock(return_value=provider)
    manager = _make_manager(None, operational_config)

    async def create_component(attr_name, factory, component_name):
        assert attr_name == "_consensus_engine"
        assert component_name == "ConsensusEngine"
        return factory()

    get_or_create = AsyncMock(side_effect=create_component)
    monkeypatch.setattr(
        manager,
        "_require_model_provider",
        require_provider,
        raising=False,
    )
    monkeypatch.setattr(manager, "_get_or_create_component", get_or_create)
    monkeypatch.setattr(lifecycle_module, "ConsensusEngine", constructor)

    result = await manager.get_consensus_engine(consensus_config)

    assert result is engine
    require_provider.assert_called_once_with()
    assert consensus_config.operational_config is operational_config
    constructor.assert_called_once_with(provider, consensus_config)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("getter_name", "component_name", "attr_name", "uses_operational_config"),
    [
        (
            "get_collaborative_solver",
            "CollaborativeSolver",
            "_collaborative_solver",
            True,
        ),
        ("get_ensemble_reasoner", "EnsembleReasoner", "_ensemble_reasoner", False),
        ("get_adaptive_router", "AdaptiveRouter", "_adaptive_router", False),
        ("get_cross_validator", "CrossValidator", "_cross_validator", False),
    ],
)
async def test_component_getters_use_required_provider(
    monkeypatch,
    getter_name,
    component_name,
    attr_name,
    uses_operational_config,
):
    provider = Mock()
    operational_config = Mock()
    component = Mock()
    constructor = Mock(return_value=component)
    require_provider = Mock(return_value=provider)
    manager = _make_manager(None, operational_config)

    async def create_component(observed_attr, factory, observed_name):
        assert observed_attr == attr_name
        assert observed_name == component_name
        return factory()

    get_or_create = AsyncMock(side_effect=create_component)
    monkeypatch.setattr(
        manager,
        "_require_model_provider",
        require_provider,
        raising=False,
    )
    monkeypatch.setattr(manager, "_get_or_create_component", get_or_create)
    monkeypatch.setattr(lifecycle_module, component_name, constructor)

    result = await getattr(manager, getter_name)()

    assert result is component
    assert require_provider.call_args_list == [call()]
    expected_args = (
        (provider, operational_config) if uses_operational_config else (provider,)
    )
    assert constructor.call_args_list == [call(*expected_args)]


@pytest.mark.asyncio
async def test_get_or_create_component_keeps_independent_provider_guard():
    manager = CollectiveIntelligenceLifecycleManager()
    factory = Mock()

    with pytest.raises(RuntimeError, match="not configured"):
        await manager._get_or_create_component("_consensus_engine", factory, "test")

    factory.assert_not_called()
