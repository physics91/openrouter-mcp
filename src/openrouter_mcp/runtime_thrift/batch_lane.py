"""Deferred batch export helpers for offline workloads."""

from __future__ import annotations

import json
import re
import tempfile
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ..utils._atomic_file import replace_file_atomically
from .metrics import record_deferred_requests
from .policy import get_runtime_thrift_policy


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "batch"


def _infer_provider(model_id: str) -> str:
    if "/" in model_id:
        provider, _rest = model_id.split("/", 1)
        return provider or "unknown"
    return "unknown"


@dataclass(frozen=True)
class DeferredBatchRequest:
    """A single request prepared for deferred execution."""

    custom_id: str
    endpoint: str
    model_id: str
    body: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def provider(self) -> str:
        return _infer_provider(self.model_id)

    def to_jsonl_record(self) -> dict[str, Any]:
        return {
            "custom_id": self.custom_id,
            "method": "POST",
            "url": self.endpoint,
            "body": self.body,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class DeferredBatchExport:
    """Metadata returned after writing deferred batch artifacts."""

    batch_dir: Path
    manifest_path: Path
    total_requests: int
    group_count: int
    groups: list[dict[str, Any]]
    sla_window_hours: int
    target_spend_usd: Optional[float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_dir": str(self.batch_dir),
            "manifest_path": str(self.manifest_path),
            "total_requests": self.total_requests,
            "group_count": self.group_count,
            "groups": self.groups,
            "sla_window_hours": self.sla_window_hours,
            "target_spend_usd": self.target_spend_usd,
        }


def _write_grouped_request_files(
    batch_dir: Path,
    requests: list[DeferredBatchRequest],
) -> list[dict[str, Any]]:
    """Write provider/model grouped JSONL files and describe each group."""
    grouped: dict[tuple[str, str], list[DeferredBatchRequest]] = defaultdict(list)
    for request in requests:
        grouped[(request.provider, request.model_id)].append(request)

    groups_payload: list[dict[str, Any]] = []
    for index, ((provider, model_id), group_requests) in enumerate(
        sorted(grouped.items())
    ):
        # The index prevents distinct model names from colliding after slugging.
        file_name = (
            f"{index:04d}_{_slugify(provider)[:48]}__{_slugify(model_id)[:96]}.jsonl"
        )
        output_path = batch_dir / file_name

        def write_group(handle, records=group_requests):
            for request in records:
                handle.write(json.dumps(request.to_jsonl_record(), ensure_ascii=False))
                handle.write("\n")

        replace_file_atomically(
            str(output_path), str(batch_dir), write_group, encoding="utf-8"
        )
        groups_payload.append(
            {
                "provider": provider,
                "model_id": model_id,
                "file_name": file_name,
                "request_count": len(group_requests),
            }
        )

    return groups_payload


class DeferredBatchLane:
    """Write deferred-execution requests into grouped JSONL artifacts."""

    def __init__(self, base_dir: Path | str) -> None:
        self.base_dir = Path(base_dir)

    def export_requests(
        self,
        requests: Iterable[DeferredBatchRequest],
        batch_name: str,
        *,
        sla_window_hours: int = 24,
        target_spend_usd: Optional[float] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> DeferredBatchExport:
        if not get_runtime_thrift_policy().enable_deferred_batch_lane:
            raise ValueError("deferred batch lane is disabled by runtime thrift policy")

        request_list = list(requests)
        if not request_list:
            raise ValueError("Deferred batch export requires at least one request")

        created_at = datetime.now(timezone.utc)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        prefix = f"{_slugify(batch_name)[:80]}-{created_at.strftime('%Y%m%d_%H%M%S')}-"
        # Create an exclusive private directory; never reuse a predictable path.
        batch_dir = Path(tempfile.mkdtemp(prefix=prefix, dir=self.base_dir))
        batch_id = batch_dir.name

        groups_payload = _write_grouped_request_files(batch_dir, request_list)

        manifest_path = batch_dir / "manifest.json"
        manifest = {
            "batch_id": batch_id,
            "batch_name": batch_name,
            "created_at": created_at.isoformat(),
            "total_requests": len(request_list),
            "group_count": len(groups_payload),
            "sla_window_hours": sla_window_hours,
            "target_spend_usd": target_spend_usd,
            "metadata": metadata or {},
            "groups": groups_payload,
        }
        replace_file_atomically(
            str(manifest_path),
            str(batch_dir),
            lambda handle: json.dump(manifest, handle, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        record_deferred_requests(len(request_list))
        return DeferredBatchExport(
            batch_dir=batch_dir,
            manifest_path=manifest_path,
            total_requests=len(request_list),
            group_count=len(groups_payload),
            groups=groups_payload,
            sla_window_hours=sla_window_hours,
            target_spend_usd=target_spend_usd,
        )


__all__ = [
    "DeferredBatchExport",
    "DeferredBatchLane",
    "DeferredBatchRequest",
]
