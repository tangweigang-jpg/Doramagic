"""cross-project.discovery — 候选项目发现模块。

职责：把用户模糊需求转换成 3-5 个高价值候选项目和 0-N 个社区资源，
并明确覆盖了哪些搜索方向。

设计原则：
- 粗筛：stars > 10，6 个月内更新，有 README，不在暗雷黑名单
- 精筛：相关度 + 质量信号 + 知识互补性
- candidate_id 由 URL hash 生成，必须稳定（幂等）
- search_coverage 必须覆盖所有 search_directions，不允许静默丢弃
- github_repo 与 community_skill 必须严格区分

当前实现：基于内置项目库的 mock 版本（10-15 个项目）。
真实 GitHub API 集成留给后续。
"""

from __future__ import annotations

import hashlib
import math
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# 引用 contracts 包
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "contracts"))
# 引用 cross_project 包（供外部调用时使用）
sys.path.insert(0, str(Path(__file__).parent.parent))

from doramagic_contracts.base import (  # noqa: E402
    CandidateQualitySignals,
    DiscoveryCandidate,
    SearchCoverageItem,
)
from doramagic_contracts.cross_project import (  # noqa: E402
    ApiDomainHint,
    DiscoveryConfig,
    DiscoveryInput,
    DiscoveryResult,
)
from doramagic_contracts.envelope import (  # noqa: E402
    ErrorCodes,
    ModuleResultEnvelope,
    RunMetrics,
    WarningItem,
)

MODULE_NAME = "cross-project.discovery"

# ──────────────────────────────────────────────────────────────────────────────
# 暗雷黑名单：已知不适合参考的项目
# ──────────────────────────────────────────────────────────────────────────────

_DARK_TRAP_BLACKLIST = {
    "https://github.com/example/abandoned-diet-app",  # 已废弃
    "https://github.com/example/closed-source-flight",  # 闭源
}

# ──────────────────────────────────────────────────────────────────────────────
# 内置项目库（Mock）
# 涵盖：卡路里/健康、财务、笔记、旅行/机票、NLU 等领域
# ──────────────────────────────────────────────────────────────────────────────

