"""File access tracking for extraction worker phases.

Uses contextvars.ContextVar for per-asyncio-task isolation so parallel
workers sharing the same ToolRegistry each get their own tracker.
"""

from __future__ import annotations

import contextvars
import json
from pathlib import PurePosixPath

_ACTIVE_TRACKER: contextvars.ContextVar[FileAccessTracker | None] = contextvars.ContextVar(
    "_ACTIVE_TRACKER",
    default=None,
)


class FileAccessTracker:
    """Records file paths accessed by filesystem tools during a phase."""

    __slots__ = ("_accessed",)

    def __init__(self) -> None:
        self._accessed: set[str] = set()

    def record(self, path: str) -> None:
        """Record a file path (relative to repo root)."""
        # Normalise to forward-slash POSIX style
        self._accessed.add(str(PurePosixPath(path)))

    def get_visited_files(self) -> set[str]:
        return set(self._accessed)

    def get_visited_dirs(self) -> set[str]:
        return {str(PurePosixPath(p).parent) for p in self._accessed if "/" in p}

    def to_json(self) -> str:
        return json.dumps(
            {"files": sorted(self._accessed), "count": len(self._accessed)},
            indent=2,
        )

    @classmethod
    def from_json(cls, text: str) -> FileAccessTracker:
        data = json.loads(text)
        tracker = cls()
        for f in data.get("files", []):
            tracker.record(f)
        return tracker


def get_active_tracker() -> FileAccessTracker | None:
    """Return the tracker bound to the current asyncio task, or None."""
    return _ACTIVE_TRACKER.get()


def set_active_tracker(
    tracker: FileAccessTracker | None,
) -> contextvars.Token[FileAccessTracker | None]:
    """Set the active tracker for the current task. Returns a token for reset."""
    return _ACTIVE_TRACKER.set(tracker)
