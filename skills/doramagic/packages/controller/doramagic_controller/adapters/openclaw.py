"""OpenClaw platform adapter.

Handles I/O with the OpenClaw skill runtime:
- Input: /dora args passed via --input
- Output: JSON to stdout (message field displayed by OpenClaw)
- Progress: JSON to stdout (may or may not be displayed)
- Clarification: Saves state and exits; next invocation resumes
- Storage: ~/clawd/doramagic/runs/
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from doramagic_contracts.adapter import ClarificationRequest, ProgressUpdate
from doramagic_contracts.skill import PlatformRules


class OpenClawAdapter:
    """PlatformAdapter implementation for OpenClaw."""

    def __init__(
        self,
        platform_rules_path: Path | None = None,
        storage_root: Path | None = None,
    ) -> None:
        self._storage_root = storage_root or Path("~/clawd/doramagic/runs/").expanduser()
        self._platform_rules_path = platform_rules_path
        self._platform_rules: PlatformRules | None = None

    async def receive_input(self) -> str:
        """On OpenClaw, input comes via --input arg, not this method."""
        return ""

    async def send_output(self, message: str, artifacts: dict[str, Path]) -> None:
        """Print final output JSON to stdout for OpenClaw to display."""
        output = {
            "message": message,
            "delivery_path": str(artifacts.get("delivery", "")),
            "artifacts": {k: str(v) for k, v in artifacts.items()},
        }
        print(json.dumps(output, ensure_ascii=False))
        sys.stdout.flush()

    async def send_progress(self, update: ProgressUpdate) -> None:
        """Print progress JSON to stdout. OpenClaw may or may not display it."""
        progress = {
            "progress": True,
            "phase": update.phase,
            "status": update.status,
            "message": update.message,
            "percent": update.percent_complete,
        }
        print(json.dumps(progress, ensure_ascii=False))
        sys.stdout.flush()

    async def ask_clarification(self, request: ClarificationRequest) -> str:
        """On OpenClaw, clarification requires re-invocation.

        This method outputs the question and returns empty string,
        signaling the controller to save state and exit.
        The next invocation with --continue will provide the answer.
        """
        output = {
            "clarification": True,
            "question": request.question,
            "options": request.options,
            "round": request.round_number,
        }
        print(json.dumps(output, ensure_ascii=False))
        sys.stdout.flush()
        return ""  # signals controller to pause

    def get_storage_root(self) -> Path:
        return self._storage_root

    def get_platform_rules(self) -> PlatformRules:
        if self._platform_rules is None:
            if self._platform_rules_path and self._platform_rules_path.exists():
                data = json.loads(self._platform_rules_path.read_text(encoding="utf-8"))
                self._platform_rules = PlatformRules(**data)
            else:
                self._platform_rules = PlatformRules(
                    schema_version="dm.platform-rules.v1",
                    allowed_tools=["exec", "read", "write"],
                    metadata_openclaw_whitelist=[
                        "always", "emoji", "homepage", "skillKey",
                        "primaryEnv", "os", "requires", "install",
                    ],
                    forbid_frontmatter_fields=["cron"],
                    storage_prefix="~/clawd/",
                )
        return self._platform_rules

    def get_concurrency_limit(self) -> int:
        return 3  # OpenClaw max 5 agents, controller=1, reserve 1 for Agent Loop
