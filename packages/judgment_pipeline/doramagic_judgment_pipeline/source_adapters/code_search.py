"""代码分析适配器 — 从 GitHub 仓库代码中采集知识层和资源层原材料。"""

from __future__ import annotations

import base64
import logging
import time

import httpx

from .base import BaseAdapter, RawExperienceRecord

logger = logging.getLogger(__name__)


# ── 通用搜索模式（所有领域共享） ──
UNIVERSAL_SEARCH_PATTERNS: list[dict] = [
    {
        "query_term": "assert",
        "category": "assertion",
        "target_layer": "knowledge",
        "description": "断言语句——领域不变量的硬编码",
    },
    {
        "query_term": "raise ValueError",
        "category": "validation",
        "target_layer": "knowledge",
        "description": "值校验——领域规则的防御性编码",
    },
    {
        "query_term": "raise TypeError",
        "category": "type_check",
        "target_layer": "knowledge",
        "description": "类型检查——数据类型约束",
    },
    {
        "query_term": "RATE_LIMIT",
        "category": "config_rate",
        "target_layer": "resource",
        "description": "限流配置——API 能力边界",
    },
    {
        "query_term": "TIMEOUT",
        "category": "config_timeout",
        "target_layer": "resource",
        "description": "超时配置——服务可靠性边界",
    },
    {
        "query_term": "MAX_RETRIES",
        "category": "config_retry",
        "target_layer": "resource",
        "description": "重试配置——容错边界",
    },
    {
        "query_term": "deprecated",
        "category": "deprecation",
        "target_layer": "resource",
        "description": "弃用标记——版本迁移约束",
    },
]

# ── 领域专用搜索模式 ──
DOMAIN_SEARCH_PATTERNS: dict[str, list[dict]] = {
    "ai_tooling": [
        {
            "query_term": "max_tokens",
            "category": "output_boundary",
            "target_layer": "resource",
            "description": "LLM 输出 token 上限",
        },
        {
            "query_term": "context_window",
            "category": "context_limit",
            "target_layer": "resource",
            "description": "上下文窗口大小限制",
        },
        {
            "query_term": "MAX_ITERATIONS",
            "category": "iteration_limit",
            "target_layer": "resource",
            "description": "Agent 迭代次数上限",
        },
        {
            "query_term": "tool_choice",
            "category": "tool_constraint",
            "target_layer": "knowledge",
            "description": "工具选择策略约束",
        },
        {
            "query_term": "count_tokens",
            "category": "token_accounting",
            "target_layer": "knowledge",
            "description": "token 计算逻辑——成本和截断的基础",
        },
        {
            "query_term": "retry",
            "category": "retry_strategy",
            "target_layer": "resource",
            "description": "重试策略——API 容错边界",
        },
    ],
    "finance": [
        {
            "query_term": "Decimal",
            "category": "precision",
            "target_layer": "knowledge",
            "description": "Decimal 使用——金融精度约束",
        },
        {
            "query_term": "slippage",
            "category": "trading_cost",
            "target_layer": "knowledge",
            "description": "滑点建模——交易成本约束",
        },
        {
            "query_term": "look_ahead",
            "category": "lookahead_bias",
            "target_layer": "knowledge",
            "description": "前瞻偏差检测——回测有效性",
        },
    ],
}


def get_search_patterns(domain: str | None = None) -> list[dict]:
    """获取搜索模式：通用 + 领域专用。"""
    patterns = list(UNIVERSAL_SEARCH_PATTERNS)
    if domain and domain in DOMAIN_SEARCH_PATTERNS:
        patterns.extend(DOMAIN_SEARCH_PATTERNS[domain])
    return patterns