_MOCK_PROJECT_LIBRARY: list[dict] = [
    # === 卡路里 / 营养 / 健身 ===
    {
        "name": "ai-calorie-counter",
        "url": "https://github.com/open-kbs/ai-calorie-counter",
        "type": "github_repo",
        "tags": ["卡路里", "calorie", "食物", "food", "AI", "识别", "热量", "估算"],
        "directions": ["AI 食物识别", "卡路里计算", "卡路里估算", "食物识别"],
        "stars": 128,
        "forks": 14,
        "last_updated": "2026-03-01",
        "has_readme": True,
        "license": "MIT",
        "issue_activity": "medium",
        "description": "AI 食物识别 + 卡路里估算核心架构，LLM-as-Parser 模式",
        "knowledge_domains": ["AI食物识别", "卡路里计算", "LLM解析"],
        "complementarity_score": 0.9,
    },
    {
        "name": "OpenNutriTracker",
        "url": "https://github.com/simonoppowa/OpenNutriTracker",
        "type": "github_repo",
        "tags": ["营养", "nutrition", "食物", "food", "数据库", "database", "卡路里", "calorie"],
        "directions": ["营养数据库", "食物成分", "食物成分表", "营养数据"],
        "stars": 430,
        "forks": 52,
        "last_updated": "2025-12-15",
        "has_readme": True,
        "license": "GPL-3.0",
        "issue_activity": "active",
        "description": "开源营养追踪应用，包含完整食物成分数据库集成",
        "knowledge_domains": ["营养数据库", "食物成分", "移动端架构"],
        "complementarity_score": 0.85,
    },
    {
        "name": "FoodYou",
        "url": "https://github.com/Vazkii/FoodYou",
        "type": "github_repo",
        "tags": ["食物", "food", "健康", "health", "追踪", "tracker", "营养", "nutrition"],
        "directions": ["营养数据库", "健康追踪", "健康追踪应用", "食物追踪"],
        "stars": 215,
        "forks": 28,
        "last_updated": "2026-01-20",
        "has_readme": True,
        "license": "MIT",
        "issue_activity": "medium",
        "description": "简洁的食物追踪应用，UX 优先设计",
        "knowledge_domains": ["健康追踪", "用户界面", "饮食记录"],
        "complementarity_score": 0.75,
    },
    {
        "name": "wger",
        "url": "https://github.com/wger-project/wger",
        "type": "github_repo",
        "tags": ["健身", "fitness", "营养", "nutrition", "健康", "health", "追踪", "tracker"],
        "directions": ["健康追踪应用", "健康追踪", "营养数据库", "健身追踪"],
        "stars": 3800,
        "forks": 620,
        "last_updated": "2026-02-28",
        "has_readme": True,
        "license": "AGPL-3.0",
        "issue_activity": "active",
        "description": "成熟的健身 + 营养管理平台，REST API 完善",
        "knowledge_domains": ["健康追踪", "REST API", "营养管理", "多平台"],
        "complementarity_score": 0.7,
    },
    {
        "name": "calorie-counter",
        "url": "clawhub://cnqso/calorie-counter",
        "type": "community_skill",
        "tags": ["卡路里", "calorie", "OpenClaw", "skill", "饮食", "饮食记录"],
        "directions": ["OpenClaw 社区", "社区 skill", "饮食/健康 skill", "饮食 skill", "健康 skill"],
        "stars": None,
        "forks": None,
        "last_updated": None,
        "has_readme": True,
        "license": None,
        "issue_activity": None,
        "description": "OpenClaw 原生卡路里追踪 skill，可直接参考格式",
        "knowledge_domains": ["OpenClaw格式", "卡路里追踪"],
        "complementarity_score": 0.95,
    },
    {
        "name": "diet-tracker-skill",
        "url": "clawhub://healthbot/diet-tracker",
        "type": "community_skill",
        "tags": ["饮食", "diet", "健康", "health", "OpenClaw", "skill", "追踪", "tracker"],
        "directions": ["OpenClaw 社区", "社区 skill", "饮食/健康 skill", "饮食 skill", "健康 skill"],
        "stars": None,
        "forks": None,
        "last_updated": None,
        "has_readme": True,
        "license": None,
        "issue_activity": None,
        "description": "OpenClaw 饮食追踪 skill，支持中文交互",
        "knowledge_domains": ["OpenClaw格式", "饮食追踪", "中文"],
        "complementarity_score": 0.88,
    },
    # === 机票 / 旅行 ===
    {
        "name": "flight-search-api-demo",
        "url": "https://github.com/amadeus4dev/amadeus-flight-price-analysis",
        "type": "github_repo",
        "tags": ["机票", "flight", "Amadeus", "API", "搜索", "search", "旅行", "travel"],
        "directions": ["航班搜索 API", "Amadeus", "Skyscanner", "机票搜索"],
        "stars": 342,
        "forks": 87,
        "last_updated": "2025-11-10",
        "has_readme": True,
        "license": "MIT",
        "issue_activity": "medium",
        "description": "Amadeus API 机票价格分析示例，含 API 集成最佳实践",
        "knowledge_domains": ["Amadeus API", "机票搜索", "价格分析"],
        "complementarity_score": 0.9,
    },
    {
        "name": "cheap-flights-aggregator",
        "url": "https://github.com/paulc/cheapflights",
        "type": "github_repo",
        "tags": ["机票", "flight", "比价", "compare", "聚合", "aggregator", "价格", "price"],
        "directions": ["机票比价", "机票比价聚合器", "比价聚合", "机票聚合"],
        "stars": 156,
        "forks": 31,
        "last_updated": "2025-10-05",
        "has_readme": True,
        "license": "Apache-2.0",
        "issue_activity": "low",
        "description": "多源机票比价聚合器，支持 Skyscanner/Kiwi 等多个 API",
        "knowledge_domains": ["机票比价", "多API聚合", "价格对比"],
        "complementarity_score": 0.85,
    },
    {
        "name": "kiwi-tequila-client",
        "url": "https://github.com/kiwicom/tequila-python",
        "type": "github_repo",
        "tags": ["机票", "flight", "Kiwi", "API", "搜索", "search", "旅行", "travel"],
        "directions": ["航班搜索 API", "Kiwi", "机票搜索", "机票 API"],
        "stars": 89,
        "forks": 22,
        "last_updated": "2025-09-15",
        "has_readme": True,
        "license": "MIT",
        "issue_activity": "low",
        "description": "Kiwi Tequila API Python 客户端，免费额度机票搜索",
        "knowledge_domains": ["Kiwi API", "低成本API", "机票搜索"],
        "complementarity_score": 0.8,
    },
    {
        "name": "flight-booking-skill",
        "url": "clawhub://travelbot/flight-booking",
        "type": "community_skill",
        "tags": ["机票", "flight", "旅行", "travel", "OpenClaw", "skill", "预订", "booking"],
        "directions": ["OpenClaw 社区", "社区 skill", "旅行/机票 skill", "机票 skill"],
        "stars": None,
        "forks": None,
        "last_updated": None,
        "has_readme": True,
        "license": None,
        "issue_activity": None,
        "description": "OpenClaw 机票搜索 skill，支持中文出发地/目的地解析",
        "knowledge_domains": ["OpenClaw格式", "机票搜索", "NLU解析"],
        "complementarity_score": 0.92,
    },
    {
        "name": "rasa-travel-nlu",
        "url": "https://github.com/rasa/rasa-travel-demo",
        "type": "github_repo",
        "tags": ["NLU", "自然语言", "旅行", "travel", "解析", "parse", "出发地", "目的地"],
        "directions": ["NLU", "自然语言解析", "出发地/目的地解析", "NLU 方案"],
        "stars": 524,
        "forks": 143,
        "last_updated": "2025-08-20",
        "has_readme": True,
        "license": "Apache-2.0",
        "issue_activity": "low",
        "description": "Rasa 旅行 NLU demo，包含出发地/目的地/时间实体识别",
        "knowledge_domains": ["NLU", "实体识别", "旅行领域"],
        "complementarity_score": 0.75,
    },
    # === 财务 / 笔记（填充多样性）===
    {
        "name": "budget-tracker",
        "url": "https://github.com/nickspaargaren/budget-tracker",
        "type": "github_repo",
        "tags": ["财务", "finance", "预算", "budget", "追踪", "tracker", "记录"],
        "directions": ["财务追踪", "预算管理", "记账"],
        "stars": 45,
        "forks": 8,
        "last_updated": "2025-07-10",
        "has_readme": True,
        "license": "MIT",
        "issue_activity": "low",
        "description": "简单的预算追踪工具",
        "knowledge_domains": ["财务追踪", "预算管理"],
        "complementarity_score": 0.5,
    },
    {
        "name": "obsidian-plugin-tracker",
        "url": "https://github.com/pyrochlore/obsidian-tracker",
        "type": "github_repo",
        "tags": ["笔记", "note", "追踪", "tracker", "记录", "记录模式"],
        "directions": ["追踪模式", "记录模式", "习惯追踪"],
        "stars": 1200,
        "forks": 89,
        "last_updated": "2025-06-30",
        "has_readme": True,
        "license": "MIT",
        "issue_activity": "medium",
        "description": "Obsidian 追踪插件，通用数据追踪模式参考",
        "knowledge_domains": ["追踪模式", "数据可视化"],
        "complementarity_score": 0.5,
    },
]

