"""Doramagic v13 记忆管理器 — 短期 + 长期用户画像。

存储位置：~/.doramagic/memory/{user_id}.json
离线工作，无需外部服务。

参考 DeerFlow 三层时间结构 + facts 列表设计：
- 短期记忆：当前会话焦点与最近请求历史
- 长期记忆：跨会话的用户偏好、领域兴趣、事实列表
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_DEFAULT_MEMORY_DIR = Path.home() / ".doramagic" / "memory"

# 技术术语关键词（用于推断技术水平）
_TECH_TERMS = frozenset(
    {
        "api",
        "sdk",
        "webhook",
        "http",
        "rest",
        "graphql",
        "json",
        "yaml",
        "docker",
        "kubernetes",
        "terraform",
        "ci/cd",
        "pipeline",
        "async",
        "await",
        "thread",
        "process",
        "regex",
        "orm",
        "sql",
        "nosql",
        "redis",
        "kafka",
        "grpc",
        "oauth",
        "jwt",
        "lambda",
        "recursion",
        "algorithm",
        "complexity",
        "bigquery",
        "pandas",
        "numpy",
        "pytorch",
        "tensorflow",
        "llm",
        "embedding",
        "vector",
        "git",
        "branch",
        "merge",
        "rebase",
        "cron",
        "systemd",
    }
)

# recent_requests 最大保留条数
_RECENT_REQUESTS_LIMIT = 10

# to_prompt_context 中 facts 最多展示条数（控制 token 长度）
_MAX_FACTS_IN_CONTEXT = 8

# 技术水平判断阈值：词频占比
_TECH_RATIO_ADVANCED = 0.10
_TECH_RATIO_INTERMEDIATE = 0.03

# 技术水平中文映射（用于 prompt 输出）
_TECH_LEVEL_LABELS: dict[str, str] = {
    "beginner": "初级",
    "intermediate": "中级",
    "advanced": "高级",
    "unknown": "未知",
}

# category 中文映射
_CATEGORY_LABELS: dict[str, str] = {
    "preference": "偏好",
    "knowledge": "知识背景",
    "context": "上下文",
    "behavior": "行为模式",
    "goal": "目标",
}


def _now_iso() -> str:
    """返回当前 UTC 时间的 ISO 8601 字符串。"""
    return datetime.now(UTC).isoformat()


class UserFact(BaseModel):
    """用户事实。

    属性：
        content: 事实内容描述。
        category: 分类，允许值：preference | knowledge | context | behavior | goal。
        confidence: 置信度，范围 0-1。
        created_at: 创建时间（ISO 8601 UTC）。
        source: 来源描述，通常是触发该事实提取的交互摘要。
    """

    content: str
    category: str
    confidence: float = 0.8
    created_at: str = Field(default_factory=_now_iso)
    source: str = ""


class UserProfile(BaseModel):
    """用户画像。

    属性：
        user_id: 用户标识符，默认 "default"。
        current_focus: 用户当前聚焦的任务或话题。
        recent_requests: 最近请求列表（FIFO，最多 10 条）。
        preferred_language: 界面/回复语言偏好，"auto" 表示自动检测。
        technical_level: 技术水平，beginner | intermediate | advanced | unknown。
        preferred_tools: 用户偏好使用的工具或库。
        avoided_tools: 用户明确不想使用的工具或库。
        domain_interests: 用户关注的领域（如金融、监控、办公）。
        facts: 用户事实列表。
        created_at: 档案创建时间（ISO 8601 UTC）。
        updated_at: 档案最后更新时间（ISO 8601 UTC）。
        interaction_count: 累计交互次数。
    """

    user_id: str = "default"

    # 短期记忆（当前焦点）
    current_focus: str = ""
    recent_requests: list[str] = Field(default_factory=list)

    # 长期记忆
    preferred_language: str = "auto"
    technical_level: str = "unknown"
    preferred_tools: list[str] = Field(default_factory=list)
    avoided_tools: list[str] = Field(default_factory=list)
    domain_interests: list[str] = Field(default_factory=list)

    # 事实列表（参考 DeerFlow）
    facts: list[UserFact] = Field(default_factory=list)

    # 元数据
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)
    interaction_count: int = 0


def _infer_technical_level(text: str) -> str:
    """从文本措辞推断用户技术水平。

    算法：统计技术术语在总词数中的占比，分档判断。
    简单关键词计数，无需 NLP 依赖。

    参数：
        text: 用户输入文本。

    返回：
        "advanced" | "intermediate" | "beginner"
    """
    words = text.lower().split()
    if not words:
        return "beginner"

    tech_count = sum(1 for w in words if w.strip(".,!?\"'()[]{}:;") in _TECH_TERMS)
    ratio = tech_count / len(words)

    if ratio >= _TECH_RATIO_ADVANCED:
        return "advanced"
    if ratio >= _TECH_RATIO_INTERMEDIATE:
        return "intermediate"
    return "beginner"


def _merge_technical_level(current: str, new_inference: str) -> str:
    """合并当前技术水平与新推断值。

    策略：保守上调——新推断更高才更新，避免单次偶然用词导致误降级。
    "unknown" 始终被新推断替换。

    参数：
        current: 当前技术水平标签。
        new_inference: 从最新交互推断的技术水平标签。

    返回：
        合并后的技术水平标签。
    """
    order = {"beginner": 0, "intermediate": 1, "advanced": 2, "unknown": -1}
    if current == "unknown":
        return new_inference
    if order.get(new_inference, -1) > order.get(current, -1):
        return new_inference
    return current


def _extract_domain_from_bricks(matched_bricks: list[str]) -> list[str]:
    """从匹配的积木 ID 中提取领域兴趣关键词。

    积木 ID 格式通常为 "category/subcategory/name"，提取第一段作为领域。

    参数：
        matched_bricks: 本次交互命中的积木 ID 列表。

    返回：
        提取出的领域关键词列表（去重）。
    """
    domains: list[str] = []
    for brick_id in matched_bricks:
        parts = brick_id.split("/")
        if parts:
            domain = parts[0].strip()
            if domain and domain not in domains:
                domains.append(domain)
    return domains


class MemoryManager:
    """记忆管理器。

    负责加载、保存、更新用户画像，并将画像格式化为可注入 system prompt 的文本。
    每个用户一个 JSON 文件，离线工作，无需外部服务。

    用法::

        mgr = MemoryManager()
        profile = mgr.load("alice")
        profile = mgr.update_from_interaction(
            user_id="alice",
            user_input="帮我用 akshare 查比特币价格",
            intent={"action": "query_price"},
            matched_bricks=["finance/crypto/btc"],
            result_success=True,
        )
        ctx = mgr.to_prompt_context("alice")
    """

    def __init__(self, memory_dir: str | Path | None = None) -> None:
        """初始化记忆管理器。

        参数：
            memory_dir: 记忆文件存储目录。默认 ~/.doramagic/memory/。
        """
        self._memory_dir = Path(memory_dir).resolve() if memory_dir else _DEFAULT_MEMORY_DIR

    def _profile_path(self, user_id: str) -> Path:
        """返回指定用户的画像文件路径。

        参数：
            user_id: 用户标识符。

        返回：
            画像文件的绝对路径。
        """
        # 简单清理：只保留字母数字和下划线，防止路径穿越
        safe_id = "".join(c if c.isalnum() or c in "_-" else "_" for c in user_id)
        return self._memory_dir / f"{safe_id}.json"

    def load(self, user_id: str = "default") -> UserProfile:
        """加载用户画像。文件不存在时返回新建的空画像。

        参数：
            user_id: 用户标识符。

        返回：
            用户画像对象。
        """
        path = self._profile_path(user_id)
        if not path.exists():
            logger.debug("memory file not found, returning blank profile: %s", path)
            return UserProfile(user_id=user_id)

        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
            profile = UserProfile.model_validate(data)
            logger.debug(
                "loaded memory profile: user=%s, interactions=%d",
                user_id,
                profile.interaction_count,
            )
            return profile
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning(
                "failed to parse memory file %s: %s — returning blank profile", path, exc
            )
            return UserProfile(user_id=user_id)

    def save(self, profile: UserProfile) -> None:
        """保存用户画像到 JSON 文件。

        参数：
            profile: 要保存的用户画像对象。
        """
        path = self._profile_path(profile.user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        profile.updated_at = _now_iso()
        path.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
        logger.debug("saved memory profile: user=%s -> %s", profile.user_id, path)

    def update_from_interaction(
        self,
        user_id: str,
        user_input: str,
        intent: dict,
        matched_bricks: list[str],
        result_success: bool,
    ) -> UserProfile:
        """从一次交互中更新用户画像并持久化。

        自动提取：
        - 当前焦点（current_focus）：设为本次用户输入
        - 请求历史（recent_requests）：追加并保持最多 10 条
        - 技术水平（technical_level）：从用户输入措辞推断，保守上调
        - 领域兴趣（domain_interests）：从 matched_bricks 的分类前缀提取
        - 交互计数（interaction_count）：递增

        参数：
            user_id: 用户标识符。
            user_input: 本次用户输入文本。
            intent: 意图解析结果字典（当前暂不用于自动提取，供扩展）。
            matched_bricks: 本次命中的积木 ID 列表。
            result_success: 本次交互是否成功产出结果。

        返回：
            更新后的用户画像对象。
        """
        profile = self.load(user_id)

        # 更新短期记忆
        profile.current_focus = user_input[:200]  # 截断防止过长
        profile.recent_requests.append(user_input[:200])
        if len(profile.recent_requests) > _RECENT_REQUESTS_LIMIT:
            profile.recent_requests = profile.recent_requests[-_RECENT_REQUESTS_LIMIT:]

        # 推断技术水平（保守上调）
        inferred = _infer_technical_level(user_input)
        profile.technical_level = _merge_technical_level(profile.technical_level, inferred)

        # 提取领域兴趣
        new_domains = _extract_domain_from_bricks(matched_bricks)
        for domain in new_domains:
            if domain not in profile.domain_interests:
                profile.domain_interests.append(domain)

        profile.interaction_count += 1

        self.save(profile)
        logger.debug(
            "updated profile: user=%s, tech_level=%s, domains=%s",
            user_id,
            profile.technical_level,
            profile.domain_interests,
        )
        return profile

    def to_prompt_context(self, user_id: str = "default") -> str:
        """将用户画像格式化为可注入 system prompt 的文本。

        格式示例::

            用户画像：
            - 技术水平：中级
            - 偏好语言：中文
            - 关注领域：金融、监控
            - 偏好工具：akshare
            - 近期关注：比特币价格监控

        控制在 500 tokens 以内。

        参数：
            user_id: 用户标识符。

        返回：
            格式化后的画像文本，若画像为空则返回空字符串。
        """
        profile = self.load(user_id)

        # 画像完全空时不注入上下文，避免无意义噪音
        if profile.interaction_count == 0 and not profile.facts:
            return ""

        lines: list[str] = ["用户画像："]

        tech_label = _TECH_LEVEL_LABELS.get(profile.technical_level, profile.technical_level)
        if profile.technical_level != "unknown":
            lines.append(f"- 技术水平：{tech_label}")

        if profile.preferred_language != "auto":
            lines.append(f"- 偏好语言：{profile.preferred_language}")

        if profile.domain_interests:
            lines.append(f"- 关注领域：{'、'.join(profile.domain_interests[:6])}")

        if profile.preferred_tools:
            lines.append(f"- 偏好工具：{'、'.join(profile.preferred_tools[:5])}")

        if profile.avoided_tools:
            lines.append(f"- 不使用：{'、'.join(profile.avoided_tools[:5])}")

        if profile.current_focus:
            lines.append(f"- 近期关注：{profile.current_focus[:100]}")

        # 事实列表：按 confidence 降序取前 N 条
        top_facts = sorted(profile.facts, key=lambda f: f.confidence, reverse=True)[
            :_MAX_FACTS_IN_CONTEXT
        ]
        if top_facts:
            lines.append("- 已知事实：")
            for fact in top_facts:
                cat_label = _CATEGORY_LABELS.get(fact.category, fact.category)
                lines.append(f"  [{cat_label}] {fact.content}")

        return "\n".join(lines)

    def add_fact(
        self,
        user_id: str,
        content: str,
        category: str,
        source: str = "",
    ) -> None:
        """手动添加用户事实。相同内容的 fact 不重复，更新 confidence。

        参数：
            user_id: 用户标识符。
            content: 事实内容描述。
            category: 事实分类（preference | knowledge | context | behavior | goal）。
            source: 来源描述（可选）。
        """
        profile = self.load(user_id)

        # 去重：content 完全一致时更新 confidence 和 source，不新增
        for existing in profile.facts:
            if existing.content == content:
                existing.confidence = min(1.0, existing.confidence + 0.1)
                if source:
                    existing.source = source
                logger.debug("fact already exists, boosted confidence: %r", content[:60])
                self.save(profile)
                return

        new_fact = UserFact(content=content, category=category, source=source)
        profile.facts.append(new_fact)
        self.save(profile)
        logger.debug("added new fact: category=%s, content=%r", category, content[:60])

    def get_facts(
        self,
        user_id: str,
        category: str | None = None,
    ) -> list[UserFact]:
        """获取用户事实列表，可按分类过滤。

        参数：
            user_id: 用户标识符。
            category: 若提供，只返回该分类的事实；None 返回全部。

        返回：
            用户事实列表，按 confidence 降序排列。
        """
        profile = self.load(user_id)
        facts = profile.facts
        if category is not None:
            facts = [f for f in facts if f.category == category]
        return sorted(facts, key=lambda f: f.confidence, reverse=True)
