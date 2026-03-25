"""Checkpoint-based lease manager.

Leases are persisted to JSON files. No background renewal — each executor
call validates and renews on entry. If expired, controller transitions to DEGRADED.

Design from v7 controller, enhanced with:
- TTL/expiry support (v7 had no expiry)
- Checkpoint-based renewal (no asyncio background tasks)
- Platform-agnostic (works on OpenClaw per-invocation and CLI long-running)
"""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


class LeaseError(Exception):
    """Raised when a lease operation fails."""


class LeaseManager:
    """Manages lease tokens for execution control.

    Each state transition issues a new lease token. The token must be
    presented to advance to the next state. Prevents replay attacks
    and out-of-order execution.
    """

    def __init__(self, leases_dir: Path, default_ttl_seconds: int = 300) -> None:
        self._leases_dir = leases_dir
        self._leases_dir.mkdir(parents=True, exist_ok=True)
        self._default_ttl = default_ttl_seconds

    def issue(self, step_name: str, ttl_seconds: int | None = None) -> str:
        """Issue a new lease token for a step.

        Returns the token string. The token is stored as a JSON file.
        """
        token = secrets.token_urlsafe(16)
        ttl = ttl_seconds or self._default_ttl
        now = datetime.now()
        lease_data = {
            "token": token,
            "step": step_name,
            "issued_at": now.isoformat(),
            "expires_at": (now + timedelta(seconds=ttl)).isoformat(),
            "consumed": False,
        }
        lease_file = self._leases_dir / f"{token}.json"
        lease_file.write_text(json.dumps(lease_data, ensure_ascii=False, indent=2), encoding="utf-8")
        return token

    def validate(self, token: str) -> bool:
        """Check if a token is valid (exists, not consumed, not expired)."""
        lease_file = self._leases_dir / f"{token}.json"
        if not lease_file.exists():
            return False
        lease_data = json.loads(lease_file.read_text(encoding="utf-8"))
        if lease_data.get("consumed", False):
            return False
        expires_at = datetime.fromisoformat(lease_data["expires_at"])
        if datetime.now() > expires_at:
            return False
        return True

    def consume(self, token: str) -> bool:
        """Validate and consume a token in one atomic operation.

        Returns True if consumed successfully, False otherwise.
        """
        lease_file = self._leases_dir / f"{token}.json"
        if not lease_file.exists():
            return False
        lease_data = json.loads(lease_file.read_text(encoding="utf-8"))
        if lease_data.get("consumed", False):
            return False
        expires_at = datetime.fromisoformat(lease_data["expires_at"])
        if datetime.now() > expires_at:
            return False
        lease_data["consumed"] = True
        lease_data["consumed_at"] = datetime.now().isoformat()
        lease_file.write_text(
            json.dumps(lease_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return True

    def renew(self, token: str, ttl_seconds: int | None = None) -> bool:
        """Extend a lease's expiry without consuming it.

        Used by the controller at phase boundaries for long-running phases.
        """
        lease_file = self._leases_dir / f"{token}.json"
        if not lease_file.exists():
            return False
        lease_data = json.loads(lease_file.read_text(encoding="utf-8"))
        if lease_data.get("consumed", False):
            return False
        ttl = ttl_seconds or self._default_ttl
        lease_data["expires_at"] = (datetime.now() + timedelta(seconds=ttl)).isoformat()
        lease_data["renewed_at"] = datetime.now().isoformat()
        lease_file.write_text(
            json.dumps(lease_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return True

    def get_current_step(self, token: str) -> Optional[str]:
        """Get the step name associated with a token."""
        lease_file = self._leases_dir / f"{token}.json"
        if not lease_file.exists():
            return None
        lease_data = json.loads(lease_file.read_text(encoding="utf-8"))
        return lease_data.get("step")