# ──────────────────────────────────────────────────────────────────────────────
# Utilities
# ──────────────────────────────────────────────────────────────────────────────


def _make_candidate_id(url: str) -> str:
    """由 URL hash 生成稳定的 candidate_id。"""
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:8]
    return f"cand-{digest}"


def _is_recent(last_updated_str: Optional[str], stale_months: int) -> bool:
    """判断项目是否在 stale_months 个月内有更新。community_skill 无日期时视为通过。"""
    if last_updated_str is None:
        return True  # community skill 无日期，不过滤
    try:
        last_updated = datetime.strptime(last_updated_str, "%Y-%m-%d")
        cutoff = datetime.now() - timedelta(days=stale_months * 30)
        return last_updated >= cutoff
    except ValueError:
        return True  # 无法解析时宽松处理


def _passes_coarse_filter(
    project: dict,
    config: DiscoveryConfig,
) -> bool:
    """粗筛：stars, 更新时间, README, 暗雷黑名单。

    community_skill 的 stars 字段为 None，跳过 stars 检查。
    """
    url = project["url"]
    if url in _DARK_TRAP_BLACKLIST:
        return False

    if not project.get("has_readme", False):
        return False

    # community_skill 不做 stars/更新 检查
    if project["type"] == "github_repo":
        stars = project.get("stars")
        if stars is None or stars < config.github_min_stars:
            return False
        if not _is_recent(project.get("last_updated"), config.stale_months_threshold):
            return False

    return True


