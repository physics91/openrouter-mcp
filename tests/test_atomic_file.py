from unittest.mock import MagicMock, Mock, call

import pytest

from src.openrouter_mcp.free import metrics as free_metrics_module
from src.openrouter_mcp.runtime_thrift import metrics as thrift_metrics_module
from src.openrouter_mcp.utils import _atomic_file

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("encoding", "expected_fdopen"),
    [
        (None, call(7, "w")),
        ("utf-8", call(7, "w", encoding="utf-8")),
    ],
)
def test_replace_file_atomically_preserves_operation_order(
    monkeypatch, encoding, expected_fdopen
):
    events = []
    handle = object()

    class OpenedFile:
        def __enter__(self):
            events.append("enter")
            return handle

        def __exit__(self, exc_type, exc, traceback):
            events.append("exit")

    mkstemp = Mock(
        side_effect=lambda **kwargs: (events.append(("mkstemp", kwargs)) or (7, "temp"))
    )
    fdopen = Mock(
        side_effect=lambda *args, **kwargs: (
            events.append(("fdopen", args, kwargs)) or OpenedFile()
        )
    )
    replace = Mock(side_effect=lambda *args: events.append(("replace", args)))
    writer = Mock(side_effect=lambda value: events.append(("write", value)))
    monkeypatch.setattr(_atomic_file.tempfile, "mkstemp", mkstemp)
    monkeypatch.setattr(_atomic_file.os, "fdopen", fdopen)
    monkeypatch.setattr(_atomic_file.os, "replace", replace)

    _atomic_file.replace_file_atomically(
        "destination",
        "directory",
        writer,
        encoding=encoding,
    )

    mkstemp.assert_called_once_with(dir="directory", suffix=".tmp")
    assert fdopen.call_args == expected_fdopen
    writer.assert_called_once_with(handle)
    replace.assert_called_once_with("temp", "destination")
    assert events == [
        ("mkstemp", {"dir": "directory", "suffix": ".tmp"}),
        (
            "fdopen",
            (7, "w"),
            {} if encoding is None else {"encoding": "utf-8"},
        ),
        "enter",
        ("write", handle),
        "exit",
        ("replace", ("temp", "destination")),
    ]


def test_replace_file_atomically_cleans_temp_and_preserves_interrupt(monkeypatch):
    interrupt = KeyboardInterrupt()
    monkeypatch.setattr(
        _atomic_file.tempfile, "mkstemp", Mock(return_value=(7, "temp"))
    )
    opened_file = MagicMock()
    opened_file.__enter__ = Mock(return_value=object())
    opened_file.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(_atomic_file.os, "fdopen", Mock(return_value=opened_file))
    unlink = Mock()
    monkeypatch.setattr(_atomic_file.os, "unlink", unlink)
    replace = Mock()
    monkeypatch.setattr(_atomic_file.os, "replace", replace)

    with pytest.raises(KeyboardInterrupt) as raised:
        _atomic_file.replace_file_atomically(
            "destination",
            "directory",
            Mock(side_effect=interrupt),
        )

    assert raised.value is interrupt
    unlink.assert_called_once_with("temp")
    replace.assert_not_called()


def test_replace_file_atomically_preserves_unlink_error_precedence(monkeypatch):
    unlink_error = OSError("unlink failed")
    monkeypatch.setattr(
        _atomic_file.tempfile, "mkstemp", Mock(return_value=(7, "temp"))
    )
    opened_file = MagicMock()
    opened_file.__enter__ = Mock(return_value=object())
    opened_file.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(_atomic_file.os, "fdopen", Mock(return_value=opened_file))
    monkeypatch.setattr(
        _atomic_file.os,
        "unlink",
        Mock(side_effect=unlink_error),
    )

    with pytest.raises(OSError) as raised:
        _atomic_file.replace_file_atomically(
            "destination",
            "directory",
            Mock(side_effect=RuntimeError("write failed")),
        )

    assert raised.value is unlink_error


def test_free_metrics_writer_keeps_json_defaults_and_absorbs_oserror(monkeypatch):
    collector = free_metrics_module.MetricsCollector()
    collector._persistence_path = "destination"
    data = {"model": {"total_requests": 1}}
    handle = object()
    dump = Mock()
    monkeypatch.setattr(free_metrics_module.json, "dump", dump)
    calls = []

    def replace(destination, directory, writer, *, encoding=None):
        calls.append((destination, directory, encoding))
        writer(handle)

    monkeypatch.setattr(free_metrics_module, "replace_file_atomically", replace)

    collector._write_metrics_atomically(data, "directory")

    assert calls == [("destination", "directory", None)]
    dump.assert_called_once_with(data, handle)

    warning = Mock()
    monkeypatch.setattr(free_metrics_module.logger, "warning", warning)
    save_error = OSError("disk full")
    monkeypatch.setattr(
        free_metrics_module,
        "replace_file_atomically",
        Mock(side_effect=save_error),
    )

    collector._write_metrics_atomically(data, "directory")

    warning.assert_called_once_with("메트릭 저장 실패: %s", save_error)


def test_runtime_thrift_writer_keeps_json_options_and_absorbs_oserror(
    monkeypatch, tmp_path
):
    destination = tmp_path / "metrics.json"
    collector = thrift_metrics_module.ThriftMetricsCollector(
        persistence_path=str(destination)
    )
    payload = {"version": 1, "days": {}}
    handle = object()
    dump = Mock()
    monkeypatch.setattr(collector, "_serialize_days", Mock(return_value=payload))
    monkeypatch.setattr(thrift_metrics_module.json, "dump", dump)
    calls = []

    def replace(destination_path, directory, writer, *, encoding=None):
        calls.append((destination_path, directory, encoding))
        writer(handle)

    monkeypatch.setattr(thrift_metrics_module, "replace_file_atomically", replace)

    collector._save()

    assert calls == [(str(destination), str(tmp_path), "utf-8")]
    dump.assert_called_once_with(
        payload,
        handle,
        ensure_ascii=False,
        sort_keys=True,
    )

    warning = Mock()
    save_error = OSError("disk full")
    monkeypatch.setattr(thrift_metrics_module.logger, "warning", warning)
    monkeypatch.setattr(
        thrift_metrics_module,
        "replace_file_atomically",
        Mock(side_effect=save_error),
    )

    collector._save()

    warning.assert_called_once_with(
        "Runtime thrift metrics save failed: %s", save_error
    )
