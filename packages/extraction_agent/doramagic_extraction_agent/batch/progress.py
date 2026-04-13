"""Progress tracking for batch extraction."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class _JobRecord:
    blueprint_id: str
    started_at: float = field(default_factory=time.monotonic)
    finished_at: float = field(default=0.0)
    tokens: int = 0
    error: str = ""
    status: str = "running"  # running | completed | failed

    def elapsed_since(self, batch_start: float) -> float:
        """Return seconds from batch start to when this job finished (or now)."""
        end = self.finished_at if self.finished_at else time.monotonic()
        return end - batch_start


class ProgressTracker:
    """Simple progress tracker that logs state to console / logger.

    Thread-safe for read operations; all mutations happen from async tasks
    running in the same event loop, so no additional locking is needed.

    Args:
        total_jobs: Total number of extraction jobs in the batch.
    """

    def __init__(self, total_jobs: int) -> None:
        self._total = total_jobs
        self._jobs: dict[str, _JobRecord] = {}
        self._batch_start = time.monotonic()
        logger.info("BatchProgress: starting %d job(s)", total_jobs)

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def start_job(self, blueprint_id: str) -> None:
        """Record that a job has started.

        Args:
            blueprint_id: Unique identifier for the job being started.
        """
        self._jobs[blueprint_id] = _JobRecord(blueprint_id=blueprint_id)
        done = self._count_done()
        logger.info(
            "[%d/%d] START  %s  (running=%d)",
            done,
            self._total,
            blueprint_id,
            self._count_running(),
        )

    def complete_job(self, blueprint_id: str, tokens: int) -> None:
        """Record that a job completed successfully.

        Args:
            blueprint_id: Unique identifier of the finished job.
            tokens: Total LLM tokens consumed by the job.
        """
        record = self._jobs.get(blueprint_id)
        if record is None:
            record = _JobRecord(blueprint_id=blueprint_id)
            self._jobs[blueprint_id] = record
        record.finished_at = time.monotonic()
        record.tokens = tokens
        record.status = "completed"
        elapsed = record.elapsed_since(self._batch_start)
        logger.info(
            "[%d/%d] DONE   %s  tokens=%s  elapsed=%.1fs",
            self._count_done(),
            self._total,
            blueprint_id,
            f"{tokens:,}",
            elapsed,
        )

    def fail_job(self, blueprint_id: str, error: str) -> None:
        """Record that a job failed.

        Args:
            blueprint_id: Unique identifier of the failed job.
            error: Human-readable error description.
        """
        record = self._jobs.get(blueprint_id)
        if record is None:
            record = _JobRecord(blueprint_id=blueprint_id)
            self._jobs[blueprint_id] = record
        record.finished_at = time.monotonic()
        record.error = error
        record.status = "failed"
        logger.error(
            "[%d/%d] FAILED %s  error=%r",
            self._count_done(),
            self._total,
            blueprint_id,
            error,
        )

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def summary(self) -> str:
        """Return a human-readable batch summary string.

        Returns:
            Multi-line summary covering total jobs, completed, failed, elapsed
            time, and total tokens consumed.
        """
        completed = [r for r in self._jobs.values() if r.status == "completed"]
        failed = [r for r in self._jobs.values() if r.status == "failed"]
        running = [r for r in self._jobs.values() if r.status == "running"]
        total_tokens = sum(r.tokens for r in completed)
        elapsed = time.monotonic() - self._batch_start

        lines = [
            "=" * 60,
            "Batch Extraction Summary",
            "=" * 60,
            f"  Total jobs : {self._total}",
            f"  Completed  : {len(completed)}",
            f"  Failed     : {len(failed)}",
            f"  Still running: {len(running)}",
            f"  Total tokens: {total_tokens:,}",
            f"  Elapsed    : {elapsed:.1f}s",
        ]

        if failed:
            lines.append("")
            lines.append("Failed jobs:")
            for r in failed:
                lines.append(f"  - {r.blueprint_id}: {r.error}")

        lines.append("=" * 60)
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _count_done(self) -> int:
        return sum(1 for r in self._jobs.values() if r.status in ("completed", "failed"))

    def _count_running(self) -> int:
        return sum(1 for r in self._jobs.values() if r.status == "running")