def _direction_relevance_score(project: dict, direction: str) -> float:
    """计算项目与某个搜索方向的相关度（0-1）。

    策略：关键词匹配 + 显式方向声明。
    """
    score = 0.0
    direction_lower = direction.lower()

    # 检查 directions 字段中的显式声明
    for d in project.get("directions", []):
        if d.lower() in direction_lower or direction_lower in d.lower():
            score += 0.6
            break
        # 部分匹配：direction 中有 d 的关键词
        d_words = set(d.lower().split())
        dir_words = set(direction_lower.split())
        overlap = d_words & dir_words
        if overlap:
            score += 0.3 * (len(overlap) / max(len(d_words), 1))

    # 检查 tags 关键词匹配
    tag_score = 0.0
    for tag in project.get("tags", []):
        if tag.lower() in direction_lower:
            tag_score += 0.1
    score += min(tag_score, 0.4)

    return min(score, 1.0)


def _quality_score(project: dict) -> float:
    """计算项目质量分（0-1）。

    综合 stars、forks、更新频率、issue 活跃度。
    community_skill 使用固定中等质量分。
    """
    if project["type"] == "community_skill":
        return 0.65  # community skill 无量化指标，给中等固定分

    stars = project.get("stars") or 0
    forks = project.get("forks") or 0
    issue_activity = project.get("issue_activity", "low")

    # stars 分（log scale，1000 stars ≈ 0.5）
    stars_score = min(math.log10(max(stars, 1)) / 4.0, 0.5)

    # forks 比率分
    forks_ratio = forks / max(stars, 1)
    forks_score = min(forks_ratio * 0.5, 0.2)

    # issue 活跃度分
    activity_map = {"active": 0.2, "medium": 0.15, "low": 0.05}
    activity_score = activity_map.get(issue_activity, 0.1)

    # 更新时间分
    last_updated = project.get("last_updated")
    recency_score = 0.0
    if last_updated:
        try:
            lu = datetime.strptime(last_updated, "%Y-%m-%d")
            days_ago = (datetime.now() - lu).days
            if days_ago < 90:
                recency_score = 0.1
            elif days_ago < 180:
                recency_score = 0.07
            elif days_ago < 365:
                recency_score = 0.04
        except ValueError:
            pass

    return min(stars_score + forks_score + activity_score + recency_score, 1.0)


def _compute_quick_score(project: dict, direction: str) -> float:
    """综合得分（0-10）：相关度 × 0.5 + 质量 × 0.3 + 互补性 × 0.2。"""
    relevance = _direction_relevance_score(project, direction)
    quality = _quality_score(project)
    complementarity = project.get("complementarity_score", 0.5)

    raw = relevance * 0.5 + quality * 0.3 + complementarity * 0.2
    return round(min(raw * 10, 10.0), 2)


def _search_direction(
    direction: str,
    priority: str,
    all_projects: list[dict],
    config: DiscoveryConfig,
    api_hint: Optional[ApiDomainHint],
) -> list[dict]:
    """搜索单个方向，返回粗筛通过的候选列表（含得分）。

    api_hint 存在时，利用 domain_bricks 对候选加权。
    """
    candidates_with_score = []

    # Minimum relevance threshold: projects with 0 relevance are not useful
    _MIN_RELEVANCE = 0.05

    for proj in all_projects:
        if not _passes_coarse_filter(proj, config):
            continue

        relevance = _direction_relevance_score(proj, direction)
        if relevance < _MIN_RELEVANCE:
            continue

        score = _compute_quick_score(proj, direction)
        if score <= 0:
            continue

        # api_hint 加权：如果项目 tags 命中 domain_bricks，+0.5 分
        if api_hint and api_hint.domain_bricks:
            for brick in api_hint.domain_bricks:
                brick_lower = brick.lower()
                for tag in proj.get("tags", []):
                    if brick_lower in tag.lower() or tag.lower() in brick_lower:
                        score = min(score + 0.5, 10.0)
                        break

        candidates_with_score.append({**proj, "_score": score, "_direction": direction})

    # 按得分降序
    candidates_with_score.sort(key=lambda x: x["_score"], reverse=True)
    return candidates_with_score[: config.github_max_candidates_per_direction]


