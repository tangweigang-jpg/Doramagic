"""RepoWorker -- isolated single-repo extraction worker.

Each worker runs in its own thread with:
  - Independent working directory
  - Independent budget
  - Independent timeout
  - Domain-matched brick loading

Steps:
  1. Clone repo (or download ZIP)
  2. Extract repo_facts (deterministic, no LLM)
  3. Classify repo type (TOOL/FRAMEWORK/CATALOG)
  4. Extract soul (deep for TOOL/FRAMEWORK, shallow for CATALOG)
  5. Collect community signals (GitHub API, no LLM)
  6. Build standardized RepoExtractionEnvelope
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger("doramagic.worker")


@dataclass
class RepoWorkerContext:
    """Isolated context for one worker. Each worker gets its own."""

    worker_id: str
    repo_url: str
    repo_name: str
    full_name: str = ""
    repo_type: Literal["TOOL", "FRAMEWORK", "CATALOG"] = "TOOL"
    work_dir: Path = field(default_factory=lambda: Path("/tmp/doramagic-worker"))
    token_budget: int = 50000
    cost_budget_usd: float = 0.5
    timeout_seconds: int = 180
    max_retries: int = 2
    status: str = "pending"
    started_at: float | None = None
    finished_at: float | None = None


class RepoWorker:
    """Single-repo extraction worker. Runs in an isolated thread."""

    def __init__(self, ctx: RepoWorkerContext, adapter: object = None) -> None:
        self.ctx = ctx
        self.adapter = adapter
        self.ctx.work_dir.mkdir(parents=True, exist_ok=True)

    def run(self) -> Any:
        """Execute the full extraction pipeline. Returns RepoExtractionEnvelope."""
        from doramagic_contracts.worker import RepoExtractionEnvelope

        from .repo_type_classifier import classify_repo_type

        self.ctx.status = "running"
        self.ctx.started_at = time.monotonic()

        try:
            # Step 1: Clone/download
            local_path = self._clone_repo()
            if not local_path or Path(local_path).resolve() == Path.cwd().resolve():
                raise RuntimeError(
                    f"Clone returned empty/CWD path for {self.ctx.repo_name}; "
                    f"refusing to analyze current working directory"
                )

            # Step 2: Extract facts (deterministic, no LLM)
            facts = self._extract_facts(local_path)

            # Step 3: Classify repo type
            repo_type = classify_repo_type(facts, self.ctx.repo_name)
            self.ctx.repo_type = repo_type

            # Step 4: Load domain-matched bricks
            bricks = self._load_domain_bricks(facts)

            # Step 5: Extract soul
            if repo_type == "CATALOG":
                soul = self._shallow_extract(local_path, facts)
            else:
                soul = self._deep_extract(local_path, facts, bricks)

            # Step 6: Community signals
            signals = self._collect_community()

            # Step 7: Build envelope
            self.ctx.status = "done"
            self.ctx.finished_at = time.monotonic()
            elapsed = int((self.ctx.finished_at - self.ctx.started_at) * 1000)

            return RepoExtractionEnvelope(
                worker_id=self.ctx.worker_id,
                repo_name=self.ctx.repo_name,
                repo_url=self.ctx.repo_url,
                repo_type=repo_type,
                design_philosophy=soul.get("design_philosophy"),
                mental_model=soul.get("mental_model"),
                why_decisions=soul.get("why_decisions", []),
                unsaid_traps=soul.get("unsaid_traps", []),
                feature_inventory=soul.get("feature_inventory", []),
                community_signals=signals,
                extraction_confidence=self._compute_confidence(soul, facts),
                evidence_count=self._count_evidence(soul),
                wall_time_ms=elapsed,
                status="ok",
                dsd_metrics=soul.get("dsd_metrics"),
            )

        except Exception as e:
            self.ctx.status = "failed"
            self.ctx.finished_at = time.monotonic()
            elapsed = int((self.ctx.finished_at - self.ctx.started_at) * 1000)
            logger.exception(f"Worker {self.ctx.worker_id} failed: {e}")

            return RepoExtractionEnvelope(
                worker_id=self.ctx.worker_id,
                repo_name=self.ctx.repo_name,
                repo_url=self.ctx.repo_url,
                repo_type=self.ctx.repo_type,
                extraction_confidence=0.0,
                evidence_count=0,
                wall_time_ms=elapsed,
                status="failed",
                warnings=[str(e)[:500]],
            )

    def _clone_repo(self) -> str:
        """Clone or download the repo. Returns local path."""
        full_name = self.ctx.full_name or self.ctx.repo_name
        if not full_name and "github.com/" in self.ctx.repo_url:
            parts = self.ctx.repo_url.rstrip("/").split("github.com/")[-1].split("/")
            if len(parts) >= 2:
                full_name = f"{parts[0]}/{parts[1]}"

        if not full_name:
            raise ValueError(f"Cannot determine repo full_name for {self.ctx.repo_url}")

        try:
            from doramagic_community.github_search import download_repo

            local_path = download_repo(full_name, "main", str(self.ctx.work_dir / "repo"))
            if local_path:
                return local_path
        except Exception as e:
            logger.warning(f"Primary download failed for {full_name}: {e}")

        # Try with master branch
        try:
            from doramagic_community.github_search import download_repo

            local_path = download_repo(full_name, "master", str(self.ctx.work_dir / "repo"))
            if local_path:
                return local_path
        except Exception:
            pass

        raise RuntimeError(f"Failed to download {full_name}")

    def _extract_facts(self, local_path: str) -> dict:
        """Extract repo_facts.json deterministically (no LLM)."""
        try:
            from doramagic_extraction.stage0 import run_stage0

            result = run_stage0(local_path, str(self.ctx.work_dir / "artifacts"))
            facts_path = self.ctx.work_dir / "artifacts" / "repo_facts.json"
            if facts_path.exists():
                return json.loads(facts_path.read_text(encoding="utf-8"))
            return result if isinstance(result, dict) else {}
        except Exception as e:
            logger.warning(f"Stage0 failed for {self.ctx.repo_name}: {e}")
            return self._minimal_facts(local_path)

    def _minimal_facts(self, local_path: str) -> dict:
        """Minimal facts when stage0 fails."""
        p = Path(local_path)
        return {
            "repo_name": self.ctx.repo_name,
            "has_readme": (p / "README.md").exists() or (p / "readme.md").exists(),
            "has_docs": (p / "docs").exists(),
            "has_src": (p / "src").exists() or (p / "lib").exists(),
            "file_count": sum(1 for _ in p.rglob("*") if _.is_file()),
        }

    def _load_domain_bricks(self, facts: dict) -> list[dict]:
        """Load domain-matched bricks for this worker. Domain-isolated."""
        try:
            from doramagic_extraction.brick_injection import load_bricks_for_domain

            domain = facts.get("primary_domain", facts.get("domain", "general"))
            return load_bricks_for_domain(domain)
        except Exception:
            return []

    def _deep_extract(self, local_path: str, facts: dict, bricks: list[dict]) -> dict:
        """Deep soul extraction for TOOL/FRAMEWORK repos."""
        soul: dict = {}

        # Run the orchestration pipeline
        try:
            from doramagic_orchestration.phase_runner import run_single_project_pipeline

            result = run_single_project_pipeline(
                repo_path=local_path,
                output_dir=str(self.ctx.work_dir / "extraction"),
                adapter=self.adapter,
                router=None,
                config=None,
            )
        except Exception as e:
            logger.warning(f"Pipeline failed for {self.ctx.repo_name}: {e}")

        # Run LLM stages if router available
        try:
            from doramagic_extraction.llm_stage_runner import run_llm_stages
            from doramagic_shared_utils.capability_router import CapabilityRouter

            router = CapabilityRouter.from_config("models.json")
            run_llm_stages(local_path, str(self.ctx.work_dir / "extraction"), router)
        except Exception as e:
            logger.info(f"LLM stages skipped for {self.ctx.repo_name}: {e}")

        # Read soul data
        soul = self._read_soul_files(self.ctx.work_dir / "extraction")
        soul["repo_facts"] = facts
        return soul

    def _shallow_extract(self, local_path: str, facts: dict) -> dict:
        """Shallow extraction for CATALOG repos (awesome-lists).

        Focus on: taxonomy, selection criteria, maintenance patterns.
        Skip: deep code analysis.
        """
        soul: dict = {"repo_facts": facts}
        p = Path(local_path)

        # Read README for catalog analysis
        readme_path = p / "README.md"
        if not readme_path.exists():
            readme_path = p / "readme.md"

        if readme_path.exists():
            readme = readme_path.read_text(encoding="utf-8", errors="replace")[:10000]

            # Count links (catalog indicator)
            import re

            links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", readme)
            soul["feature_inventory"] = [
                f"Catalog entry: {name}"
                for name, url in links[:20]
                if "github.com" in url or "http" in url
            ]
            soul["design_philosophy"] = f"Curated catalog of {len(links)} resources"
            soul["mental_model"] = "Resource curation and categorization"

            # Extract section headings as taxonomy
            sections = re.findall(r"^##\s+(.+)", readme, re.MULTILINE)
            if sections:
                soul["why_decisions"] = [
                    {
                        "decision": f"Category: {s}",
                        "reasoning": "Catalog taxonomy",
                        "evidence": "README",
                    }
                    for s in sections[:10]
                ]

        return soul

    def _collect_community(self) -> list[dict]:
        """Collect community signals from GitHub API."""
        if not self.ctx.repo_url or "github.com" not in self.ctx.repo_url:
            return []

        try:
            from doramagic_community.community_signals import collect_community_signals

            token = os.environ.get("GITHUB_TOKEN")
            signals = collect_community_signals(self.ctx.repo_url, None, token)
            if isinstance(signals, dict):
                return signals.get("signals", [])[:5]
            return []
        except Exception as e:
            logger.warning(f"Community signals failed for {self.ctx.repo_name}: {e}")
            return []

    def _read_soul_files(self, output_dir: Path) -> dict:
        """Read extracted soul from output directory."""
        soul: dict = {}
        soul_dir = output_dir / "soul"
        if not soul_dir.exists():
            soul_dir = output_dir

        for name in ["essence.json", "stage1_output.json", "repo_soul.json"]:
            f = soul_dir / name
            if f.exists():
                try:
                    soul.update(json.loads(f.read_text(encoding="utf-8")))
                except (json.JSONDecodeError, OSError):
                    pass

        facts_path = output_dir / "artifacts" / "repo_facts.json"
        if facts_path.exists():
            try:
                soul["repo_facts"] = json.loads(facts_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass

        return soul

    def _compute_confidence(self, soul: dict, facts: dict) -> float:
        """Compute extraction confidence (0.0-1.0) from evidence density."""
        score = 0.0
        if soul.get("design_philosophy"):
            score += 0.2
        if soul.get("mental_model"):
            score += 0.15
        why_count = len(soul.get("why_decisions", []))
        score += min(0.3, why_count * 0.06)
        trap_count = len(soul.get("unsaid_traps", []))
        score += min(0.15, trap_count * 0.05)
        if facts.get("has_readme"):
            score += 0.1
        if facts.get("has_docs"):
            score += 0.1
        return min(1.0, score)

    def _count_evidence(self, soul: dict) -> int:
        """Count total evidence items in the soul."""
        count = 0
        count += len(soul.get("why_decisions", []))
        count += len(soul.get("unsaid_traps", []))
        count += len(soul.get("feature_inventory", []))
        if soul.get("design_philosophy"):
            count += 1
        if soul.get("mental_model"):
            count += 1
        return count
