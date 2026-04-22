# Doramagic 判断系统 — Sprint 4 增量开发需求文档 v1.2

> **三层完整采集 + 三段式晶体配方 + AI 工具链支持**
> 本文档是 `implementation-spec-v1.md`（Sprint 1-3）的增量扩展。
> 交给 Claude Code CLI 执行开发。

---

## 前置必读

**开始编码前，先执行以下步骤：**

1. 阅读项目根目录的 `CLAUDE.md`，了解项目级工程规范
2. 阅读 `PRODUCT_CONSTITUTION_v2.md`，理解产品路径：**Doramagic 是知识锻造师，交付物是种子晶体（配方/蓝图），不是 system prompt 注入物。** 晶体消费者是用户的 AI 工具，用户把晶体丢进 AI 对话窗口，AI 按配方现场构建 skill。
3. 阅读 `implementation-spec-v1.md` 全文，理解 Sprint 1-3 的架构和已有代码
4. 确认 Sprint 1-3 已完成：运行 `make check` 通过，且 `knowledge/judgments/domains/` 目录存在
5. 阅读本文档全文后再开始编码

---

## Sprint 4 背景

### 问题

Sprint 1-3 只覆盖了**经验层**（从 GitHub Issue 提取社区踩坑经验）。但 Doramagic 的三层知识架构要求：

| 层 | 定义 | Sprint 1-3 覆盖情况 |
|---|---|---|
| **知识（Knowledge）** | 领域客观规律、因果关系、不变量——"世界如何运转" | ❌ 未覆盖 |
| **资源（Resource）** | 工具/API/数据源的真实能力边界——"手里有什么装备" | ❌ 未覆盖 |
| **经验（Experience）** | 实践验证、失败模式、社区踩坑——"战场上学到的" | ✅ GitHubAdapter |

没有知识层和资源层的判断，编译出的种子晶体只有经验层约束，缺少代码骨架中的断言/验证和资源边界约束。晶体不完整，无法验证三层碰撞的编译效果。

### 解决方案

知识层和资源层的信息藏在两个地方：**仓库文档**和**代码本身**。

- **文档**（README、docs、CHANGELOG）：包含领域规则的自然语言描述、工具能力边界、已知限制
- **代码**（assertions、validators、configs、type definitions）：包含领域规则的硬编码实现——这是比文档更可靠的知识来源，因为代码是被验证过的

Sprint 4 新增两个适配器：
1. **RepoDocAdapter** — 从仓库文档中采集知识层和资源层原材料
2. **CodeSearchAdapter** — 从仓库代码中采集知识层原材料（断言、验证、配置、类型定义）

两个适配器与 Sprint 2 的 Issue 流水线并行运行，实现三层完整采集。

### 架构对照

```
三层知识架构                    采集来源                           Adapter
──────────────────────────────────────────────────────────────────────────
知识（世界如何运转）     ←   README 原理说明、docs/架构文档        RepoDocAdapter  [NEW]
                         ←   代码中的 assert/validation/types      CodeSearchAdapter [NEW]
资源（手里有什么装备）   ←   README Limitations、CHANGELOG         RepoDocAdapter  [NEW]
                         ←   代码中的配置常量(TIMEOUT/RATE_LIMIT)  CodeSearchAdapter [NEW]
经验（战场上学到的）     ←   GitHub Issues                         GitHubAdapter [Sprint 2]
```

**代码→知识的提取逻辑**：
- `assert balance >= 0` → 知识层判断："余额必须为非负数"（不变量）
- `if not isinstance(price, Decimal): raise TypeError` → 知识层判断："金融价格必须用 Decimal"（领域规则）
- `RATE_LIMIT = 100  # requests per minute` → 资源层判断："API 限流 100次/分钟"（工具边界）
- 多个项目都有 `assert not df.isnull().any()` → 跨项目共识（置信度更高）

晶体三段式配方的来源映射（对照 `PRODUCT_CONSTITUTION_v2.md` Section 4.4 和参考实现 `multi-agent-orchestration.seed.md`）：

```
三层知识架构           →    晶体配方段落                    →    编译方式
──────────────────────────────────────────────────────────────────────────
知识层 judgment        →    代码骨架（Section 1）           →    断言/验证/类型定义 植入最小可运行样本
资源层 judgment        →    硬约束表（Section 2）行         →    标注工具能力边界的约束行
经验层 judgment        →    硬约束表（Section 2）行         →    每行：约束 / 原因 / 违反后果
三层交叉碰撞           →    验收标准（Section 3）           →    合格 skill 必须通过的检验项
所有层                 →    context_acquisition 指令块      →    要求宿主 AI 查阅用户历史 + 补充提问
```

**关键理解**：晶体是配方/蓝图，消费者是用户的 AI 工具。用户把晶体丢进 AI 对话窗口，AI 按配方构建个性化 skill。晶体不是被注入 system prompt 的约束文本。

---

## 工作目录与成果位置

### 新建文件的精确位置

```
packages/judgment_pipeline/doramagic_judgment_pipeline/
├── source_adapters/
│   ├── __init__.py              # 已存在，需追加 import
│   ├── base.py                  # 已存在，不修改
│   ├── github.py                # 已存在，不修改
│   ├── repo_doc.py              # 🆕 仓库文档适配器
│   └── code_search.py           # 🆕 代码分析适配器
├── extract/
│   ├── __init__.py              # 已存在，需追加 import
│   ├── filter.py                # 已存在，不修改
│   ├── classifier.py            # 已存在，不修改
│   ├── extractor.py             # 已存在，不修改
│   ├── doc_filter.py            # 🆕 文档过滤器
│   └── doc_extractor.py         # 🆕 知识/资源层提取器
├── pipeline.py                  # 已存在，需扩展
└── ...

scripts/
└── harvest.py                   # 已存在，需扩展

tests/judgment_pipeline/
├── test_repo_doc_adapter.py     # 🆕
├── test_code_search_adapter.py  # 🆕
├── test_doc_filter.py           # 🆕
├── test_doc_extractor.py        # 🆕
└── test_full_pipeline.py        # 🆕
```

### 修改文件清单

| 文件 | 修改内容 |
|---|---|
| `source_adapters/__init__.py` | 追加 `from .repo_doc import RepoDocAdapter` 和 `from .code_search import CodeSearchAdapter` |
| `extract/__init__.py` | 追加 doc_filter、doc_extractor 的导出 |
| `pipeline.py` | 新增 `run_doc_pipeline()` 和 `run_full_pipeline()` |
| `scripts/harvest.py` | 新增 `--mode` 参数支持 `issue`/`doc`/`full` |

**不修改 Sprint 1-3 的任何已有模块的内部逻辑。** 只在 pipeline.py 和 harvest.py 追加新函数/新参数。

---

## 一、source_adapters/repo_doc.py — 仓库文档适配器

### 1.1 职责

从 GitHub 仓库拉取文档文件（README、docs/、CHANGELOG、依赖声明），按 markdown 标题拆分为语义段落，每段转换为一个 `RawExperienceRecord`。

### 1.2 GitHub API 端点

```
GET /repos/{owner}/{repo}/readme                    → README 内容（base64）
GET /repos/{owner}/{repo}/contents/docs              → docs/ 目录列表
GET /repos/{owner}/{repo}/contents/{path}            → 具体文件内容
GET /repos/{owner}/{repo}/contents/CHANGELOG.md      → 变更日志
GET /repos/{owner}/{repo}/contents/pyproject.toml    → 依赖声明（或 setup.py / requirements.txt）
```

所有端点返回的文件内容是 base64 编码，需要 `base64.b64decode(content["content"]).decode("utf-8")` 解码。

### 1.3 精确代码