class CodeSearchAdapter(BaseAdapter):
    """从 GitHub 仓库代码中搜索高价值代码片段。"""

    def __init__(self, token: str):
        self.token = token
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }
        self.base_url = "https://api.github.com"

    async def fetch(self, target: dict) -> list[RawExperienceRecord]:
        """
        target 格式:
        {
            "owner": "freqtrade",
            "repo": "freqtrade",
            "language": "python",
            "domain": "finance",
            "max_results_per_pattern": 10,
            "search_delay": 2.5,
        }
        """
        owner = target["owner"]
        repo = target["repo"]
        language = target.get("language", "python")
        domain = target.get("domain")
        patterns = target.get("patterns", get_search_patterns(domain))
        max_per_pattern = target.get("max_results_per_pattern", 10)
        delay = target.get("search_delay", 2.5)
        records: list[RawExperienceRecord] = []
        seen_files: set[str] = set()

        async with httpx.AsyncClient(headers=self.headers, timeout=30) as client:
            for pattern in patterns:
                query = self._build_query(
                    term=pattern["query_term"],
                    owner=owner,
                    repo=repo,
                    language=language,
                )

                try:
                    search_results = await self._search_code(client, query, max_per_pattern)
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 403:
                        logger.warning("Code Search 限流，等待后重试: %s", pattern["query_term"])
                        time.sleep(delay * 2)
                        try:
                            search_results = await self._search_code(client, query, max_per_pattern)
                        except Exception:
                            logger.warning("Code Search 重试失败，跳过: %s", pattern["query_term"])
                            continue
                    elif e.response.status_code == 422:
                        logger.info("Code Search 不支持此查询，跳过: %s", query)
                        continue
                    else:
                        logger.warning(
                            "Code Search 失败: %s status=%d",
                            pattern["query_term"],
                            e.response.status_code,
                        )
                        continue

                for item in search_results:
                    file_path = item.get("path", "")
                    if file_path in seen_files:
                        continue
                    seen_files.add(file_path)

                    try:
                        content = await self._fetch_file(client, owner, repo, file_path)
                    except Exception as e:
                        logger.warning("拉取文件失败: %s error=%s", file_path, e)
                        continue

                    if not content:
                        continue

                    snippets = self._extract_relevant_snippets(
                        content=content,
                        search_term=pattern["query_term"],
                        context_lines=10,
                    )

                    if not snippets:
                        continue

                    body = f"文件: {file_path}\n搜索模式: {pattern['description']}\n\n"
                    body += "\n\n---\n\n".join(snippets)

                    records.append(
                        RawExperienceRecord(
                            source_type="github_code",
                            source_id=f"code:{file_path}:{pattern['category']}",
                            source_url=f"https://github.com/{owner}/{repo}/blob/main/{file_path}",
                            source_platform="github",
                            project_or_community=f"{owner}/{repo}",
                            title=f"[{pattern['category']}] {file_path}",
                            body=body,
                            replies=[],
                            code_blocks=snippets,
                            signals={
                                "is_documentation": False,
                                "is_code": True,
                                "source_type": "github_code",
                                "body_length": len(body),
                                "code_category": pattern["category"],
                                "target_layer": pattern["target_layer"],
                                "snippet_count": len(snippets),
                                "has_assertions": pattern["category"] == "assertion",
                                "has_validations": pattern["category"]
                                in ("validation", "type_check"),
                                "has_config": pattern["category"].startswith("config_"),
                            },
                            created_at="",
                            resolved_at=None,
                            pre_category=None,
                        )
                    )

                time.sleep(delay)

        logger.info("CodeSearchAdapter 采集完成: %s/%s → %d 条记录", owner, repo, len(records))
        return records

    # ── 内部方法 ──

    def _build_query(self, term: str, owner: str, repo: str, language: str) -> str:
        """构建 Code Search 查询。"""
        q = f"{term} repo:{owner}/{repo}"
        if language:
            q += f" language:{language}"
        return q

    async def _search_code(
        self, client: httpx.AsyncClient, query: str, max_results: int
    ) -> list[dict]:
        """执行代码搜索。"""
        resp = await client.get(
            f"{self.base_url}/search/code",
            params={"q": query, "per_page": min(max_results, 100)},
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("items", [])

    async def _fetch_file(
        self, client: httpx.AsyncClient, owner: str, repo: str, path: str
    ) -> str | None:
        """拉取文件完整内容。"""
        resp = await client.get(f"{self.base_url}/repos/{owner}/{repo}/contents/{path}")
        resp.raise_for_status()
        data = resp.json()
        if data.get("type") != "file":
            return None
        return base64.b64decode(data["content"]).decode("utf-8")

    @staticmethod
    def _extract_relevant_snippets(
        content: str,
        search_term: str,
        context_lines: int = 10,
    ) -> list[str]:
        """从文件内容中提取包含搜索词的代码片段（匹配行 ± context_lines 行）。"""
        lines = content.split("\n")
        match_indices: list[int] = []

        for i, line in enumerate(lines):
            if search_term.lower() in line.lower():
                match_indices.append(i)

        if not match_indices:
            return []

        ranges: list[tuple[int, int]] = []
        for idx in match_indices:
            start = max(0, idx - context_lines)
            end = min(len(lines), idx + context_lines + 1)
            if ranges and start <= ranges[-1][1]:
                ranges[-1] = (ranges[-1][0], max(ranges[-1][1], end))
            else:
                ranges.append((start, end))

        snippets: list[str] = []
        for start, end in ranges:
            actual_end = min(end, start + 30)
            snippet_lines = []
            for i in range(start, actual_end):
                snippet_lines.append(f"L{i + 1}: {lines[i]}")
            snippets.append("\n".join(snippet_lines))

        return snippets[:5]