def _determine_coverage_status(
    direction: str, matched_projects: list[dict]
) -> tuple[str, str]:
    """判断该方向的覆盖状态。

    - covered：有 1 个以上强匹配（score >= 4）
    - partial：有候选但得分偏低（score < 4）
    - missing：无候选
    """
    if not matched_projects:
        return "missing", f"No candidates found for direction: {direction}"

    best_score = max(p["_score"] for p in matched_projects)
    if best_score >= 4.0:
        names = [p["name"] for p in matched_projects[:3]]
        return "covered", f"Found: {', '.join(names)}"
    else:
        names = [p["name"] for p in matched_projects[:2]]
        return "partial", f"Low-confidence matches: {', '.join(names)}"


def _deduplicate_and_rank(
    all_candidates: list[dict],
    config: DiscoveryConfig,
) -> list[dict]:
    """去重并按综合得分排序，保证 github_repo 和 community_skill 都有代表。

    策略：
    1. URL 去重（取最高分）
    2. 强制至少 1 个 community_skill（如有）
    3. 取 top_k_final 个
    """
    # URL 去重：取每个 URL 的最高分
    seen_urls: dict[str, dict] = {}
    for cand in all_candidates:
        url = cand["url"]
        if url not in seen_urls or cand["_score"] > seen_urls[url]["_score"]:
            seen_urls[url] = cand

    unique = list(seen_urls.values())
    unique.sort(key=lambda x: x["_score"], reverse=True)

    # 分类
    github_repos = [p for p in unique if p["type"] == "github_repo"]
    community_skills = [p for p in unique if p["type"] == "community_skill"]

    # 构建最终列表：保证 github_repo 和 community_skill 都有
    result: list[dict] = []
    top_k = config.top_k_final

    # 至少留 1 个 community_skill 槽位（如果有的话）
    if community_skills:
        # 先加顶部 (top_k - 1) 个 github_repo
        result.extend(github_repos[: max(top_k - 1, 1)])
        # 再补 community_skill
        remaining = top_k - len(result)
        result.extend(community_skills[:remaining])
    else:
        result.extend(github_repos[:top_k])

    # 最后按得分重排
    result.sort(key=lambda x: x["_score"], reverse=True)
    return result[:top_k]


def _build_discovery_candidate(
    project: dict, is_phase_c: bool, is_phase_d: bool
) -> DiscoveryCandidate:
    """从项目字典构建 DiscoveryCandidate。"""
    candidate_id = _make_candidate_id(project["url"])

    quality_signals = CandidateQualitySignals(
        stars=project.get("stars"),
        forks=project.get("forks"),
        last_updated=project.get("last_updated"),
        has_readme=project.get("has_readme", True),
        issue_activity=project.get("issue_activity"),
        license=project.get("license"),
    )

    return DiscoveryCandidate(
        candidate_id=candidate_id,
        name=project["name"],
        url=project["url"],
        type=project["type"],
        relevance=_score_to_priority(project["_score"]),
        contribution=project.get("description", ""),
        quick_score=project["_score"],
        quality_signals=quality_signals,
        selected_for_phase_c=is_phase_c,
        selected_for_phase_d=is_phase_d,
    )


def _score_to_priority(score: float) -> str:
    """将数值得分转为优先级标签。"""
    if score >= 6.0:
        return "high"
    elif score >= 4.0:
        return "medium"
    else:
        return "low"


# ──────────────────────────────────────────────────────────────────────────────
# 主函数
# ──────────────────────────────────────────────────────────────────────────────