```python
"""仓库文档适配器 — 从 GitHub 仓库文档中采集知识层和资源层原材料。"""

from __future__ import annotations

import base64
import logging
import re

import httpx

from .base import BaseAdapter, RawExperienceRecord

logger = logging.getLogger(__name__)


# 文档文件的采集优先级（按信息密度排序）
DOC_TARGETS = [
    {"path": "README", "source_type": "github_readme"},
    {"path": "CHANGELOG.md", "source_type": "github_changelog"},
    {"path": "docs/", "source_type": "github_doc"},
    {"path": "pyproject.toml", "source_type": "github_deps"},
    {"path": "setup.py", "source_type": "github_deps"},
    {"path": "requirements.txt", "source_type": "github_deps"},
]


class RepoDocAdapter(BaseAdapter):
    """从 GitHub 仓库文档中采集结构化内容。"""

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
            "doc_paths": ["README", "CHANGELOG.md", "docs/", "pyproject.toml"],  # 可选，默认全部
            "max_doc_files": 20,  # docs/ 目录最多拉取文件数
        }
        """
        owner = target["owner"]
        repo = target["repo"]
        doc_paths = target.get("doc_paths", [d["path"] for d in DOC_TARGETS])
        max_doc_files = target.get("max_doc_files", 20)
        records: list[RawExperienceRecord] = []

        async with httpx.AsyncClient(headers=self.headers, timeout=30) as client:
            for doc_target in DOC_TARGETS:
                if doc_target["path"] not in doc_paths:
                    continue

                path = doc_target["path"]
                source_type = doc_target["source_type"]

                try:
                    if path == "README":
                        content = await self._fetch_readme(client, owner, repo)
                        if content:
                            sections = self._split_markdown(content)
                            for section in sections:
                                records.append(self._make_record(
                                    source_type=source_type,
                                    source_id=f"readme:{section['heading_slug']}",
                                    source_url=f"https://github.com/{owner}/{repo}#readme",
                                    project=f"{owner}/{repo}",
                                    title=section["heading"],
                                    body=section["content"],
                                ))

                    elif path.endswith("/"):
                        # 目录：列出文件并逐个拉取
                        dir_path = path.rstrip("/")
                        files = await self._list_directory(client, owner, repo, dir_path)
                        md_files = [
                            f for f in files
                            if f["name"].endswith(".md") and f["type"] == "file"
                        ][:max_doc_files]

                        for file_info in md_files:
                            content = await self._fetch_file(client, owner, repo, file_info["path"])
                            if content:
                                sections = self._split_markdown(content)
                                for section in sections:
                                    records.append(self._make_record(
                                        source_type=source_type,
                                        source_id=f"doc:{file_info['path']}:{section['heading_slug']}",
                                        source_url=f"https://github.com/{owner}/{repo}/blob/main/{file_info['path']}",
                                        project=f"{owner}/{repo}",
                                        title=f"{file_info['name']} > {section['heading']}",
                                        body=section["content"],
                                    ))

                    elif path in ("pyproject.toml", "setup.py", "requirements.txt"):
                        content = await self._fetch_file(client, owner, repo, path)
                        if content:
                            records.append(self._make_record(
                                source_type=source_type,
                                source_id=f"deps:{path}",
                                source_url=f"https://github.com/{owner}/{repo}/blob/main/{path}",
                                project=f"{owner}/{repo}",
                                title=f"Dependencies: {path}",
                                body=content,
                            ))

                    else:
                        # 具体文件（如 CHANGELOG.md）
                        content = await self._fetch_file(client, owner, repo, path)
                        if content:
                            sections = self._split_markdown(content)
                            for section in sections:
                                records.append(self._make_record(
                                    source_type=source_type,
                                    source_id=f"{path}:{section['heading_slug']}",
                                    source_url=f"https://github.com/{owner}/{repo}/blob/main/{path}",
                                    project=f"{owner}/{repo}",
                                    title=f"{path} > {section['heading']}",
                                    body=section["content"],
                                ))

                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 404:
                        logger.info("文件不存在，跳过: %s/%s/%s", owner, repo, path)
                    else:
                        logger.warning("拉取文件失败: %s/%s/%s status=%d", owner, repo, path, e.response.status_code)
                except httpx.HTTPError as e:
                    logger.warning("网络错误: %s/%s/%s error=%s", owner, repo, path, e)

        logger.info("RepoDocAdapter 采集完成: %s/%s → %d 条记录", owner, repo, len(records))
        return records

    # ── 内部方法 ──

    async def _fetch_readme(self, client: httpx.AsyncClient, owner: str, repo: str) -> str | None:
        """拉取 README（GitHub 自动识别 README.md / README.rst 等）。"""
        resp = await client.get(
            f"{self.base_url}/repos/{owner}/{repo}/readme",
            headers={"Accept": "application/vnd.github.v3+json"},
        )
        resp.raise_for_status()
        data = resp.json()
        return base64.b64decode(data["content"]).decode("utf-8")

    async def _fetch_file(self, client: httpx.AsyncClient, owner: str, repo: str, path: str) -> str | None:
        """拉取单个文件内容。"""
        resp = await client.get(f"{self.base_url}/repos/{owner}/{repo}/contents/{path}")
        resp.raise_for_status()
        data = resp.json()
        if data.get("type") != "file":
            return None
        return base64.b64decode(data["content"]).decode("utf-8")

    async def _list_directory(self, client: httpx.AsyncClient, owner: str, repo: str, path: str) -> list[dict]:
        """列出目录内容。"""
        resp = await client.get(f"{self.base_url}/repos/{owner}/{repo}/contents/{path}")
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list):
            return []
        return data

    def _split_markdown(self, content: str) -> list[dict]:
        """
        按 markdown 标题（## 或 ###）拆分为语义段落。
        每段包含标题及其下方的全部内容，直到下一个同级或更高级标题。
        段落内容少于 50 字符的跳过（标题行、空段等）。
        """
        sections: list[dict] = []
        # 匹配 ## 和 ### 级别标题
        pattern = re.compile(r"^(#{2,3})\s+(.+)$", re.MULTILINE)
        matches = list(pattern.finditer(content))

        if not matches:
            # 没有标题，把整个文档作为一个段落
            stripped = content.strip()
            if len(stripped) >= 50:
                sections.append({
                    "heading": "Overview",
                    "heading_slug": "overview",
                    "content": stripped,
                })
            return sections

        # 如果第一个标题前有内容，加为 overview
        preamble = content[:matches[0].start()].strip()
        if len(preamble) >= 50:
            sections.append({
                "heading": "Overview",
                "heading_slug": "overview",
                "content": preamble,
            })

        for i, match in enumerate(matches):
            heading = match.group(2).strip()
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            body = content[start:end].strip()

            if len(body) < 50:
                continue

            slug = re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-")[:60]
            sections.append({
                "heading": heading,
                "heading_slug": slug or f"section-{i}",
                "content": f"## {heading}\n\n{body}",
            })

        return sections

    def _make_record(
        self,
        source_type: str,
        source_id: str,
        source_url: str,
        project: str,
        title: str,
        body: str,
    ) -> RawExperienceRecord:
        """构建标准记录。文档记录的信号集与 Issue 不同。"""
        return RawExperienceRecord(
            source_type=source_type,
            source_id=source_id,
            source_url=source_url,
            source_platform="github",
            project_or_community=project,
            title=title,
            body=body,
            replies=[],
            code_blocks=self._extract_code_blocks(body),
            signals={
                # 文档专用信号（供 doc_filter 使用）
                "is_documentation": True,
                "source_type": source_type,
                "body_length": len(body),
                "has_code_blocks": bool(self._extract_code_blocks(body)),
                "has_warnings": bool(re.search(r"(?i)(warning|caution|note|important|limitation|caveat|⚠)", body)),
                "has_api_boundaries": bool(re.search(r"(?i)(limit|quota|rate.?limit|deprecat|breaking.?change|not.?support|does.?not)", body)),
                "has_domain_rules": bool(re.search(r"(?i)(must|shall|require|always|never|invariant|constraint|rule)", body)),
            },
            created_at="",
            resolved_at=None,
            pre_category=None,  # 由 doc_filter 决定
        )

    @staticmethod
    def _extract_code_blocks(text: str) -> list[str]:
        """提取 markdown 代码块。"""
        pattern = re.compile(r"```[\w]*\n(.*?)```", re.DOTALL)
        return [m.group(1).strip() for m in pattern.finditer(text)]
```

---

## 一B、source_adapters/code_search.py — 代码分析适配器

### 1B.1 职责

从 GitHub 仓库的代码中定向采集包含领域知识的代码片段。代码中的知识比文档更可靠——断言(assert)是被测试验证过的不变量，验证函数是被生产环境校验过的规则。

### 1B.2 采集策略

**不克隆仓库**。使用 GitHub Code Search API（`GET /search/code`）在仓库内搜索高价值代码模式，然后用 Contents API 拉取文件上下文。

搜索模式按知识类型分组，且**按领域配置化**（通用模式 + 领域专用模式）：

**通用搜索模式**（所有领域共享）：

| 搜索模式 | 知识类型 | 产出层 | 示例 |
|---|---|---|---|
| `assert` | 不变量 | knowledge | `assert balance >= 0` |
| `raise ValueError` / `raise TypeError` | 输入验证规则 | knowledge | `raise ValueError("price must be Decimal")` |
| `TIMEOUT` / `RATE_LIMIT` / `MAX_RETRIES` | 资源配置 | resource | `RATE_LIMIT = 100` |
| `deprecated` / `@deprecated` | 版本边界 | resource | `@deprecated("Use v2 API")` |
| `WARNING` / `CAUTION` (in comments) | 注意事项 | knowledge | `# WARNING: not thread-safe` |

**AI 工具链领域专用模式**（domain = "ai_tooling"）：

| 搜索模式 | 知识类型 | 产出层 | 示例 |
|---|---|---|---|
| `max_tokens` | 输出边界 | resource | `max_tokens=4096` |
| `context_window` / `max_context` | 上下文限制 | resource | `MAX_CONTEXT_LENGTH = 200000` |
| `MAX_ITERATIONS` / `max_steps` | 迭代限制 | resource | `MAX_ITERATIONS = 15` |
| `tool_choice` / `tool_use` | 工具调用约束 | knowledge | `tool_choice="required"` |
| `retry` / `backoff` | 容错边界 | resource | `@retry(max_attempts=3)` |
| `token_count` / `count_tokens` | token 计算 | knowledge | `num_tokens = count_tokens(text)` |

**金融领域专用模式**（domain = "finance"）：

| 搜索模式 | 知识类型 | 产出层 | 示例 |
|---|---|---|---|
| `Decimal` | 精度约束 | knowledge | `Decimal(str(price))` |
| `slippage` | 交易成本 | knowledge | `slippage_model = VolumeSlippage()` |
| `look_ahead` / `lookahead` | 前瞻偏差 | knowledge | `assert no_lookahead(signals)` |

### 1B.3 GitHub Code Search API

```
GET /search/code?q={query}+repo:{owner}/{repo}+language:{language}
```

注意事项：
- Code Search API 有**二级限频**：认证用户 30次/分钟
- 每次搜索最多返回 100 条结果（分页）
- 结果只包含文件路径和匹配片段，完整内容需要用 Contents API 拉取
- 搜索 query 中 `+` 代表 AND，空格也是 AND

### 1B.4 精确代码

```python
"""代码分析适配器 — 从 GitHub 仓库代码中采集知识层和资源层原材料。"""

from __future__ import annotations

import base64
import logging
import re
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
            "language": "python",           # 可选，搜索语言过滤
            "domain": "finance",            # 可选，领域标签（决定使用哪组搜索模式）
            "patterns": [...],              # 可选，自定义搜索模式（覆盖默认）
            "max_results_per_pattern": 10,  # 可选，每个模式最多取几条
            "search_delay": 2.5,            # 可选，搜索间隔秒数（避免限流）
        }
        """
        owner = target["owner"]
        repo = target["repo"]
        language = target.get("language", "python")
        domain = target.get("domain")
        patterns = target.get("patterns", get_search_patterns(domain))
        max_per_pattern = target.get("max_results_per_pattern", 10)
        delay = target.get("search_delay", 2.5)  # Code Search API 限流 30次/分
        records: list[RawExperienceRecord] = []
        seen_files: set[str] = set()  # 避免同一文件被多个模式重复拉取

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
                        logger.warning("Code Search 失败: %s status=%d", pattern["query_term"], e.response.status_code)
                        continue

                for item in search_results:
                    file_path = item.get("path", "")
                    if file_path in seen_files:
                        continue
                    seen_files.add(file_path)

                    # 拉取完整文件内容（Code Search 只返回片段）
                    try:
                        content = await self._fetch_file(client, owner, repo, file_path)
                    except Exception as e:
                        logger.warning("拉取文件失败: %s error=%s", file_path, e)
                        continue

                    if not content:
                        continue

                    # 从文件中提取相关代码上下文（匹配行 ± 周围行）
                    snippets = self._extract_relevant_snippets(
                        content=content,
                        search_term=pattern["query_term"],
                        context_lines=10,
                    )

                    if not snippets:
                        continue

                    body = f"文件: {file_path}\n搜索模式: {pattern['description']}\n\n"
                    body += "\n\n---\n\n".join(snippets)

                    records.append(RawExperienceRecord(
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
                            "has_validations": pattern["category"] in ("validation", "type_check"),
                            "has_config": pattern["category"].startswith("config_"),
                        },
                        created_at="",
                        resolved_at=None,
                        pre_category=None,
                    ))

                # 限流控制
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

    async def _search_code(self, client: httpx.AsyncClient, query: str, max_results: int) -> list[dict]:
        """执行代码搜索。"""
        resp = await client.get(
            f"{self.base_url}/search/code",
            params={"q": query, "per_page": min(max_results, 100)},
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("items", [])

    async def _fetch_file(self, client: httpx.AsyncClient, owner: str, repo: str, path: str) -> str | None:
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
        """
        从文件内容中提取包含搜索词的代码片段（匹配行 ± context_lines 行）。
        合并重叠的片段，每个片段最多 30 行。
        """
        lines = content.split("\n")
        match_indices: list[int] = []

        for i, line in enumerate(lines):
            if search_term.lower() in line.lower():
                match_indices.append(i)

        if not match_indices:
            return []

        # 合并重叠区间
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
            # 限制单个片段最大行数
            actual_end = min(end, start + 30)
            snippet_lines = []
            for i in range(start, actual_end):
                # 添加行号前缀，帮助 LLM 理解代码位置
                snippet_lines.append(f"L{i+1}: {lines[i]}")
            snippets.append("\n".join(snippet_lines))

        return snippets[:5]  # 最多 5 个片段
```

---

## 二、extract/doc_filter.py — 文档过滤器

### 2.1 职责

过滤文档段落，只保留包含领域规则（知识层）或工具边界（资源层）信息的段落。与 Issue 的三轨过滤器不同，文档过滤器是**规则匹配 + 信号打分**，不依赖 LLM。

### 2.2 过滤策略

文档与 Issue 的本质区别：Issue 是用户生成的噪声内容（需要三轨重过滤），文档是项目维护者的策划内容（信噪比高，轻过滤即可）。

```
文档过滤流程：
1. 硬排除：标题匹配黑名单 → 直接丢弃
2. 快速通过：标题匹配白名单 → 直接通过
3. 信号打分：综合信号判断 → 超阈值通过
```

### 2.3 精确代码

