import json

import pytest

from src.openrouter_mcp.runtime_thrift import (
    get_thrift_metrics_snapshot,
    reset_runtime_thrift_policy,
    reset_thrift_metrics,
)
from src.openrouter_mcp.runtime_thrift.batch_lane import (
    DeferredBatchLane,
    DeferredBatchRequest,
    _write_grouped_request_files,
)


class TestDeferredBatchLane:
    @pytest.mark.unit
    def test_write_grouped_request_files_preserves_group_and_record_order(
        self, tmp_path
    ):
        requests = [
            DeferredBatchRequest(
                custom_id="zeta-1",
                endpoint="/chat/completions",
                model_id="zeta/model one",
                body={"message": "안녕"},
            ),
            DeferredBatchRequest(
                custom_id="alpha-1",
                endpoint="/chat/completions",
                model_id="alpha/model-two",
                body={"message": "hello"},
            ),
            DeferredBatchRequest(
                custom_id="zeta-2",
                endpoint="/chat/completions",
                model_id="zeta/model one",
                body={"message": "다시 안녕"},
            ),
        ]
        original_requests = list(requests)
        original_records = json.loads(
            json.dumps([request.to_jsonl_record() for request in requests])
        )

        groups = _write_grouped_request_files(tmp_path, requests)

        assert groups == [
            {
                "provider": "alpha",
                "model_id": "alpha/model-two",
                "file_name": "0000_alpha__alpha-model-two.jsonl",
                "request_count": 1,
            },
            {
                "provider": "zeta",
                "model_id": "zeta/model one",
                "file_name": "0001_zeta__zeta-model-one.jsonl",
                "request_count": 2,
            },
        ]
        zeta_text = (tmp_path / "0001_zeta__zeta-model-one.jsonl").read_text(
            encoding="utf-8"
        )
        assert "안녕" in zeta_text
        assert "\\uc548" not in zeta_text
        assert [json.loads(line)["custom_id"] for line in zeta_text.splitlines()] == [
            "zeta-1",
            "zeta-2",
        ]
        assert all(
            current is original
            for current, original in zip(requests, original_requests)
        )
        assert [request.to_jsonl_record() for request in requests] == original_records

    @pytest.mark.unit
    def test_export_requests_groups_by_provider_and_model(self, tmp_path):
        lane = DeferredBatchLane(tmp_path)
        requests = [
            DeferredBatchRequest(
                custom_id="bench-openai-001",
                endpoint="/chat/completions",
                model_id="openai/gpt-4",
                body={
                    "model": "openai/gpt-4",
                    "messages": [{"role": "user", "content": "hi"}],
                },
                metadata={"run_index": 1},
            ),
            DeferredBatchRequest(
                custom_id="bench-openai-002",
                endpoint="/chat/completions",
                model_id="openai/gpt-4",
                body={
                    "model": "openai/gpt-4",
                    "messages": [{"role": "user", "content": "hi"}],
                },
                metadata={"run_index": 2},
            ),
            DeferredBatchRequest(
                custom_id="bench-anthropic-001",
                endpoint="/chat/completions",
                model_id="anthropic/claude-3-haiku",
                body={
                    "model": "anthropic/claude-3-haiku",
                    "messages": [{"role": "user", "content": "hi"}],
                },
                metadata={"run_index": 1},
            ),
        ]

        export = lane.export_requests(
            requests=requests,
            batch_name="nightly benchmark sweep",
            sla_window_hours=24,
            target_spend_usd=3.5,
        )

        assert export.total_requests == 3
        assert export.group_count == 2
        assert export.batch_dir.exists()
        assert export.manifest_path.exists()

        manifest = json.loads(export.manifest_path.read_text(encoding="utf-8"))
        assert manifest["total_requests"] == 3
        assert manifest["sla_window_hours"] == 24
        assert manifest["target_spend_usd"] == 3.5
        assert len(manifest["groups"]) == 2

        openai_group = next(
            group for group in manifest["groups"] if group["provider"] == "openai"
        )
        jsonl_lines = (
            (export.batch_dir / openai_group["file_name"])
            .read_text(encoding="utf-8")
            .strip()
            .splitlines()
        )
        assert len(jsonl_lines) == 2
        first_line = json.loads(jsonl_lines[0])
        assert first_line["custom_id"] == "bench-openai-001"
        assert first_line["method"] == "POST"
        assert first_line["url"] == "/chat/completions"
        assert first_line["metadata"]["run_index"] == 1

    @pytest.mark.unit
    def test_export_requests_records_deferred_request_metric(self, tmp_path):
        reset_thrift_metrics()
        lane = DeferredBatchLane(tmp_path)

        lane.export_requests(
            requests=[
                DeferredBatchRequest(
                    custom_id="bench-openai-001",
                    endpoint="/chat/completions",
                    model_id="openai/gpt-4",
                    body={
                        "model": "openai/gpt-4",
                        "messages": [{"role": "user", "content": "hi"}],
                    },
                ),
                DeferredBatchRequest(
                    custom_id="bench-openai-002",
                    endpoint="/chat/completions",
                    model_id="openai/gpt-4",
                    body={
                        "model": "openai/gpt-4",
                        "messages": [{"role": "user", "content": "hi"}],
                    },
                ),
            ],
            batch_name="nightly benchmark sweep",
        )

        metrics = get_thrift_metrics_snapshot()
        assert metrics["deferred_requests"] == 2

    @pytest.mark.unit
    def test_export_requests_rejects_when_policy_disabled(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENROUTER_THRIFT_ENABLE_DEFERRED_BATCH_LANE", "false")
        reset_runtime_thrift_policy()
        lane = DeferredBatchLane(tmp_path)

        with pytest.raises(ValueError, match="deferred batch lane is disabled"):
            lane.export_requests(
                requests=[
                    DeferredBatchRequest(
                        custom_id="bench-openai-001",
                        endpoint="/chat/completions",
                        model_id="openai/gpt-4",
                        body={
                            "model": "openai/gpt-4",
                            "messages": [{"role": "user", "content": "hi"}],
                        },
                    )
                ],
                batch_name="nightly benchmark sweep",
            )
