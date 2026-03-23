"""Phase A executor: Parse user input into a NeedProfile.

Uses LLM when available, falls back to heuristic keyword extraction.
Signals CLARIFY when input is too ambiguous to parse.
"""

from __future__ import annotations

import re
import time

from pydantic import BaseModel

from doramagic_contracts.base import NeedProfile, SearchDirection
from doramagic_contracts.envelope import ErrorCodes, ModuleResultEnvelope, RunMetrics, WarningItem
from doramagic_contracts.executor import ExecutorConfig

# Chinese → English keyword mapping (from singleshot + pipeline)
_CN_TO_EN: dict[str, list[str]] = {
    "记账": ["accounting", "expense tracker", "finance"],
    "菜谱": ["recipe", "cookbook", "meal planner"],
    "日记": ["journal", "diary", "note taking"],
    "翻译": ["translation", "translator", "i18n"],
    "天气": ["weather", "forecast", "climate"],
    "健身": ["fitness", "workout", "exercise tracker"],
    "阅读": ["reading", "book", "reader"],
    "音乐": ["music", "player", "audio"],
    "照片": ["photo", "gallery", "image"],
    "视频": ["video", "player", "streaming"],
    "购物": ["shopping", "e-commerce", "cart"],
    "社交": ["social", "chat", "messaging"],
    "地图": ["map", "navigation", "location"],
    "日历": ["calendar", "schedule", "planner"],
    "密码": ["password", "credential", "security"],
    "备份": ["backup", "sync", "storage"],
    "下载": ["download", "downloader", "torrent"],
    "管理": ["management", "admin", "dashboard"],
    "监控": ["monitoring", "alerting", "observability"],
    "自动化": ["automation", "workflow", "pipeline"],
}

# Stopwords to filter out
_STOPWORDS = {"的", "了", "是", "在", "我", "要", "做", "一个", "帮我", "帮", "app", "skill", "工具", "一下"}


class NeedProfileBuilder:
    """Builds a NeedProfile from raw user input.

    Supports two modes:
    - LLM mode: uses adapter to parse intent (richer, more accurate)
    - Heuristic mode: CN→EN keyword extraction (always available)

    If input is too ambiguous, returns degraded with CLARIFY warning.
    """

    async def execute(
        self, input: BaseModel, adapter: object, config: ExecutorConfig,
    ) -> ModuleResultEnvelope[NeedProfile]:
        start = time.monotonic()
        raw = input.raw_input if hasattr(input, "raw_input") else str(input)

        # Strip /dora prefix
        raw = re.sub(r"^/?dora\s*", "", raw).strip()

        if not raw:
            return self._error_result(ErrorCodes.INPUT_INVALID, "Empty input", start)

        # Try heuristic parsing (always available, no LLM cost)
        profile = self._build_heuristic(raw)

        # Check if we have enough signal
        if len(profile.keywords) < 2 and len(profile.search_directions) < 1:
            # Too ambiguous — signal for clarification
            elapsed = int((time.monotonic() - start) * 1000)
            return ModuleResultEnvelope(
                module_name="NeedProfileBuilder",
                status="degraded",
                warnings=[WarningItem(
                    code="CLARIFY",
                    message="CLARIFY:您能具体描述一下想要什么功能吗？比如「帮我做一个管理家庭菜谱的工具」",
                )],
                data=profile,
                metrics=RunMetrics(
                    wall_time_ms=elapsed, llm_calls=0,
                    prompt_tokens=0, completion_tokens=0,
                    estimated_cost_usd=0.0,
                ),
            )

        elapsed = int((time.monotonic() - start) * 1000)
        return ModuleResultEnvelope(
            module_name="NeedProfileBuilder",
            status="ok",
            data=profile,
            metrics=RunMetrics(
                wall_time_ms=elapsed, llm_calls=0,
                prompt_tokens=0, completion_tokens=0,
                estimated_cost_usd=0.0,
            ),
        )

    def _build_heuristic(self, raw: str) -> NeedProfile:
        """Extract keywords and build NeedProfile without LLM."""
        keywords: list[str] = []
        seen: set[str] = set()

        # Match CN→EN keywords
        for cn, en_list in _CN_TO_EN.items():
            if cn in raw:
                for en in en_list:
                    if en not in seen:
                        keywords.append(en)
                        seen.add(en)

        # Extract English words from input
        en_words = re.findall(r"[a-zA-Z]{3,}", raw)
        for w in en_words:
            wl = w.lower()
            if wl not in seen and wl not in _STOPWORDS:
                keywords.append(wl)
                seen.add(wl)

        # Extract Chinese tokens (2+ chars, not stopwords)
        cn_tokens = re.findall(r"[\u4e00-\u9fff]{2,}", raw)
        for t in cn_tokens:
            if t not in _STOPWORDS and t not in _CN_TO_EN and t not in seen:
                keywords.append(t)
                seen.add(t)

        # Pad if too few
        if len(keywords) < 2:
            for pad in ["open source", "tool"]:
                if pad not in seen:
                    keywords.append(pad)
                    seen.add(pad)

        # Build search directions from first 5 keywords
        directions = []
        for i, kw in enumerate(keywords[:5]):
            directions.append(SearchDirection(
                direction=kw,
                priority="high" if i < 2 else "medium",
            ))

        return NeedProfile(
            raw_input=raw,
            keywords=keywords[:8],
            intent=raw,
            search_directions=directions,
            constraints=["openclaw_compatible"],
            quality_expectations={},
        )

    def _error_result(
        self, code: str, msg: str, start: float
    ) -> ModuleResultEnvelope[NeedProfile]:
        elapsed = int((time.monotonic() - start) * 1000)
        return ModuleResultEnvelope(
            module_name="NeedProfileBuilder",
            status="error",
            error_code=code,
            warnings=[WarningItem(code=code, message=msg)],
            data=None,
            metrics=RunMetrics(
                wall_time_ms=elapsed, llm_calls=0,
                prompt_tokens=0, completion_tokens=0,
                estimated_cost_usd=0.0,
            ),
        )

    def validate_input(self, input: BaseModel) -> list[str]:
        if not hasattr(input, "raw_input") and not isinstance(input, str):
            return ["Input must have raw_input field or be a string"]
        return []

    def can_degrade(self) -> bool:
        return True  # Can degrade to heuristic parsing