```python
"""文档过滤器 — 为仓库文档内容做相关性过滤。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from ..source_adapters.base import RawExperienceRecord


class DocFilterTrack(str, Enum):
    BLACKLIST_EXCLUDED = "blacklist_excluded"
    WHITELIST_PASSED = "whitelist_passed"
    SIGNAL_PASSED = "signal_passed"
    SIGNAL_REJECTED = "signal_rejected"


@dataclass
class DocFilterResult:
    record: RawExperienceRecord
    track: DocFilterTrack
    score: float
    reason: str

    @property
    def passed(self) -> bool:
        return self.track in (DocFilterTrack.WHITELIST_PASSED, DocFilterTrack.SIGNAL_PASSED)


# 黑名单：这些段落标题几乎不含领域知识或资源边界信息
HEADING_BLACKLIST = re.compile(
    r"(?i)^(contribut|license|changelog|release\s+note|acknowledgment|sponsor|"
    r"code\s+of\s+conduct|citation|badge|build\s+status|ci[/ ]cd|"
    r"table\s+of\s+contents|development\s+setup|how\s+to\s+contribute|"
    r"pull\s+request|commit\s+convention|git\s+workflow)"
)

# 白名单：这些段落标题高概率含有知识层或资源层信息
HEADING_WHITELIST = re.compile(
    r"(?i)(limitation|caveat|known\s+issue|breaking\s+change|deprecat|"
    r"constraint|warning|important|requirement|architecture|design|"
    r"how\s+it\s+works|concept|overview|api\s+reference|usage|"
    r"configuration|faq|troubleshoot|migration|upgrade|"
    r"performance|benchmark|comparison|vs\s+|alternative)"
)


def filter_doc_records(records: list[RawExperienceRecord]) -> list[DocFilterResult]:
    """
    过滤文档记录。返回每条记录的过滤结果。
    """
    results: list[DocFilterResult] = []

    for record in records:
        title_lower = record.title.lower()
        signals = record.signals

        # Step 1: 黑名单硬排除
        if HEADING_BLACKLIST.search(title_lower):
            results.append(DocFilterResult(
                record=record,
                track=DocFilterTrack.BLACKLIST_EXCLUDED,
                score=0,
                reason=f"标题命中黑名单: {record.title}",
            ))
            continue

        # Step 2: 白名单快速通过
        if HEADING_WHITELIST.search(title_lower):
            results.append(DocFilterResult(
                record=record,
                track=DocFilterTrack.WHITELIST_PASSED,
                score=10.0,
                reason=f"标题命中白名单: {record.title}",
            ))
            continue

        # Step 3: 信号打分
        score = _compute_doc_score(signals)
        threshold = _get_doc_threshold(record)

        if score >= threshold:
            results.append(DocFilterResult(
                record=record,
                track=DocFilterTrack.SIGNAL_PASSED,
                score=score,
                reason=f"文档信号得分 {score:.1f} >= 阈值 {threshold}",
            ))
        else:
            results.append(DocFilterResult(
                record=record,
                track=DocFilterTrack.SIGNAL_REJECTED,
                score=score,
                reason=f"文档信号得分 {score:.1f} < 阈值 {threshold}",
            ))

    return results


def _compute_doc_score(signals: dict) -> float:
    """文档信号打分。"""
    score = 0.0

    # 内容有实质性长度
    body_length = signals.get("body_length", 0)
    if body_length >= 200:
        score += 1.0
    if body_length >= 500:
        score += 0.5

    # 包含代码示例（说明有实操信息）
    if signals.get("has_code_blocks"):
        score += 1.5

    # 包含警告/注意事项（高价值边界信息）
    if signals.get("has_warnings"):
        score += 2.5

    # 包含 API 边界信息
    if signals.get("has_api_boundaries"):
        score += 2.5

    # 包含领域规则语言
    if signals.get("has_domain_rules"):
        score += 2.0

    return score


def _get_doc_threshold(record: RawExperienceRecord) -> float:
    """根据文档类型调整阈值。"""
    source_type = record.signals.get("source_type", "")

    if source_type == "github_readme":
        return 2.0   # README 信噪比高，低阈值
    if source_type == "github_changelog":
        return 3.0   # CHANGELOG 多为版本列表，稍高
    if source_type == "github_deps":
        return 0.0   # 依赖声明直接通过（由 doc_extractor 判断价值）
    if source_type == "github_doc":
        return 2.5   # docs/ 下的文档，中等阈值
    if source_type == "github_code":
        return 0.0   # 代码记录已由 CodeSearchAdapter 预筛选，直接通过

    return 3.0  # 默认
```

---

## 三、extract/doc_extractor.py — 知识/资源层提取器

### 3.1 职责

从文档内容中提取知识层（领域规则、不变量）和资源层（工具边界、API 限制）的判断。与 Sprint 2 的 `extractor.py` 平行，但 prompt 完全不同——面向文档而非 Issue 讨论。

### 3.2 关键区别

| 维度 | Issue 提取器 (extractor.py) | 文档提取器 (doc_extractor.py) |
|---|---|---|
| 输入类型 | Issue 标题 + 正文 + 评论 | 文档段落（markdown） |
| 主要产出层 | experience | knowledge + resource |
| evidence_ref.type | ISSUE | DOC |
| source_level | S3_COMMUNITY | S1_SINGLE_PROJECT |
| 提取重点 | 失败模式、踩坑经验 | 领域规则、工具边界 |
| crystal_section 偏好 | constraints, protocols | code_skeleton, hard_constraints |

### 3.3 精确代码

```python
"""文档知识/资源层提取器 — 从仓库文档中提取知识层和资源层判断。"""

from __future__ import annotations

import logging

from doramagic_shared_utils.llm_adapter import LLMAdapter, LLMMessage
from doramagic_judgment_schema.types import (
    Judgment, JudgmentCore, JudgmentScope, JudgmentConfidence,
    JudgmentCompilation, JudgmentVersion, Consequence, EvidenceRef,
    Layer, Modality, Severity, ScopeLevel, Freshness, SourceLevel,
    ConsensusLevel, CrystalSection, ConsequenceKind, EvidenceRefType,
    LifecycleStatus,
)
from doramagic_judgment_schema.validators import validate_judgment
from doramagic_judgment_schema.utils import parse_llm_json

from ..source_adapters.base import RawExperienceRecord

logger = logging.getLogger(__name__)


DOC_EXTRACTION_SYSTEM_PROMPT = """你是 Doramagic 的知识提取专家。你的任务是从项目文档中提取两类判断：

**知识层判断**（世界如何运转）：
- 领域的客观规律和因果关系
- 不变量（无论用什么工具、什么场景，这条规则都成立）
- 系统/领域的物理约束
- 例：当处理金融数据时，必须使用 Decimal 而非 float 进行金额计算，否则累计误差会在三天内达到 0.8%

**资源层判断**（手里有什么装备）：
- 工具/API/库的真实能力边界
- 资源的限制条件（免费 vs 付费、速率限制、数据范围）
- 选择某个资源就必须接受的约束
- 例：当使用 yfinance 获取行情数据时，禁止将其用于实时交易决策，否则因数据延迟 15-20 分钟导致交易信号失效

每颗判断必须严格遵循三元组格式：
  当 [具体条件] 时，必须/禁止 [具体行为]，否则 [可量化后果]。

约束（违反任何一条你的输出将被代码级拒绝）：
1. [条件] 必须具体到一个工作场景，不能是"使用时"这种泛泛之词
2. [行为] 必须是一个可执行指令，不能是"注意安全"这种建议
3. [后果] 必须包含可量化的影响或具体的失败表现
4. 如果无法量化后果，写明"后果程度未知，需实验验证"并建议 confidence_score < 0.6
5. 一颗判断只说一件事。如果你发现两件事，拆成两颗
6. action 中不允许出现：注意、考虑、适当、合理、尽量、可能需要
7. **layer 必须是 "knowledge" 或 "resource"**，不要写 "experience"（经验层由 Issue 提取器负责）

输出格式：只输出一个 JSON 数组，不要添加任何解释文字。每个元素：
{
  "when": "触发条件",
  "modality": "must" | "must_not" | "should" | "should_not",
  "action": "具体行为",
  "consequence_kind": "bug" | "performance" | "data_corruption" | "service_disruption" | "financial_loss" | "operational_failure" | "compliance" | "safety" | "false_claim",
  "consequence_description": "后果描述",
  "layer": "knowledge" | "resource",
  "severity": "fatal" | "high" | "medium" | "low",
  "confidence_score": 0.0-1.0,
  "crystal_section": "code_skeleton" | "hard_constraints" | "acceptance_criteria",
  "evidence_summary": "引用文档中的具体内容作为证据"
}

crystal_section 选择指南（文档提取专用）：
- "code_skeleton"：领域客观规律、不变量、因果关系 → 将植入代码骨架的 assert/validation
- "hard_constraints"：实践约束、工具边界、迁移规则 → 将成为硬约束表中的行
- "acceptance_criteria"：跨层验证条件 → 将成为验收标准中的条目

如果文档段落没有可提取的判断（纯安装步骤、纯 API 列表等），返回空数组 []。
不要编造文档中没有提到的信息。
最多提取 5 颗判断，优先提取 severity 最高的。"""


DOC_EXTRACTION_FEW_SHOT = """
示例 — 知识层提取（从 README "How it works" 段落）：
{"when": "使用时间序列数据进行量化回测时", "modality": "must", "action": "基于交易日序列计算技术指标，禁止对非交易日插值填充", "consequence_kind": "data_corruption", "consequence_description": "插值会引入虚假数据点，导致均线等指标计算结果偏离真实市场状态，回测收益率虚高 5-15%", "layer": "knowledge", "severity": "high", "confidence_score": 0.9, "crystal_section": "world_model", "evidence_summary": "README Architecture 章节说明：交易日历是非连续的，所有计算必须基于交易日序列"}

示例 — 资源层提取（从 README "Limitations" 段落）：
{"when": "使用 yfinance 获取股票历史数据进行策略研究时", "modality": "must", "action": "在本地建立数据缓存层，避免每次运行都从 API 拉取", "consequence_kind": "service_disruption", "consequence_description": "yfinance 无官方 API key，高频请求会触发 IP 限流，导致数据拉取中断", "layer": "resource", "severity": "medium", "confidence_score": 0.85, "crystal_section": "resource_profile", "evidence_summary": "README Limitations 章节：yfinance is unofficial, rate limits may apply"}

示例 — 会被拒绝的提取：
{"when": "开发时", "modality": "should", "action": "考虑性能", ...}
↑ 被拒绝原因：when 太笼统、action 包含"考虑"
"""


DOC_EXTRACTION_USER_TEMPLATE = """项目: {project}
文档来源: {source_type}
段落标题: {title}
URL: {url}

文档内容:
{body}

请从以上文档内容中提取知识层和资源层的判断。"""


# 代码专用提取 prompt（断言/验证代码 → 知识层判断）
CODE_EXTRACTION_SYSTEM_PROMPT = """你是 Doramagic 的代码知识提取专家。你的任务是从代码片段中提取隐含的领域知识。

代码中的知识比文档更可靠——断言是被测试验证过的不变量，验证函数是被生产环境校验过的规则。

你需要提取的知识类型：
1. **断言 (assert)** → 不变量："当[条件]时，[某个属性]必须始终成立"
2. **验证 (raise ValueError/TypeError)** → 输入规则："当[操作]时，[输入]必须满足[条件]"
3. **配置常量 (TIMEOUT/RATE_LIMIT)** → 资源边界："当使用[资源]时，[参数]的真实边界是[值]"
4. **类型选择 (Decimal vs float)** → 领域决策："当[场景]时，必须使用[类型A]而非[类型B]"

约束：
1. 只提取代码中**明确表达**的知识，不要推测或编造
2. 三元组格式：当 [具体条件] 时，必须/禁止 [具体行为]，否则 [可量化后果]
3. action 中不允许出现：注意、考虑、适当、合理、尽量、可能需要
4. 如果代码片段只是普通业务逻辑（没有断言、验证或配置），返回空数组 []
5. **layer 必须是 "knowledge" 或 "resource"**

输出格式：只输出一个 JSON 数组。每个元素同文档提取器格式。
最多提取 3 颗判断（代码片段通常信息密度低于文档）。"""


CODE_EXTRACTION_USER_TEMPLATE = """项目: {project}
文件: {title}
代码类别: {code_category}
URL: {url}

代码片段:
{body}

请从以上代码中提取知识层和资源层的判断。如果代码只是普通业务逻辑，返回 []。"""


# source_type 到默认 crystal_section 的映射
# 注意：这些映射只是默认值，LLM 提取结果可以覆盖
SOURCE_TYPE_TO_SECTION: dict[str, CrystalSection] = {
    "github_readme": CrystalSection.CODE_SKELETON,      # README 中的原理/规则 → 代码骨架中的 assert
    "github_doc": CrystalSection.CODE_SKELETON,         # 架构文档 → 代码骨架中的类型约束
    "github_changelog": CrystalSection.HARD_CONSTRAINTS, # CHANGELOG 变更 → 硬约束表（版本迁移约束）
    "github_deps": CrystalSection.HARD_CONSTRAINTS,      # 依赖声明 → 硬约束表（版本边界）
    "github_code": CrystalSection.CODE_SKELETON,         # 代码中的 assert/validation → 代码骨架
}

# source_type 到默认 layer 的映射
SOURCE_TYPE_TO_LAYER: dict[str, Layer] = {
    "github_readme": Layer.KNOWLEDGE,
    "github_doc": Layer.KNOWLEDGE,
    "github_changelog": Layer.RESOURCE,
    "github_deps": Layer.RESOURCE,
    "github_code": Layer.KNOWLEDGE,
}


async def extract_doc_judgments(
    record: RawExperienceRecord,
    adapter: LLMAdapter,
    domain: str,
    model: str = "sonnet",
    id_counter: int = 1,
) -> list[Judgment]:
    """
    从一条文档记录中提取判断。
    返回通过校验的 Judgment 列表。
    """
    source_type = record.signals.get("source_type", "github_doc")
    is_code = source_type == "github_code"

    if is_code:
        # 代码记录使用专用 prompt
        user_content = CODE_EXTRACTION_USER_TEMPLATE.format(
            project=record.project_or_community,
            title=record.title,
            code_category=record.signals.get("code_category", "unknown"),
            url=record.source_url,
            body=record.body[:4000],
        )
        system_prompt = CODE_EXTRACTION_SYSTEM_PROMPT
        few_shot = ""  # 代码提取不需要 few-shot（system prompt 已含示例）
    else:
        # 文档记录使用文档 prompt
        user_content = DOC_EXTRACTION_USER_TEMPLATE.format(
            project=record.project_or_community,
            source_type=source_type,
            title=record.title,
            url=record.source_url,
            body=record.body[:4000],
        )
        system_prompt = DOC_EXTRACTION_SYSTEM_PROMPT
        few_shot = DOC_EXTRACTION_FEW_SHOT

    messages_content = f"{few_shot}\n\n{user_content}" if few_shot else user_content
    response = adapter.chat(
        messages=[LLMMessage(role="user", content=messages_content)],
        system=system_prompt,
        temperature=0.0,
        max_tokens=3000,
    )

    try:
        raw_judgments = parse_llm_json(response.text)
    except ValueError as e:
        logger.warning("文档提取 LLM 输出无法解析: %s (record=%s)", e, record.source_id)
        return []

    if not isinstance(raw_judgments, list):
        logger.warning("文档提取 LLM 输出不是数组: type=%s (record=%s)", type(raw_judgments), record.source_id)
        return []

    results: list[Judgment] = []
    rejected: list[dict] = []

    default_layer = SOURCE_TYPE_TO_LAYER.get(source_type, Layer.KNOWLEDGE)
    default_section = SOURCE_TYPE_TO_SECTION.get(source_type, CrystalSection.WORLD_MODEL)

    for i, raw_item in enumerate(raw_judgments):
        try:
            # layer: LLM 输出优先，限定为 knowledge 或 resource
            layer_str = raw_item.get("layer", default_layer.value)
            if layer_str == "experience":
                layer_str = default_layer.value  # 文档提取不产出 experience 层
            layer_initial = layer_str[0].upper() if layer_str else "K"

            # crystal_section: LLM 输出优先
            section_str = raw_item.get("crystal_section", "")
            try:
                crystal_section = CrystalSection(section_str)
            except ValueError:
                crystal_section = default_section

            judgment = Judgment(
                id=f"{domain}-{layer_initial}-{id_counter + i:03d}",
                core=JudgmentCore(
                    when=raw_item.get("when", ""),
                    modality=Modality(raw_item.get("modality", "should")),
                    action=raw_item.get("action", ""),
                    consequence=Consequence(
                        kind=ConsequenceKind(raw_item.get("consequence_kind", "bug")),
                        description=raw_item.get("consequence_description", "后果未明确"),
                    ),
                ),
                layer=Layer(layer_str),
                scope=JudgmentScope(
                    level=ScopeLevel.DOMAIN,  # 文档提取的判断通常是领域级
                    domains=[domain],
                ),
                confidence=JudgmentConfidence(
                    source=SourceLevel.S1_SINGLE_PROJECT,  # 文档 = 单项目来源
                    score=raw_item.get("confidence_score", 0.7),
                    consensus=ConsensusLevel.MIXED,
                    evidence_refs=[
                        EvidenceRef(
                            type=EvidenceRefType.DOC,
                            source=record.project_or_community,
                            locator=record.source_url,
                            summary=raw_item.get("evidence_summary", record.title),
                        ),
                    ],
                ),
                compilation=JudgmentCompilation(
                    severity=Severity(raw_item.get("severity", "medium")),
                    crystal_section=crystal_section,
                    freshness=Freshness.SEMI_STABLE,
                    query_tags=[domain],
                ),
                version=JudgmentVersion(status=LifecycleStatus.DRAFT),
            )

            validation = validate_judgment(judgment)
            if validation.valid:
                results.append(judgment)
            else:
                logger.info("文档判断校验失败: id=%s errors=%s", judgment.id, validation.errors)
                rejected.append({
                    "stage": "validate",
                    "judgment_id": judgment.id,
                    "errors": validation.errors,
                    "raw": raw_item,
                })

        except (KeyError, ValueError, TypeError) as e:
            logger.warning("构造文档 Judgment 失败: %s (record=%s, item=%d)", e, record.source_id, i)
            rejected.append({
                "stage": "construct",
                "error": str(e),
                "raw": raw_item,
            })
            continue

    if rejected:
        logger.info("文档提取 rejected %d 条 (record=%s)", len(rejected), record.source_id)

    return results
```

