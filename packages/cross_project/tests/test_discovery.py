"""cross-project.discovery 模块测试。

测试覆盖：
1. Sim2 卡路里场景正常路径：≥2 github_repo + ≥1 community_skill
2. Sim3 机票场景正常路径：≥2 github_repo + ≥1 community_skill
3. search_coverage 完整性：每个 direction 有 covered/partial/missing
4. 无候选时返回 degraded + E_NO_CANDIDATES
5. API hint 缺失时仍能独立工作
6. API hint 存在时能利用 domain_bricks 加权
7. candidate_id 稳定性（幂等）
8. selected_for_phase_c / selected_for_phase_d 区分正确
9. github_repo 与 community_skill 严格区分（不允许混淆）
10. direction 全覆盖：不允许静默丢弃任何 search_direction
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# 引用 contracts 包
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "packages" / "contracts"))
# 引用 cross_project 包
sys.path.insert(0, str(Path(__file__).parent.parent))

from doramagic_contracts.base import NeedProfile, SearchDirection  # noqa: E402
from doramagic_contracts.cross_project import (  # noqa: E402
    ApiDomainHint,
    DiscoveryConfig,
    DiscoveryInput,
    DiscoveryResult,
)
from doramagic_contracts.envelope import ErrorCodes, ModuleResultEnvelope  # noqa: E402
from doramagic_cross_project.discovery import (  # noqa: E402
    _make_candidate_id,
    run_discovery,
    _MOCK_PROJECT_LIBRARY,
    _passes_coarse_filter,
    _DARK_TRAP_BLACKLIST,
)

# ──────────────────────────────────────────────────────────────────────────────
# Fixture 路径
# ──────────────────────────────────────────────────────────────────────────────

FIXTURE_DIR = (
    Path(__file__).parent.parent.parent.parent / "data" / "fixtures"
)
SIM2_PATH = FIXTURE_DIR / "sim2_need_profile.json"
SIM3_PATH = FIXTURE_DIR / "sim3_need_profile_flight.json"


# ──────────────────────────────────────────────────────────────────────────────
# Helper builders
# ──────────────────────────────────────────────────────────────────────────────


def _load_need_profile(path: Path) -> NeedProfile:
    """Load a NeedProfile from a JSON fixture file."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return NeedProfile.model_validate(raw)


def _make_input(
    need_profile: NeedProfile,
    api_hint: ApiDomainHint | None = None,
    config: DiscoveryConfig | None = None,
) -> DiscoveryInput:
    if config is None:
        config = DiscoveryConfig()
    return DiscoveryInput(
        need_profile=need_profile,
        api_hint=api_hint,
        config=config,
    )


def _make_empty_need_profile() -> NeedProfile:
    """构造一个匹配不到任何项目的 NeedProfile（用于测试无候选路径）。"""
    return NeedProfile(
        raw_input="我想做一个量子加密区块链 skill",
        keywords=["量子", "加密", "区块链"],
        intent="构建量子加密区块链 skill",
        search_directions=[
            SearchDirection(direction="量子计算框架", priority="high"),
            SearchDirection(direction="零知识证明库", priority="high"),
        ],
        constraints=["OpenClaw 平台"],
        quality_expectations={},
    )


# ──────────────────────────────────────────────────────────────────────────────
# Test 1: Sim2 卡路里正常路径
# ──────────────────────────────────────────────────────────────────────────────


