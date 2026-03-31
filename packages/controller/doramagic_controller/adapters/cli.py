"""CLI platform adapter for local development and testing.

Supports multi-turn clarification via stdin/stdout.
"""

from __future__ import annotations

import json
from pathlib import Path

from doramagic_contracts.adapter import ClarificationRequest, ProgressUpdate
from doramagic_contracts.skill import PlatformRules


class CLIAdapter:
    """PlatformAdapter implementation for local CLI."""

    def __init__(
        self,
        storage_root: Path | None = None,
        platform_rules_path: Path | None = None,
    ) -> None:
        self._storage_root = storage_root or Path("~/.doramagic/runs/").expanduser()
        self._platform_rules_path = platform_rules_path

    async def receive_input(self) -> str:
        return input("doramagic> ").strip()

    async def send_output(self, message: str, artifacts: dict[str, Path]) -> None:
        print("\n" + "=" * 60)
        print(message)
        if artifacts:
            print("\nArtifacts:")
            for name, path in artifacts.items():
                print(f"  {name}: {path}")
        print("=" * 60)

    async def send_progress(self, update: ProgressUpdate) -> None:
        print(f"  [{update.percent_complete:3d}%] {update.message}")

    async def ask_clarification(self, request: ClarificationRequest) -> str:
        """Interactive clarification via stdin."""
        print(f"\n{request.question}")
        if request.options:
            for i, opt in enumerate(request.options, 1):
                print(f"  {i}) {opt}")
            raw = input("Choice (number or text): ").strip()
            try:
                idx = int(raw) - 1
                if 0 <= idx < len(request.options):
                    return request.options[idx]
            except ValueError:
                pass
            return raw
        return input("Answer: ").strip()

    def get_storage_root(self) -> Path:
        return self._storage_root

    def get_platform_rules(self) -> PlatformRules:
        if self._platform_rules_path and self._platform_rules_path.exists():
            data = json.loads(self._platform_rules_path.read_text(encoding="utf-8"))
            return PlatformRules(**data)
        # CLI uses relaxed rules
        return PlatformRules(
            schema_version="dm.platform-rules.v1",
            allowed_tools=["exec", "read", "write"],
            metadata_openclaw_whitelist=[],
            forbid_frontmatter_fields=[],
            storage_prefix="~/.doramagic/",
        )

    def get_concurrency_limit(self) -> int:
        return 4  # CLI has no agent limit, but keep reasonable