---

## 四、pipeline.py 扩展 — 多来源编排

### 4.1 新增函数

在现有 `pipeline.py` 中追加以下函数（**不修改** `run_pipeline()` 原有逻辑）：

```python
# ── 追加在 pipeline.py 末尾 ──

from .source_adapters.repo_doc import RepoDocAdapter
from .source_adapters.code_search import CodeSearchAdapter
from .extract.doc_filter import filter_doc_records
from .extract.doc_extractor import extract_doc_judgments


@dataclass
class DocPipelineResult:
    """文档采集流水线结果统计。"""
    fetched: int = 0
    filtered_in: int = 0
    filtered_out: int = 0
    extracted: int = 0
    after_dedup: int = 0
    stored: int = 0
    errors: list[str] = field(default_factory=list)


async def run_doc_pipeline(
    github_token: str,
    target: dict,
    domain: str,
    judgments_path: str,
    adapter: LLMAdapter,
    model: str = "sonnet",
) -> DocPipelineResult:
    """
    文档采集流水线：RepoDocAdapter → DocFilter → DocExtractor → Dedup → Store
    """
    result = DocPipelineResult()

    # 1. Fetch（文档 + 代码两个来源）
    records: list[RawExperienceRecord] = []

    # 1a. 文档采集
    doc_adapter = RepoDocAdapter(token=github_token)
    try:
        doc_records = await doc_adapter.fetch(target)
        records.extend(doc_records)
        logger.info("[Doc] 文档采集: %d 条", len(doc_records))
    except Exception as e:
        result.errors.append(f"文档拉取失败: {e}")

    # 1b. 代码采集
    code_target = {
        "owner": target["owner"],
        "repo": target["repo"],
        "language": target.get("language", "python"),
        "max_results_per_pattern": target.get("max_code_results", 10),
    }
    code_adapter = CodeSearchAdapter(token=github_token)
    try:
        code_records = await code_adapter.fetch(code_target)
        records.extend(code_records)
        logger.info("[Doc] 代码采集: %d 条", len(code_records))
    except Exception as e:
        result.errors.append(f"代码采集失败: {e}")

    result.fetched = len(records)
    logger.info("[Doc] 总采集: %d 条记录", result.fetched)

    if not records:
        return result

    # 2. Filter
    filter_results = filter_doc_records(records)
    passed = [fr.record for fr in filter_results if fr.passed]
    result.filtered_in = len(passed)
    result.filtered_out = result.fetched - result.filtered_in
    logger.info("[Doc] Filter: %d 通过 / %d 丢弃", result.filtered_in, result.filtered_out)

    if not passed:
        return result

    # 3. Extract（文档不需要 classifier，直接提取）
    all_judgments: list[Judgment] = []
    id_counter = _get_next_id_counter(judgments_path, domain)

    for record in passed:
        try:
            judgments = await extract_doc_judgments(
                record=record,
                adapter=adapter,
                domain=domain,
                model=model,
                id_counter=id_counter,
            )
            all_judgments.extend(judgments)
            id_counter += len(judgments)
        except Exception as e:
            logger.warning("[Doc] 提取失败: %s (record=%s)", e, record.source_id)
            result.errors.append(f"提取失败 {record.source_id}: {e}")

    result.extracted = len(all_judgments)
    logger.info("[Doc] Extracted %d 颗判断", result.extracted)

    if not all_judgments:
        return result

    # 4. Dedup
    from .refine.dedup import dedup_judgments
    dedup_result = dedup_judgments(all_judgments)
    result.after_dedup = len(dedup_result.unique)
    logger.info("[Doc] Dedup: %d → %d", result.extracted, result.after_dedup)

    # 5. Store
    from doramagic_judgment_schema.serializer import JudgmentStore
    store = JudgmentStore(base_path=judgments_path)
    stored_count = 0
    for j in dedup_result.unique:
        try:
            store.store(j)
            stored_count += 1
        except Exception as e:
            logger.warning("[Doc] 入库失败: %s (id=%s)", e, j.id)
            result.errors.append(f"入库失败 {j.id}: {e}")

    result.stored = stored_count
    logger.info("[Doc] Stored %d 颗判断", result.stored)

    return result


@dataclass
class FullPipelineResult:
    """三层完整采集结果。"""
    issue_result: PipelineResult | None = None
    doc_result: DocPipelineResult | None = None
    total_stored: int = 0
    layer_coverage: dict[str, int] = field(default_factory=dict)
    crystal_text: str = ""


async def run_full_pipeline(
    github_token: str,
    issue_target: dict,
    doc_target: dict,
    domain: str,
    task_description: str,
    judgments_path: str,
    adapter: LLMAdapter,
    model: str = "sonnet",
    compile_crystal: bool = True,
) -> FullPipelineResult:
    """
    三层完整采集流水线：
    1. 并行运行 Issue 流水线（经验层）和文档流水线（知识+资源层）
    2. 统计三层覆盖度
    3. 可选：编译种子晶体
    """
    import asyncio

    result = FullPipelineResult()

    # 并行运行两条流水线
    issue_task = asyncio.create_task(
        run_pipeline(
            github_token=github_token,
            target=issue_target,
            domain=domain,
            judgments_path=judgments_path,
            adapter=adapter,
            model=model,
        )
    )
    doc_task = asyncio.create_task(
        run_doc_pipeline(
            github_token=github_token,
            target=doc_target,
            domain=domain,
            judgments_path=judgments_path,
            adapter=adapter,
            model=model,
        )
    )

    result.issue_result, result.doc_result = await asyncio.gather(issue_task, doc_task)
    result.total_stored = (
        (result.issue_result.stored if result.issue_result else 0)
        + (result.doc_result.stored if result.doc_result else 0)
    )

    # 统计三层覆盖度
    from doramagic_judgment_schema.serializer import JudgmentStore
    store = JudgmentStore(base_path=judgments_path)
    all_domain = store.list_by_domain(domain)
    for j in all_domain:
        layer_name = j.layer.value if hasattr(j.layer, "value") else str(j.layer)
        result.layer_coverage[layer_name] = result.layer_coverage.get(layer_name, 0) + 1

    logger.info("[Full] 三层覆盖: %s", result.layer_coverage)

    # 编译晶体
    if compile_crystal:
        from doramagic_crystal_compiler.retrieve import retrieve
        from doramagic_crystal_compiler.compiler import compile_crystal as do_compile

        retrieval = retrieve(store=store, domain=domain)
        result.crystal_text = do_compile(
            retrieval=retrieval,
            domain=domain,
            task_description=task_description,
        )
        logger.info("[Full] 晶体编译完成，长度=%d 字符", len(result.crystal_text))

    return result


def _get_next_id_counter(judgments_path: str, domain: str) -> int:
    """获取下一个可用的 ID 计数器（避免与已有判断 ID 冲突）。"""
    from doramagic_judgment_schema.serializer import JudgmentStore
    try:
        store = JudgmentStore(base_path=judgments_path)
        existing = store.list_by_domain(domain)
        if not existing:
            return 1
        # 从已有 ID 中提取最大数字后缀
        max_num = 0
        for j in existing:
            parts = j.id.rsplit("-", 1)
            if len(parts) == 2 and parts[1].isdigit():
                max_num = max(max_num, int(parts[1]))
        return max_num + 1
    except Exception:
        return 1
```

