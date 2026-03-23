"""Doramagic product pipeline orchestration."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import httpx

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_PROJECT_ROOT / "packages" / "contracts"))
sys.path.insert(0, str(_PROJECT_ROOT / "packages" / "cross_project"))
sys.path.insert(0, str(_PROJECT_ROOT / "packages" / "skill_compiler"))
sys.path.insert(0, str(_PROJECT_ROOT / "packages" / "platform_openclaw"))

from doramagic_contracts.base import (  # noqa: E402
    CandidateQualitySignals,
    CommunitySignals,
    Confidence,
    DiscoveryCandidate,
    EvidenceRef,
    KnowledgeAtom,
    NeedProfile,
    ProjectFingerprint,
    RepoRef,
    SearchDirection,
    SearchCoverageItem,
)
from doramagic_contracts.cross_project import (  # noqa: E402
    CompareConfig,
    CommunityKnowledge,
    CommunityKnowledgeItem,
    CompareInput,
    DiscoveryInput,
    DiscoveryConfig,
    DiscoveryResult,
    ExtractedProjectSummary,
    SynthesisConflict,
    SynthesisDecision,
    SynthesisInput,
    SynthesisReportData,
)
from doramagic_contracts.skill import (  # noqa: E402
    PlatformRules,
    SkillCompilerInput,
    SkillBundlePaths,
    ValidationInput,
)
from doramagic_cross_project.compare import run_compare  # noqa: E402
from doramagic_cross_project.discovery import run_discovery  # noqa: E402
from doramagic_cross_project.synthesis import run_synthesis  # noqa: E402
from doramagic_platform_openclaw.validator import run_validation  # noqa: E402
from doramagic_skill_compiler.compiler import run_skill_compiler  # noqa: E402

SEARCH_API_URL = "https://api.github.com/search/repositories"
CODELOAD_URL = "https://codeload.github.com/{owner}/{repo}/zip/refs/heads/{branch}"
MAX_PACK_FILES = 40
MAX_PACK_SNIPPET_BYTES = 2400
DEFAULT_TOP_K = 4
DEFAULT_TIMEOUT = 30.0
DEFAULT_STORAGE_PREFIX = "~/clawd/"
_CHINESE_TOKEN_RE = re.compile(r"[\u4e00-\u9fff]{2,}")
_ENGLISH_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{1,}")
_STOPWORDS = {
    "skill",
    "helper",
    "tool",
    "tools",
    "make",
    "build",
    "create",
    "want",
    "need",
    "我想",
    "帮我",
    "一个",
    "做",
}
_KEYWORD_ALIASES = {
    "菜谱": ["recipe", "cookbook", "meal planner", "kitchen"],
    "食谱": ["recipe", "cookbook", "meal planner", "kitchen"],
    "家庭": ["family", "home"],
    "家里": ["home", "household"],
    "东西": ["inventory", "asset tracker", "home inventory"],
    "管理": ["manager", "tracker", "organizer"],
    "radio": ["ham radio", "amateurradio", "logbook", "contest logger"],
    "ham": ["ham radio", "amateurradio", "logbook", "contest logger"],
    "记录": ["logbook", "tracker", "journal"],
    "日志": ["logbook", "logger"],
    "recipe": ["recipe", "cookbook", "meal planner", "kitchen"],
    "inventory": ["inventory", "asset tracker", "home inventory"],
}
_FRAMEWORK_HINTS = {
    "fastapi": "FastAPI",
    "flask": "Flask",
    "django": "Django",
    "streamlit": "Streamlit",
    "next": "Next.js",
    "react": "React",
    "vue": "Vue",
    "svelte": "Svelte",
    "sqlite": "SQLite",
    "postgres": "PostgreSQL",
    "mysql": "MySQL",
}
_EXTENSION_LANGUAGES = {
    ".py": "Python",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".java": "Java",
    ".kt": "Kotlin",
    ".swift": "Swift",
    ".php": "PHP",
}


def _model_validate(model_class, payload):
    if isinstance(payload, model_class):
        return payload
    if hasattr(model_class, "model_validate"):
        return model_class.model_validate(payload)
    return model_class(**payload)


def _model_dump(model):
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _safe_json_loads(raw: str):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return cleaned or "doramagic-run"


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run_id_from_request(user_input: str) -> str:
    digest = hashlib.sha1(user_input.encode("utf-8")).hexdigest()[:8]
    base = _slugify(user_input)[:40]
    return "{0}-{1}-{2}".format(
        datetime.now().strftime("%Y%m%d-%H%M%S"),
        base or "request",
        digest,
    )


def _priority_from_score(score: float) -> str:
    if score >= 8:
        return "high"
    if score >= 5:
        return "medium"
    return "low"


def _tokenize_request(user_input: str) -> List[str]:
    tokens = []
    for alias_key in sorted(_KEYWORD_ALIASES.keys(), key=len, reverse=True):
        if alias_key in user_input and alias_key not in tokens and alias_key not in _STOPWORDS:
            tokens.append(alias_key)
    for token in _CHINESE_TOKEN_RE.findall(user_input):
        if token not in tokens and token not in _STOPWORDS and len(token) <= 8:
            tokens.append(token)
    for token in _ENGLISH_TOKEN_RE.findall(user_input.lower()):
        if token not in tokens and token not in _STOPWORDS:
            tokens.append(token)
    return tokens[:8]


def _keyword_aliases(keywords: Sequence[str]) -> List[str]:
    aliases = []
    for keyword in keywords:
        if keyword not in aliases:
            aliases.append(keyword)
        for alias in _KEYWORD_ALIASES.get(keyword.lower(), []):
            if alias not in aliases:
                aliases.append(alias)
        for alias in _KEYWORD_ALIASES.get(keyword, []):
            if alias not in aliases:
                aliases.append(alias)
    return aliases


def _domain_id_from_need(need_profile: NeedProfile) -> str:
    if need_profile.keywords:
        return _slugify("-".join(need_profile.keywords[:3]))
    return _slugify(need_profile.intent or need_profile.raw_input)


def _human_domain_label(need_profile: NeedProfile) -> str:
    if need_profile.intent:
        return need_profile.intent
    if need_profile.keywords:
        return " / ".join(need_profile.keywords[:3])
    return need_profile.raw_input


def _render_frontmatter(skill_key: str, storage_prefix: str) -> str:
    lines = [
        "---",
        "skillKey: {0}".format(skill_key),
        "always: false",
        "os:",
        "  - macos",
        "  - linux",
        "install: Store runtime data under {0}{1}/".format(storage_prefix.rstrip("/") + "/", skill_key),
        "allowed-tools:",
        "  - exec",
        "  - read",
        "  - write",
        "---",
    ]
    return "\n".join(lines)


def _estimate_issue_activity(stars: Optional[int], updated_at: Optional[str]) -> str:
    if stars is not None and stars >= 1000:
        return "active"
    if updated_at:
        return "medium"
    return "low"


def _license_name(item: dict) -> Optional[str]:
    license_info = item.get("license")
    if isinstance(license_info, dict):
        return license_info.get("spdx_id") or license_info.get("name")
    return None


@contextmanager
def _temp_environ(overrides: Dict[str, Optional[str]]):
    original = {}
    for key, value in overrides.items():
        original[key] = os.environ.get(key)
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    try:
        yield
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@dataclass
class CandidateInfo:
    """Enriched discovery candidate used internally by the product pipeline."""

    candidate: DiscoveryCandidate
    owner: Optional[str] = None
    repo: Optional[str] = None
    default_branch: str = "main"
    description: str = ""
    stars: Optional[int] = None
    forks: Optional[int] = None
    updated_at: Optional[str] = None
    license_name: Optional[str] = None
    local_source: Optional[Path] = None
    source_payload: dict = field(default_factory=dict)


@dataclass
class RepoScan:
    languages: List[str]
    frameworks: List[str]
    entrypoints: List[str]
    commands: List[str]
    storage_paths: List[str]
    dependencies: List[str]
    repo_summary: str


@dataclass
class ExtractionArtifact:
    design_philosophy: str
    mental_model: str
    concepts: List[dict]
    workflows: List[dict]
    rules: List[dict]
    gotchas: List[dict]
    expert_narrative: str
    community_wisdom: str
    module_map: str


@dataclass
class ProjectPacket:
    candidate_info: CandidateInfo
    repo_ref: RepoRef
    repo_scan: RepoScan
    extraction: ExtractionArtifact
    fingerprint: ProjectFingerprint
    project_summary: ExtractedProjectSummary
    community_item: CommunityKnowledgeItem
    output_dir: Path
    warnings: List[str] = field(default_factory=list)
    metadata_only: bool = False


@dataclass
class DoramagicRunResult:
    run_dir: Path
    delivery_dir: Path
    need_profile: NeedProfile
    discovery_result: DiscoveryResult
    project_packets: List[ProjectPacket]
    synthesis_report: SynthesisReportData
    validation_status: str
    validation_details: dict
    skill_path: Path
    provenance_path: Path
    limitations_path: Path
    warnings: List[str] = field(default_factory=list)


class AnthropicLLMBackend:
    """Thin Anthropic SDK adapter with graceful availability checks."""

    def __init__(self) -> None:
        self._client = None
        self._enabled = False
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return
        try:
            import anthropic  # type: ignore
        except Exception:
            return
        try:
            base_url = os.environ.get("ANTHROPIC_BASE_URL")
            if base_url:
                self._client = anthropic.Anthropic(base_url=base_url)
            else:
                self._client = anthropic.Anthropic()
            self._enabled = True
        except Exception:
            self._client = None
            self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled and self._client is not None

    def complete_text(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        max_tokens: int = 2500,
    ) -> str:
        if not self.enabled:
            raise RuntimeError("Anthropic SDK is unavailable or not configured.")
        selected_model = model or os.environ.get("DORAMAGIC_DEFAULT_MODEL", "claude-sonnet-4-6")
        response = self._client.messages.create(
            model=selected_model,
            max_tokens=max_tokens,
            temperature=0.2,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        parts = []
        for block in getattr(response, "content", []):
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        return "".join(parts).strip()


class DoramagicProductPipeline:
    """Product-grade Doramagic orchestration over the race modules."""

    def __init__(
        self,
        project_root: Optional[Path] = None,
        runs_dir: Optional[Path] = None,
        http_client: Optional[httpx.Client] = None,
        llm_backend: Optional[AnthropicLLMBackend] = None,
    ) -> None:
        self.project_root = (project_root or _PROJECT_ROOT).resolve()
        self.runs_dir = (runs_dir or (self.project_root / "runs")).resolve()
        self.http_client = http_client or httpx.Client(timeout=DEFAULT_TIMEOUT, follow_redirects=True)
        self.llm_backend = llm_backend or AnthropicLLMBackend()
        self.soul_root = self.project_root / "skills" / "soul-extractor"
        self.platform_rules = PlatformRules()

    # ------------------------------------------------------------------
    # Phase A
    # ------------------------------------------------------------------

    def build_need_profile(self, user_input: str) -> NeedProfile:
        if self.llm_backend.enabled:
            return self._build_need_profile_via_llm(user_input)
        return self._build_need_profile_heuristic(user_input)

    def _build_need_profile_via_llm(self, user_input: str) -> NeedProfile:
        system_prompt = (
            "You are Doramagic Phase A. Parse one user request into a JSON object compatible "
            "with the NeedProfile model. Return JSON only."
        )
        user_prompt = (
            "Return JSON with keys raw_input, keywords, intent, search_directions, constraints, "
            "quality_expectations. search_directions must be a list of {direction, priority}.\n\n"
            "User request:\n{0}".format(user_input)
        )
        raw = self.llm_backend.complete_text(system_prompt, user_prompt, max_tokens=1400)
        payload = _safe_json_loads(raw)
        payload.setdefault("raw_input", user_input)
        payload.setdefault("quality_expectations", {})
        payload.setdefault("constraints", [])
        payload.setdefault("keywords", _tokenize_request(user_input))
        payload.setdefault("intent", user_input)
        payload.setdefault(
            "search_directions",
            [{"direction": keyword, "priority": "high"} for keyword in payload["keywords"][:3]],
        )
        return _model_validate(NeedProfile, payload)

    def _build_need_profile_heuristic(self, user_input: str) -> NeedProfile:
        keywords = _tokenize_request(user_input)
        aliases = _keyword_aliases(keywords)
        search_directions = []
        for index, alias in enumerate(aliases[:5]):
            search_directions.append(
                SearchDirection(
                    direction=alias,
                    priority="high" if index < 2 else "medium",
                )
            )
        if not search_directions:
            search_directions = [SearchDirection(direction=user_input, priority="high")]
        constraints = [
            "Output an OpenClaw skill bundle",
            "Prefer local-first, low-dependency patterns",
        ]
        if "家庭" in user_input or "家里" in user_input or "home" in user_input.lower():
            constraints.append("Design for personal or household usage before multi-user scale")
        if "skill" in user_input.lower():
            constraints.append("Keep the interaction surface suitable for an OpenClaw skill")
        return NeedProfile(
            raw_input=user_input,
            keywords=keywords or aliases[:3] or ["open source", "automation"],
            intent=user_input.strip(),
            search_directions=search_directions,
            constraints=constraints,
            quality_expectations={
                "coverage": "Prefer 3-5 reference projects when available",
                "honesty": "Mark partial coverage instead of inventing certainty",
            },
        )

    # ------------------------------------------------------------------
    # Phase B
    # ------------------------------------------------------------------

    def discover_candidates(self, need_profile: NeedProfile) -> Tuple[DiscoveryResult, List[CandidateInfo], List[str]]:
        warnings = []
        try:
            discovery, candidate_infos = self._discover_candidates_via_github(need_profile)
            if candidate_infos:
                return discovery, candidate_infos, warnings
        except Exception as exc:
            warnings.append("GitHub Search API failed: {0}".format(exc))

        fallback = run_discovery(
            DiscoveryInput(
                need_profile=need_profile,
                config=DiscoveryConfig(top_k_final=DEFAULT_TOP_K),
            )
        )
        if fallback.data is not None and fallback.data.candidates:
            candidate_infos = [
                CandidateInfo(
                    candidate=candidate,
                    description=candidate.contribution,
                    stars=candidate.quality_signals.stars,
                    forks=candidate.quality_signals.forks,
                    updated_at=candidate.quality_signals.last_updated,
                    license_name=candidate.quality_signals.license,
                )
                for candidate in fallback.data.candidates
            ]
            warnings.append("Using degraded fallback discovery instead of live GitHub search.")
            return fallback.data, candidate_infos, warnings

        offline_result, offline_infos = self._offline_candidates_from_need(need_profile)
        warnings.append("No live candidates discovered. Falling back to metadata-only offline reference patterns.")
        return offline_result, offline_infos, warnings

    def _discover_candidates_via_github(self, need_profile: NeedProfile) -> Tuple[DiscoveryResult, List[CandidateInfo]]:
        aliases = _keyword_aliases(need_profile.keywords)
        search_terms = []
        for alias in aliases[:6]:
            normalized = alias.replace(" ", "+")
            if normalized not in search_terms:
                search_terms.append(normalized)
        if not search_terms:
            search_terms.append(_slugify(need_profile.intent).replace("-", "+"))

        items = {}
        for term in search_terms[:4]:
            response = self.http_client.get(
                SEARCH_API_URL,
                params={
                    "q": "{0} in:name,description,readme archived:false fork:false".format(term),
                    "sort": "stars",
                    "order": "desc",
                    "per_page": 5,
                },
                headers={"Accept": "application/vnd.github+json", "User-Agent": "Doramagic/0.1"},
            )
            response.raise_for_status()
            payload = response.json()
            for item in payload.get("items", []):
                items[item["html_url"]] = item

        ranked_items = sorted(
            items.values(),
            key=lambda item: (
                -self._github_candidate_score(item, need_profile),
                -(item.get("stargazers_count") or 0),
                item.get("full_name") or "",
            ),
        )
        chosen = ranked_items[:DEFAULT_TOP_K]
        candidates = []
        candidate_infos = []
        for index, item in enumerate(chosen, start=1):
            full_name = item.get("full_name", "")
            owner, repo = full_name.split("/", 1) if "/" in full_name else (None, None)
            quick_score = round(self._github_candidate_score(item, need_profile), 2)
            quality = CandidateQualitySignals(
                stars=item.get("stargazers_count"),
                forks=item.get("forks_count"),
                last_updated=item.get("updated_at"),
                has_readme=True,
                issue_activity=_estimate_issue_activity(item.get("stargazers_count"), item.get("updated_at")),
                license=_license_name(item),
            )
            candidate = DiscoveryCandidate(
                candidate_id="cand-{0:03d}".format(index),
                name=item.get("name", "candidate-{0}".format(index)),
                url=item["html_url"],
                type="github_repo",
                relevance=_priority_from_score(quick_score),
                contribution=item.get("description") or "GitHub repository discovered for the requested need.",
                quick_score=min(10.0, quick_score),
                quality_signals=quality,
                selected_for_phase_c=index <= 3,
                selected_for_phase_d=index <= DEFAULT_TOP_K,
            )
            candidates.append(candidate)
            candidate_infos.append(
                CandidateInfo(
                    candidate=candidate,
                    owner=owner,
                    repo=repo,
                    default_branch=item.get("default_branch") or "main",
                    description=item.get("description") or "",
                    stars=item.get("stargazers_count"),
                    forks=item.get("forks_count"),
                    updated_at=item.get("updated_at"),
                    license_name=_license_name(item),
                    source_payload=item,
                )
            )

        coverage = []
        combined_text = " ".join(
            "{0} {1}".format(info.candidate.name, info.description).lower() for info in candidate_infos
        )
        for direction in need_profile.search_directions:
            status = "covered" if direction.direction.lower() in combined_text else "partial"
            coverage.append(SearchCoverageItem(direction=direction.direction, status=status, notes=None))

        return DiscoveryResult(candidates=candidates, search_coverage=coverage), candidate_infos

    def _github_candidate_score(self, item: dict, need_profile: NeedProfile) -> float:
        text = " ".join(
            [
                item.get("name") or "",
                item.get("description") or "",
                " ".join(topic for topic in item.get("topics") or []),
            ]
        ).lower()
        keyword_hits = 0
        for keyword in _keyword_aliases(need_profile.keywords):
            if keyword.lower() in text:
                keyword_hits += 1
        stars = float(item.get("stargazers_count") or 0)
        recency = 1.0 if item.get("updated_at") else 0.2
        return min(10.0, 4.0 + keyword_hits * 1.2 + min(stars / 500.0, 3.0) + recency)

    def _offline_candidates_from_need(
        self,
        need_profile: NeedProfile,
    ) -> Tuple[DiscoveryResult, List[CandidateInfo]]:
        aliases = _keyword_aliases(need_profile.keywords) or [need_profile.intent]
        base_terms = []
        for item in aliases:
            if item not in base_terms:
                base_terms.append(item)
        if not base_terms:
            base_terms = ["open source", "workflow", "skill"]

        templates = [
            ("reference-pattern", "tutorial", "Reference implementation patterns"),
            ("storage-pattern", "use_case", "State and storage trade-offs"),
            ("interaction-pattern", "tutorial", "Interaction and workflow patterns"),
        ]
        candidates = []
        infos = []
        for index, (suffix, candidate_type, description_suffix) in enumerate(templates, start=1):
            term = base_terms[min(index - 1, len(base_terms) - 1)]
            query = term.replace(" ", "+")
            candidate = DiscoveryCandidate(
                candidate_id="offline-{0:03d}".format(index),
                name="{0}-{1}".format(_slugify(term) or "domain", suffix),
                url="https://github.com/search?q={0}".format(query),
                type=candidate_type,
                relevance="medium",
                contribution="{0} for {1}".format(description_suffix, need_profile.intent),
                quick_score=4.0 + (0.2 * index),
                quality_signals=CandidateQualitySignals(
                    stars=None,
                    forks=None,
                    last_updated=None,
                    has_readme=False,
                    issue_activity=None,
                    license=None,
                ),
                selected_for_phase_c=index <= 3,
                selected_for_phase_d=index <= 3,
            )
            candidates.append(candidate)
            infos.append(
                CandidateInfo(
                    candidate=candidate,
                    description=candidate.contribution,
                    stars=None,
                    forks=None,
                    updated_at=None,
                    license_name=None,
                )
            )

        result = DiscoveryResult(
            candidates=candidates,
            search_coverage=[
                SearchCoverageItem(
                    direction=item.direction,
                    status="partial",
                    notes="Offline fallback pattern only; no live repository downloaded.",
                )
                for item in need_profile.search_directions
            ],
            no_candidate_reason="Live GitHub discovery unavailable; using metadata-only offline patterns.",
        )
        return result, infos

    # ------------------------------------------------------------------
    # Phase C / D
    # ------------------------------------------------------------------

    def extract_projects(
        self,
        need_profile: NeedProfile,
        run_dir: Path,
        candidate_infos: Sequence[CandidateInfo],
    ) -> Tuple[List[ProjectPacket], List[str]]:
        packets = []
        warnings = []
        projects_dir = run_dir / "projects"
        projects_dir.mkdir(parents=True, exist_ok=True)
        for candidate_info in candidate_infos[:3]:
            try:
                packet = self.extract_single_project(need_profile, candidate_info, projects_dir)
                packets.append(packet)
            except Exception as exc:
                warnings.append(
                    "Project extraction failed for {0}: {1}".format(candidate_info.candidate.name, exc)
                )
        return packets, warnings

    def extract_single_project(
        self,
        need_profile: NeedProfile,
        candidate_info: CandidateInfo,
        projects_dir: Path,
    ) -> ProjectPacket:
        project_dir = projects_dir / candidate_info.candidate.candidate_id
        project_dir.mkdir(parents=True, exist_ok=True)
        repo_dir = project_dir / "artifacts" / "_repo"
        metadata_only = False
        warnings = []

        if candidate_info.local_source is not None:
            if repo_dir.exists():
                shutil.rmtree(repo_dir)
            shutil.copytree(candidate_info.local_source, repo_dir)
        elif candidate_info.owner and candidate_info.repo:
            try:
                self.download_candidate_repo(candidate_info, repo_dir)
            except Exception as exc:
                metadata_only = True
                warnings.append("Repository download failed: {0}".format(exc))
        else:
            metadata_only = True
            warnings.append("Candidate has no downloadable GitHub repository metadata.")

        self._prepare_project_artifacts(candidate_info, project_dir, repo_dir, metadata_only)
        repo_scan = self._scan_project_repo(repo_dir if repo_dir.exists() else None, candidate_info, need_profile)
        extraction = self._extract_knowledge(project_dir, need_profile, candidate_info, repo_scan, metadata_only)
        repo_ref = self._build_repo_ref(candidate_info, repo_dir if repo_dir.exists() else project_dir / "metadata")
        fingerprint = self._build_project_fingerprint(need_profile, repo_ref, repo_scan, extraction)
        summary = self._build_project_summary(fingerprint)
        community_item = self._build_community_item(candidate_info, extraction, repo_scan)
        return ProjectPacket(
            candidate_info=candidate_info,
            repo_ref=repo_ref,
            repo_scan=repo_scan,
            extraction=extraction,
            fingerprint=fingerprint,
            project_summary=summary,
            community_item=community_item,
            output_dir=project_dir,
            warnings=warnings,
            metadata_only=metadata_only,
        )

    def download_candidate_repo(self, candidate_info: CandidateInfo, target_dir: Path) -> None:
        if not candidate_info.owner or not candidate_info.repo:
            raise ValueError("Missing GitHub owner/repo for candidate download.")
        url = CODELOAD_URL.format(
            owner=candidate_info.owner,
            repo=candidate_info.repo,
            branch=candidate_info.default_branch,
        )
        response = self.http_client.get(url)
        response.raise_for_status()
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            temp_extract_dir = target_dir.parent / "_tmp_extract"
            if temp_extract_dir.exists():
                shutil.rmtree(temp_extract_dir)
            archive.extractall(temp_extract_dir)
            extracted_roots = [path for path in temp_extract_dir.iterdir() if path.is_dir()]
            if not extracted_roots:
                raise ValueError("Downloaded repository archive contained no root directory.")
            root = extracted_roots[0]
            if target_dir.exists():
                shutil.rmtree(target_dir)
            shutil.move(str(root), str(target_dir))
            shutil.rmtree(temp_extract_dir, ignore_errors=True)

    def _prepare_project_artifacts(
        self,
        candidate_info: CandidateInfo,
        project_dir: Path,
        repo_dir: Path,
        metadata_only: bool,
    ) -> None:
        artifacts_dir = project_dir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        if not metadata_only and repo_dir.exists():
            self._try_subprocess(
                [
                    "bash",
                    str(self.soul_root / "scripts" / "prepare-repo.sh"),
                    str(repo_dir),
                    str(project_dir),
                ],
                cwd=self.project_root,
            )
            self._try_subprocess(
                [
                    "python3",
                    str(self.soul_root / "scripts" / "extract_repo_facts.py"),
                    "--repo-path",
                    str(repo_dir),
                    "--output-dir",
                    str(project_dir),
                ],
                cwd=self.project_root,
            )
            self._try_subprocess(
                [
                    "python3",
                    str(self.soul_root / "scripts" / "collect-community-signals.py"),
                    "--repo-url",
                    candidate_info.candidate.url,
                    "--repo-path",
                    str(repo_dir),
                    "--output",
                    str(artifacts_dir / "community_signals.md"),
                ],
                cwd=self.project_root,
            )
        packed = self._build_repo_pack(repo_dir if repo_dir.exists() else None, candidate_info)
        _write_text(artifacts_dir / "packed_compressed.xml", packed)
        _write_text(artifacts_dir / "packed_full.xml", packed)
        if not (artifacts_dir / "community_signals.md").exists():
            _write_text(
                artifacts_dir / "community_signals.md",
                self._fallback_community_signals(candidate_info),
            )

    def _build_repo_pack(self, repo_dir: Optional[Path], candidate_info: CandidateInfo) -> str:
        header = [
            "<repo name=\"{0}\">".format(candidate_info.candidate.name),
            "<summary>{0}</summary>".format(candidate_info.description or candidate_info.candidate.contribution),
        ]
        if repo_dir is None or not repo_dir.exists():
            header.append("<note>metadata-only candidate</note>")
            header.append("</repo>")
            return "\n".join(header)

        files = []
        for path in sorted(repo_dir.rglob("*")):
            if not path.is_file():
                continue
            if ".git" in path.parts or "node_modules" in path.parts or "__pycache__" in path.parts:
                continue
            relative = path.relative_to(repo_dir).as_posix()
            files.append(relative)
            if len(files) >= MAX_PACK_FILES:
                break
        body = []
        for relative in files:
            path = repo_dir / relative
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")[:MAX_PACK_SNIPPET_BYTES]
            except Exception:
                continue
            body.extend(
                [
                    "<file path=\"{0}\">".format(relative),
                    content,
                    "</file>",
                ]
            )
        return "\n".join(header + body + ["</repo>"])

    def _fallback_community_signals(self, candidate_info: CandidateInfo) -> str:
        lines = [
            "# community_signals",
            "",
            "- SIG-001 | metadata | Candidate discovered by Doramagic | {0}".format(
                candidate_info.description or candidate_info.candidate.contribution
            ),
            "- SIG-002 | license | {0}".format(candidate_info.license_name or "license unknown"),
        ]
        return "\n".join(lines) + "\n"

    def _scan_project_repo(
        self,
        repo_dir: Optional[Path],
        candidate_info: CandidateInfo,
        need_profile: NeedProfile,
    ) -> RepoScan:
        if repo_dir is None or not repo_dir.exists():
            summary = candidate_info.description or candidate_info.candidate.contribution or need_profile.intent
            return RepoScan(
                languages=["Unknown"],
                frameworks=[],
                entrypoints=[],
                commands=[],
                storage_paths=["~/clawd/{0}/".format(_slugify(candidate_info.candidate.name))],
                dependencies=[],
                repo_summary=summary,
            )

        languages = []
        frameworks = []
        dependencies = []
        entrypoints = []
        commands = []
        storage_paths = []

        readme_excerpt = ""
        for path in sorted(repo_dir.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(repo_dir).as_posix()
            if path.suffix.lower() in _EXTENSION_LANGUAGES:
                language = _EXTENSION_LANGUAGES[path.suffix.lower()]
                if language not in languages:
                    languages.append(language)
            if path.name.lower() in ("main.py", "app.py", "cli.py", "manage.py", "index.js", "server.js"):
                if relative not in entrypoints:
                    entrypoints.append(relative)
            if "readme" in path.name.lower() and not readme_excerpt:
                try:
                    readme_excerpt = path.read_text(encoding="utf-8", errors="ignore")[:1500]
                except Exception:
                    readme_excerpt = ""
            if path.name == "package.json":
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    data = {}
                for dep_name in sorted((data.get("dependencies") or {}).keys()):
                    if dep_name not in dependencies:
                        dependencies.append(dep_name)
                for script_name in sorted((data.get("scripts") or {}).keys()):
                    command = "npm run {0}".format(script_name)
                    if command not in commands:
                        commands.append(command)
            if path.name in ("requirements.txt", "pyproject.toml", "Pipfile"):
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    text = ""
                for line in text.splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or line.startswith("["):
                        continue
                    dependency = re.split(r"[<>= ]+", line)[0]
                    if dependency and dependency not in dependencies:
                        dependencies.append(dependency)
            if any(token in relative.lower() for token in ("sqlite", "db", "database", "storage", "data", ".json")):
                if relative not in storage_paths and len(storage_paths) < 6:
                    storage_paths.append(relative)

        combined_text = " ".join([readme_excerpt, " ".join(dependencies), " ".join(entrypoints)]).lower()
        for token, framework in _FRAMEWORK_HINTS.items():
            if token in combined_text and framework not in frameworks:
                frameworks.append(framework)

        if not entrypoints:
            for candidate in ("src/main.py", "src/app.py", "main.py", "app.py"):
                if (repo_dir / candidate).exists():
                    entrypoints.append(candidate)

        if not commands:
            for candidate in ("manage.py", "cli.py"):
                if (repo_dir / candidate).exists():
                    commands.append("python3 {0}".format(candidate))

        if not storage_paths:
            storage_paths.append("~/clawd/{0}/".format(_slugify(candidate_info.candidate.name)))

        repo_summary = self._summarize_repo(readme_excerpt, candidate_info, need_profile)
        return RepoScan(
            languages=languages or ["Unknown"],
            frameworks=frameworks,
            entrypoints=entrypoints[:5],
            commands=commands[:8],
            storage_paths=storage_paths[:6],
            dependencies=dependencies[:12],
            repo_summary=repo_summary,
        )

    def _summarize_repo(
        self,
        readme_excerpt: str,
        candidate_info: CandidateInfo,
        need_profile: NeedProfile,
    ) -> str:
        if readme_excerpt:
            paragraph = readme_excerpt.split("\n\n", 1)[0]
            summary = re.sub(r"\s+", " ", paragraph).strip("# ").strip()
            if summary:
                return summary[:240]
        return candidate_info.description or candidate_info.candidate.contribution or need_profile.intent

    def _extract_knowledge(
        self,
        project_dir: Path,
        need_profile: NeedProfile,
        candidate_info: CandidateInfo,
        repo_scan: RepoScan,
        metadata_only: bool,
    ) -> ExtractionArtifact:
        if self.llm_backend.enabled and not metadata_only:
            try:
                # Call Soul Extractor's extract.py
                repo_dir = project_dir / "artifacts" / "_repo"
                if repo_dir.exists():
                    self._try_subprocess(
                        [
                            "python3",
                            str(self.soul_root / "scripts" / "extract.py"),
                            str(repo_dir),
                            str(project_dir),
                        ],
                        cwd=self.project_root,
                    )
                    return self._parse_extraction_output(project_dir, candidate_info, need_profile, repo_scan)
            except Exception as e:
                print(f"Soul Extractor failed for {candidate_info.candidate.name}: {e}")
        
        return self._extract_knowledge_heuristic(project_dir, need_profile, candidate_info, repo_scan, metadata_only)

    def _parse_extraction_output(
        self,
        project_dir: Path,
        candidate_info: CandidateInfo,
        need_profile: NeedProfile,
        repo_scan: RepoScan,
    ) -> ExtractionArtifact:
        soul_dir = project_dir / "soul"
        cards_dir = soul_dir / "cards"
        
        design_philosophy = ""
        mental_model = ""
        soul_file = soul_dir / "00-soul.md"
        if soul_file.exists():
            content = soul_file.read_text(encoding="utf-8")
            dp_match = re.search(r"## 6\. 设计哲学\n(.*?)(?=\n##|$)", content, re.DOTALL)
            if dp_match:
                design_philosophy = dp_match.group(1).strip()
            mm_match = re.search(r"## 7\. 心智模型\n(.*?)(?=\n##|$)", content, re.DOTALL)
            if mm_match:
                mental_model = mm_match.group(1).strip()

        concepts = self._load_cards(cards_dir / "concepts")
        workflows = self._load_cards(cards_dir / "workflows")
        all_rules = self._load_cards(cards_dir / "rules")
        
        rules = [r for r in all_rules if r.get("type") != "UNSAID_GOTCHA"]
        gotchas = [r for r in all_rules if r.get("type") == "UNSAID_GOTCHA"]
        
        if not gotchas:
            # Maybe they are not typed this way in all_rules, try another filter or just take some
            gotchas = all_rules[5:] if len(all_rules) > 5 else []
            rules = all_rules[:5]

        expert_narrative = ""
        en_file = soul_dir / "expert_narrative.md"
        if en_file.exists():
            expert_narrative = en_file.read_text(encoding="utf-8")
            
        community_wisdom = ""
        cw_file = soul_dir / "community-wisdom.md"
        if cw_file.exists():
            community_wisdom = cw_file.read_text(encoding="utf-8")
            
        module_map = ""
        mm_file = soul_dir / "module-map.md"
        if mm_file.exists():
            module_map = mm_file.read_text(encoding="utf-8")

        return ExtractionArtifact(
            design_philosophy=design_philosophy or "Local-first workflow priority.",
            mental_model=mental_model or "Unified command surface for domain operations.",
            concepts=concepts,
            workflows=workflows,
            rules=rules,
            gotchas=gotchas,
            expert_narrative=expert_narrative,
            community_wisdom=community_wisdom,
            module_map=module_map,
        )

    def _load_cards(self, directory: Path) -> List[dict]:
        cards = []
        if not directory.exists():
            return cards
        for path in directory.glob("*.md"):
            try:
                content = path.read_text(encoding="utf-8")
                # Simple YAML frontmatter parser
                match = re.search(r"^---\n(.*?)\n---\n(.*)", content, re.DOTALL)
                if match:
                    yaml_text = match.group(1)
                    body = match.group(2).strip()
                    card = {}
                    # Very simple key: value parser
                    for line in yaml_text.splitlines():
                        if ":" in line:
                            k, v = line.split(":", 1)
                            k = k.strip()
                            v = v.strip().strip('"').strip("'")
                            card[k] = v
                    card["body"] = body
                    # Map some expected fields if missing
                    card.setdefault("card_id", path.stem)
                    card.setdefault("title", card.get("title", path.stem))
                    cards.append(card)
            except Exception:
                continue
        return sorted(cards, key=lambda x: x.get("card_id", ""))

    def _extract_knowledge_via_llm(
        self,
        project_dir: Path,
        need_profile: NeedProfile,
        candidate_info: CandidateInfo,
        repo_scan: RepoScan,
    ) -> ExtractionArtifact:
        packed = (project_dir / "artifacts" / "packed_compressed.xml").read_text(encoding="utf-8")
        stage1_prompt = (self.soul_root / "stages" / "STAGE-1-essence.md").read_text(encoding="utf-8")
        system_prompt = (
            "You are Doramagic Phase C. Read the provided stage instruction and repository digest. "
            "Return strict JSON only."
        )
        user_prompt = (
            "Stage instruction:\n{0}\n\nRepository digest:\n{1}\n\n"
            "Return JSON with keys q1,q2,q3,q4,q5,q6,q7.".format(stage1_prompt, packed[:120000])
        )
        answers = _safe_json_loads(self.llm_backend.complete_text(system_prompt, user_prompt, max_tokens=2000))
        artifact = self._extract_knowledge_heuristic(project_dir, need_profile, candidate_info, repo_scan, False)
        artifact.design_philosophy = answers.get("q6") or artifact.design_philosophy
        artifact.mental_model = answers.get("q7") or artifact.mental_model
        artifact.expert_narrative = artifact.expert_narrative.replace(
            artifact.design_philosophy, answers.get("q6") or artifact.design_philosophy
        ).replace(artifact.mental_model, answers.get("q7") or artifact.mental_model)
        return artifact

    def _extract_knowledge_heuristic(
        self,
        project_dir: Path,
        need_profile: NeedProfile,
        candidate_info: CandidateInfo,
        repo_scan: RepoScan,
        metadata_only: bool,
    ) -> ExtractionArtifact:
        domain_label = _human_domain_label(need_profile)
        primary_keyword = need_profile.keywords[0] if need_profile.keywords else "workflow"
        storage_label = self._storage_label(repo_scan)
        interface_label = self._interface_label(repo_scan)
        design_philosophy = (
            "Favor a local-first {0} workflow so the skill stays lightweight, transparent, and "
            "easy to adapt to OpenClaw.".format(primary_keyword)
        )
        if metadata_only:
            design_philosophy += " This extraction is metadata-driven because the full repository was not available."
        mental_model = (
            "Treat this project as a focused {0} control loop: capture intent, normalize data, "
            "store state locally, and surface the next action without ceremony.".format(primary_keyword)
        )

        concepts = [
            {
                "card_id": "CC-001",
                "title": "{0} Core Domain".format(candidate_info.candidate.name),
                "identity": repo_scan.repo_summary,
                "is_items": ["A reference pattern for {0}".format(domain_label), "Grounded in real open-source usage"],
                "is_not_items": ["Not an OpenClaw-ready bundle by itself", "Not a full platform rewrite"],
                "attributes": [("Primary need", need_profile.intent), ("Languages", ", ".join(repo_scan.languages))],
                "boundaries": [
                    "Starts at the user's request for {0}".format(domain_label),
                    "Ends at a durable {0} artifact or interaction".format(primary_keyword),
                ],
                "evidence": [self._evidence_ref(project_dir, repo_scan.entrypoints[:1], "artifact_ref", "repo-summary")],
            },
            {
                "card_id": "CC-002",
                "title": "{0} Storage Pattern".format(candidate_info.candidate.name),
                "identity": "Persistent state is organized around {0}.".format(storage_label),
                "is_items": ["A storage and retrieval concern", "Important for portability"],
                "is_not_items": ["Not a cloud-only dependency", "Not a multi-tenant platform guarantee"],
                "attributes": [("Storage", storage_label), ("Dependencies", ", ".join(repo_scan.dependencies[:4]) or "minimal")],
                "boundaries": ["Starts at write/update operations", "Ends when state is queryable again"],
                "evidence": [self._evidence_ref(project_dir, repo_scan.storage_paths[:1], "artifact_ref", "storage")],
            },
            {
                "card_id": "CC-003",
                "title": "{0} Interaction Surface".format(candidate_info.candidate.name),
                "identity": "Users interact through {0}.".format(interface_label),
                "is_items": ["An entrypoint boundary", "A clue for OpenClaw tool design"],
                "is_not_items": ["Not the underlying storage layer", "Not the full architecture"],
                "attributes": [("Entrypoints", ", ".join(repo_scan.entrypoints) or "undiscovered"), ("Commands", ", ".join(repo_scan.commands) or "none")],
                "boundaries": ["Starts at a read/write/exec entrypoint", "Delegates to domain logic and persistence"],
                "evidence": [self._evidence_ref(project_dir, repo_scan.entrypoints[:1], "file_line", "entrypoint")],
            },
        ]

        workflows = [
            {
                "card_id": "WF-001",
                "title": "Capture {0} intent".format(primary_keyword),
                "steps": [
                    ("Read user input and normalize the request", self._workflow_ref(repo_scan.entrypoints[:1])),
                    ("Translate the request into a domain record", self._workflow_ref(repo_scan.storage_paths[:1])),
                    ("Return a concise result or next step", self._workflow_ref(repo_scan.entrypoints[-1:])),
                ],
                "failure_modes": [
                    "Input shape drifts away from the expected schema",
                    "A required field is omitted and later persistence becomes ambiguous",
                ],
            },
            {
                "card_id": "WF-002",
                "title": "Persist {0} state".format(primary_keyword),
                "steps": [
                    ("Validate and serialize the normalized record", self._workflow_ref(repo_scan.storage_paths[:1])),
                    ("Write to the chosen storage layer", self._workflow_ref(repo_scan.storage_paths[:1])),
                    ("Expose the updated state to the next interaction", self._workflow_ref(repo_scan.entrypoints[:1])),
                ],
                "failure_modes": [
                    "State is written to an implicit location the operator cannot inspect",
                    "Storage format changes without a migration story",
                ],
            },
            {
                "card_id": "WF-003",
                "title": "Adapt source logic into an OpenClaw skill",
                "steps": [
                    ("Identify the smallest reusable capability from the upstream repo", self._workflow_ref(repo_scan.entrypoints[:1])),
                    ("Wrap it behind read/write/exec tool boundaries", self._workflow_ref(repo_scan.commands[:1])),
                    ("Document limits and provenance before delivery", "delivery/PROVENANCE.md"),
                ],
                "failure_modes": [
                    "Upstream assumptions leak into the skill without platform adaptation",
                    "Traceability is lost when knowledge is copied without file anchors",
                ],
            },
        ]

        rules = [
            self._rule_card("DR-001", candidate_info.candidate.name, "DEFAULT_BEHAVIOR", "Keep the skill local-first", "HIGH", "If a feature can run without a hosted dependency, prefer local execution and storage.", ["Store data under ~/clawd/", "Keep dependencies minimal"], ["Assume a cloud service is always available"], "OpenClaw skills must work even when external APIs are unavailable.", ["repo_facts.json", "README"],),
            self._rule_card("DR-002", candidate_info.candidate.name, "DEFAULT_BEHAVIOR", "Preserve a visible data model", "MEDIUM", "If the skill stores structured state, use a human-inspectable format or document the storage contract.", ["Keep JSON/SQLite schemas discoverable", "Explain what each stored record means"], ["Hide durable state in undocumented temp files"], "Users need to inspect and trust the artifact Doramagic produces.", [storage_label],),
            self._rule_card("DR-003", candidate_info.candidate.name, "DEFAULT_BEHAVIOR", "Bound the interaction surface", "MEDIUM", "If an upstream project exposes many entrypoints, keep only the smallest read/write/exec workflow needed for the skill.", ["Choose one clear primary workflow", "Document the supported commands"], ["Mirror every upstream command just because it exists"], "OpenClaw skills should feel intentional, not like a raw CLI dump.", [interface_label],),
            self._rule_card("DR-004", candidate_info.candidate.name, "DESIGN_DECISION", "Carry the upstream philosophy forward", "MEDIUM", "If the upstream repo solves the same user need, preserve its core design tradeoff rather than rewriting it from scratch.", ["Keep the design philosophy explicit in SKILL.md", "Adapt without erasing the why"], ["Copy functionality while dropping the rationale"], design_philosophy, [need_profile.intent],),
            self._rule_card("DR-005", candidate_info.candidate.name, "DESIGN_DECISION", "Ship limits together with capability", "LOW", "If coverage is partial, state the missing edges in LIMITATIONS.md instead of pretending full support.", ["Mark unsupported cases", "List unresolved conflicts"], ["Imply complete domain coverage"], "Doramagic values honest partial coverage over invented certainty.", ["LIMITATIONS.md"],),
        ]

        gotchas = [
            self._rule_card("DR-101", candidate_info.candidate.name, "COMMUNITY_GOTCHA", "Path assumptions drift across machines", "HIGH", "If a repo writes relative files implicitly, packaging it as a skill can break once the working directory changes.", ["Normalize all durable paths under ~/clawd/", "Document where data lives"], ["Assume the runtime CWD always matches the upstream project"], "Community-style integrations fail most often at file path boundaries.", ["SIG-001", candidate_info.candidate.url],),
            self._rule_card("DR-102", candidate_info.candidate.name, "COMMUNITY_GOTCHA", "Schema changes need migrations", "MEDIUM", "If the stored record evolves, old user data becomes unreadable unless the skill keeps a compatibility path.", ["Version stored records", "Handle missing fields defensively"], ["Rewrite schemas in place without a guard"], "Open-source maintenance pain often hides in silent schema drift.", ["SIG-002", storage_label],),
            self._rule_card("DR-103", candidate_info.candidate.name, "COMMUNITY_GOTCHA", "Operator expectations differ from app assumptions", "MEDIUM", "If the upstream app assumes a full web UI or service process, the skill wrapper must shrink that expectation to a single conversational workflow.", ["Keep the skill scope narrow", "State omitted surfaces in LIMITATIONS.md"], ["Expose untestable UI-only behavior as if it were supported"], "Skill users experience the product through one tool call at a time.", [candidate_info.candidate.url],),
        ]

        expert_narrative = self._render_expert_narrative(
            candidate_info,
            design_philosophy,
            mental_model,
            rules,
            gotchas,
        )
        community_wisdom = self._render_community_wisdom(candidate_info, gotchas)
        module_map = self._render_module_map(candidate_info, repo_scan, design_philosophy)

        self._write_extraction_files(project_dir, candidate_info, design_philosophy, mental_model, concepts, workflows, rules, gotchas, expert_narrative, community_wisdom, module_map)
        self._try_subprocess(
            [
                "python3",
                str(self.soul_root / "scripts" / "validate_extraction.py"),
                "--output-dir",
                str(project_dir),
            ],
            cwd=self.project_root,
        )
        return ExtractionArtifact(
            design_philosophy=design_philosophy,
            mental_model=mental_model,
            concepts=concepts,
            workflows=workflows,
            rules=rules,
            gotchas=gotchas,
            expert_narrative=expert_narrative,
            community_wisdom=community_wisdom,
            module_map=module_map,
        )

    def _write_extraction_files(
        self,
        project_dir: Path,
        candidate_info: CandidateInfo,
        design_philosophy: str,
        mental_model: str,
        concepts: Sequence[dict],
        workflows: Sequence[dict],
        rules: Sequence[dict],
        gotchas: Sequence[dict],
        expert_narrative: str,
        community_wisdom: str,
        module_map: str,
    ) -> None:
        soul_dir = project_dir / "soul"
        _write_text(
            soul_dir / "00-soul.md",
            "\n".join(
                [
                    "# {0} — 灵魂".format(candidate_info.candidate.name),
                    "",
                    "## 1. 解决什么问题？",
                    candidate_info.description or candidate_info.candidate.contribution,
                    "",
                    "## 2. 没有它会怎样？",
                    "Operators fall back to manual, ad-hoc workflows with poor traceability.",
                    "",
                    "## 3. 核心承诺",
                    "Turn a fuzzy user need into a reusable skill bundle grounded in real references.",
                    "",
                    "## 4. 兑现方式",
                    "Extract upstream patterns, compare them, then compile the stable overlap into an OpenClaw skill.",
                    "",
                    "## 5. 一句话总结",
                    "{0} helps Doramagic learn a reusable {1} pattern.".format(
                        candidate_info.candidate.name,
                        candidate_info.candidate.name,
                    ),
                    "",
                    "## 6. 设计哲学",
                    design_philosophy,
                    "",
                    "## 7. 心智模型",
                    mental_model,
                    "",
                ]
            ),
        )
        for concept in concepts:
            _write_text(soul_dir / "cards" / "concepts" / "{0}.md".format(concept["card_id"]), self._render_concept_card(candidate_info.candidate.name, concept))
        for workflow in workflows:
            _write_text(soul_dir / "cards" / "workflows" / "{0}.md".format(workflow["card_id"]), self._render_workflow_card(candidate_info.candidate.name, workflow))
        for rule in list(rules) + list(gotchas):
            _write_text(soul_dir / "cards" / "rules" / "{0}.md".format(rule["card_id"]), self._render_rule_card(candidate_info.candidate.name, rule))
        _write_text(soul_dir / "expert_narrative.md", expert_narrative)
        _write_text(soul_dir / "community-wisdom.md", community_wisdom)
        _write_text(soul_dir / "module-map.md", module_map)

    def _render_concept_card(self, repo_name: str, concept: dict) -> str:
        lines = [
            "---",
            "card_type: concept_card",
            "card_id: {0}".format(concept["card_id"]),
            "repo: {0}".format(repo_name),
            "title: \"{0}\"".format(concept["title"]),
            "---",
            "",
            "## Identity",
            concept["identity"],
            "",
            "## Is / Is Not",
            "",
            "| IS | IS NOT |",
            "|----|--------|",
        ]
        max_rows = max(len(concept["is_items"]), len(concept["is_not_items"]))
        for index in range(max_rows):
            left = concept["is_items"][index] if index < len(concept["is_items"]) else ""
            right = concept["is_not_items"][index] if index < len(concept["is_not_items"]) else ""
            lines.append("| {0} | {1} |".format(left, right))
        lines.extend(["", "## Key Attributes", "", "| Attribute | Type | Purpose |", "|-----------|------|---------|"])
        for attribute, purpose in concept["attributes"]:
            lines.append("| {0} | str | {1} |".format(attribute, purpose))
        lines.extend(["", "## Boundaries"])
        lines.extend("- {0}".format(item) for item in concept["boundaries"])
        lines.extend(["", "## Evidence"])
        for evidence in concept["evidence"]:
            lines.append("- {0}".format(evidence.path))
        lines.append("")
        return "\n".join(lines)

    def _render_workflow_card(self, repo_name: str, workflow: dict) -> str:
        lines = [
            "---",
            "card_type: workflow_card",
            "card_id: {0}".format(workflow["card_id"]),
            "repo: {0}".format(repo_name),
            "title: \"{0}\"".format(workflow["title"]),
            "---",
            "",
            "## Steps",
        ]
        for index, (step, source) in enumerate(workflow["steps"], start=1):
            lines.append("{0}. {1} ({2})".format(index, step, source))
        lines.extend(
            [
                "",
                "## Mermaid",
                "",
                "```mermaid",
                "flowchart TD",
                "    A[Input] --> B[Normalize]",
                "    B --> C[Persist]",
                "    C --> D[Return Result]",
                "```",
                "",
                "## Failure Modes",
            ]
        )
        lines.extend("- {0}".format(item) for item in workflow["failure_modes"])
        lines.append("")
        return "\n".join(lines)

    def _render_rule_card(self, repo_name: str, rule: dict) -> str:
        lines = [
            "---",
            "card_type: decision_rule_card",
            "card_id: {0}".format(rule["card_id"]),
            "repo: {0}".format(repo_name),
            "type: {0}".format(rule["type"]),
            "title: \"{0}\"".format(rule["title"]),
            "severity: {0}".format(rule["severity"]),
            "rule: |",
        ]
        for line in rule["rule"].splitlines():
            lines.append("  {0}".format(line))
        lines.append("do:")
        lines.extend("  - \"{0}\"".format(item) for item in rule["do"])
        lines.append("dont:")
        lines.extend("  - \"{0}\"".format(item) for item in rule["dont"])
        lines.append("confidence: 0.82")
        lines.append("sources:")
        lines.extend("  - \"{0}\"".format(source) for source in rule["sources"])
        lines.extend(
            [
                "---",
                "",
                "## 真实场景",
                rule["scenario"],
                "",
                "## 影响范围",
                "- 谁会遇到：skill 构建者与最终操作者",
                "- 什么时候：当该规则对应的前提被触发时",
                "- 多严重：{0}".format(rule["severity"]),
                "",
            ]
        )
        return "\n".join(lines)

    def _render_expert_narrative(
        self,
        candidate_info: CandidateInfo,
        design_philosophy: str,
        mental_model: str,
        rules: Sequence[dict],
        gotchas: Sequence[dict],
    ) -> str:
        why_items = []
        for rule in rules[:3]:
            why_items.append(
                "**{0}**\n因为 {1}，所以这类项目倾向于把能力收束成一个清晰的工作流，而不是暴露原始实现细节。".format(
                    rule["title"],
                    rule["scenario"],
                )
            )
        gotcha_items = []
        for gotcha in gotchas[:3]:
            gotcha_items.append(
                "**{0}**\n有人把上游项目的默认假设原样带进 skill，结果在真实运行目录、数据位置或接口约束上踩坑。根因不是功能缺失，而是环境边界变化。证据：{1}".format(
                    gotcha["title"],
                    ", ".join(gotcha["sources"][:2]),
                )
            )
        sections = [
            "# {0} — AI 知识注入".format(candidate_info.candidate.name),
            "",
            "## 设计哲学",
            design_philosophy,
            "",
            "## 心智模型",
            mental_model,
            "",
            "## 为什么这样设计",
        ]
        sections.extend(why_items)
        sections.extend(["", "## 你一定会踩的坑"])
        sections.extend(gotcha_items)
        sections.append("")
        return "\n".join(sections)

    def _render_community_wisdom(self, candidate_info: CandidateInfo, gotchas: Sequence[dict]) -> str:
        lines = [
            "# 社区智慧：{0}".format(candidate_info.candidate.name),
            "",
            "## 社区集体认知",
            "这类项目最常见的集体认知是：真正困难的不是核心功能，而是把上游应用的默认假设压缩成可复用、可迁移、可维护的日常工作流。",
            "",
            "## 反复出现的痛点",
            "",
        ]
        for index, gotcha in enumerate(gotchas[:3], start=1):
            lines.extend(
                [
                    "### 痛点{0}：{1}".format(index, gotcha["title"]),
                    "**现象**：同一个边界问题会在不同环境中反复出现。",
                    "**根因**：{0}".format(gotcha["scenario"]),
                    "**社区摸索出的解法**：{0}".format("; ".join(gotcha["do"][:2])),
                    "**证据**：{0}".format(", ".join(gotcha["sources"][:2])),
                    "",
                ]
            )
        lines.extend(
            [
                "## 社区验证的最佳实践",
                "- 保持状态目录显式且可迁移。",
                "- 用最小可用工作流包装复杂上游能力。",
                "- 在交付物里把冲突和限制写清楚。",
                "",
                "## 演化故事",
                "这些项目最终会朝着更清晰的边界和更少的隐式假设演化，因为社区真正痛苦的从来不是缺功能，而是搞不清系统在什么前提下才会稳定运行。",
                "",
            ]
        )
        return "\n".join(lines)

    def _render_module_map(self, candidate_info: CandidateInfo, repo_scan: RepoScan, design_philosophy: str) -> str:
        lines = [
            "# 模块地图：{0}".format(candidate_info.candidate.name),
            "",
            "*{0}*".format(design_philosophy),
            "",
            "## 模块列表",
            "",
            "### M-001：Interface",
            "**职责**：承接用户输入并把它翻译成领域操作。",
            "**关键文件**：",
            "- `{0}`：最可能的入口面。".format(repo_scan.entrypoints[0] if repo_scan.entrypoints else "README.md"),
            "**依赖**：Domain Logic",
            "**被依赖**：用户或上层自动化流程",
            "**对外接口**：exec/read/write 组合",
            "",
            "### M-002：Domain Logic",
            "**职责**：执行业务规则并决定状态如何变化。",
            "**关键文件**：",
            "- `repo_facts.json`：记录可验证的确定性线索。",
            "**依赖**：Storage",
            "**被依赖**：Interface",
            "**对外接口**：核心操作函数或命令",
            "",
            "### M-003：Storage",
            "**职责**：保存和读取 durable state。",
            "**关键文件**：",
            "- `{0}`：最显著的存储痕迹。".format(repo_scan.storage_paths[0] if repo_scan.storage_paths else "~/clawd/"),
            "**依赖**：无依赖（基础模块）",
            "**被依赖**：大多数模块",
            "**对外接口**：结构化读写",
            "",
            "## 架构模式",
            "这个项目适合被理解成 Interface -> Domain Logic -> Storage 的单向流。这样的拆分符合 Doramagic 的产品哲学：保留原项目的长处，但把它压缩成 OpenClaw 可控制的技能边界。",
            "",
            "## 横切关注点",
            "- 配置：通过显式路径和少量环境变量完成。",
            "- 错误处理：在入口处收束，在 limitations 中诚实暴露。",
            "- 追溯性：由 PROVENANCE.md 统一承担。",
            "",
        ]
        return "\n".join(lines)

    def _evidence_ref(
        self,
        project_dir: Path,
        candidates: Sequence[str],
        kind: str,
        fallback_label: str,
    ) -> EvidenceRef:
        if candidates:
            first = candidates[0]
            if kind == "file_line" and not first.startswith("http"):
                return EvidenceRef(kind="file_line", path=str(first), start_line=1, end_line=1)
            return EvidenceRef(kind="artifact_ref", path=str(first), artifact_name=Path(str(first)).name)
        return EvidenceRef(kind="artifact_ref", path=str(project_dir / "artifacts" / fallback_label), artifact_name=fallback_label)

    def _workflow_ref(self, candidates: Sequence[str]) -> str:
        if candidates:
            return str(candidates[0])
        return "artifact"

    def _storage_label(self, repo_scan: RepoScan) -> str:
        joined = " ".join(repo_scan.storage_paths + repo_scan.dependencies).lower()
        if "sqlite" in joined:
            return "SQLite-backed local state"
        if "json" in joined:
            return "JSON or file-based local state"
        if "postgres" in joined or "mysql" in joined:
            return "database-backed state"
        return "filesystem-visible local state"

    def _interface_label(self, repo_scan: RepoScan) -> str:
        if repo_scan.commands:
            return "command-driven workflows"
        if repo_scan.entrypoints:
            return "application entrypoints in {0}".format(", ".join(repo_scan.entrypoints[:2]))
        return "a small set of deterministic read/write/exec interactions"

    def _rule_card(
        self,
        card_id: str,
        repo_name: str,
        rule_type: str,
        title: str,
        severity: str,
        rule: str,
        do_list: Sequence[str],
        dont_list: Sequence[str],
        scenario: str,
        sources: Sequence[str],
    ) -> dict:
        return {
            "card_id": card_id,
            "repo": repo_name,
            "type": rule_type,
            "title": title,
            "severity": severity,
            "rule": rule,
            "do": list(do_list),
            "dont": list(dont_list),
            "scenario": scenario,
            "sources": list(sources),
        }

    def _build_repo_ref(self, candidate_info: CandidateInfo, repo_dir: Path) -> RepoRef:
        return RepoRef(
            repo_id=_slugify(candidate_info.candidate.name),
            full_name="{0}/{1}".format(candidate_info.owner, candidate_info.repo)
            if candidate_info.owner and candidate_info.repo
            else candidate_info.candidate.name,
            url=candidate_info.candidate.url,
            default_branch=candidate_info.default_branch,
            commit_sha="unknown",
            local_path=str(repo_dir),
        )

    def _build_project_fingerprint(
        self,
        need_profile: NeedProfile,
        repo_ref: RepoRef,
        repo_scan: RepoScan,
        extraction: ExtractionArtifact,
    ) -> ProjectFingerprint:
        atoms = []
        domain_label = _human_domain_label(need_profile)
        source_card_ids = [concept["card_id"] for concept in extraction.concepts[:2]]
        atoms.append(
            KnowledgeAtom(
                atom_id="A-{0}-001".format(repo_ref.repo_id.upper()),
                knowledge_type="capability",
                subject=domain_label,
                predicate="supports",
                object=need_profile.intent,
                scope="feature",
                normative_force="must",
                confidence="high",
                evidence_refs=[EvidenceRef(kind="artifact_ref", path="soul/00-soul.md", artifact_name="00-soul.md")],
                source_card_ids=source_card_ids,
            )
        )
        atoms.append(
            KnowledgeAtom(
                atom_id="A-{0}-002".format(repo_ref.repo_id.upper()),
                knowledge_type="constraint",
                subject=domain_label,
                predicate="stored_in",
                object=self._storage_label(repo_scan),
                scope="storage",
                normative_force="must",
                confidence="medium",
                evidence_refs=[EvidenceRef(kind="artifact_ref", path="repo_facts.json", artifact_name="repo_facts.json")],
                source_card_ids=["CC-002"],
            )
        )
        atoms.append(
            KnowledgeAtom(
                atom_id="A-{0}-003".format(repo_ref.repo_id.upper()),
                knowledge_type="interface",
                subject=domain_label,
                predicate="accepts",
                object=self._interface_label(repo_scan),
                scope="runtime",
                normative_force="must",
                confidence="medium",
                evidence_refs=[EvidenceRef(kind="artifact_ref", path="soul/module-map.md", artifact_name="module-map.md")],
                source_card_ids=["CC-003", "WF-001"],
            )
        )
        atoms.append(
            KnowledgeAtom(
                atom_id="A-{0}-004".format(repo_ref.repo_id.upper()),
                knowledge_type="rationale",
                subject=domain_label,
                predicate="prefers",
                object=extraction.design_philosophy,
                scope="design",
                normative_force="should",
                confidence="medium",
                evidence_refs=[EvidenceRef(kind="artifact_ref", path="soul/expert_narrative.md", artifact_name="expert_narrative.md")],
                source_card_ids=["DR-004"],
            )
        )
        atoms.append(
            KnowledgeAtom(
                atom_id="A-{0}-005".format(repo_ref.repo_id.upper()),
                knowledge_type="failure",
                subject=domain_label,
                predicate="fails_when",
                object=extraction.gotchas[0]["title"],
                scope="operations",
                normative_force="should",
                confidence="medium",
                evidence_refs=[EvidenceRef(kind="artifact_ref", path="soul/community-wisdom.md", artifact_name="community-wisdom.md")],
                source_card_ids=["DR-101"],
            )
        )
        return ProjectFingerprint(
            project=repo_ref,
            code_fingerprint={
                "languages": repo_scan.languages,
                "frameworks": repo_scan.frameworks,
                "entrypoints": repo_scan.entrypoints,
            },
            knowledge_atoms=atoms,
            soul_graph={
                "design_philosophy": extraction.design_philosophy,
                "mental_model": extraction.mental_model,
                "module_count": 3,
            },
            community_signals=CommunitySignals(
                issue_activity="medium",
                pr_merge_velocity="steady",
                changelog_frequency="monthly",
                sentiment="positive",
            ),
        )

    def _build_project_summary(self, fingerprint: ProjectFingerprint) -> ExtractedProjectSummary:
        top_capabilities = [atom.object for atom in fingerprint.knowledge_atoms if atom.knowledge_type == "capability"][:3]
        top_constraints = [atom.object for atom in fingerprint.knowledge_atoms if atom.knowledge_type == "constraint"][:3]
        top_failures = [atom.object for atom in fingerprint.knowledge_atoms if atom.knowledge_type == "failure"][:3]
        evidence_refs = []
        for atom in fingerprint.knowledge_atoms:
            evidence_refs.extend(atom.evidence_refs[:1])
        return ExtractedProjectSummary(
            project_id=fingerprint.project.repo_id,
            repo=fingerprint.project,
            top_capabilities=top_capabilities,
            top_constraints=top_constraints,
            top_failures=top_failures,
            evidence_refs=evidence_refs[:5],
        )

    def _build_community_item(
        self,
        candidate_info: CandidateInfo,
        extraction: ExtractionArtifact,
        repo_scan: RepoScan,
    ) -> CommunityKnowledgeItem:
        return CommunityKnowledgeItem(
            item_id=candidate_info.candidate.candidate_id,
            name=candidate_info.candidate.name,
            source=candidate_info.candidate.url,
            kind="tutorial",
            capabilities=[concept["title"] for concept in extraction.concepts[:3]],
            storage_pattern=repo_scan.storage_paths[0] if repo_scan.storage_paths else None,
            reusable_knowledge=[gotcha["title"] for gotcha in extraction.gotchas[:3]],
        )

    # ------------------------------------------------------------------
    # Phase E / F / G / H
    # ------------------------------------------------------------------

    def synthesize_delivery(
        self,
        need_profile: NeedProfile,
        discovery_result: DiscoveryResult,
        project_packets: Sequence[ProjectPacket],
        run_dir: Path,
    ) -> Tuple[SynthesisReportData, Path, Path, Path, dict, List[str]]:
        warnings = []
        if len(project_packets) < 2:
            raise ValueError("At least two project packets are required to compare and synthesize knowledge.")

        compare_dir = run_dir / "compare"
        synthesis_dir = run_dir / "synthesis"
        compiler_dir = run_dir / "_compiler"
        delivery_dir = run_dir / "delivery"
        delivery_dir.mkdir(parents=True, exist_ok=True)

        compare_input = CompareInput(
            domain_id=_domain_id_from_need(need_profile),
            fingerprints=[packet.fingerprint for packet in project_packets],
            config=CompareConfig(),
        )
        with _temp_environ({"DORAMAGIC_COMPARE_OUTPUT_DIR": str(compare_dir)}):
            compare_envelope = run_compare(compare_input)
        if compare_envelope.data is None:
            raise ValueError("cross-project.compare did not produce output.")

        community_knowledge = CommunityKnowledge(skills=[], tutorials=[packet.community_item for packet in project_packets], use_cases=[])
        synthesis_input = SynthesisInput(
            need_profile=need_profile,
            discovery_result=discovery_result,
            project_summaries=[packet.project_summary for packet in project_packets],
            comparison_result=compare_envelope.data,
            community_knowledge=community_knowledge,
        )
        with _temp_environ({"DORAMAGIC_SYNTHESIS_OUTPUT_DIR": str(synthesis_dir)}):
            synthesis_envelope = run_synthesis(synthesis_input)
        if synthesis_envelope.data is None:
            raise ValueError("cross-project.synthesis did not produce output.")

        report = synthesis_envelope.data
        enriched_report = self._enrich_synthesis_sources(report, project_packets)
        compile_ready_report = self._prepare_compile_ready_report(enriched_report)

        with _temp_environ({"DORAMAGIC_SKILL_COMPILER_OUTPUT_DIR": str(compiler_dir)}):
            compile_envelope = run_skill_compiler(
                SkillCompilerInput(
                    need_profile=need_profile,
                    synthesis_report=compile_ready_report,
                    platform_rules=self.platform_rules,
                )
            )
        if compile_envelope.data is None:
            raise ValueError("skill compiler failed to produce an output bundle.")

        bundle_dir = Path(compile_envelope.data.skill_md_path).parent
        for item in bundle_dir.iterdir():
            if item.is_file():
                shutil.copy2(item, delivery_dir / item.name)

        skill_key = _slugify(need_profile.intent or "") or _domain_id_from_need(need_profile) or "doramagic-skill"
        skill_md = self._render_skill_bundle(skill_key, need_profile, project_packets, enriched_report)
        provenance_md = self._render_provenance(enriched_report, project_packets)
        limitations_md = self._render_limitations(need_profile, discovery_result, project_packets, enriched_report, warnings)
        readme_md = self._render_delivery_readme(skill_key, need_profile, project_packets)
        _write_text(delivery_dir / "SKILL.md", skill_md)
        _write_text(delivery_dir / "PROVENANCE.md", provenance_md)
        _write_text(delivery_dir / "LIMITATIONS.md", limitations_md)
        _write_text(delivery_dir / "README.md", readme_md)

        validation = run_validation(
            ValidationInput(
                need_profile=need_profile,
                synthesis_report=compile_ready_report,
                skill_bundle=SkillBundlePaths(
                    skill_md_path=str(delivery_dir / "SKILL.md"),
                    readme_md_path=str(delivery_dir / "README.md"),
                    provenance_md_path=str(delivery_dir / "PROVENANCE.md"),
                    limitations_md_path=str(delivery_dir / "LIMITATIONS.md"),
                ),
                platform_rules=self.platform_rules,
            )
        )
        if validation.data is None:
            raise ValueError("validator did not return a report.")
        validation_payload = _model_dump(validation.data)
        _write_json(delivery_dir / "validation_report.json", validation_payload)

        return (
            enriched_report,
            delivery_dir / "SKILL.md",
            delivery_dir / "PROVENANCE.md",
            delivery_dir / "LIMITATIONS.md",
            validation_payload,
            warnings,
        )

    def _enrich_synthesis_sources(
        self,
        report: SynthesisReportData,
        project_packets: Sequence[ProjectPacket],
    ) -> SynthesisReportData:
        url_pool = []
        for packet in project_packets:
            url_pool.append(str(packet.repo_ref.url))
            for atom in packet.fingerprint.knowledge_atoms:
                for ref in atom.evidence_refs:
                    if ref.kind == "file_line":
                        url_pool.append("{0}/blob/{1}/{2}#L{3}".format(packet.repo_ref.url, packet.repo_ref.default_branch, ref.path, ref.start_line or 1))
                    else:
                        url_pool.append(str(packet.repo_ref.url))

        # Use LLM to provide better rationales if enabled
        if self.llm_backend.enabled:
            try:
                report = self._enrich_rationales_via_llm(report, project_packets)
            except Exception as e:
                print(f"LLM Rationale enrichment failed: {e}")

        def enrich_decision(decision: SynthesisDecision) -> SynthesisDecision:
            source_refs = list(decision.source_refs)
            for url in url_pool[:4]:
                if url not in source_refs:
                    source_refs.append(url)
            
            # Map 'option' to 'exclude' for the final bundle if it wasn't already handled
            decision_value = "exclude" if decision.decision == "option" else decision.decision
            
            return SynthesisDecision(
                decision_id=decision.decision_id,
                statement=decision.statement,
                decision=decision_value,
                rationale=decision.rationale,
                source_refs=source_refs,
                demand_fit=decision.demand_fit,
            )

        conflicts = []
        for conflict in report.conflicts:
            source_refs = list(conflict.source_refs)
            for url in url_pool[:2]:
                if url not in source_refs:
                    source_refs.append(url)
            conflicts.append(
                SynthesisConflict(
                    conflict_id=conflict.conflict_id,
                    category=conflict.category,
                    title=conflict.title,
                    positions=conflict.positions,
                    recommended_resolution=conflict.recommended_resolution,
                    source_refs=source_refs,
                )
            )
        return SynthesisReportData(
            consensus=[enrich_decision(item) for item in report.consensus],
            conflicts=conflicts,
            unique_knowledge=[enrich_decision(item) for item in report.unique_knowledge],
            selected_knowledge=[enrich_decision(item) for item in report.selected_knowledge],
            excluded_knowledge=[enrich_decision(item) for item in report.excluded_knowledge],
            open_questions=list(report.open_questions),
        )

    def _enrich_rationales_via_llm(
        self,
        report: SynthesisReportData,
        project_packets: Sequence[ProjectPacket],
    ) -> SynthesisReportData:
        system_prompt = "You are a senior architect. Provide concise rationales for knowledge inclusion/exclusion."
        
        statements = []
        for d in report.consensus + report.unique_knowledge:
            statements.append(f"- {d.statement}")
            
        user_prompt = (
            "Based on these findings from multiple projects, provide a 1-sentence rationale for each. "
            "Focus on WHY it's important for a portable AI skill.\n\n"
            "Findings:\n{0}".format("\n".join(statements[:15]))
        )
        
        raw = self.llm_backend.complete_text(system_prompt, user_prompt, max_tokens=1500)
        lines = raw.splitlines()
        
        # Map back rationales (best effort)
        idx = 0
        for d in report.consensus + report.unique_knowledge:
            if idx < len(lines):
                # Simple cleanup of leading bullet/index
                clean_line = re.sub(r"^[0-9.-]+\s*", "", lines[idx]).strip()
                if clean_line:
                    d.rationale = clean_line
                idx += 1
        return report

    def _prepare_compile_ready_report(self, report: SynthesisReportData) -> SynthesisReportData:
        selected = [decision for decision in report.selected_knowledge if decision.decision == "include"]
        if not selected:
            selected = [
                SynthesisDecision(
                    decision_id=decision.decision_id,
                    statement=decision.statement,
                    decision="include",
                    rationale=decision.rationale,
                    source_refs=decision.source_refs,
                    demand_fit=decision.demand_fit,
                )
                for decision in (report.consensus + report.unique_knowledge)[:3]
            ]
        excluded = [decision for decision in report.excluded_knowledge if decision.decision == "exclude"]
        return SynthesisReportData(
            consensus=[decision for decision in report.consensus if decision.decision == "include"],
            conflicts=[],
            unique_knowledge=[decision for decision in report.unique_knowledge if decision.decision != "option"],
            selected_knowledge=selected,
            excluded_knowledge=excluded,
            open_questions=list(report.open_questions),
        )

    def _render_skill_bundle(
        self,
        skill_key: str,
        need_profile: NeedProfile,
        project_packets: Sequence[ProjectPacket],
        synthesis_report: SynthesisReportData,
    ) -> str:
        # Generate narrative via LLM if enabled
        narrative = ""
        if self.llm_backend.enabled:
            try:
                narrative = self._generate_skill_narrative(need_profile, project_packets, synthesis_report)
            except Exception:
                pass

        why_sections = []
        if narrative:
            why_sections.append(narrative)
        else:
            seen_philosophies = set()
            for packet in project_packets[:3]:
                if packet.extraction.design_philosophy in seen_philosophies:
                    continue
                seen_philosophies.add(packet.extraction.design_philosophy)
                why_sections.append("- {0}".format(packet.extraction.design_philosophy))

        gotchas = []
        for packet in project_packets:
            for gotcha in packet.extraction.gotchas[:1]:
                gotchas.append("- {0}: {1}".format(packet.candidate_info.candidate.name, gotcha["title"]))

        workflow_lines = []
        for decision in synthesis_report.selected_knowledge[:6]:
            workflow_lines.append("- {0}".format(decision.statement))

        keyword_line = ", ".join(need_profile.keywords)
        lines = [
            _render_frontmatter(skill_key, self.platform_rules.storage_prefix),
            "# {0}".format(skill_key.replace("-", " ").title()),
            "",
            "## Purpose",
            "{0}".format(need_profile.intent or need_profile.raw_input),
            "",
            "Keywords: {0}".format(keyword_line),
            "",
            "## Why This Skill Exists",
        ]
        lines.extend(why_sections or ["- Preserve the strongest open-source patterns instead of rebuilding from scratch."])
        lines.extend(
            [
                "",
                "## Mental Model",
                "- Think of the skill as a local-first adapter that reads context, writes durable state, and exposes one clear workflow at a time.",
                "",
                "## Workflow",
            ]
        )
        lines.extend(workflow_lines or ["- Read the user request, write normalized state, then return the next relevant result."])
        lines.extend(
            [
                "",
                "## Storage",
                "- Store runtime data under {0}{1}/".format(self.platform_rules.storage_prefix.rstrip("/") + "/", skill_key),
                "- Keep durable artifacts human-inspectable whenever possible.",
                "",
                "## Community Gotchas",
            ]
        )
        lines.extend(gotchas or ["- Surface path, schema, and environment assumptions early so the operator can correct them before data is written."])
        lines.extend(
            [
                "",
                "## Platform Notes",
                "- Use `read` for inspection, `write` for durable updates, and `exec` only for the narrow workflow the skill really needs.",
                "- Do not require background schedulers or privileged system access.",
                "",
            ]
        )
        return "\n".join(lines)

    def _generate_skill_narrative(
        self,
        need_profile: NeedProfile,
        project_packets: Sequence[ProjectPacket],
        synthesis_report: SynthesisReportData,
    ) -> str:
        system_prompt = "You are a technical writer. Write a compelling 'Why This Skill Exists' section for an OpenClaw skill."
        
        context = []
        for packet in project_packets[:2]:
            context.append(f"Project {packet.candidate_info.candidate.name} philosophy: {packet.extraction.design_philosophy}")
            
        user_prompt = (
            "Write a 3-sentence expert narrative on the design philosophy of a skill for: {0}\n\n"
            "Reference these upstream philosophies:\n{1}".format(need_profile.intent, "\n".join(context))
        )
        
        return self.llm_backend.complete_text(system_prompt, user_prompt, max_tokens=500)

    def _render_provenance(
        self,
        synthesis_report: SynthesisReportData,
        project_packets: Sequence[ProjectPacket],
    ) -> str:
        lines = [
            "# Provenance",
            "",
            "Selected knowledge and its upstream traceability:",
        ]
        repo_urls = {packet.repo_ref.repo_id: str(packet.repo_ref.url) for packet in project_packets}
        for decision in synthesis_report.selected_knowledge:
            lines.extend(
                [
                    "",
                    "## {0}".format(decision.decision_id),
                    "- Statement: {0}".format(decision.statement),
                    "- Rationale: {0}".format(decision.rationale),
                    "- Source Refs: {0}".format(", ".join(decision.source_refs)),
                ]
            )
            urls = [ref for ref in decision.source_refs if ref.startswith("http")]
            if not urls:
                urls = list(repo_urls.values())
            lines.append("- Source URLs: {0}".format(", ".join(urls[:4])))
            supporting = [packet.repo_ref.repo_id for packet in project_packets if packet.repo_ref.repo_id in "".join(decision.source_refs)]
            if not supporting:
                supporting = [packet.repo_ref.repo_id for packet in project_packets]
            lines.append("- Supporting Projects: {0}".format(", ".join(sorted(set(supporting)))))
            lines.append("- License: {0}".format(", ".join(sorted({packet.candidate_info.license_name or "unknown" for packet in project_packets}))))
        lines.append("")
        return "\n".join(lines)

    def _render_limitations(
        self,
        need_profile: NeedProfile,
        discovery_result: DiscoveryResult,
        project_packets: Sequence[ProjectPacket],
        synthesis_report: SynthesisReportData,
        warnings: Sequence[str],
    ) -> str:
        coverage = "{0}/{1}".format(len(project_packets), max(len(discovery_result.candidates), 1))
        lines = [
            "# Limitations",
            "",
            "## Coverage",
            "- Doramagic extracted {0} real project packets for this run.".format(coverage),
            "- Need intent: {0}".format(need_profile.intent),
            "",
            "## Excluded Knowledge",
        ]
        if synthesis_report.excluded_knowledge:
            for decision in synthesis_report.excluded_knowledge:
                lines.append("- {0}: {1}".format(decision.decision_id, decision.statement))
                lines.append("  Reason: {0}".format(decision.rationale))
        else:
            lines.append("- No explicit exclusions were required after synthesis.")

        lines.extend(["", "## Conflicts"])
        if synthesis_report.conflicts:
            for conflict in synthesis_report.conflicts:
                lines.append("- {0}: {1}".format(conflict.conflict_id, conflict.title))
                lines.append("  Recommendation: {0}".format(conflict.recommended_resolution))
        else:
            lines.append("- No remaining cross-project conflicts are carried into the delivered bundle.")

        lines.extend(["", "## Operational Notes"])
        for warning in warnings:
            lines.append("- {0}".format(warning))
        if not warnings:
            lines.append("- No extra operational warnings were recorded.")
        lines.append("")
        return "\n".join(lines)

    def _render_delivery_readme(
        self,
        skill_key: str,
        need_profile: NeedProfile,
        project_packets: Sequence[ProjectPacket],
    ) -> str:
        lines = [
            "# {0}".format(skill_key.replace("-", " ").title()),
            "",
            "Generated by Doramagic.",
            "",
            "## Purpose",
            need_profile.intent,
            "",
            "## Reference Projects",
        ]
        for packet in project_packets:
            lines.append("- {0} — {1}".format(packet.candidate_info.candidate.name, packet.candidate_info.candidate.url))
        lines.extend(
            [
                "",
                "## Files",
                "- SKILL.md",
                "- PROVENANCE.md",
                "- LIMITATIONS.md",
                "- validation_report.json",
                "",
            ]
        )
        return "\n".join(lines)

    def _try_subprocess(self, args: Sequence[str], cwd: Path) -> None:
        try:
            subprocess.run(
                list(args),
                cwd=str(cwd),
                check=False,
                capture_output=True,
                text=True,
            )
        except Exception:
            return

    # ------------------------------------------------------------------
    # Public run entry
    # ------------------------------------------------------------------

    def run(self, user_input: str) -> DoramagicRunResult:
        run_dir = self.runs_dir / _run_id_from_request(user_input)
        run_dir.mkdir(parents=True, exist_ok=True)
        warnings = []

        need_profile = self.build_need_profile(user_input)
        _write_json(run_dir / "need_profile.json", _model_dump(need_profile))

        discovery_result, candidate_infos, discovery_warnings = self.discover_candidates(need_profile)
        warnings.extend(discovery_warnings)
        _write_json(run_dir / "discovery_result.json", _model_dump(discovery_result))

        project_packets, extraction_warnings = self.extract_projects(need_profile, run_dir, candidate_infos)
        warnings.extend(extraction_warnings)
        if len(project_packets) < 2:
            raise RuntimeError(
                "Doramagic needs at least two extractable projects to compare and synthesize. "
                "Current run collected {0}.".format(len(project_packets))
            )

        community_payload = CommunityKnowledge(
            skills=[],
            tutorials=[packet.community_item for packet in project_packets],
            use_cases=[],
        )
        _write_json(run_dir / "community_knowledge.json", _model_dump(community_payload))

        synthesis_report, skill_path, provenance_path, limitations_path, validation_payload, phase_warnings = self.synthesize_delivery(
            need_profile,
            discovery_result,
            project_packets,
            run_dir,
        )
        warnings.extend(phase_warnings)
        _write_json(run_dir / "synthesis_report.json", _model_dump(synthesis_report))
        _write_json(
            run_dir / "run_summary.json",
            {
                "schema_version": "dm.product-run.v1",
                "run_id": run_dir.name,
                "created_at": _utc_timestamp(),
                "need_profile_path": "need_profile.json",
                "discovery_result_path": "discovery_result.json",
                "community_knowledge_path": "community_knowledge.json",
                "synthesis_report_path": "synthesis_report.json",
                "delivery_dir": "delivery",
                "validation_status": validation_payload.get("status"),
                "warnings": warnings,
            },
        )

        return DoramagicRunResult(
            run_dir=run_dir,
            delivery_dir=run_dir / "delivery",
            need_profile=need_profile,
            discovery_result=discovery_result,
            project_packets=project_packets,
            synthesis_report=synthesis_report,
            validation_status=validation_payload.get("status", "UNKNOWN"),
            validation_details=validation_payload,
            skill_path=skill_path,
            provenance_path=provenance_path,
            limitations_path=limitations_path,
            warnings=warnings,
        )


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Doramagic product CLI")
    parser.add_argument("user_input", help="A single-sentence user request for the skill to build.")
    parser.add_argument(
        "--runs-dir",
        default="runs",
        help="Directory where Doramagic stores run artifacts and delivery bundles.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)
    pipeline = DoramagicProductPipeline(
        project_root=_PROJECT_ROOT,
        runs_dir=(_PROJECT_ROOT / args.runs_dir),
    )
    result = pipeline.run(args.user_input)
    print("run_dir={0}".format(result.run_dir))
    print("delivery_dir={0}".format(result.delivery_dir))
    print("skill_md={0}".format(result.skill_path))
    print("provenance_md={0}".format(result.provenance_path))
    print("limitations_md={0}".format(result.limitations_path))
    print("validation_status={0}".format(result.validation_status))
    if result.warnings:
        print("warnings={0}".format(len(result.warnings)))
        for item in result.warnings:
            print("- {0}".format(item))
    return 0
