"""Deferred batch export helpers for offline workloads."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

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
    body: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def provider(self) -> str:
        return _infer_provider(self.model_id)

    def to_jsonl_record(self) -> Dict[str, Any]:
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
    groups: List[Dict[str, Any]]
    sla_window_hours: int
    target_spend_usd: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "batch_dir": str(self.batch_dir),
            "manifest_path": str(self.manifest_path),
            "total_requests": self.total_requests,
            "group_count": self.group_count,
            "groups": self.groups,
            "sla_window_hours": self.sla_window_hours,
            "target_spend_usd": self.target_spend_usd,
        }


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
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DeferredBatchExport:
        if not get_runtime_thrift_policy().enable_deferred_batch_lane:
            raise ValueError("deferred batch lane is disabled by runtime thrift policy")

        request_list = list(requests)
        if not request_list:
            raise ValueError("Deferred batch export requires at least one request")

        created_at = datetime.now(timezone.utc)
        batch_id = f"{_slugify(batch_name)}-{created_at.strftime('%Y%m%d_%H%M%S')}"
        batch_dir = self.base_dir / batch_id
        batch_dir.mkdir(parents=True, exist_ok=True)

        grouped: Dict[tuple[str, str], List[DeferredBatchRequest]] = defaultdict(list)
        for request in request_list:
            grouped[(request.provider, request.model_id)].append(request)

        groups_payload: List[Dict[str, Any]] = []
        for (provider, model_id), group_requests in sorted(grouped.items()):
            file_name = f"{_slugify(provider)}__{_slugify(model_id)}.jsonl"
            output_path = batch_dir / file_name
            with open(output_path, "w", encoding="utf-8") as handle:
                for request in group_requests:
                    handle.write(json.dumps(request.to_jsonl_record(), ensure_ascii=False))
                    handle.write("\n")

            groups_payload.append(
                {
                    "provider": provider,
                    "model_id": model_id,
                    "file_name": file_name,
                    "request_count": len(group_requests),
                }
            )

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
        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2, ensure_ascii=False)

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
