from types import SimpleNamespace

import pytest

from src.openrouter_mcp.collective_intelligence import lifecycle_manager
from src.openrouter_mcp.collective_intelligence.lifecycle_manager import (
    CollectiveIntelligenceLifecycleManager,
)


class RecordingShutdownComponent:
    def __init__(self, name, manager, call_records, execution_records, fail=False):
        self.name = name
        self.manager = manager
        self.call_records = call_records
        self.execution_records = execution_records
        self.fail = fail

    def shutdown(self):
        self.call_records.append(
            (
                self.name,
                self.manager.is_shutdown(),
                self.manager._shutdown_event.is_set(),
            )
        )

        async def complete_shutdown():
            self.execution_records.append(self.name)
            if self.fail:
                raise RuntimeError(f"{self.name} failed")

        return complete_shutdown()


@pytest.mark.asyncio
async def test_shutdown_preserves_collection_and_gather_invariants(monkeypatch):
    manager = CollectiveIntelligenceLifecycleManager()
    call_records = []
    execution_records = []
    gather_calls = []
    original_gather = lifecycle_manager.asyncio.gather

    async def recording_gather(*awaitables, **kwargs):
        gather_calls.append((len(awaitables), kwargs))
        return await original_gather(*awaitables, **kwargs)

    monkeypatch.setattr(lifecycle_manager.asyncio, "gather", recording_gather)

    manager._consensus_engine = RecordingShutdownComponent(
        "consensus", manager, call_records, execution_records
    )
    manager._collaborative_solver = RecordingShutdownComponent(
        "collaborative", manager, call_records, execution_records, fail=True
    )
    manager._ensemble_reasoner = SimpleNamespace()
    manager._adaptive_router = RecordingShutdownComponent(
        "adaptive", manager, call_records, execution_records
    )
    manager._cross_validator = RecordingShutdownComponent(
        "cross-validator", manager, call_records, execution_records
    )

    await manager.shutdown()

    assert call_records == [
        ("consensus", True, True),
        ("collaborative", True, True),
        ("adaptive", True, True),
        ("cross-validator", True, True),
    ]
    assert execution_records == [
        "consensus",
        "collaborative",
        "adaptive",
        "cross-validator",
    ]
    assert gather_calls == [(4, {"return_exceptions": True})]

    await manager.shutdown()

    assert len(call_records) == 4
    assert gather_calls == [(4, {"return_exceptions": True})]