### 4.2 import 补充

在 `pipeline.py` 文件顶部的 import 区域，确保已有以下导入（大部分已存在，只需确认 `Judgment` 被导入）：

```python
from doramagic_judgment_schema.types import Judgment
```

---

## 五、scripts/harvest.py 扩展

### 5.1 修改后的完整代码

```python
# scripts/harvest.py
"""判断采集 CLI 入口 — 支持三层完整采集。"""

import argparse
import asyncio
import os
import sys


async def main():
    parser = argparse.ArgumentParser(description="Doramagic 判断采集器")
    parser.add_argument(
        "--mode",
        choices=["issue", "doc", "full"],
        default="full",
        help="采集模式: issue=仅 Issue 经验层, doc=仅文档知识/资源层, full=三层完整采集（默认）",
    )
    parser.add_argument(
        "--domain",
        default="finance",
        help="领域标签（默认: finance）",
    )
    parser.add_argument(
        "--owner",
        default="freqtrade",
        help="GitHub 仓库 owner（默认: freqtrade）",
    )
    parser.add_argument(
        "--repo",
        default="freqtrade",
        help="GitHub 仓库名（默认: freqtrade）",
    )
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("ERROR: GITHUB_TOKEN 环境变量未设置")
        sys.exit(1)

    # 预检
    from doramagic_judgment_pipeline.pipeline import preflight_check
    preflight_check()

    from doramagic_shared_utils.llm_adapter import LLMAdapter
    adapter = LLMAdapter()

    issue_target = {
        "owner": args.owner,
        "repo": args.repo,
        "state": "closed",
        "labels": "bug",
        "min_comments": 3,
        "since": "2024-01-01",
        "max_pages": 5,
    }

    doc_target = {
        "owner": args.owner,
        "repo": args.repo,
        "doc_paths": ["README", "CHANGELOG.md", "docs/", "pyproject.toml"],
        "max_doc_files": 20,
        "language": "python",        # 代码搜索语言过滤
        "max_code_results": 10,      # 每个搜索模式最多取几条代码结果
    }

    judgments_path = "knowledge/judgments"

    if args.mode == "issue":
        from doramagic_judgment_pipeline.pipeline import run_pipeline
        result = await run_pipeline(
            github_token=token,
            target=issue_target,
            domain=args.domain,
            judgments_path=judgments_path,
            adapter=adapter,
        )
        _print_issue_result(result)

    elif args.mode == "doc":
        from doramagic_judgment_pipeline.pipeline import run_doc_pipeline
        result = await run_doc_pipeline(
            github_token=token,
            target=doc_target,
            domain=args.domain,
            judgments_path=judgments_path,
            adapter=adapter,
        )
        _print_doc_result(result)

    elif args.mode == "full":
        from doramagic_judgment_pipeline.pipeline import run_full_pipeline
        result = await run_full_pipeline(
            github_token=token,
            issue_target=issue_target,
            doc_target=doc_target,
            domain=args.domain,
            task_description="量化投资分析工具",
            judgments_path=judgments_path,
            adapter=adapter,
        )
        _print_full_result(result)


def _print_issue_result(result):
    print(f"\n=== Issue 采集完成 ===")
    print(f"拉取: {result.fetched}")
    print(f"过滤通过: {result.filtered_in} / 过滤丢弃: {result.filtered_out}")
    print(f"分类有效: {result.classified}")
    print(f"提取判断: {result.extracted}")
    print(f"去重后: {result.after_dedup}")
    print(f"入库: {result.stored}")
    if result.errors:
        print(f"错误: {result.errors}")


def _print_doc_result(result):
    print(f"\n=== 文档采集完成 ===")
    print(f"拉取: {result.fetched}")
    print(f"过滤通过: {result.filtered_in} / 过滤丢弃: {result.filtered_out}")
    print(f"提取判断: {result.extracted}")
    print(f"去重后: {result.after_dedup}")
    print(f"入库: {result.stored}")
    if result.errors:
        print(f"错误: {result.errors}")


def _print_full_result(result):
    print(f"\n{'='*60}")
    print(f"  三层完整采集结果")
    print(f"{'='*60}")

    if result.issue_result:
        print(f"\n[经验层 — Issue]")
        print(f"  拉取: {result.issue_result.fetched}")
        print(f"  入库: {result.issue_result.stored}")

    if result.doc_result:
        print(f"\n[知识+资源层 — 文档]")
        print(f"  拉取: {result.doc_result.fetched}")
        print(f"  入库: {result.doc_result.stored}")

    print(f"\n[汇总]")
    print(f"  总入库: {result.total_stored}")
    print(f"  三层覆盖: {result.layer_coverage}")

    if result.crystal_text:
        print(f"\n[晶体预览（前 500 字符）]")
        print(result.crystal_text[:500])
        print("...")

        # 保存晶体到文件
        crystal_path = f"knowledge/judgments/crystals/{result.issue_result and 'finance' or 'unknown'}_crystal.md"
        import os
        os.makedirs(os.path.dirname(crystal_path), exist_ok=True)
        with open(crystal_path, "w") as f:
            f.write(result.crystal_text)
        print(f"\n晶体已保存: {crystal_path}")


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 六、测试

### 6.1 test_repo_doc_adapter.py

```python
"""RepoDocAdapter 单元测试。"""

import pytest

from doramagic_judgment_pipeline.source_adapters.repo_doc import RepoDocAdapter


class TestMarkdownSplitting:
    """测试 markdown 拆分逻辑（纯本地，不依赖 GitHub API）。"""

    def setup_method(self):
        self.adapter = RepoDocAdapter.__new__(RepoDocAdapter)

    def test_split_with_headers(self):
        content = """# Title

Some preamble text that is long enough to be kept as a section for the overview.

## Installation

Run pip install to set up the project. This section has enough content to pass the threshold.

## Architecture

The system uses event-driven design. Data flows through ingestion, normalization, and computation layers.

### Known Limitations

Rate limiting applies after 100 requests per minute. The API does not support real-time streaming.
"""
        sections = self.adapter._split_markdown(content)
        assert len(sections) >= 3
        assert sections[0]["heading"] == "Overview"
        headings = [s["heading"] for s in sections]
        assert "Installation" in headings or "Architecture" in headings

    def test_split_no_headers(self):
        content = "A" * 100  # 没有标题，足够长
        sections = self.adapter._split_markdown(content)
        assert len(sections) == 1
        assert sections[0]["heading"] == "Overview"

    def test_skip_short_sections(self):
        content = """## Short

Hi.

## Long Enough Section

This section has plenty of content to make it past the minimum threshold of fifty characters.
"""
        sections = self.adapter._split_markdown(content)
        # "Short" 段落只有 "Hi." → 少于 50 字符 → 被跳过
        headings = [s["heading"] for s in sections]
        assert "Short" not in headings

    def test_extract_code_blocks(self):
        text = "Some text\n```python\nprint('hello')\n```\nMore text\n```\nraw block\n```"
        blocks = RepoDocAdapter._extract_code_blocks(text)
        assert len(blocks) == 2
        assert "print('hello')" in blocks[0]

    def test_make_record_signals(self):
        record = self.adapter._make_record(
            source_type="github_readme",
            source_id="readme:overview",
            source_url="https://github.com/test/repo#readme",
            project="test/repo",
            title="Overview",
            body="This tool has a limitation: rate limits apply. You must always use caching.",
        )
        assert record.signals["is_documentation"] is True
        assert record.signals["has_api_boundaries"] is True
        assert record.signals["has_domain_rules"] is True
```

### 6.2 test_code_search_adapter.py

```python
"""CodeSearchAdapter 单元测试。"""

import pytest

from doramagic_judgment_pipeline.source_adapters.code_search import CodeSearchAdapter


class TestCodeSnippetExtraction:
    """测试代码片段提取逻辑（纯本地，不依赖 GitHub API）。"""

    def test_extract_assert_snippets(self):
        content = """import pandas as pd

def validate_data(df):
    # 确保没有空值
    assert not df.isnull().any().any(), "DataFrame contains null values"

    # 确保价格为正
    assert (df['price'] > 0).all(), "Prices must be positive"

    return df

def process():
    pass
"""
        snippets = CodeSearchAdapter._extract_relevant_snippets(content, "assert", context_lines=3)
        assert len(snippets) >= 1
        # 至少一个片段包含 assert
        assert any("assert" in s for s in snippets)

    def test_extract_raise_snippets(self):
        content = """from decimal import Decimal

def set_price(value):
    if not isinstance(value, Decimal):
        raise TypeError("Price must be Decimal, got {type(value)}")
    if value < 0:
        raise ValueError("Price cannot be negative")
    return value
"""
        snippets = CodeSearchAdapter._extract_relevant_snippets(content, "raise ValueError", context_lines=5)
        assert len(snippets) >= 1
        assert any("raise ValueError" in s for s in snippets)

    def test_no_match_returns_empty(self):
        content = "def hello():\n    print('world')\n"
        snippets = CodeSearchAdapter._extract_relevant_snippets(content, "assert", context_lines=3)
        assert snippets == []

    def test_overlapping_ranges_merged(self):
        content = "\n".join([f"line {i}" for i in range(50)])
        # 植入两个相邻的匹配
        lines = content.split("\n")
        lines[10] = "assert x > 0"
        lines[12] = "assert y > 0"
        content = "\n".join(lines)

        snippets = CodeSearchAdapter._extract_relevant_snippets(content, "assert", context_lines=5)
        # 两个匹配很近，应该合并为一个片段
        assert len(snippets) == 1

    def test_max_snippets_capped(self):
        # 创建很多匹配
        lines = [f"assert condition_{i}" for i in range(20)]
        content = "\n\n\n\n\n\n\n\n\n\n\n".join(lines)  # 足够间距避免合并

        snippets = CodeSearchAdapter._extract_relevant_snippets(content, "assert", context_lines=2)
        assert len(snippets) <= 5  # 最多 5 个

    def test_line_numbers_in_snippets(self):
        content = "line1\nline2\nassert something\nline4\n"
        snippets = CodeSearchAdapter._extract_relevant_snippets(content, "assert", context_lines=1)
        assert len(snippets) == 1
        assert "L3:" in snippets[0]  # 行号标记
