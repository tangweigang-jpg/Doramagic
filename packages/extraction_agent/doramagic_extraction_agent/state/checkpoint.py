"""Checkpoint persistence — save/load agent state + conversation archives."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .schema import AgentState


class CheckpointManager:
    """Manages agent state persistence and conversation archival.

    Directory layout under run_dir::

        _agent_state.json          ← atomic checkpoint (rename from .tmp)
        conversations/
            {phase_name}_{seq}.jsonl   ← one message per line
        artifacts/
            <phase-specific files>

    The atomic-write pattern (write to .tmp, then os.replace) ensures that a
    crash mid-write never corrupts the previous good checkpoint.
    """

    def __init__(self, run_dir: Path) -> None:
        self._run_dir = run_dir
        self._state_path = run_dir / "_agent_state.json"
        self._conversations_dir = run_dir / "conversations"
        self._artifacts_dir = run_dir / "artifacts"

        # Ensure required directories exist
        self._run_dir.mkdir(parents=True, exist_ok=True)
        self._conversations_dir.mkdir(parents=True, exist_ok=True)
        self._artifacts_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # State persistence                                                    #
    # ------------------------------------------------------------------ #

    def save_state(self, state: AgentState) -> None:
        """Atomically write agent state to disk.

        Writes to a sibling .tmp file first, then renames over the real path.
        This guarantees the on-disk file is always either the previous complete
        checkpoint or the new one — never a partial write.
        """
        fd, tmp_path = tempfile.mkstemp(dir=self._state_path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                f.write(state.model_dump_json(indent=2))
                f.flush()
                os.fsync(f.fileno())  # crash-durable
            os.replace(tmp_path, self._state_path)  # atomic rename
        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def load_state(self) -> AgentState | None:
        """Load agent state from disk.

        Returns:
            The deserialized AgentState, or None if no checkpoint file exists
            (i.e. this is a fresh run).
        """
        if not self._state_path.exists():
            return None
        raw = self._state_path.read_text(encoding="utf-8")
        return AgentState.model_validate_json(raw)

    # ------------------------------------------------------------------ #
    # Conversation archival                                                #
    # ------------------------------------------------------------------ #

    def archive_conversation(
        self,
        phase_name: str,
        messages: list[dict],
        sequence: int = 0,
    ) -> Path:
        """Archive a conversation to a JSONL file for later recovery.

        Each line in the JSONL contains one serialized message dict.  The
        sequence number allows multiple conversations within the same phase
        (e.g. after a context-window reset) to be stored separately.

        Args:
            phase_name: The phase this conversation belongs to.
            messages: List of message dicts (role + content).
            sequence: Monotonically increasing integer within the phase.

        Returns:
            The Path where the archive was written.
        """
        archive_path = self._conversations_dir / f"{phase_name}_{sequence}.jsonl"
        with archive_path.open("w", encoding="utf-8") as fh:
            for msg in messages:
                fh.write(json.dumps(msg, ensure_ascii=False) + "\n")
        return archive_path

    def load_conversation(
        self,
        phase_name: str,
        sequence: int = 0,
    ) -> list[dict] | None:
        """Load an archived conversation from JSONL.

        Args:
            phase_name: The phase whose conversation to load.
            sequence: The sequence number of the archive to load.

        Returns:
            List of message dicts, or None if the archive does not exist.
        """
        archive_path = self._conversations_dir / f"{phase_name}_{sequence}.jsonl"
        if not archive_path.exists():
            return None
        messages: list[dict] = []
        with archive_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    messages.append(json.loads(line))
        return messages

    # ------------------------------------------------------------------ #
    # Properties                                                           #
    # ------------------------------------------------------------------ #

    @property
    def artifacts_dir(self) -> Path:
        """Directory where phase artifacts (JSON, JSONL outputs) are written."""
        return self._artifacts_dir

    @property
    def run_dir(self) -> Path:
        """Root directory for this extraction run."""
        return self._run_dir
