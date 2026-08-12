import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.openrouter_mcp.collective_intelligence import lifecycle_manager
from src.openrouter_mcp.collective_intelligence.lifecycle_manager import (
    CollectiveIntelligenceLifecycleManager,
)


class RecordingShutdownComponent:
    def __init__(
        self,
        name,
        manager,
        call_records,
        execution_records,
        fail=False,
        failure=None,
    ):
        self.name = name
        self.manager = manager
        self.call_records = call_records
        self.execution_records = execution_records
        self.fail = fail
        self.failure = failure

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
            if self.failure is not None:
                raise self.failure
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


class FatalShutdownError(BaseException):
    pass


@pytest.mark.asyncio
async def test_shutdown_logs_named_failures_with_optional_components_omitted():
    manager = CollectiveIntelligenceLifecycleManager()
    calls = []
    executions = []
    manager._consensus_engine = RecordingShutdownComponent(
        "consensus",
        manager,
        calls,
        executions,
        failure=FatalShutdownError("fatal cleanup"),
    )
    manager._ensemble_reasoner = SimpleNamespace()
    manager._adaptive_router = RecordingShutdownComponent(
        "adaptive",
        manager,
        calls,
        executions,
        failure=asyncio.CancelledError("child cleanup"),
    )
    manager._cross_validator = RecordingShutdownComponent(
        "cross-validator",
        manager,
        calls,
        executions,
        failure=RuntimeError("ordinary cleanup"),
    )

    with patch.object(lifecycle_manager.logger, "warning") as warning, patch.object(
        lifecycle_manager.logger, "error"
    ) as error, patch.object(lifecycle_manager.logger, "critical") as critical:
        await manager.shutdown()

    assert executions == ["consensus", "adaptive", "cross-validator"]
    warning.assert_called_once_with("Component AdaptiveRouter shutdown was cancelled")
    error.assert_called_once_with(
        "Component CrossValidator shutdown failed: ordinary cleanup"
    )
    critical.assert_called_once_with(
        "Component ConsensusEngine shutdown failed: fatal cleanup"
    )


@pytest.mark.asyncio
async def test_shutdown_success_does_not_log_component_failure():
    manager = CollectiveIntelligenceLifecycleManager()
    manager._consensus_engine = RecordingShutdownComponent("consensus", manager, [], [])

    with patch.object(lifecycle_manager.logger, "warning") as warning, patch.object(
        lifecycle_manager.logger, "error"
    ) as error, patch.object(lifecycle_manager.logger, "critical") as critical:
        await manager.shutdown()

    warning.assert_not_called()
    error.assert_not_called()
    critical.assert_not_called()


@pytest.mark.asyncio
async def test_shutdown_caller_cancellation_reclaims_component_tasks():
    manager = CollectiveIntelligenceLifecycleManager()
    started = {"consensus": asyncio.Event(), "collaborative": asyncio.Event()}
    finalized = []

    class BlockingShutdownComponent:
        def __init__(self, name):
            self.name = name

        async def shutdown(self):
            started[self.name].set()
            try:
                await asyncio.Event().wait()
            finally:
                finalized.append(self.name)

    manager._consensus_engine = BlockingShutdownComponent("consensus")
    manager._collaborative_solver = BlockingShutdownComponent("collaborative")
    shutdown_task = asyncio.create_task(manager.shutdown())
    await asyncio.gather(*(event.wait() for event in started.values()))

    shutdown_task.cancel("stop manager shutdown")
    with pytest.raises(asyncio.CancelledError) as raised:
        await shutdown_task

    assert raised.value.args == ("stop manager shutdown",)
    assert finalized == ["consensus", "collaborative"]