```

### 6.3 test_doc_filter.py

```python
"""文档过滤器单元测试。"""

import pytest

from doramagic_judgment_pipeline.source_adapters.base import RawExperienceRecord
from doramagic_judgment_pipeline.extract.doc_filter import (
    filter_doc_records,
    DocFilterTrack,
)


def _make_doc_record(title: str, body: str, source_type: str = "github_readme") -> RawExperienceRecord:
    return RawExperienceRecord(
        source_type=source_type,
        source_id=f"test:{title}",
        source_url="https://github.com/test/repo",
        source_platform="github",
        project_or_community="test/repo",
        title=title,
        body=body,
        signals={
            "is_documentation": True,
            "source_type": source_type,
            "body_length": len(body),
            "has_code_blocks": "```" in body,
            "has_warnings": bool(__import__("re").search(r"(?i)(warning|limitation)", body)),
            "has_api_boundaries": bool(__import__("re").search(r"(?i)(limit|not.?support)", body)),
            "has_domain_rules": bool(__import__("re").search(r"(?i)(must|never|always)", body)),
        },
    )


class TestDocFilter:

    def test_blacklist_excludes_contributing(self):
        record = _make_doc_record("Contributing Guide", "How to contribute to this project..." * 10)
        results = filter_doc_records([record])
        assert len(results) == 1
        assert results[0].track == DocFilterTrack.BLACKLIST_EXCLUDED
        assert not results[0].passed

    def test_blacklist_excludes_license(self):
        record = _make_doc_record("License", "MIT License..." * 10)
        results = filter_doc_records([record])
        assert results[0].track == DocFilterTrack.BLACKLIST_EXCLUDED

    def test_whitelist_passes_limitations(self):
        record = _make_doc_record("Known Limitations", "Rate limiting applies..." * 10)
        results = filter_doc_records([record])
        assert results[0].track == DocFilterTrack.WHITELIST_PASSED
        assert results[0].passed

    def test_whitelist_passes_architecture(self):
        record = _make_doc_record("Architecture Overview", "The system design..." * 10)
        results = filter_doc_records([record])
        assert results[0].track == DocFilterTrack.WHITELIST_PASSED

    def test_signal_scoring_high_value(self):
        body = "Warning: You must never use float for financial calculations. " * 5
        record = _make_doc_record("Data Processing", body)
        results = filter_doc_records([record])
        assert results[0].passed  # has_warnings + has_domain_rules → 高分

    def test_signal_scoring_low_value(self):
        body = "x" * 60  # 超过 50 但无任何信号
        record = _make_doc_record("Some Section", body)
        results = filter_doc_records([record])
        assert not results[0].passed  # 无信号 → 低分

    def test_deps_always_pass(self):
        record = _make_doc_record("Dependencies: pyproject.toml", "pandas>=2.0", source_type="github_deps")
        results = filter_doc_records([record])
        assert results[0].passed  # github_deps 阈值 = 0
```

### 6.3 test_doc_extractor.py

```python
"""文档提取器单元测试 — 使用 mock LLM。"""

import json
import pytest

from doramagic_judgment_pipeline.source_adapters.base import RawExperienceRecord
from doramagic_judgment_pipeline.extract.doc_extractor import (
    extract_doc_judgments,
    SOURCE_TYPE_TO_LAYER,
    SOURCE_TYPE_TO_SECTION,
)


class MockLLMResponse:
    def __init__(self, text: str):
        self.text = text


class MockLLMAdapter:
    def __init__(self, response_text: str):
        self._response_text = response_text

    def chat(self, **kwargs):
        return MockLLMResponse(self._response_text)


def _make_doc_record() -> RawExperienceRecord:
    return RawExperienceRecord(
        source_type="github_readme",
        source_id="readme:limitations",
        source_url="https://github.com/freqtrade/freqtrade#readme",
        source_platform="github",
        project_or_community="freqtrade/freqtrade",
        title="Known Limitations",
        body="yfinance has rate limits. You must cache data locally to avoid disruption.",
        signals={"source_type": "github_readme"},
    )


class TestDocExtractor:

    @pytest.mark.asyncio
    async def test_extract_valid_judgment(self):
        llm_output = json.dumps([{
            "when": "使用 yfinance 拉取历史数据进行回测时",
            "modality": "must",
            "action": "在本地建立数据缓存，每次运行先检查缓存是否存在",
            "consequence_kind": "service_disruption",
            "consequence_description": "高频请求触发 yfinance 限流，回测流水线中断",
            "layer": "resource",
            "severity": "medium",
            "confidence_score": 0.8,
            "crystal_section": "resource_profile",
            "evidence_summary": "README Limitations: rate limits may apply",
        }])

        adapter = MockLLMAdapter(llm_output)
        record = _make_doc_record()

        judgments = await extract_doc_judgments(
            record=record,
            adapter=adapter,
            domain="finance",
            id_counter=1,
        )

        assert len(judgments) == 1
        j = judgments[0]
        assert j.layer == "resource"  # use_enum_values=True
        assert j.compilation.crystal_section == "resource_profile"
        assert j.confidence.source == "S1_single_project"
        assert j.confidence.evidence_refs[0].type == "doc"

    @pytest.mark.asyncio
    async def test_experience_layer_rejected(self):
        """文档提取器不应产出 experience 层判断。"""
        llm_output = json.dumps([{
            "when": "测试时",
            "modality": "must",
            "action": "使用 mock 数据避免外部依赖",
            "consequence_kind": "bug",
            "consequence_description": "测试不稳定",
            "layer": "experience",  # 错误的层
            "severity": "low",
            "confidence_score": 0.6,
            "crystal_section": "protocols",
            "evidence_summary": "文档中的测试建议",
        }])

        adapter = MockLLMAdapter(llm_output)
        record = _make_doc_record()

        judgments = await extract_doc_judgments(
            record=record,
            adapter=adapter,
            domain="finance",
            id_counter=1,
        )

        # 即使 LLM 输出 experience，也会被映射回 knowledge（README 的默认层）
        if judgments:
            assert judgments[0].layer != "experience"

    @pytest.mark.asyncio
    async def test_empty_extraction(self):
        adapter = MockLLMAdapter("[]")
        record = _make_doc_record()
        judgments = await extract_doc_judgments(record=record, adapter=adapter, domain="finance")
        assert judgments == []

    @pytest.mark.asyncio
    async def test_invalid_json(self):
        adapter = MockLLMAdapter("This is not JSON at all")
        record = _make_doc_record()
        judgments = await extract_doc_judgments(record=record, adapter=adapter, domain="finance")
        assert judgments == []

    def test_source_type_mappings(self):
        assert SOURCE_TYPE_TO_LAYER["github_readme"].value == "knowledge"
        assert SOURCE_TYPE_TO_LAYER["github_changelog"].value == "resource"
        assert SOURCE_TYPE_TO_SECTION["github_readme"].value == "world_model"
        assert SOURCE_TYPE_TO_SECTION["github_deps"].value == "resource_profile"
```

### 6.4 test_full_pipeline.py

```python
"""三层完整采集集成测试 — 验证晶体覆盖度。"""

import pytest

from doramagic_judgment_schema.types import Judgment, Layer, CrystalSection
from doramagic_judgment_schema.serializer import JudgmentStore
from doramagic_crystal_compiler.retrieve import retrieve
from doramagic_crystal_compiler.compiler import compile_crystal


class TestCrystalCoverage:
    """验证三层判断能正确编译为完整晶体。"""

    @pytest.fixture
    def populated_store(self, tmp_path):
        """创建一个包含三层判断的临时 store。"""
        store = JudgmentStore(base_path=str(tmp_path / "judgments"))

        # 手工构建三层判断样本
        from doramagic_judgment_schema.types import (
            JudgmentCore, JudgmentScope, JudgmentConfidence,
            JudgmentCompilation, JudgmentVersion, Consequence, EvidenceRef,
            Modality, Severity, ScopeLevel, Freshness, SourceLevel,
            ConsensusLevel, ConsequenceKind, EvidenceRefType, LifecycleStatus,
        )

        def make_judgment(id_str, layer, section, when, action, consequence_desc):
            return Judgment(
                id=id_str,
                core=JudgmentCore(
                    when=when,
                    modality=Modality.MUST,
                    action=action,
                    consequence=Consequence(
                        kind=ConsequenceKind.BUG,
                        description=consequence_desc,
                    ),
                ),
                layer=layer,
                scope=JudgmentScope(level=ScopeLevel.DOMAIN, domains=["finance"]),
                confidence=JudgmentConfidence(
                    source=SourceLevel.S1_SINGLE_PROJECT,
                    score=0.8,
                    consensus=ConsensusLevel.STRONG,
                    evidence_refs=[
                        EvidenceRef(type=EvidenceRefType.DOC, source="test/repo", summary="test evidence"),
                    ],
                ),
                compilation=JudgmentCompilation(
                    severity=Severity.HIGH,
                    crystal_section=section,
                    freshness=Freshness.SEMI_STABLE,
                    query_tags=["finance"],
                ),
                version=JudgmentVersion(status=LifecycleStatus.DRAFT),
            )

        # 知识层 → world_model
        store.store(make_judgment(
            "finance-K-001", Layer.KNOWLEDGE, CrystalSection.WORLD_MODEL,
            "处理股票价格时间序列时",
            "基于交易日序列计算指标，禁止对非交易日插值",
            "插值导致指标偏离真实市场状态，回测收益率虚高 5-15%",
        ))

        # 资源层 → resource_profile
        store.store(make_judgment(
            "finance-R-001", Layer.RESOURCE, CrystalSection.RESOURCE_PROFILE,
            "使用 yfinance 获取历史数据时",
            "在本地建立缓存层避免重复请求",
            "高频请求触发限流，数据拉取中断导致流水线失败",
        ))

        # 经验层 → constraints
        store.store(make_judgment(
            "finance-E-001", Layer.EXPERIENCE, CrystalSection.CONSTRAINTS,
            "使用 pandas 的 rolling 函数做回测计算时",
            "检查是否引入了未来数据（look-ahead bias）",
            "look-ahead 导致回测收益虚假，实盘亏损",
        ))

        return store

    def test_crystal_has_recipe_structure(self, populated_store):
        """晶体必须包含三段式配方结构。"""
        retrieval = retrieve(store=populated_store, domain="finance")
        crystal = compile_crystal(
            retrieval=retrieval,
            domain="finance",
            task_description="量化投资分析工具",
        )

        # 三段式配方结构
        assert "## 一、最小可运行样本" in crystal
        assert "## 二、硬约束" in crystal
        assert "## 三、验收标准" in crystal
        assert "## context_acquisition" in crystal

        # 代码骨架包含知识层
        assert "```python" in crystal
        assert "assert" in crystal or "# 领域规则" in crystal

        # 硬约束表为表格格式
        assert "| # | 约束 | 原因 | 违反后果 |" in crystal

        # 三层判断都应影响晶体
        assert "交易日序列" in crystal or "balance" in crystal
        assert "yfinance" in crystal or "缓存" in crystal
        assert "look-ahead" in crystal or "rolling" in crystal

        # 不包含旧格式残留
        assert "<crystal" not in crystal
        assert "个性化提示" not in crystal

    def test_crystal_context_acquisition(self, populated_store):
        """晶体必须包含 context_acquisition 指令块。"""
        retrieval = retrieve(store=populated_store, domain="finance")
        crystal = compile_crystal(
            retrieval=retrieval,
            domain="finance",
            task_description="量化投资分析工具",
        )
        assert "查阅用户历史会话" in crystal or "查阅当前用户" in crystal
        assert "宿主 AI" in crystal

    def test_three_layer_coverage(self, populated_store):
        """检索结果应覆盖三层。"""
        retrieval = retrieve(store=populated_store, domain="finance")
        layers = {j.layer for j, _ in retrieval.judgments}

        # 注意：use_enum_values=True 导致 layer 是字符串
        layer_values = set()
        for j, _ in retrieval.judgments:
            val = j.layer.value if hasattr(j.layer, "value") else j.layer
            layer_values.add(val)

        assert "knowledge" in layer_values
        assert "resource" in layer_values
        assert "experience" in layer_values

    def test_no_coverage_gaps_with_three_layers(self, populated_store):
        """三层都有判断时，不应报告层级缺口。"""
        retrieval = retrieve(store=populated_store, domain="finance")
        layer_gaps = [g for g in retrieval.coverage_gaps if "缺少" in g and "层判断" in g]
        assert len(layer_gaps) == 0
