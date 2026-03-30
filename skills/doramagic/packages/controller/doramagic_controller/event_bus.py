"""Append-only event bus for run_events.jsonl."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any


class EventBus:
    """Thread-safe JSONL event writer."""

    def __init__(self, run_dir: Path, run_id: str = "") -> None:
        self._path = run_dir / "run_events.jsonl"
        self._run_id = run_id
        self._seq = 0
        self._lock = Lock()

    @property
    def path(self) -> Path:
        return self._path

    def emit(
        self,
        event_type: str,
        message: str,
        *,
        phase: str,
        worker_id: str | None = None,
        status: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            self._seq += 1
            entry: dict[str, Any] = {
                "ts": datetime.now(UTC).isoformat(timespec="seconds"),
                "run_id": self._run_id,
                "seq": self._seq,
                "event_type": event_type,
                "event": event_type,
                "phase": phase,
                "message": message,
            }
            if worker_id:
                entry["worker_id"] = worker_id
            if status:
                entry["status"] = status
            if meta:
                entry["meta"] = meta

            line = json.dumps(entry, ensure_ascii=False) + "\n"
            with open(self._path, "a", encoding="utf-8") as handle:
                handle.write(line)
                handle.flush()
                os.fsync(handle.fileno())