def run_discovery(input: DiscoveryInput) -> ModuleResultEnvelope[DiscoveryResult]:
    """执行候选项目发现。

    按 need_profile.search_directions 并行搜索（mock：内置项目库匹配），
    粗筛 + 精筛后输出 3-5 个候选，并明确覆盖了哪些搜索方向。
    """
    t_start = time.monotonic()
    warnings: list[WarningItem] = []

    need_profile = input.need_profile
    config = input.config
    api_hint = input.api_hint

    if api_hint is None:
        warnings.append(
            WarningItem(
                code="W_NO_API_HINT",
                message="api_hint not provided; proceeding with library-only search",
            )
        )

    all_projects = _MOCK_PROJECT_LIBRARY

    # ──────────────────────────────────────────────────────────────────────────
    # 按 search_directions 并行搜索（当前 mock，直接串行）
    # ──────────────────────────────────────────────────────────────────────────
    direction_results: dict[str, list[dict]] = {}
    for sd in need_profile.search_directions:
        matched = _search_direction(
            direction=sd.direction,
            priority=sd.priority,
            all_projects=all_projects,
            config=config,
            api_hint=api_hint,
        )
        direction_results[sd.direction] = matched

    # ──────────────────────────────────────────────────────────────────────────
    # 构建 search_coverage（不允许静默丢弃任何方向）
    # ──────────────────────────────────────────────────────────────────────────
    search_coverage: list[SearchCoverageItem] = []
    for sd in need_profile.search_directions:
        matched = direction_results[sd.direction]
        status, notes = _determine_coverage_status(sd.direction, matched)
        search_coverage.append(
            SearchCoverageItem(
                direction=sd.direction,
                status=status,
                notes=notes,
            )
        )

    # ──────────────────────────────────────────────────────────────────────────
    # 合并所有方向的候选，去重，排序
    # ──────────────────────────────────────────────────────────────────────────
    all_candidates_flat: list[dict] = []
    for matched in direction_results.values():
        all_candidates_flat.extend(matched)

    final_projects = _deduplicate_and_rank(all_candidates_flat, config)

    # ──────────────────────────────────────────────────────────────────────────
    # 标记 selected_for_phase_c / selected_for_phase_d
    #   - github_repo → phase_c（代码提取）
    #   - community_skill → phase_d（社区资源）
    # ──────────────────────────────────────────────────────────────────────────
    candidates: list[DiscoveryCandidate] = []
    for proj in final_projects:
        is_github = proj["type"] == "github_repo"
        is_community = proj["type"] == "community_skill"
        cand = _build_discovery_candidate(
            project=proj,
            is_phase_c=is_github,
            is_phase_d=is_community,
        )
        candidates.append(cand)

    # ──────────────────────────────────────────────────────────────────────────
    # 检查是否有候选
    # ──────────────────────────────────────────────────────────────────────────
    t_end = time.monotonic()
    wall_time_ms = int((t_end - t_start) * 1000)

    metrics = RunMetrics(
        wall_time_ms=wall_time_ms,
        llm_calls=0,
        prompt_tokens=0,
        completion_tokens=0,
        estimated_cost_usd=0.0,
        retries=0,
    )

    if not candidates:
        result = DiscoveryResult(
            candidates=[],
            search_coverage=search_coverage,
            no_candidate_reason=(
                "No candidates passed coarse filter for any search direction. "
                "Try relaxing github_min_stars or stale_months_threshold."
            ),
        )
        return ModuleResultEnvelope(
            module_name=MODULE_NAME,
            status="degraded",
            error_code=ErrorCodes.NO_CANDIDATES,
            warnings=warnings,
            data=result,
            metrics=metrics,
        )

    # 检查是否少于 3 个候选（降级警告）
    if len(candidates) < 3:
        warnings.append(
            WarningItem(
                code="W_FEW_CANDIDATES",
                message=f"Only {len(candidates)} candidate(s) found; expected 3-5",
            )
        )

    # 检查 missing 方向
    missing_directions = [
        sc.direction for sc in search_coverage if sc.status == "missing"
    ]
    if missing_directions:
        warnings.append(
            WarningItem(
                code="W_MISSING_DIRECTIONS",
                message=f"No candidates found for directions: {missing_directions}",
            )
        )

    result = DiscoveryResult(
        candidates=candidates,
        search_coverage=search_coverage,
        no_candidate_reason=None,
    )

    status = "ok"
    if missing_directions or len(candidates) < 3:
        status = "degraded"

    return ModuleResultEnvelope(
        module_name=MODULE_NAME,
        status=status,
        error_code=None,
        warnings=warnings,
        data=result,
        metrics=metrics,
    )
