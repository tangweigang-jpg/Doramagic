"""Phase A executor: Parse user input into a NeedProfile.

v9.0: LLM-powered keyword generation (primary) + improved heuristic fallback.
Signals CLARIFY when input is too ambiguous to parse.
"""

from __future__ import annotations

import json
import re
import time

from pydantic import BaseModel

from doramagic_contracts.base import NeedProfile, SearchDirection
from doramagic_contracts.envelope import ErrorCodes, ModuleResultEnvelope, RunMetrics, WarningItem
from doramagic_contracts.executor import ExecutorConfig

# LLM system prompt for keyword generation
_NEED_PROFILE_SYSTEM = """You generate GitHub search queries from user requests. The user wants to find open-source projects to learn from.

Output valid JSON only, no other text. Schema:
{
  "domain": "software domain in English (e.g., 'password management', 'fitness tracking')",
  "intent_en": "what the user wants, translated to English (1 sentence)",
  "github_queries": ["query1", "query2", "query3"],
  "relevance_terms": ["term1", "term2", "term3", "term4", "term5"]
}

Rules:
- github_queries: 3 different search strings (2-4 words each) optimized for GitHub search API.
  Think about what developers actually NAME their repos and write in descriptions.
- relevance_terms: 5 English keywords that a RELEVANT repo would mention in its README or description.
- domain: the software domain, NOT a generic label. Be specific.
- intent_en: precise translation of the user's goal."""

# Improved fallback mapping: each CN term → list of compound search terms
_CN_TO_EN: dict[str, list[str]] = {
    "记账": ["expense tracker", "personal finance", "bookkeeping"],
    "菜谱": ["recipe manager", "cookbook app", "meal planner"],
    "日记": ["journal app", "diary", "note taking"],
    "翻译": ["translation tool", "translator", "i18n"],
    "天气": ["weather app", "forecast", "weather API"],
    "健身": ["fitness tracker", "workout app", "exercise"],
    "阅读": ["reading app", "book reader", "ebook"],
    "音乐": ["music player", "audio streaming", "playlist"],
    "照片": ["photo gallery", "image manager", "photo editor"],
    "视频": ["video player", "streaming app", "media player"],
    "购物": ["shopping app", "e-commerce", "price comparison"],
    "社交": ["social network", "chat app", "messaging"],
    "地图": ["map navigation", "location service", "GPS tracker"],
    "日历": ["calendar app", "schedule planner", "task manager"],
    "密码": ["password manager", "credential manager", "security vault"],
    "备份": ["backup tool", "file sync", "cloud storage"],
    "下载": ["download manager", "downloader", "torrent client"],
    "管理": ["management tool", "admin dashboard", "organizer"],
    "监控": ["monitoring tool", "alerting system", "observability"],
    "自动化": ["automation workflow", "task automation", "pipeline"],
    "家居": ["smart home", "home automation", "IoT"],
    "笔记": ["note taking", "knowledge base", "markdown editor"],
    "AI": ["AI tool", "machine learning", "LLM application"],
    "数据": ["data analytics", "data visualization", "dashboard"],
}

_STOPWORDS = {"的", "了", "是", "在", "我", "要", "做", "一个", "帮我", "帮", "app", "skill", "工具", "一下"}


class NeedProfileBuilder:
    """Builds a NeedProfile from raw user input.

    Primary: LLM mode via adapter (generates domain-specific GitHub search keywords).
    Fallback: improved CN→EN keyword extraction (always available).
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

        # Try LLM-powered keyword generation if adapter supports it
        llm_calls = 0
        prompt_tokens = 0
        completion_tokens = 0
        profile = None

        if hasattr(adapter, "call_json") or hasattr(adapter, "call"):
            try:
                profile, llm_calls, prompt_tokens, completion_tokens = await self._build_llm(raw, adapter)
            except Exception:
                pass  # Fall through to heuristic

        if profile is None:
            profile = self._build_heuristic(raw)

        # Check if we have enough signal
        if len(profile.keywords) < 2 and len(profile.search_directions) < 1:
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
                    wall_time_ms=elapsed, llm_calls=llm_calls,
                    prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
                    estimated_cost_usd=0.0,
                ),
            )

        elapsed = int((time.monotonic() - start) * 1000)
        return ModuleResultEnvelope(
            module_name="NeedProfileBuilder",
            status="ok",
            data=profile,
            metrics=RunMetrics(
                wall_time_ms=elapsed, llm_calls=llm_calls,
                prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
                estimated_cost_usd=0.0,
            ),
        )

    async def _build_llm(
        self, raw: str, adapter: object,
    ) -> tuple[NeedProfile, int, int, int]:
        """Use LLM to generate search keywords. Returns (profile, calls, prompt_tok, comp_tok)."""
        if hasattr(adapter, "call_json"):
            result = await adapter.call_json(_NEED_PROFILE_SYSTEM, raw, max_tokens=500)
        else:
            text = await adapter.call(_NEED_PROFILE_SYSTEM, raw, max_tokens=500)
            # Parse JSON from response
            if "```json" in text:
                text = text.split("```json", 1)[1].split("```", 1)[0]
            elif "```" in text:
                text = text.split("```", 1)[1].split("```", 1)[0]
            result = json.loads(text.strip())

        domain = result.get("domain", "general")
        intent_en = result.get("intent_en", raw)
        github_queries = result.get("github_queries", [])
        relevance_terms = result.get("relevance_terms", [])

        # Build keywords from github_queries
        keywords = []
        seen: set[str] = set()
        for q in github_queries:
            for word in q.split():
                wl = word.lower()
                if wl not in seen and len(wl) >= 2:
                    keywords.append(word)
                    seen.add(wl)

        # Build search directions
        directions = []
        for i, q in enumerate(github_queries[:5]):
            directions.append(SearchDirection(
                direction=q,
                priority="high" if i < 2 else "medium",
            ))

        return NeedProfile(
            raw_input=raw,
            keywords=keywords[:8],
            intent=raw,
            intent_en=intent_en,
            domain=domain,
            search_directions=directions,
            constraints=["openclaw_compatible"],
            quality_expectations={},
            github_queries=github_queries[:3],
            relevance_terms=relevance_terms,
        ), 1, 0, 0  # Token counts not available from adapter

    def _build_heuristic(self, raw: str) -> NeedProfile:
        """Improved heuristic: CN→EN compound terms, no garbage padding."""
        keywords: list[str] = []
        seen: set[str] = set()

        # Match CN→EN keywords (now compound terms like "password manager")
        for cn, en_list in _CN_TO_EN.items():
            if cn in raw:
                for en in en_list:
                    if en.lower() not in seen:
                        keywords.append(en)
                        seen.add(en.lower())

        # Extract English words from input (3+ chars)
        en_words = re.findall(r"[a-zA-Z]{3,}", raw)
        for w in en_words:
            wl = w.lower()
            if wl not in seen and wl not in _STOPWORDS:
                keywords.append(wl)
                seen.add(wl)

        # Extract Chinese tokens (2+ chars, not stopwords, not in dict)
        cn_tokens = re.findall(r"[\u4e00-\u9fff]{2,}", raw)
        for t in cn_tokens:
            if t not in _STOPWORDS and t not in _CN_TO_EN and t not in seen:
                keywords.append(t)
                seen.add(t)

        # Only pad if truly empty (no more "open source tool" garbage)
        if not keywords:
            keywords = ["open source tool"]

        # Build search directions from compound keywords
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