```

---

## 七、crystal_compiler 重写 — 三段式配方格式

### 7.1 背景

晶体的消费者是用户的 AI 工具。用户把晶体文件丢进 AI 对话窗口，宿主 AI 读取配方后现场构建个性化 skill。

Sprint 3 的编译器输出 emoji markdown + 个性化提问——错误。晶体不是约束列表，是可被 AI 消费的结构化配方，包含四部分：

1. **代码骨架** — 最小可运行样本，知识层 judgment 以 assert/validation/类型约束的形式植入代码
2. **硬约束表** — 表格形式，每行：约束 / 原因 / 违反后果。经验层和资源层 judgment 在此聚合
3. **验收标准** — 编号列表，三层交叉碰撞产出的检验项，合格 skill 必须全部通过
4. **context_acquisition** — 指令块，告诉宿主 AI 先查阅用户历史会话，再补充采集缺失信息

参考实现：`docs/research/judgment-system/multi-agent-orchestration.seed.md`（A/B 测试 7/8 vs 0/8）

### 7.2 对 Sprint 3 compiler.py 的修改

**本节替换 `packages/crystal_compiler/doramagic_crystal_compiler/compiler.py` 的全部内容。**

```python
"""种子晶体编译器 — 将判断集编译为三段式配方（代码骨架 + 硬约束表 + 验收标准）。

晶体是配方/蓝图，消费者是用户的 AI 工具。
参考实现：docs/research/judgment-system/multi-agent-orchestration.seed.md
"""

from __future__ import annotations

from datetime import datetime, timezone

from doramagic_judgment_schema.types import (
    CrystalSection,
    Judgment,
    Layer,
    Severity,
)

from .retrieve import RetrievalResult


def compile_crystal(
    retrieval: RetrievalResult,
    domain: str,
    task_description: str,
    version: str = "0.1.0",
    max_tokens: int | None = None,
) -> str:
    """
    将检索结果编译为种子晶体 — 三段式配方格式。

    输出结构：
    1. 代码骨架（最小可运行样本，知识层 judgment 植入为 assert/validation）
    2. 硬约束表（经验层 + 资源层 judgment，表格形式）
    3. 验收标准（三层交叉碰撞，编号列表）
    4. context_acquisition 指令块

    max_tokens: 粗略按 1 token ≈ 4 字符估算。超出预算时从硬约束表末尾截断，
    代码骨架和验收标准永不截断。
    """
    # ── 分拣判断到三段 ──
    skeleton_judgments: list[tuple[Judgment, float]] = []  # → 代码骨架中的 assert/validation
    constraint_rows: list[tuple[Judgment, float]] = []     # → 硬约束表行
    acceptance_judgments: list[tuple[Judgment, float]] = [] # → 验收标准条目

    for judgment, weight in retrieval.judgments:
        layer = judgment.layer
        if not isinstance(layer, str):
            layer = layer.value

        severity = judgment.compilation.severity
        if not isinstance(severity, str):
            severity = severity.value

        # 分拣逻辑（对照 PRODUCT_CONSTITUTION_v2.md Section 4.4）：
        # 知识层 → 代码骨架（assert/validation/类型定义）
        # 经验层 + 资源层 → 硬约束表
        if layer == "knowledge":
            skeleton_judgments.append((judgment, weight))
        elif layer in ("experience", "resource"):
            constraint_rows.append((judgment, weight))
        else:
            constraint_rows.append((judgment, weight))

    # 从三层碰撞中提取验收标准候选
    knowledge_whens = {j.core.when for j, _ in skeleton_judgments}
    experience_whens = {j.core.when for j, _ in constraint_rows}
    cross_layer_whens = knowledge_whens & experience_whens

    remaining_constraints: list[tuple[Judgment, float]] = []
    for judgment, weight in constraint_rows:
        if judgment.core.when in cross_layer_whens:
            acceptance_judgments.append((judgment, weight))
        else:
            remaining_constraints.append((judgment, weight))
    constraint_rows = remaining_constraints

    # severity = FATAL 也进入验收标准
    final_constraints: list[tuple[Judgment, float]] = []
    for judgment, weight in constraint_rows:
        sev = judgment.compilation.severity
        if not isinstance(sev, str):
            sev = sev.value
        if sev == "fatal":
            acceptance_judgments.append((judgment, weight))
        else:
            final_constraints.append((judgment, weight))
    constraint_rows = final_constraints

    # ── 渲染四段 ──
    section_1 = _render_code_skeleton(skeleton_judgments, domain, task_description)
    section_2 = _render_hard_constraints_table(constraint_rows)
    section_3 = _render_acceptance_criteria(acceptance_judgments)
    section_4 = _render_context_acquisition(domain)
    coverage = _render_coverage_gaps(retrieval.coverage_gaps)

    compiled_at = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    crystal = f"""# 种子晶体：{domain} — {task_description}

> 来源：Doramagic 知识引擎 | 基于 {len(retrieval.judgments)} 颗判断编译
> 知识库版本: {version} | 编译时间: {compiled_at}
> 适用场景：{task_description}

---

{section_4}

---

## 一、最小可运行样本

{section_1}

---

## 二、硬约束（违反必出 bug）

{section_2}

---

## 三、验收标准

{section_3}

---

{coverage}

---

*生成自 Doramagic 知识引擎*
"""

    if max_tokens:
        max_chars = max_tokens * 4
        if len(crystal) > max_chars:
            crystal = _trim_to_budget(crystal, max_chars)

    return crystal


def _render_code_skeleton(
    judgments: list[tuple[Judgment, float]],
    domain: str,
    task_description: str,
) -> str:
    if not judgments:
        return f'```python\n"""{domain}: {task_description} — 最小可运行骨架"""\n\n# 知识库中暂无知识层判断，骨架待填充\npass\n```'

    lines = [f'"""{domain}: {task_description} — 最小可运行骨架"""', ""]
    for judgment, _ in judgments:
        lines.append(f"# 领域规则：当{judgment.core.when}时")
        lines.append(f"# → {judgment.core.action}")
        lines.append(f"assert True  # 待实现: {judgment.core.action}")
        lines.append(f"# 违反后果: {judgment.core.consequence.description}")
        lines.append("")
    return "```python\n" + "\n".join(lines) + "\n```"


def _render_hard_constraints_table(
    judgments: list[tuple[Judgment, float]],
) -> str:
    if not judgments:
        return "| # | 约束 | 原因 | 违反后果 |\n|---|------|------|---------|"

    rows = ["| # | 约束 | 原因 | 违反后果 |", "|---|------|------|---------|"]
    for i, (judgment, _) in enumerate(judgments, 1):
        modality_map = {"must": "必须", "must_not": "禁止", "should": "应当", "should_not": "不应"}
        mod = judgment.core.modality
        if not isinstance(mod, str):
            mod = mod.value
        prefix = modality_map.get(mod, "")
        constraint = f"**{prefix}**：当{judgment.core.when}时，{judgment.core.action}"
        reason = _get_evidence_summary(judgment)
        consequence = judgment.core.consequence.description
        rows.append(f"| C{i} | {constraint} | {reason} | {consequence} |")
    return "\n".join(rows)


def _render_acceptance_criteria(
    judgments: list[tuple[Judgment, float]],
) -> str:
    if not judgments:
        return "（暂无验收标准 — 需要更多三层交叉判断）"

    lines = ["一个合格的 skill 必须通过以下检验：", ""]
    for i, (judgment, _) in enumerate(judgments, 1):
        lines.append(
            f"{i}. **{judgment.core.action}**：当{judgment.core.when}时，"
            f"违反将导致 {judgment.core.consequence.description}"
        )
    return "\n".join(lines)


def _render_context_acquisition(domain: str) -> str:
    return f"""## context_acquisition

> **以下指令面向消费本晶体的宿主 AI 系统（Claude Code / Codex / Antigravity 等）。**

在按本配方构建 skill 之前，你（宿主 AI）必须先获取用户的个性化上下文：

1. **查阅用户历史会话**：翻阅当前用户之前的对话记录，提取：
   - 用户的项目背景和技术栈
   - 用户过往的偏好和约束（如特定框架版本、部署环境）
   - 用户在 {domain} 领域的经验水平

2. **补充采集缺失信息**：如果历史会话中缺少以下关键信息，向用户提问：
   - 具体使用的框架和版本？
   - 目标部署环境（本地 / 云 / 边缘）？
   - 性能/成本/可维护性的优先级排序？
   - 是否有特殊约束（合规要求、网络隔离等）？

3. **基于用户上下文 + 本晶体的代码骨架 + 硬约束 + 验收标准，现场构建定制 skill。**
   同一颗晶体在不同用户手里产出不同的 skill，因为每个用户的上下文不同。"""


def _render_coverage_gaps(gaps: list[str]) -> str:
    if not gaps:
        return "## 已知缺口\n\n无已知缺口。"
    lines = ["## 已知缺口", ""]
    for g in gaps:
        lines.append(f"- {g}")
    return "\n".join(lines)


def _get_evidence_summary(judgment: Judgment) -> str:
    if judgment.confidence.evidence_refs:
        ref = judgment.confidence.evidence_refs[0]
        return ref.summary if hasattr(ref, "summary") and ref.summary else ref.source
    return "社区实践经验"


def _trim_to_budget(crystal: str, max_chars: int) -> str:
    """代码骨架和验收标准永不截断，从硬约束表末尾行截断。"""
    table_start = crystal.find("## 二、硬约束")
    table_end = crystal.find("---", table_start + 10) if table_start >= 0 else -1
    if table_start < 0 or table_end < 0:
        return crystal[:max_chars]

    before_table = crystal[:table_start]
    table_section = crystal[table_start:table_end]
    after_table = crystal[table_end:]
    non_table_size = len(before_table) + len(after_table)
    table_budget = max_chars - non_table_size

    if table_budget <= 0:
        return crystal[:max_chars]

    table_lines = table_section.split("\n")
    trimmed_lines: list[str] = []
    used = 0
    for line in table_lines:
        if used + len(line) + 1 > table_budget:
            trimmed_lines.append("| ... | （因 token 预算限制，部分约束被省略） | | |")
            break
        trimmed_lines.append(line)
        used += len(line) + 1
    return before_table + "\n".join(trimmed_lines) + after_table
