from collections import deque
from unittest.mock import Mock, call

import pytest

from src.openrouter_mcp.collective_intelligence import (
    operational_controls as controls_module,
)
from src.openrouter_mcp.collective_intelligence.collaborative_solver import (
    CollaborativeSolver,
)
from src.openrouter_mcp.collective_intelligence.consensus_engine import ConsensusEngine
from src.openrouter_mcp.collective_intelligence.operational_controls import (
    StorageConfig,
    StorageManager,
)


class _FailingValues(list):
    def __iter__(self):
        yield self[0]
        raise RuntimeError("iteration failed")


@pytest.mark.unit
def test_replace_items_preserves_clock_and_append_order(monkeypatch):
    events = []

    class TrackingMoment:
        def __init__(self, value):
            self.value = value

        def timestamp(self):
            events.append(("timestamp", self.value))
            return self.value

    class TrackingClock:
        value = 0

        @classmethod
        def now(cls):
            cls.value += 1
            events.append(("now", cls.value))
            return TrackingMoment(cls.value)

    class TrackingDeque(deque):
        def __init__(self, iterable=(), maxlen=None):
            events.append(("deque", maxlen))
            super().__init__(iterable, maxlen=maxlen)

        def append(self, item):
            events.append(("append", item[0]))
            super().append(item)

    monkeypatch.setattr(controls_module, "datetime", TrackingClock)
    monkeypatch.setattr(controls_module, "deque", TrackingDeque)
    manager = StorageManager(
        StorageConfig(max_history_size=3, enable_auto_cleanup=False)
    )
    events.clear()

    manager.replace_items(["first", "second"], id_prefix="history")

    assert events == [
        ("deque", 3),
        ("now", 1),
        ("timestamp", 1),
        ("append", "history_0_1"),
        ("now", 2),
        ("now", 3),
        ("timestamp", 3),
        ("append", "history_1_3"),
        ("now", 4),
    ]
    assert list(manager.items) == [
        ("history_0_1", "first"),
        ("history_1_3", "second"),
    ]
    assert {
        item_id: timestamp.value
        for item_id, timestamp in manager.item_timestamps.items()
    } == {
        "history_0_1": 2,
        "history_1_3": 4,
    }


@pytest.mark.unit
def test_replace_items_preserves_maxlen_orphan_timestamps():
    manager = StorageManager(
        StorageConfig(max_history_size=2, enable_auto_cleanup=False)
    )

    manager.replace_items(["first", "second", "third"], id_prefix="history")

    assert manager.get_items() == ["second", "third"]
    assert len(manager.item_timestamps) == 3
    assert [item_id.split("_", 2)[:2] for item_id in manager.item_timestamps] == [
        ["history", "0"],
        ["history", "1"],
        ["history", "2"],
    ]


@pytest.mark.unit
def test_replace_items_propagates_iteration_failure_with_partial_state():
    manager = StorageManager(
        StorageConfig(max_history_size=3, enable_auto_cleanup=False)
    )
    manager.items.append(("old", "old value"))
    manager.item_timestamps["old"] = Mock()

    with pytest.raises(RuntimeError, match="iteration failed"):
        manager.replace_items(_FailingValues(["first"]), id_prefix="history")

    assert manager.get_items() == ["first"]
    assert "old" not in manager.item_timestamps
    assert len(manager.item_timestamps) == 1


@pytest.mark.unit
@pytest.mark.parametrize(
    ("component_type", "property_name", "id_prefix"),
    [
        (ConsensusEngine, "consensus_history", "consensus"),
        (CollaborativeSolver, "completed_sessions", "session"),
    ],
)
def test_history_setters_delegate_replacement(
    component_type,
    property_name,
    id_prefix,
):
    component = object.__new__(component_type)
    component.storage_manager = Mock()
    values = [object(), object()]

    setattr(component, property_name, values)

    assert component.storage_manager.replace_items.call_args_list == [
        call(values, id_prefix=id_prefix)
    ]