def test_sim2_calorie_normal_path():
    """Sim2 卡路里场景：至少返回 2 个 github_repo + 1 个 community_skill。"""
    need_profile = _load_need_profile(SIM2_PATH)
    inp = _make_input(need_profile)
    envelope = run_discovery(inp)

    assert envelope.status in ("ok", "degraded"), f"Unexpected status: {envelope.status}"
    assert envelope.data is not None

    result: DiscoveryResult = envelope.data
    github_repos = [c for c in result.candidates if c.type == "github_repo"]
    community_skills = [c for c in result.candidates if c.type == "community_skill"]

    assert len(github_repos) >= 2, (
        f"Expected ≥2 github_repos, got {len(github_repos)}: "
        f"{[c.name for c in github_repos]}"
    )
    assert len(community_skills) >= 1, (
        f"Expected ≥1 community_skill, got {len(community_skills)}: "
        f"{[c.name for c in community_skills]}"
    )
    assert len(result.candidates) >= 3, (
        f"Expected ≥3 total candidates, got {len(result.candidates)}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Test 2: Sim3 机票正常路径
# ──────────────────────────────────────────────────────────────────────────────


def test_sim3_flight_normal_path():
    """Sim3 机票场景：至少返回 2 个 github_repo + 1 个 community_skill。"""
    need_profile = _load_need_profile(SIM3_PATH)
    inp = _make_input(need_profile)
    envelope = run_discovery(inp)

    assert envelope.status in ("ok", "degraded"), f"Unexpected status: {envelope.status}"
    assert envelope.data is not None

    result: DiscoveryResult = envelope.data
    github_repos = [c for c in result.candidates if c.type == "github_repo"]
    community_skills = [c for c in result.candidates if c.type == "community_skill"]

    assert len(github_repos) >= 2, (
        f"Expected ≥2 github_repos, got {len(github_repos)}: "
        f"{[c.name for c in github_repos]}"
    )
    assert len(community_skills) >= 1, (
        f"Expected ≥1 community_skill, got {len(community_skills)}: "
        f"{[c.name for c in community_skills]}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Test 3: search_coverage 完整性
# ──────────────────────────────────────────────────────────────────────────────


def test_search_coverage_completeness_sim2():
    """每个 search_direction 必须在 search_coverage 中有对应条目。"""
    need_profile = _load_need_profile(SIM2_PATH)
    inp = _make_input(need_profile)
    envelope = run_discovery(inp)

    result: DiscoveryResult = envelope.data
    assert result is not None

    direction_names = {sd.direction for sd in need_profile.search_directions}
    covered_directions = {sc.direction for sc in result.search_coverage}

    assert direction_names == covered_directions, (
        f"Missing directions in coverage: {direction_names - covered_directions}"
    )

    valid_statuses = {"covered", "partial", "missing"}
    for sc in result.search_coverage:
        assert sc.status in valid_statuses, f"Invalid status '{sc.status}' for {sc.direction}"


def test_search_coverage_completeness_sim3():
    """Sim3 机票场景：每个 search_direction 必须有覆盖状态。"""
    need_profile = _load_need_profile(SIM3_PATH)
    inp = _make_input(need_profile)
    envelope = run_discovery(inp)

    result: DiscoveryResult = envelope.data
    direction_names = {sd.direction for sd in need_profile.search_directions}
    covered_directions = {sc.direction for sc in result.search_coverage}

    assert direction_names == covered_directions


# ──────────────────────────────────────────────────────────────────────────────
# Test 4: 无候选时返回 degraded + E_NO_CANDIDATES
# ──────────────────────────────────────────────────────────────────────────────


def test_no_candidates_degraded():
    """当没有候选时，返回 degraded + E_NO_CANDIDATES，但 search_coverage 仍完整。"""
    need_profile = _make_empty_need_profile()
    # 设置极高的 stars 要求，强制过滤掉所有项目
    config = DiscoveryConfig(
        github_min_stars=999999,
        stale_months_threshold=1,
        top_k_final=5,
    )
    inp = _make_input(need_profile, config=config)
    envelope = run_discovery(inp)

    assert envelope.status == "degraded", f"Expected degraded, got {envelope.status}"
    assert envelope.error_code == ErrorCodes.NO_CANDIDATES, (
        f"Expected E_NO_CANDIDATES, got {envelope.error_code}"
    )
    assert envelope.data is not None

    result: DiscoveryResult = envelope.data
    assert result.candidates == [], "No candidates expected"
    assert result.no_candidate_reason is not None and len(result.no_candidate_reason) > 0

    # search_coverage 仍必须完整（不允许静默丢弃）
    direction_names = {sd.direction for sd in need_profile.search_directions}
    covered_directions = {sc.direction for sc in result.search_coverage}
    assert direction_names == covered_directions, (
        f"search_coverage missing directions: {direction_names - covered_directions}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Test 5: API hint 缺失时仍能独立工作
# ──────────────────────────────────────────────────────────────────────────────


def test_no_api_hint_still_works():
    """API hint 缺失时，结果仍能独立产出（不崩溃，有合理候选）。"""
    need_profile = _load_need_profile(SIM2_PATH)
    inp = _make_input(need_profile, api_hint=None)  # 显式 None
    envelope = run_discovery(inp)

    # 应有 W_NO_API_HINT 警告，但不影响结果
    warning_codes = [w.code for w in envelope.warnings]
    assert "W_NO_API_HINT" in warning_codes, (
        f"Expected W_NO_API_HINT warning, got: {warning_codes}"
    )

    assert envelope.data is not None
    assert len(envelope.data.candidates) >= 2, (
        "Should return at least 2 candidates even without api_hint"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Test 6: API hint 存在时能利用 domain_bricks 加权
# ──────────────────────────────────────────────────────────────────────────────


def test_api_hint_boosts_candidates():
    """API hint 带 domain_bricks 时，命中 bricks 的候选应排序更靠前。"""
    need_profile = _load_need_profile(SIM2_PATH)

    api_hint_with_bricks = ApiDomainHint(
        domain_id="nutrition",
        matched_keywords=["卡路里", "食物"],
        domain_bricks=["AI", "calorie"],
    )
    inp_with_hint = _make_input(need_profile, api_hint=api_hint_with_bricks)
    envelope_with = run_discovery(inp_with_hint)

    inp_without = _make_input(need_profile, api_hint=None)
    envelope_without = run_discovery(inp_without)

    # 两者都应能返回结果
    assert envelope_with.data is not None
    assert envelope_without.data is not None
    assert len(envelope_with.data.candidates) >= 2
    assert len(envelope_without.data.candidates) >= 2

    # 有 api_hint 时，ai-calorie-counter 应仍在候选中
    names_with = [c.name for c in envelope_with.data.candidates]
    assert "ai-calorie-counter" in names_with, (
        f"ai-calorie-counter should appear when API hint mentions 'calorie', got: {names_with}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Test 7: candidate_id 稳定性（幂等）
# ──────────────────────────────────────────────────────────────────────────────


def test_candidate_id_stability():
    """相同 URL 必须生成相同的 candidate_id（幂等性）。"""
    url = "https://github.com/open-kbs/ai-calorie-counter"
    id1 = _make_candidate_id(url)
    id2 = _make_candidate_id(url)
    assert id1 == id2, "candidate_id must be stable for the same URL"

    # 不同 URL 必须生成不同 id
    url2 = "https://github.com/simonoppowa/OpenNutriTracker"
    id3 = _make_candidate_id(url2)
    assert id1 != id3, "Different URLs must produce different candidate_ids"

    # 运行两次 discovery，同一候选的 id 必须一致
    need_profile = _load_need_profile(SIM2_PATH)
    inp = _make_input(need_profile)
    result1 = run_discovery(inp)
    result2 = run_discovery(inp)

    ids1 = {c.candidate_id for c in result1.data.candidates}
    ids2 = {c.candidate_id for c in result2.data.candidates}
    assert ids1 == ids2, "candidate_ids must be stable across repeated runs"


# ──────────────────────────────────────────────────────────────────────────────
# Test 8: selected_for_phase_c / selected_for_phase_d 区分正确
# ──────────────────────────────────────────────────────────────────────────────


def test_phase_c_and_phase_d_flags():
    """github_repo → selected_for_phase_c=True; community_skill → selected_for_phase_d=True。"""
    need_profile = _load_need_profile(SIM2_PATH)
    inp = _make_input(need_profile)
    envelope = run_discovery(inp)
    result: DiscoveryResult = envelope.data

    for cand in result.candidates:
        if cand.type == "github_repo":
            assert cand.selected_for_phase_c is True, (
                f"{cand.name} (github_repo) must have selected_for_phase_c=True"
            )
            assert cand.selected_for_phase_d is False, (
                f"{cand.name} (github_repo) must have selected_for_phase_d=False"
            )
        elif cand.type == "community_skill":
            assert cand.selected_for_phase_d is True, (
                f"{cand.name} (community_skill) must have selected_for_phase_d=True"
            )
            assert cand.selected_for_phase_c is False, (
                f"{cand.name} (community_skill) must have selected_for_phase_c=False"
            )


# ──────────────────────────────────────────────────────────────────────────────
# Test 9: github_repo 与 community_skill 严格区分
# ──────────────────────────────────────────────────────────────────────────────


def test_candidate_type_distinction():
    """所有候选的 type 必须是合法枚举值；clawhub:// URL 必须为 community_skill。"""
    need_profile = _load_need_profile(SIM2_PATH)
    inp = _make_input(need_profile)
    envelope = run_discovery(inp)
    result: DiscoveryResult = envelope.data

    valid_types = {"github_repo", "community_skill", "tutorial", "use_case"}
    for cand in result.candidates:
        assert cand.type in valid_types, f"Invalid type: {cand.type}"

        if cand.url.startswith("clawhub://"):
            assert cand.type == "community_skill", (
                f"{cand.url} should be community_skill, got {cand.type}"
            )

        if cand.url.startswith("https://github.com/"):
            assert cand.type == "github_repo", (
                f"{cand.url} should be github_repo, got {cand.type}"
            )


# ──────────────────────────────────────────────────────────────────────────────
# Test 10: direction 全覆盖 — 不允许静默丢弃任何 search_direction
# ──────────────────────────────────────────────────────────────────────────────


def test_all_directions_covered_in_search_coverage():
    """search_coverage 条目数必须等于 search_directions 数量。"""
    # 用有多个方向的 sim3 机票场景
    need_profile = _load_need_profile(SIM3_PATH)
    inp = _make_input(need_profile)
    envelope = run_discovery(inp)

    result: DiscoveryResult = envelope.data
    num_directions = len(need_profile.search_directions)
    num_coverage = len(result.search_coverage)

    assert num_coverage == num_directions, (
        f"search_coverage has {num_coverage} items but need_profile has "
        f"{num_directions} directions — some were silently dropped"
    )

    # 所有方向名称必须在 coverage 中出现
    direction_names = {sd.direction for sd in need_profile.search_directions}
    coverage_names = {sc.direction for sc in result.search_coverage}
    assert direction_names == coverage_names


# ──────────────────────────────────────────────────────────────────────────────
# Test 11: 暗雷黑名单过滤
# ──────────────────────────────────────────────────────────────────────────────


def test_blacklisted_urls_filtered_out():
    """暗雷黑名单中的 URL 不应出现在候选中。"""
    need_profile = _load_need_profile(SIM2_PATH)
    inp = _make_input(need_profile)
    envelope = run_discovery(inp)
    result: DiscoveryResult = envelope.data

    candidate_urls = {c.url for c in result.candidates}
    for blacklisted_url in _DARK_TRAP_BLACKLIST:
        assert blacklisted_url not in candidate_urls, (
            f"Blacklisted URL should not appear in candidates: {blacklisted_url}"
        )


# ──────────────────────────────────────────────────────────────────────────────
# Test 12: envelope schema 合规
# ──────────────────────────────────────────────────────────────────────────────


def test_envelope_schema_compliance():
    """返回的 envelope 必须符合统一 schema。"""
    need_profile = _load_need_profile(SIM2_PATH)
    inp = _make_input(need_profile)
    envelope = run_discovery(inp)

    assert envelope.schema_version == "dm.module-envelope.v1"
    assert envelope.module_name == "cross-project.discovery"
    assert envelope.status in ("ok", "degraded", "blocked", "error")
    assert envelope.metrics is not None
    assert envelope.metrics.wall_time_ms >= 0
    assert envelope.metrics.estimated_cost_usd >= 0

    result: DiscoveryResult = envelope.data
    assert result.schema_version == "dm.discovery-result.v1"