```

### 7.5 CrystalSection 枚举扩展

Sprint 3 的 `CrystalSection` 枚举只有旧值（`WORLD_MODEL`, `RESOURCE_PROFILE`, `CONSTRAINTS`, `ARCHITECTURE`, `PROTOCOLS`, `EVIDENCE`）。需要在 `packages/judgment_schema/doramagic_judgment_schema/types.py` 中追加新值：

```python
class CrystalSection(str, Enum):
    # 旧值（保留向后兼容，但编译器不再使用）
    WORLD_MODEL = "world_model"
    RESOURCE_PROFILE = "resource_profile"
    CONSTRAINTS = "constraints"
    ARCHITECTURE = "architecture"
    PROTOCOLS = "protocols"
    EVIDENCE = "evidence"
    # 新值（v1.2 三段式配方）
    CODE_SKELETON = "code_skeleton"
    HARD_CONSTRAINTS = "hard_constraints"
    ACCEPTANCE_CRITERIA = "acceptance_criteria"
```

doc_extractor.py 的 `SOURCE_TYPE_TO_SECTION` 映射和 LLM prompt 中的 `crystal_section` 选项已在本文档中更新为新值。测试中如有旧值断言（如 `assert ... == "world_model"`），一律改为对应的新值。

### 7.3 templates/base.yaml 更新

```yaml
# 种子晶体配方模板
crystal:
  version: "2.0"
  format: "recipe"
  consumer: "ai_tool"
  sections:
    - name: context_acquisition
      title: "context_acquisition"
      purpose: "指导宿主 AI 获取用户上下文"
      required: true
    - name: code_skeleton
      title: "最小可运行样本"
      source_layer: "knowledge"
      required: true
    - name: hard_constraints
      title: "硬约束（违反必出 bug）"
      format: "table"
      source_layer: ["experience", "resource"]
      required: true
    - name: acceptance_criteria
      title: "验收标准"
      format: "numbered_list"
      source_layer: "cross_layer"
      required: true
```

### 7.4 harvest.py 支持 token 预算参数

在 `scripts/harvest.py` 的 argparse 中追加：

```python
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="晶体 token 预算上限（默认: 不限制）",
    )
```

并在调用 `run_full_pipeline` 时传递此参数。

---

## 七B、harvest.py 默认目标列表 — AI 工具链优先

### 7B.1 背景

第一期晶体消费场景是开发 CLI/IDE（Claude Code、Codex、Antigravity）。最刚需的晶体不是金融领域，而是"如何正确使用 AI 工具链"。harvest.py 应预置 AI 工具链仓库作为默认目标。

### 7B.2 预置目标列表

在 `scripts/harvest.py` 中新增默认目标配置：

```python
# 预置 harvest 目标
DEFAULT_TARGETS: dict[str, list[dict]] = {
    "ai_tooling": [
        {"owner": "anthropics", "repo": "anthropic-sdk-python", "domain": "ai_tooling"},
        {"owner": "openai", "repo": "openai-python", "domain": "ai_tooling"},
        {"owner": "langchain-ai", "repo": "langchain", "domain": "ai_tooling"},
        {"owner": "run-llama", "repo": "llama_index", "domain": "ai_tooling"},
        {"owner": "crewAIInc", "repo": "crewAI", "domain": "ai_tooling"},
        {"owner": "anthropics", "repo": "claude-code", "domain": "ai_tooling"},
    ],
    "finance": [
        {"owner": "freqtrade", "repo": "freqtrade", "domain": "finance"},
        {"owner": "stefan-jansen", "repo": "zipline-reloaded", "domain": "finance"},
        {"owner": "vnpy", "repo": "vnpy", "domain": "finance"},
    ],
}
```

harvest.py 新增 `--preset` 参数：

```python
    parser.add_argument(
        "--preset",
        choices=list(DEFAULT_TARGETS.keys()),
        default=None,
        help="使用预置目标列表（ai_tooling / finance），覆盖 --owner/--repo",
    )
```

当 `--preset ai_tooling` 时，自动遍历 6 个 AI 工具链仓库做完整采集。

---

## 八、目录创建清单

Sprint 4 需要创建的新文件（目录在 Sprint 1-3 中已创建）：

```bash
# 新文件
touch packages/judgment_pipeline/doramagic_judgment_pipeline/source_adapters/repo_doc.py
touch packages/judgment_pipeline/doramagic_judgment_pipeline/source_adapters/code_search.py
touch packages/judgment_pipeline/doramagic_judgment_pipeline/extract/doc_filter.py
touch packages/judgment_pipeline/doramagic_judgment_pipeline/extract/doc_extractor.py
touch tests/judgment_pipeline/test_repo_doc_adapter.py
touch tests/judgment_pipeline/test_code_search_adapter.py
touch tests/judgment_pipeline/test_doc_filter.py
touch tests/judgment_pipeline/test_doc_extractor.py
touch tests/judgment_pipeline/test_full_pipeline.py

# 晶体输出目录
mkdir -p knowledge/judgments/crystals
```

---

## 九、Sprint 4 执行流程

```
1. 确认 Sprint 1-3 已完成（make check 通过）
2. 创建新文件
3. 实现 source_adapters/repo_doc.py（文档适配器）
4. 实现 source_adapters/code_search.py（代码分析适配器，含领域配置化搜索模式）
5. 实现 extract/doc_filter.py（文档+代码过滤器）
6. 实现 extract/doc_extractor.py（知识/资源层提取器，含代码专用 prompt）
7. 扩展 pipeline.py（追加 run_doc_pipeline + run_full_pipeline）
8. 修改 crystal_compiler/compiler.py（三段式配方格式 + token 预算裁剪 + context_acquisition，替换 Sprint 3 的 emoji markdown）
9. 更新 source_adapters/__init__.py 和 extract/__init__.py
10. 修改 scripts/harvest.py（--mode + --max-tokens + --preset 参数）
11. 实现所有测试文件
12. 运行 make check
13. 如果 make check 失败：
    a. 看报错信息
    b. 修复
    c. 再跑 make check
    d. 重复直到全部通过（最多 5 轮修复）
14. make check 全部通过后，git commit
    commit message 格式：feat(judgment): Sprint 4 — three-layer harvesting + recipe-format crystal + AI tooling support
```

---

## 十、验收标准

### Sprint 4 验收

- [ ] `make check` 通过（lint + typecheck + test）
- [ ] 所有 test_repo_doc_adapter.py 测试通过
- [ ] 所有 test_code_search_adapter.py 测试通过
- [ ] 所有 test_doc_filter.py 测试通过
- [ ] 所有 test_doc_extractor.py 测试通过
- [ ] 所有 test_full_pipeline.py 测试通过
- [ ] `python scripts/harvest.py --mode doc` 能运行完成
- [ ] `python scripts/harvest.py --mode full` 能运行完成
- [ ] knowledge/judgments/domains/finance.jsonl 中包含三层判断（knowledge + resource + experience）
- [ ] 编译产出的种子晶体包含**三段式配方结构**：代码骨架 + 硬约束表 + 验收标准 + context_acquisition 指令块
- [ ] 晶体的**代码骨架**中包含知识层 judgment 植入的 assert/validation（非空）
- [ ] 晶体的**硬约束表**为 markdown 表格格式，每行含：约束 / 原因 / 违反后果
- [ ] 晶体的**验收标准**为编号列表，包含至少 1 条三层碰撞产出的检验项
- [ ] 晶体包含 **context_acquisition 指令块**，指示宿主 AI 先查阅用户历史会话
- [ ] 晶体不包含 emoji、XML 标记、system prompt 指令格式、面向人类的个性化提问
- [ ] 晶体的 coverage_gaps 中**不再报告** "缺少 knowledge 层" 或 "缺少 resource 层"
- [ ] **token 预算**：`--max-tokens 2000` 时晶体长度不超过约 8000 字符，代码骨架和验收标准不被截断
- [ ] **领域配置化**：CodeSearchAdapter 使用 `--domain ai_tooling` 时搜索 max_tokens/context_window 等 AI 专用模式
- [ ] **预置目标**：`--preset ai_tooling` 能遍历 AI 工具链仓库做完整采集

### 端到端验证命令

```bash
# 金融领域三层采集（原有验证）
PYTHONPATH=packages/judgment_schema:packages/judgment_pipeline:packages/crystal_compiler:packages/shared_utils \
  .venv/bin/python scripts/harvest.py --mode full --owner freqtrade --repo freqtrade --domain finance

# AI 工具链领域采集（新增验证）
PYTHONPATH=packages/judgment_schema:packages/judgment_pipeline:packages/crystal_compiler:packages/shared_utils \
  .venv/bin/python scripts/harvest.py --mode full --preset ai_tooling

# token 预算验证
PYTHONPATH=packages/judgment_schema:packages/judgment_pipeline:packages/crystal_compiler:packages/shared_utils \
  .venv/bin/python scripts/harvest.py --mode full --owner freqtrade --repo freqtrade --domain finance --max-tokens 2000

# 验证三层覆盖
PYTHONPATH=packages/judgment_schema:packages/judgment_pipeline:packages/crystal_compiler:packages/shared_utils \
  .venv/bin/python -c "
from doramagic_judgment_schema.serializer import JudgmentStore
store = JudgmentStore(base_path='knowledge/judgments')
js = store.list_by_domain('finance')
layers = {}
for j in js:
    l = j.layer.value if hasattr(j.layer, 'value') else j.layer
    layers[l] = layers.get(l, 0) + 1
print('三层覆盖:', layers)
assert 'knowledge' in layers, '缺少知识层判断'
assert 'resource' in layers, '缺少资源层判断'
assert 'experience' in layers, '缺少经验层判断'
print('✅ 三层验证通过')
"
```

---

## 十一、pyproject.toml 与 Makefile 变更

Sprint 4 **不需要**修改 `pyproject.toml` 或 `Makefile`，因为：
- 新文件全部在 Sprint 1-3 已注册的包目录内（`judgment_pipeline`）
- 测试在 Sprint 1-3 已注册的测试目录内
- 没有新包

但需要在 `pyproject.toml` 的 ruff lint 忽略中为新文件添加例外（如有需要）：

```toml
# 如果 doc_extractor.py 的 prompt 模板超过 100 字符行宽限制，追加：
"packages/judgment_pipeline/doramagic_judgment_pipeline/extract/doc_extractor.py" = ["E501"]
"packages/judgment_pipeline/doramagic_judgment_pipeline/source_adapters/repo_doc.py" = ["E501"]
"packages/judgment_pipeline/doramagic_judgment_pipeline/source_adapters/code_search.py" = ["E501"]
```

---

## 十二、成本估算

Sprint 4 新增的 LLM 调用（Sonnet）：

| 步骤 | 每条记录 token | 记录数（freqtrade） | 小计 |
|---|---|---|---|
| DocExtractor（文档→知识/资源） | ~2000 input + ~800 output | ~30 条（过滤后） | ~84K tokens |
| DocExtractor（代码→知识/资源） | ~1500 input + ~600 output | ~20 条（过滤后） | ~42K tokens |

不需要 classifier 环节（文档和代码不需要分类，直接由 filter 决定通过与否）。

**GitHub API 调用量**：
- RepoDocAdapter: ~25 次（README + docs 目录 + 各文件）
- CodeSearchAdapter: ~8 次搜索 + ~40 次文件拉取 ≈ 48 次
- 总计 ~73 次 GitHub API 调用（免费额度 5000次/小时，完全足够）

预估单次完整采集（Issue + Doc + Code）总成本：~$0.06（全 Sonnet）。

---

*v1.0: 2026-04-03 — 三层完整采集*
*v1.1: 2026-04-03 — 晶体输出改为 LLM 原生 XML 格式（去掉 emoji markdown 和个性化提问）+ token 预算 + AI 工具链领域支持 + 预置目标列表*
*v1.2: 2026-04-03 — 晶体格式从 XML 约束列表改为三段式配方（代码骨架 + 硬约束表 + 验收标准 + context_acquisition），对齐 PRODUCT_CONSTITUTION_v2.md*
