# Doramagic 判断系统 — 开发需求文档 v1.2（三方挑战修复版）

> **本文档交给 Claude Code CLI 执行开发。**
> 每个模块有精确的数据模型、函数签名、测试用例。执行者不需要做设计决策。
> **执行者必须按顺序阅读完整份文档后再开始编码。**

---

## 前置必读

**开始编码前，先执行以下两步：**

1. 阅读项目根目录的 `CLAUDE.md`，它包含项目级的工程规范（LLM 调用约束、构建命令、lint 规则等）。本文档的所有要求在 `CLAUDE.md` 的框架之上，两者不冲突。
2. 阅读本文档全文（约 2400 行），理解整体架构后再开始编码。不要读一段写一段。

---

## 项目背景（执行者须知）

**Doramagic** 是一个从开源社区（GitHub Issue、Discussion 等）中自动提取结构化经验知识的系统。

**核心概念**：
- **判断（Judgment）**：最小知识单元，三元组格式——"当[条件]时，必须/禁止[行为]，否则[后果]"。例：*当使用 yfinance 获取 A 股日线数据时，必须使用 adj_close 而非 close 字段，否则未复权价格会导致回测收益率偏差超过 30%*
- **种子晶体（Seed Crystal）**：将一组判断编译成的约束文本，用于注入用户的 LLM system prompt，使 LLM 在特定领域不踩已知的坑
- **知识工厂**：本地 Mac Mini 上运行的采集+提取流水线，从 GitHub 拉取 Issue → 过滤 → LLM 提取判断 → 存储

**你要开发的是知识工厂的核心三个包**，按 Sprint 顺序：
1. `judgment_schema`（Sprint 1）— 判断的数据模型、校验、序列化
2. `judgment_pipeline`（Sprint 2）— 从 GitHub 采集并提取判断的流水线
3. `crystal_compiler`（Sprint 3）— 将判断编译成种子晶体

---

## 工作目录与成果位置

### 执行环境假设

- Claude Code CLI 在 **Doramagic 项目根目录** 启动（即包含 `pyproject.toml`、`Makefile`、`packages/` 的目录）
- 虚拟环境 `.venv/` 已存在且可用，所有命令通过 `.venv/bin/python` 或 `make` 执行
- Git 仓库已初始化，可以直接 commit

### 新建文件的精确位置

本项目在以下路径创建**新文件/新目录**（这些目录目前不存在，需要创建）：

```
packages/judgment_schema/                    # 🆕 Sprint 1 新包
├── pyproject.toml
└── doramagic_judgment_schema/
    ├── __init__.py
    ├── types.py
    ├── validators.py
    ├── normalizer.py
    ├── serializer.py
    └── utils.py                             # 🆕 parse_llm_json 等通用工具

packages/judgment_pipeline/                  # 🆕 Sprint 2 新包
├── pyproject.toml
└── doramagic_judgment_pipeline/
    ├── __init__.py
    ├── source_adapters/
    │   ├── __init__.py
    │   ├── base.py
    │   └── github.py
    ├── extract/
    │   ├── __init__.py
    │   ├── filter.py
    │   ├── classifier.py
    │   └── extractor.py
    ├── refine/
    │   ├── __init__.py
    │   └── dedup.py
    ├── store/
    │   ├── __init__.py
    │   ├── ingester.py
    │   └── linker.py
    └── pipeline.py

packages/crystal_compiler/                   # 🆕 Sprint 3 新包
├── pyproject.toml
└── doramagic_crystal_compiler/
    ├── __init__.py
    ├── retrieve.py
    ├── compiler.py
    └── templates/
        └── base.yaml

tests/judgment_schema/                       # 🆕 Sprint 1 测试
├── __init__.py
├── test_types.py
├── test_validators.py
├── test_normalizer.py
└── test_serializer.py

tests/judgment_pipeline/                     # 🆕 Sprint 2 测试
└── __init__.py

tests/crystal_compiler/                      # 🆕 Sprint 3 测试
└── __init__.py

knowledge/judgments/domains/                 # 🆕 判断存储目录
knowledge/pipeline/raw_records/              # 🆕 流水线中间产物
knowledge/pipeline/gap_reports/              # 🆕 缺口报告
knowledge/pipeline/rejected.jsonl            # 🆕 被丢弃记录的审计日志

scripts/harvest.py                           # 🆕 Sprint 3 CLI 入口
```

### 需要修改的现有文件

除了新建文件，还必须修改以下**已有文件**（修改内容在后续章节 0.5、0.6 中有精确说明）：

| 文件 | 修改内容 |
|------|----------|
| `Makefile` | `PACKAGES_PATH` 追加 3 个新包路径 |
| `pyproject.toml`（根目录） | `[tool.hatch.build.targets.wheel]` 追加 3 个新包；`[[tool.mypy.overrides]]` 追加 3 个新包的类型检查配置 |

**除以上两个文件外，不修改任何现有文件。**

### Sprint 执行流程

每个 Sprint 严格按以下步骤执行：

```
1. 创建该 Sprint 的所有目录和 __init__.py
2. 逐个实现该 Sprint 的所有模块（按 spec 中的文件顺序）
3. 实现该 Sprint 的测试文件
4. 运行 make check（= make lint + make typecheck + make test）
5. 如果 make check 失败：
   a. 阅读错误信息
   b. 修复代码
   c. 重新运行 make check
   d. 重复直到全部通过（最多 5 轮修复，超过则停下来报告问题）
6. make check 全部通过后，git add 新建和修改的文件，git commit
   commit message 格式：feat(judgment): Sprint N — 简要描述
7. 进入下一个 Sprint
```

### 最终交付物

3 个 Sprint 全部完成后，项目根目录下应该能执行：

```bash
# 验证 Sprint 1：Schema 完整可用
PYTHONPATH=packages/judgment_schema .venv/bin/python -c "from doramagic_judgment_schema.types import Judgment; print('Schema OK')"

# 验证 Sprint 2+3：端到端流水线
PYTHONPATH=packages/judgment_schema:packages/judgment_pipeline:packages/crystal_compiler:packages/shared_utils \
  .venv/bin/python scripts/harvest.py

# 验证全局：lint + typecheck + test 全部通过
make check
```

---

## 〇、全局约束

### 0.1 运行环境

- **开发与运行机器**：macOS（Mac Mini M2/M4），本机就是知识工厂
- **Python 版本**：3.12（通过 `uv` 管理）
- **虚拟环境**：项目根目录 `.venv/`，已存在，由 `uv` 创建
- **包管理器**：`uv`（不使用 pip install），安装依赖统一用 `uv pip install -e "packages/xxx"`
- **本项目不是 uv workspace**：根 `pyproject.toml` 不包含 `[tool.uv.workspace]` 声明，每个子包通过 `uv pip install -e` 单独安装到 `.venv/`
- **测试运行方式**：`make test` 通过 `PYTHONPATH` 注入所有包路径（见 Makefile），不依赖 editable install 也能跑测试

### 0.2 环境变量（执行前必须设置）

| 变量名 | 用途 | 获取方式 |
|--------|------|----------|
| `GITHUB_TOKEN` | GitHub API 访问（采集 issue/PR） | GitHub Settings → Developer settings → Personal access tokens → 创建 classic token，权限勾选 `repo`（public_repo 足够） |
| `ANTHROPIC_API_KEY` | Sonnet 调用（分类、提取、关系建立） | Anthropic Console → API Keys |

**验证命令**（执行者开始前必须跑通）：

```bash
# 验证 GitHub Token
curl -s -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/rate_limit | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Rate limit: {d[\"rate\"][\"remaining\"]}/{d[\"rate\"][\"limit\"]}')"

# 验证 Anthropic Key
python3 -c "
import asyncio, sys
sys.path.insert(0, 'packages/shared_utils')
from doramagic_shared_utils.llm_adapter import LLMAdapter
adapter = LLMAdapter()
resp = asyncio.run(adapter.generate('claude-sonnet-4-20250514', [{'role':'user','content':'Say OK'}], system='Reply with one word.'))
print(f'LLM OK: {resp.text[:20]}')
"
```

### 0.3 LLMAdapter 能力边界（CRITICAL — 决定代码怎么写）

现有 `LLMAdapter` 提供三个方法，执行者必须只用这三个：

| 方法 | 签名 | 适用场景 |
|------|------|----------|
| `chat()` | `chat(messages, system=, temperature=, max_tokens=) → LLMResponse` | **同步**调用，内部桥接 async |
| `generate()` | `async generate(model_id, messages, *, system=, temperature=, max_tokens=) → LLMResponse` | **异步**调用，指定模型 |
| `generate_with_tools()` | `async generate_with_tools(model_id, messages, tools, *, system=, ...) → LLMResponse` | 工具调用（本项目不使用） |

**LLMResponse 结构**：`text: str`（文本内容）、`prompt_tokens: int`、`completion_tokens: int`

**⚠️ LLMAdapter 没有原生 JSON mode**。提取结构化数据的正确方式：
1. 在 `system` prompt 中要求 LLM 输出纯 JSON
2. 从 `response.text` 中手动 `json.loads()` 解析
3. 如果 LLM 返回了 markdown code fence（\`\`\`json ... \`\`\`），先用正则剥离再解析
4. 解析失败时记录 warning 并跳过该条，不要 crash

**正确的调用模式**：
```python
# ✅ 正确
adapter = LLMAdapter()
resp = await adapter.generate(
    "claude-sonnet-4-20250514",
    [{"role": "user", "content": prompt}],
    system="你是一个知识提取专家。请只输出 JSON，不要任何其他文字。",
    temperature=0.0,
    max_tokens=4096,
)
raw = resp.text.strip()
# 剥离 code fence
if raw.startswith("```"):
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
data = json.loads(raw)

# ❌ 错误 — LLMAdapter 没有 response_format 参数
resp = await adapter.generate(..., response_format={"type": "json_object"})
```

### 0.4 与现有 knowledge/ 目录的关系

项目已有知识目录结构：
```
knowledge/
├── bricks/          # 现有 50+ 个 JSONL 积木文件（旧体系，格式不同）
├── meta/            # 元数据
├── api_catalog/     # API 目录
├── INDEX.md
└── __init__.py
```

新判断系统的数据目录是 **独立且并行** 的：
```
knowledge/
├── bricks/          # 现有 — 不动、不读、不修改
├── judgments/        # 🆕 判断系统存储
│   └── domains/     # 按领域分 JSONL（如 finance.jsonl）
├── pipeline/        # 🆕 流水线中间产物
│   ├── raw_records/ # 原始采集记录（调试用，可清理）
│   └── gap_reports/ # 缺口报告
├── meta/            # 现有 — 不动
└── ...
```

**规则**：
- `knowledge/bricks/` 是旧积木体系，本项目**完全不碰**
- `knowledge/judgments/` 是新判断的唯一存储位置
- 两套系统物理隔离，未来可能有迁移脚本，但不在本 Sprint 范围

### 0.5 Makefile 与新包集成

现有 Makefile 的 `PACKAGES_PATH` 需要追加新包，否则 `make test` 找不到它们。

**执行者必须修改 `Makefile`**：

```makefile
# 在 PACKAGES_PATH 末尾追加三个新包
PACKAGES_PATH = packages/contracts:packages/extraction:packages/shared_utils:packages/community:packages/cross_project:packages/skill_compiler:packages/orchestration:packages/platform_openclaw:packages/domain_graph:packages/controller:packages/executors:packages/racekit:packages/evals:packages/preextract_api:packages/doramagic_product:packages/judgment_schema:packages/judgment_pipeline:packages/crystal_compiler
```

同时在根 `pyproject.toml` 的 `[tool.hatch.build.targets.wheel]` packages 列表追加：
```toml
    "packages/judgment_schema/doramagic_judgment_schema",
    "packages/judgment_pipeline/doramagic_judgment_pipeline",
    "packages/crystal_compiler/doramagic_crystal_compiler",
```

在 `[tool.ruff.lint.extend-per-file-ignores]` 中预注册新包的宽松规则（如有必要）。

### 0.6 mypy 配置

现有 mypy 只检查 `doramagic_contracts.*`。新包需要注册到 `pyproject.toml`：

```toml
[[tool.mypy.overrides]]
module = "doramagic_judgment_schema.*"
disallow_untyped_defs = true

[[tool.mypy.overrides]]
module = "doramagic_judgment_pipeline.*"
disallow_untyped_defs = true

[[tool.mypy.overrides]]
module = "doramagic_crystal_compiler.*"
disallow_untyped_defs = true
```

### 0.7 PostgreSQL 同步预留（本 Sprint 不实现，但必须预留接口）

本地 JSONL 是 Sprint 1-3 的唯一存储。但架构设计中，知识最终要同步到线上 PostgreSQL。

**预留方式**：`serializer.py` 中的 `JudgmentStore` 必须实现以下抽象：
```python
class JudgmentStoreProtocol(Protocol):
    """未来 PostgresJudgmentStore 将实现同一接口"""
    def store(self, judgment: Judgment) -> None: ...
    def get(self, judgment_id: str) -> Judgment | None: ...
    def list_by_domain(self, domain: str) -> list[Judgment]: ...
    def get_relations(self, judgment_id: str) -> list[Relation]: ...
    def count(self) -> int: ...
```

Sprint 1 的 `JudgmentStore`（JSONL 实现）必须满足此 Protocol，但**不需要**做成 ABC 继承。只需要方法签名匹配，未来 PostgreSQL 实现可以用 `isinstance()` 或 structural subtyping 对接。

### 0.8 异常处理策略（CRITICAL — 全自动执行下的安全网）

本项目所有模块必须遵守以下异常分级处理：

| 异常类型 | 处理策略 | 示例 |
|----------|----------|------|
| 环境缺失 | **fail-fast**，立即退出并报错 | GITHUB_TOKEN 未设置、store 路径不可写 |
| LLM 调用失败 | **记录 + 跳过当条**，继续处理下一条 | API 超时、rate limit |
| JSON 解析失败 | **记录 + 跳过当条**，继续处理下一条 | LLM 输出非 JSON |
| 校验不通过 | **记录到 rejected pool + 跳过**，不丢弃 | validate_judgment 返回 errors |
| 文件 I/O 错误 | **fail-fast**，立即退出 | 磁盘满、权限不足 |

**通用 JSON 解析工具函数**（所有 LLM 响应解析必须使用此函数）：

```python
# 放在 packages/judgment_schema/doramagic_judgment_schema/utils.py

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def parse_llm_json(raw_text: str) -> Any:
    """
    从 LLM 响应文本中安全提取 JSON。
    处理：纯 JSON、code fence 包裹、前后多余文字。
    返回解析后的 Python 对象，解析失败抛出 ValueError。
    """
    text = raw_text.strip()

    # 策略1：直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 策略2：提取 code fence 内的 JSON
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 策略3：找到第一个 [ 或 { 开始的子串
    for start_char, end_char in [("[", "]"), ("{", "}")]:
        start_idx = text.find(start_char)
        if start_idx >= 0:
            # 从后往前找对应的闭合括号
            end_idx = text.rfind(end_char)
            if end_idx > start_idx:
                try:
                    return json.loads(text[start_idx : end_idx + 1])
                except json.JSONDecodeError:
                    pass

    raise ValueError(f"无法从 LLM 响应中提取 JSON: {text[:200]}...")
```

**rejected pool 文件格式**（记录所有被丢弃的数据，供事后审计）：

```python
# 每条 rejected 记录追加到 knowledge/pipeline/rejected.jsonl
# 格式：{"timestamp": "...", "stage": "extract|validate|dedup", "reason": "...", "data": {...}}
```

### 0.9 幂等性设计

流水线必须支持重复执行同一批 Issue 而不产生重复数据：

1. **入库前查重**：`JudgmentStore.store()` 在写入前检查 `content_hash` 是否已存在，已存在则跳过
2. **Issue ID 追踪**：`JudgmentStore` 维护一个 `processed_issues.jsonl`，记录已处理的 `{source}:{source_id}`
3. **pipeline.py** 在 Fetch 阶段跳过已处理的 Issue

### 0.10 启动自检（CLI 入口的第一件事）

```python
def preflight_check() -> None:
    """启动前 fail-fast 检查。任何一项失败立即退出。"""
    import sys
    import os
    from pathlib import Path

    errors: list[str] = []

    # Python 版本
    if sys.version_info < (3, 12):
        errors.append(f"需要 Python >= 3.12，当前: {sys.version}")

    # 环境变量
    if not os.environ.get("GITHUB_TOKEN"):
        errors.append("GITHUB_TOKEN 环境变量未设置")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        errors.append("ANTHROPIC_API_KEY 环境变量未设置")

    # 存储路径可写
    store_path = Path("knowledge/judgments/domains")
    try:
        store_path.mkdir(parents=True, exist_ok=True)
        test_file = store_path / ".write_test"
        test_file.write_text("ok")
        test_file.unlink()
    except OSError as e:
        errors.append(f"存储路径不可写: {store_path} ({e})")

    if errors:
        for err in errors:
            print(f"[PREFLIGHT FAIL] {err}", file=sys.stderr)
        sys.exit(1)

    print("[PREFLIGHT] All checks passed.")
```

### 工程规范
- Python 3.12，包管理 uv + hatchling
- 所有 LLM 调用通过 `packages/shared_utils/doramagic_shared_utils/llm_adapter.py` 的 `LLMAdapter`
- 禁止直接 `import anthropic` 或 `import google.generativeai`
- 代码风格：ruff，类型检查：mypy，测试：pytest
- 提交前必须通过 `make check`（lint + typecheck + test）

### 新建的包

```
packages/
├── judgment_schema/          # Sprint 1
│   ├── pyproject.toml
│   └── doramagic_judgment_schema/
│       ├── __init__.py
│       ├── types.py          # Pydantic models
│       ├── validators.py     # 代码级校验
│       ├── normalizer.py     # 词汇归一化 + canonical signature
│       └── serializer.py     # JSONL 读写 + 索引维护
│
├── judgment_pipeline/        # Sprint 2
│   ├── pyproject.toml
│   └── doramagic_judgment_pipeline/
│       ├── __init__.py
│       ├── source_adapters/
│       │   ├── __init__.py
│       │   ├── base.py       # RawExperienceRecord + BaseAdapter
│       │   └── github.py     # GitHubAdapter
│       ├── extract/
│       │   ├── __init__.py
│       │   ├── filter.py     # 三轨预过滤器
│       │   ├── classifier.py # LLM 分类
│       │   └── extractor.py  # LLM 判断提取
│       ├── refine/
│       │   ├── __init__.py
│       │   ├── normalizer.py # canonical signature
│       │   ├── bucketer.py   # 分桶
│       │   └── dedup.py      # 强重复匹配
│       ├── store/
│       │   ├── __init__.py
│       │   ├── ingester.py   # JSONL 写入
│       │   ├── linker.py     # 关系自动建立
│       │   └── indexer.py    # 索引维护
│       └── pipeline.py       # 线性编排（Scout→Extract→Refine→Store）
│
├── crystal_compiler/         # Sprint 3
│   ├── pyproject.toml
│   └── doramagic_crystal_compiler/
│       ├── __init__.py
│       ├── retrieve.py       # 检索（直接匹配 + 1跳图谱 + 排序）
│       ├── compiler.py       # 判断集 → 晶体文本
│       └── templates/
│           └── base.yaml     # 晶体模板
```

### pyproject.toml 模板

```toml
# packages/judgment_schema/pyproject.toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "doramagic-judgment-schema"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "pydantic>=2.0",
    "doramagic-contracts",
]
```

```toml
# packages/judgment_pipeline/pyproject.toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "doramagic-judgment-pipeline"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "doramagic-judgment-schema",
    "doramagic-shared-utils",
    "httpx>=0.27",
]
```

```toml
# packages/crystal_compiler/pyproject.toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "doramagic-crystal-compiler"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "doramagic-judgment-schema",
    "doramagic-shared-utils",
]
```

---

## 一、Sprint 1：judgment_schema（地基）

### 1.1 types.py — Pydantic Models

将 `schema-synthesis.md` 中的 TypeScript Schema 翻译为 Pydantic v2 模型。以下是**精确定义**：

```python
"""Doramagic Judgment Schema v1.0 — Pydantic 实现"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ── 枚举 ──

class Layer(str, Enum):
    KNOWLEDGE = "knowledge"
    RESOURCE = "resource"
    EXPERIENCE = "experience"


class Modality(str, Enum):
    MUST = "must"
    MUST_NOT = "must_not"
    SHOULD = "should"
    SHOULD_NOT = "should_not"


class Severity(str, Enum):
    FATAL = "fatal"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ScopeLevel(str, Enum):
    UNIVERSAL = "universal"
    DOMAIN = "domain"
    CONTEXT = "context"


class Freshness(str, Enum):
    STABLE = "stable"          # 3年+ 不变
    SEMI_STABLE = "semi_stable"  # 6-18月
    VOLATILE = "volatile"      # <6月


class LifecycleStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    SUPERSEDED = "superseded"
    INVALIDATED = "invalidated"


class ConsequenceKind(str, Enum):
    BUG = "bug"
    PERFORMANCE = "performance"
    COMPLIANCE = "compliance"
    SAFETY = "safety"
    FINANCIAL_LOSS = "financial_loss"
    FALSE_CLAIM = "false_claim"
    OPERATIONAL_FAILURE = "operational_failure"
    DATA_CORRUPTION = "data_corruption"
    SERVICE_DISRUPTION = "service_disruption"


class SourceLevel(str, Enum):
    S1_SINGLE_PROJECT = "S1_single_project"
    S2_CROSS_PROJECT = "S2_cross_project"
    S3_COMMUNITY = "S3_community"
    S4_REASONING = "S4_reasoning"


class ConsensusLevel(str, Enum):
    UNIVERSAL = "universal"
    STRONG = "strong"
    MIXED = "mixed"
    CONTESTED = "contested"


class CrystalSection(str, Enum):
    WORLD_MODEL = "world_model"
    CONSTRAINTS = "constraints"
    RESOURCE_PROFILE = "resource_profile"
    ARCHITECTURE = "architecture"
    PROTOCOLS = "protocols"
    EVIDENCE = "evidence"


class RelationType(str, Enum):
    GENERATES = "generates"
    DEPENDS_ON = "depends_on"
    CONFLICTS = "conflicts"
    STRENGTHENS = "strengthens"
    SUPERSEDES = "supersedes"
    SUBSUMES = "subsumes"


class EvidenceRefType(str, Enum):
    SOURCE_CODE = "source_code"
    ISSUE = "issue"
    PULL_REQUEST = "pull_request"
    DISCUSSION = "discussion"
    BENCHMARK = "benchmark"
    PAPER = "paper"
    DOC = "doc"
    USER_FEEDBACK = "user_feedback"


# ── 子模型 ──

class Consequence(BaseModel):
    kind: ConsequenceKind
    description: str = Field(min_length=10)


class JudgmentCore(BaseModel):
    when: str = Field(min_length=5, description="触发条件")
    modality: Modality
    action: str = Field(min_length=5, description="具体行为")
    consequence: Consequence


class ContextRequires(BaseModel):
    resources: list[str] = Field(default_factory=list)
    markets: list[str] = Field(default_factory=list)
    task_types: list[str] = Field(default_factory=list)
    tech_stack: list[str] = Field(default_factory=list)
    environments: list[str] = Field(default_factory=list)
    target_versions: dict[str, str] = Field(default_factory=dict)


class JudgmentScope(BaseModel):
    level: ScopeLevel
    domains: list[str] = Field(min_length=1)
    context_requires: Optional[ContextRequires] = None


class EvidenceRef(BaseModel):
    type: EvidenceRefType
    source: str
    locator: Optional[str] = None
    summary: str


class JudgmentConfidence(BaseModel):
    source: SourceLevel
    score: float = Field(ge=0.0, le=1.0)
    consensus: ConsensusLevel
    verified_by: list[str] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)


class JudgmentCompilation(BaseModel):
    severity: Severity
    crystal_section: CrystalSection
    freshness: Freshness
    freshness_note: Optional[str] = None
    emit_as_hard_constraint: bool = False
    machine_checkable: bool = False
    validator_template: Optional[str] = None
    degradation_action: Optional[str] = None
    query_tags: list[str] = Field(default_factory=list)


class Relation(BaseModel):
    type: RelationType
    target_id: str
    description: str = Field(min_length=5, description="给编译器 LLM 的因果解释")


class JudgmentVersion(BaseModel):
    status: LifecycleStatus = LifecycleStatus.DRAFT
    created_at: str = Field(default_factory=lambda: datetime.now(tz=timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(tz=timezone.utc).isoformat())
    review_after_days: Optional[int] = None
    superseded_by: Optional[str] = None
    schema_version: str = "1.0"


class JudgmentExamples(BaseModel):
    positive: list[str] = Field(default_factory=list)
    negative: list[str] = Field(default_factory=list)


# ── 主模型 ──

class Judgment(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    # ID 格式: {domain}-{K|R|E}-{数字}
    # domain 允许小写字母、数字、连字符、下划线
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*-[KRE]-\d{3,}$")
    hash: str = ""
    core: JudgmentCore
    layer: Layer
    scope: JudgmentScope
    confidence: JudgmentConfidence
    compilation: JudgmentCompilation
    relations: list[Relation] = Field(default_factory=list)
    version: JudgmentVersion = Field(default_factory=JudgmentVersion)
    examples: Optional[JudgmentExamples] = None
    notes: Optional[str] = None

    def model_post_init(self, __context: object) -> None:
        """自动计算 content hash。"""
        if not self.hash:
            # mode='json' 确保 Enum 被序列化为字符串值，避免 TypeError
            content = json.dumps(
                {
                    "core": self.core.model_dump(mode="json"),
                    "scope": self.scope.model_dump(mode="json"),
                },
                sort_keys=True,
                ensure_ascii=False,
            )
            self.hash = hashlib.sha256(content.encode()).hexdigest()[:16]
```

### 1.2 validators.py — 代码级校验

```python
"""判断质量的代码级强制校验。不依赖 LLM，纯确定性。"""

from __future__ import annotations

from dataclasses import dataclass

from .types import Judgment, SourceLevel


# 中英文模糊词
VAGUE_WORDS_ZH = ["注意", "考虑", "适当", "合理", "尽量", "可能需要", "建议", "参考"]
VAGUE_WORDS_EN = [
    "consider", "be careful", "try to", "might need", "possibly",
    "appropriate", "reasonable", "should consider",
]
VAGUE_WORDS = VAGUE_WORDS_ZH + VAGUE_WORDS_EN

# 非原子性标志词
NON_ATOMIC_MARKERS_ZH = ["以及", "同时", "并且", "此外", "另外"]
NON_ATOMIC_MARKERS_EN = ["and also", "as well as", "in addition", "furthermore", "additionally"]
NON_ATOMIC_MARKERS = NON_ATOMIC_MARKERS_ZH + NON_ATOMIC_MARKERS_EN


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str]       # 致命问题，必须修复
    warnings: list[str]     # 建议修复


def validate_judgment(judgment: Judgment) -> ValidationResult:
    """完整校验一颗判断。返回结构化结果。"""
    errors: list[str] = []
    warnings: list[str] = []

    # === 三元组完整性 ===
    if not judgment.core.when.strip():
        errors.append("core.when 为空")
    if not judgment.core.action.strip():
        errors.append("core.action 为空")
    if not judgment.core.consequence.description.strip():
        errors.append("core.consequence.description 为空")

    # === 模糊词检测 ===
    action = judgment.core.action.lower()
    for word in VAGUE_WORDS:
        if word.lower() in action:
            errors.append(f"core.action 包含模糊词 '{word}'，需要更具体的行为描述")
            break

    # === 原子性检测 ===
    when_and_action = judgment.core.when + " " + judgment.core.action
    for marker in NON_ATOMIC_MARKERS:
        if marker in when_and_action:
            warnings.append(
                f"疑似非原子判断：'{marker}' 出现在 when/action 中。"
                f"考虑拆分为多颗判断。"
            )
            break

    # === 证据强制 ===
    if judgment.confidence.source != SourceLevel.S4_REASONING:
        if not judgment.confidence.evidence_refs:
            errors.append(
                "非 S4_reasoning 来源的判断必须有 evidence_refs。"
                "如果确实无法提供证据，请将 source 设为 S4_reasoning 并将 score 设为 < 0.6。"
            )
    else:
        if judgment.confidence.score >= 0.6:
            warnings.append(
                "S4_reasoning 来源的判断 confidence.score 应 < 0.6。"
                f"当前值: {judgment.confidence.score}"
            )

    # === when 复杂度 ===
    if len(judgment.core.when) > 100:
        warnings.append(
            f"core.when 过长（{len(judgment.core.when)} 字符），可能太复杂。"
            "考虑拆分或精简条件描述。"
        )

    # === action 具体性 ===
    if len(judgment.core.action) < 10:
        warnings.append(
            f"core.action 过短（{len(judgment.core.action)} 字符），可能太模糊。"
        )

    # === scope 一致性 ===
    if judgment.scope.level.value == "context" and not judgment.scope.context_requires:
        errors.append("scope.level 为 context 但缺少 context_requires")

    # === layer 与 source 一致性 ===
    if judgment.layer.value == "knowledge" and judgment.confidence.source == SourceLevel.S1_SINGLE_PROJECT:
        warnings.append(
            "knowledge 层判断通常不应来自单个项目。"
            "考虑验证是否有跨项目佐证。"
        )

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )
```

### 1.3 normalizer.py — 词汇归一化 + Canonical Signature

```python
"""将判断规范化为可比较的签名，用于确定性去重。"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .types import Judgment


# 词汇归一化字典
VOCABULARY_MAP: dict[str, str] = {
    # 浮点数相关
    "float": "binary_float",
    "double": "binary_float",
    "ieee 754": "binary_float",
    "浮点": "binary_float",
    "浮点数": "binary_float",
    # 精确数值
    "decimal": "exact_decimal",
    "bigdecimal": "exact_decimal",
    # 金融概念
    "pnl": "profit_and_loss",
    "p&l": "profit_and_loss",
    "盈亏": "profit_and_loss",
    "收益": "profit_and_loss",
    # 数据获取
    "yfinance": "yfinance_api",
    "yahoo finance": "yfinance_api",
    # 交易类型
    "实盘": "live_trading",
    "live trading": "live_trading",
    "回测": "backtest",
    "backtesting": "backtest",
    # 时间频率
    "日线": "daily_bar",
    "eod": "daily_bar",
    "end of day": "daily_bar",
    "实时": "realtime",
    "real-time": "realtime",
    "real time": "realtime",
}


def normalize_text(text: str) -> str:
    """对文本做词汇归一化。"""
    result = text.lower().strip()
    # 按长度降序替换（避免短词误替换长词的一部分）
    for original, normalized in sorted(VOCABULARY_MAP.items(), key=lambda x: -len(x[0])):
        result = result.replace(original.lower(), normalized)
    # 去除多余空格
    result = re.sub(r"\s+", " ", result)
    return result


@dataclass
class CanonicalSignature:
    scope_sig: str    # 归一化的 domains + resources + task_types
    rule_sig: str     # 归一化的 modality + action 核心动词/对象
    cause_sig: str    # 归一化的 consequence.kind + 关键实体


def compute_signature(judgment: Judgment) -> CanonicalSignature:
    """计算一颗判断的 canonical signature，用于确定性去重。"""

    # scope_sig: 领域 + 资源 + 任务类型
    scope_parts: list[str] = []
    scope_parts.extend(sorted(judgment.scope.domains))
    if judgment.scope.context_requires:
        scope_parts.extend(sorted(judgment.scope.context_requires.resources))
        scope_parts.extend(sorted(judgment.scope.context_requires.task_types))
    scope_sig = normalize_text("|".join(scope_parts))

    # rule_sig: modality + action 关键内容
    rule_sig = normalize_text(f"{judgment.core.modality.value}|{judgment.core.action}")

    # cause_sig: consequence 类型 + 描述中的关键实体
    cause_sig = normalize_text(
        f"{judgment.core.consequence.kind.value}|{judgment.core.consequence.description}"
    )

    return CanonicalSignature(
        scope_sig=scope_sig,
        rule_sig=rule_sig,
        cause_sig=cause_sig,
    )
```

### 1.4 serializer.py — JSONL 读写 + 索引

```python
"""JSONL 格式的判断持久化和索引维护。"""

from __future__ import annotations

import json
from pathlib import Path

from .types import Judgment, Relation


class JudgmentStore:
    """文件系统上的判断库。JSONL 存储 + 内存索引。"""

    def __init__(self, base_path: str | Path):
        self.base_path = Path(base_path)
        self.domains_dir = self.base_path / "domains"
        self.domains_dir.mkdir(parents=True, exist_ok=True)

        # 内存索引
        self._judgments: dict[str, Judgment] = {}  # id → Judgment
        self._domain_index: dict[str, list[str]] = {}  # domain → [ids]
        self._relation_graph: dict[str, list[Relation]] = {}  # id → [relations]

        # 初始化：加载已有数据
        self._load_all()

    def _load_all(self) -> None:
        """从 JSONL 文件加载所有判断到内存。"""
        for jsonl_file in self.domains_dir.glob("*.jsonl"):
            for line in jsonl_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                judgment = Judgment.model_validate_json(line)
                self._index(judgment)

        # 加载 universal
        universal_path = self.base_path / "universal.jsonl"
        if universal_path.exists():
            for line in universal_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                judgment = Judgment.model_validate_json(line)
                self._index(judgment)

    def _index(self, judgment: Judgment) -> None:
        """将判断加入内存索引。"""
        self._judgments[judgment.id] = judgment
        for domain in judgment.scope.domains:
            self._domain_index.setdefault(domain, []).append(judgment.id)
        self._relation_graph[judgment.id] = list(judgment.relations)

    def get(self, judgment_id: str) -> Judgment | None:
        return self._judgments.get(judgment_id)

    def list_by_domain(self, domain: str) -> list[Judgment]:
        ids = self._domain_index.get(domain, [])
        return [self._judgments[id_] for id_ in ids if id_ in self._judgments]

    def list_all(self) -> list[Judgment]:
        return list(self._judgments.values())

    def get_relations(self, judgment_id: str, max_hops: int = 2) -> list[Judgment]:
        """BFS 图谱扩展，返回 max_hops 跳内的所有相关判断。"""
        visited: set[str] = {judgment_id}
        frontier: set[str] = {judgment_id}
        result: list[Judgment] = []

        for _ in range(max_hops):
            next_frontier: set[str] = set()
            for current_id in frontier:
                for rel in self._relation_graph.get(current_id, []):
                    if rel.target_id not in visited:
                        visited.add(rel.target_id)
                        next_frontier.add(rel.target_id)
                        j = self._judgments.get(rel.target_id)
                        if j:
                            result.append(j)
            frontier = next_frontier
            if not frontier:
                break

        return result

    def store(self, judgment: Judgment) -> None:
        """写入一颗判断。追加到对应的 JSONL 文件 + 更新内存索引。"""
        # 确定文件路径
        primary_domain = judgment.scope.domains[0]
        if judgment.scope.level.value == "universal":
            file_path = self.base_path / "universal.jsonl"
        else:
            file_path = self.domains_dir / f"{primary_domain}.jsonl"

        # 追加写入
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(judgment.model_dump_json(exclude_none=True) + "\n")

        # 更新内存索引
        self._index(judgment)

    def count(self) -> int:
        return len(self._judgments)

    def count_by_domain(self) -> dict[str, int]:
        return {domain: len(ids) for domain, ids in self._domain_index.items()}

    def count_by_layer(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for j in self._judgments.values():
            result[j.layer.value] = result.get(j.layer.value, 0) + 1
        return result
```

### 1.5 测试用例 — tests/judgment_schema/

```python
# tests/judgment_schema/test_types.py

"""测试 Judgment Pydantic 模型的基本行为。"""

import pytest
from doramagic_judgment_schema.types import (
    Judgment, JudgmentCore, JudgmentScope, JudgmentConfidence,
    JudgmentCompilation, JudgmentVersion, Consequence, EvidenceRef,
    Layer, Modality, Severity, ScopeLevel, Freshness, SourceLevel,
    ConsensusLevel, CrystalSection, ConsequenceKind, EvidenceRefType,
)


def _make_valid_judgment(**overrides) -> Judgment:
    """工厂函数：创建一个完整合法的判断，可通过 overrides 覆盖任意字段。"""
    defaults = {
        "id": "finance-K-001",
        "core": JudgmentCore(
            when="进行金融计算（价格、资金、盈亏）时",
            modality=Modality.MUST_NOT,
            action="使用 IEEE 754 binary float 做算术运算",
            consequence=Consequence(
                kind=ConsequenceKind.FINANCIAL_LOSS,
                description="浮点累积误差导致 PnL 偏差，万次运算后偏差可达 0.01%-0.1%",
            ),
        ),
        "layer": Layer.KNOWLEDGE,
        "scope": JudgmentScope(
            level=ScopeLevel.DOMAIN,
            domains=["finance"],
        ),
        "confidence": JudgmentConfidence(
            source=SourceLevel.S2_CROSS_PROJECT,
            score=0.95,
            consensus=ConsensusLevel.STRONG,
            evidence_refs=[
                EvidenceRef(
                    type=EvidenceRefType.SOURCE_CODE,
                    source="freqtrade",
                    locator="https://github.com/freqtrade/freqtrade/blob/main/freqtrade/persistence/trade_model.py#L45",
                    summary="freqtrade 用 Decimal 处理所有交易金额",
                ),
            ],
        ),
        "compilation": JudgmentCompilation(
            severity=Severity.FATAL,
            crystal_section=CrystalSection.CONSTRAINTS,
            freshness=Freshness.STABLE,
            query_tags=["float", "precision", "decimal"],
        ),
    }
    defaults.update(overrides)
    return Judgment(**defaults)


class TestJudgmentCreation:
    def test_valid_judgment_creates_successfully(self):
        j = _make_valid_judgment()
        assert j.id == "finance-K-001"
        assert j.hash != ""  # auto-computed

    def test_hash_is_deterministic(self):
        j1 = _make_valid_judgment()
        j2 = _make_valid_judgment()
        assert j1.hash == j2.hash

    def test_hash_changes_with_content(self):
        j1 = _make_valid_judgment()
        j2 = _make_valid_judgment(
            core=JudgmentCore(
                when="不同的条件",
                modality=Modality.MUST,
                action="不同的行为描述内容",
                consequence=Consequence(kind=ConsequenceKind.BUG, description="不同的后果描述内容"),
            )
        )
        assert j1.hash != j2.hash

    def test_invalid_id_format_rejected(self):
        with pytest.raises(Exception):
            _make_valid_judgment(id="bad-format")

    def test_empty_domains_rejected(self):
        with pytest.raises(Exception):
            _make_valid_judgment(
                scope=JudgmentScope(level=ScopeLevel.DOMAIN, domains=[])
            )

    def test_confidence_score_out_of_range_rejected(self):
        with pytest.raises(Exception):
            _make_valid_judgment(
                confidence=JudgmentConfidence(
                    source=SourceLevel.S2_CROSS_PROJECT,
                    score=1.5,  # out of range
                    consensus=ConsensusLevel.STRONG,
                )
            )


# tests/judgment_schema/test_validators.py

"""测试判断质量校验器。"""

from doramagic_judgment_schema.types import (
    Judgment, JudgmentCore, JudgmentScope, JudgmentConfidence,
    JudgmentCompilation, Consequence,
    Layer, Modality, Severity, ScopeLevel, Freshness, SourceLevel,
    ConsensusLevel, CrystalSection, ConsequenceKind,
)
from doramagic_judgment_schema.validators import validate_judgment


# 复用上面的 _make_valid_judgment 工厂函数


class TestValidateJudgment:
    def test_valid_judgment_passes(self):
        j = _make_valid_judgment()
        result = validate_judgment(j)
        assert result.valid is True
        assert result.errors == []

    def test_vague_action_rejected(self):
        """action 中包含模糊词'注意'应产出错误。"""
        j = _make_valid_judgment(
            core=JudgmentCore(
                when="使用浮点数时",
                modality=Modality.SHOULD,
                action="注意精度问题可能导致的偏差",
                consequence=Consequence(kind=ConsequenceKind.BUG, description="精度偏差导致计算错误的结果"),
            )
        )
        result = validate_judgment(j)
        assert result.valid is False
        assert any("模糊词" in e for e in result.errors)

    def test_missing_evidence_rejected(self):
        """非 S4_reasoning 来源缺少 evidence_refs 应产出错误。"""
        j = _make_valid_judgment(
            confidence=JudgmentConfidence(
                source=SourceLevel.S3_COMMUNITY,
                score=0.8,
                consensus=ConsensusLevel.STRONG,
                evidence_refs=[],  # empty
            )
        )
        result = validate_judgment(j)
        assert result.valid is False
        assert any("evidence_refs" in e for e in result.errors)

    def test_s4_reasoning_high_score_warned(self):
        """S4_reasoning 来源 score >= 0.6 应产出警告。"""
        j = _make_valid_judgment(
            confidence=JudgmentConfidence(
                source=SourceLevel.S4_REASONING,
                score=0.8,
                consensus=ConsensusLevel.MIXED,
            )
        )
        result = validate_judgment(j)
        assert result.valid is True  # warning, not error
        assert len(result.warnings) > 0

    def test_non_atomic_warned(self):
        """when 中包含'以及'应产出非原子警告。"""
        j = _make_valid_judgment(
            core=JudgmentCore(
                when="处理价格数据以及计算仓位比例时",
                modality=Modality.MUST_NOT,
                action="使用 float 类型做算术运算",
                consequence=Consequence(kind=ConsequenceKind.FINANCIAL_LOSS, description="精度偏差导致资金计算错误"),
            )
        )
        result = validate_judgment(j)
        assert any("非原子" in w for w in result.warnings)

    def test_context_scope_without_context_requires_rejected(self):
        """scope.level=context 但缺少 context_requires 应产出错误。"""
        j = _make_valid_judgment(
            scope=JudgmentScope(
                level=ScopeLevel.CONTEXT,
                domains=["finance"],
                context_requires=None,
            )
        )
        result = validate_judgment(j)
        assert result.valid is False


# tests/judgment_schema/test_normalizer.py

"""测试词汇归一化和 canonical signature。"""

from doramagic_judgment_schema.normalizer import normalize_text, compute_signature


class TestNormalizeText:
    def test_float_normalization(self):
        assert "binary_float" in normalize_text("使用 float 类型")
        assert "binary_float" in normalize_text("IEEE 754 double 精度")

    def test_trading_normalization(self):
        assert "live_trading" in normalize_text("实盘交易")
        assert "backtest" in normalize_text("回测系统")

    def test_case_insensitive(self):
        assert normalize_text("Float") == normalize_text("float")


class TestCanonicalSignature:
    def test_same_judgment_same_signature(self):
        j = _make_valid_judgment()
        sig1 = compute_signature(j)
        sig2 = compute_signature(j)
        assert sig1.scope_sig == sig2.scope_sig
        assert sig1.rule_sig == sig2.rule_sig
        assert sig1.cause_sig == sig2.cause_sig

    def test_different_domain_different_scope_sig(self):
        j1 = _make_valid_judgment()
        j2 = _make_valid_judgment(
            scope=JudgmentScope(level=ScopeLevel.DOMAIN, domains=["healthcare"])
        )
        sig1 = compute_signature(j1)
        sig2 = compute_signature(j2)
        assert sig1.scope_sig != sig2.scope_sig


# tests/judgment_schema/test_serializer.py

"""测试 JSONL 读写和索引。"""

import tempfile
from pathlib import Path

from doramagic_judgment_schema.serializer import JudgmentStore


class TestJudgmentStore:
    def test_store_and_retrieve(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JudgmentStore(tmpdir)
            j = _make_valid_judgment()
            store.store(j)
            assert store.count() == 1
            assert store.get("finance-K-001") is not None

    def test_list_by_domain(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JudgmentStore(tmpdir)
            store.store(_make_valid_judgment(id="finance-K-001"))
            store.store(_make_valid_judgment(
                id="finance-K-002",
                core=JudgmentCore(
                    when="进行回测时的不同条件",
                    modality=Modality.SHOULD,
                    action="使用 Decimal 类型处理所有金额",
                    consequence=Consequence(kind=ConsequenceKind.BUG, description="避免精度累积偏差导致回测结果不可复现"),
                )
            ))
            results = store.list_by_domain("finance")
            assert len(results) == 2

    def test_persistence_across_instances(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store1 = JudgmentStore(tmpdir)
            store1.store(_make_valid_judgment())
            del store1

            store2 = JudgmentStore(tmpdir)
            assert store2.count() == 1

    def test_graph_expansion(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from doramagic_judgment_schema.types import Relation, RelationType
            store = JudgmentStore(tmpdir)

            j1 = _make_valid_judgment(
                id="finance-K-001",
                relations=[Relation(
                    type=RelationType.GENERATES,
                    target_id="finance-R-001",
                    description="精度约束导致必须选择支持 Decimal 的数据管道",
                )],
            )
            j2 = _make_valid_judgment(
                id="finance-R-001",
                layer=Layer.RESOURCE,
            )
            store.store(j1)
            store.store(j2)

            related = store.get_relations("finance-K-001", max_hops=1)
            assert len(related) == 1
            assert related[0].id == "finance-R-001"
```

---

## 二、Sprint 2：judgment_pipeline（采集流水线）

### 2.1 source_adapters/base.py

```python
"""所有来源适配器的统一输出格式。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RawExperienceRecord:
    """所有来源适配器的统一输出格式。"""
    # 来源标识
    source_type: str          # "github_issue" | "reddit_post" | "discord_message" | ...
    source_id: str            # 来源内唯一 ID
    source_url: str           # 原始 URL
    source_platform: str      # "github" | "reddit" | "discord" | ...
    project_or_community: str # "freqtrade" | "r/algotrading" | ...

    # 内容
    title: str
    body: str
    replies: list[str] = field(default_factory=list)
    code_blocks: list[str] = field(default_factory=list)

    # 质量信号（各来源适配器负责映射为标准信号）
    signals: dict = field(default_factory=dict)

    # 时间
    created_at: str = ""
    resolved_at: str | None = None

    # 分类
    pre_category: str | None = None  # "bug" | "incident" | "workaround" | "design_boundary" | "discussion"


class BaseAdapter(ABC):
    """来源适配器基类。"""

    @abstractmethod
    async def fetch(self, target: dict) -> list[RawExperienceRecord]:
        """
        根据 target 配置拉取数据。
        target 示例: {"owner": "freqtrade", "repo": "freqtrade", "labels": ["bug"], "min_comments": 3}
        """
        ...
```

### 2.2 source_adapters/github.py

```python
"""GitHub Issues/PRs 适配器。"""

from __future__ import annotations

import httpx

from .base import BaseAdapter, RawExperienceRecord


class GitHubAdapter(BaseAdapter):
    """从 GitHub 拉取 Issues/PRs 并转换为 RawExperienceRecord。"""

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
            "state": "closed",          # "open" | "closed" | "all"
            "labels": "bug",            # 可选，逗号分隔
            "min_comments": 3,          # 可选，过滤评论数
            "since": "2024-01-01",      # 可选，ISO8601
            "max_pages": 5,             # 可选，最多拉取页数（每页 100）
        }
        """
        owner = target["owner"]
        repo = target["repo"]
        records: list[RawExperienceRecord] = []

        issues = await self._fetch_issues(owner, repo, target)

        for issue in issues:
            # 跳过 PR（GitHub API 中 PR 也在 issues 里）
            if "pull_request" in issue:
                continue

            # 过滤评论数
            min_comments = target.get("min_comments", 0)
            if issue.get("comments", 0) < min_comments:
                continue

            # 拉取评论
            comments = await self._fetch_comments(owner, repo, issue["number"])

            # 检查是否有关联的 merged PR
            linked_pr_merged = await self._check_linked_pr(owner, repo, issue["number"])

            # 提取代码块
            code_blocks = self._extract_code_blocks(issue.get("body", "") or "")
            for comment in comments:
                code_blocks.extend(self._extract_code_blocks(comment.get("body", "") or ""))

            # 构建标准信号
            labels = [l["name"] for l in issue.get("labels", [])]
            signals = {
                # 轨道一信号
                "has_code_fix": linked_pr_merged,
                # 轨道二信号
                "is_design_boundary": any(
                    l in labels
                    for l in ["wontfix", "works-as-intended", "known-issue", "by-design", "won't fix"]
                ),
                # 轨道三信号
                "has_official_resolution": issue.get("state") == "closed",
                "approval_score": issue.get("reactions", {}).get("total_count", 0),
                "reply_count": issue.get("comments", 0),
                "has_repro_steps": self._has_repro_steps(issue.get("body", "") or ""),
                "has_logs_or_evidence": self._has_logs(issue.get("body", "") or ""),
                "author_credibility": self._author_credibility(issue, owner, repo),
                "expert_reply": self._has_maintainer_reply(comments, owner, repo),
                "body_length": len(issue.get("body", "") or ""),
                "contains_code": len(code_blocks) > 0,
                "labels": labels,
            }

            # 预分类
            pre_category = self._pre_classify(labels, signals)

            records.append(RawExperienceRecord(
                source_type="github_issue",
                source_id=str(issue["number"]),
                source_url=issue["html_url"],
                source_platform="github",
                project_or_community=f"{owner}/{repo}",
                title=issue.get("title", ""),
                body=issue.get("body", "") or "",
                replies=[c.get("body", "") or "" for c in comments],
                code_blocks=code_blocks,
                signals=signals,
                created_at=issue.get("created_at", ""),
                resolved_at=issue.get("closed_at"),
                pre_category=pre_category,
            ))

        return records

    async def _fetch_issues(self, owner: str, repo: str, target: dict) -> list[dict]:
        """分页拉取 Issues。"""
        all_issues: list[dict] = []
        max_pages = target.get("max_pages", 5)

        async with httpx.AsyncClient(headers=self.headers, timeout=30) as client:
            for page in range(1, max_pages + 1):
                params: dict = {
                    "state": target.get("state", "closed"),
                    "per_page": 100,
                    "page": page,
                    "sort": "comments",
                    "direction": "desc",
                }
                if target.get("labels"):
                    params["labels"] = target["labels"]
                if target.get("since"):
                    params["since"] = target["since"]

                resp = await client.get(
                    f"{self.base_url}/repos/{owner}/{repo}/issues",
                    params=params,
                )
                resp.raise_for_status()
                issues = resp.json()

                if not issues:
                    break
                all_issues.extend(issues)

        return all_issues

    async def _fetch_comments(self, owner: str, repo: str, issue_number: int) -> list[dict]:
        """拉取单个 Issue 的所有评论。"""
        async with httpx.AsyncClient(headers=self.headers, timeout=30) as client:
            resp = await client.get(
                f"{self.base_url}/repos/{owner}/{repo}/issues/{issue_number}/comments",
                params={"per_page": 100},
            )
            resp.raise_for_status()
            return resp.json()

    async def _check_linked_pr(self, owner: str, repo: str, issue_number: int) -> bool:
        """检查 Issue 是否有关联的 merged PR。通过 timeline events API。"""
        async with httpx.AsyncClient(headers=self.headers, timeout=30) as client:
            resp = await client.get(
                f"{self.base_url}/repos/{owner}/{repo}/issues/{issue_number}/timeline",
                headers={**self.headers, "Accept": "application/vnd.github.mockingbird-preview+json"},
                params={"per_page": 100},
            )
            if resp.status_code != 200:
                return False
            events = resp.json()
            for event in events:
                if event.get("event") == "cross-referenced":
                    source = event.get("source", {}).get("issue", {})
                    if source.get("pull_request") and source.get("state") == "closed":
                        # 检查 PR 是否 merged
                        pr_url = source["pull_request"].get("url", "")
                        if pr_url:
                            pr_resp = await client.get(pr_url, headers=self.headers)
                            if pr_resp.status_code == 200 and pr_resp.json().get("merged"):
                                return True
            return False

    @staticmethod
    def _extract_code_blocks(text: str) -> list[str]:
        """从 markdown 中提取 ``` 代码块。"""
        import re
        return re.findall(r"```[\w]*\n(.*?)```", text, re.DOTALL)

    @staticmethod
    def _has_repro_steps(body: str) -> bool:
        """检查是否包含复现步骤。"""
        markers = ["steps to reproduce", "how to reproduce", "reproduction",
                    "expected behavior", "actual behavior", "复现步骤", "预期行为", "实际行为"]
        body_lower = body.lower()
        return any(m in body_lower for m in markers)

    @staticmethod
    def _has_logs(body: str) -> bool:
        """检查是否包含日志/堆栈信息。"""
        markers = ["traceback", "exception", "error:", "stacktrace",
                    "at line", "file \"", "stderr", "stdout"]
        body_lower = body.lower()
        return any(m in body_lower for m in markers)

    @staticmethod
    def _author_credibility(issue: dict, owner: str, repo: str) -> float:
        """粗略评估作者可信度。"""
        author = issue.get("user", {})
        if author.get("login") == owner:
            return 1.0  # 项目所有者
        association = issue.get("author_association", "")
        if association in ("OWNER", "MEMBER", "COLLABORATOR"):
            return 0.9
        if association == "CONTRIBUTOR":
            return 0.7
        return 0.3

    @staticmethod
    def _has_maintainer_reply(comments: list[dict], owner: str, repo: str) -> bool:
        """检查是否有维护者回复。"""
        for comment in comments:
            association = comment.get("author_association", "")
            if association in ("OWNER", "MEMBER", "COLLABORATOR"):
                return True
        return False

    @staticmethod
    def _pre_classify(labels: list[str], signals: dict) -> str | None:
        """基于标签的粗分类。"""
        label_set = {l.lower() for l in labels}
        if label_set & {"wontfix", "works-as-intended", "known-issue", "by-design", "won't fix"}:
            return "design_boundary"
        if label_set & {"bug", "regression", "defect"}:
            return "bug"
        if label_set & {"security", "vulnerability"}:
            return "incident"
        return None
```

### 2.3 extract/filter.py — 三轨预过滤器

```python
"""三轨预过滤器。确定性，不用 LLM。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..source_adapters.base import RawExperienceRecord


class FilterTrack(str, Enum):
    TRACK_1_CODE_EVIDENCE = "track_1"   # 代码共证
    TRACK_2_DESIGN_BOUNDARY = "track_2"  # 边界妥协
    TRACK_3_SIGNAL_SCORE = "track_3"    # 信号打分
    REJECTED = "rejected"


@dataclass
class FilterResult:
    record: RawExperienceRecord
    track: FilterTrack
    score: float  # 轨道三的得分，轨道一/二为 0
    reason: str


def filter_records(records: list[RawExperienceRecord]) -> list[FilterResult]:
    """对所有记录执行三轨过滤，返回通过的记录及其轨道归属。"""
    results: list[FilterResult] = []

    for record in records:
        signals = record.signals

        # 轨道一：代码共证（需同时有技术失败信号，避免收录 typo/doc fix）
        if signals.get("has_code_fix"):
            labels = {l.lower() for l in signals.get("labels", [])}
            has_failure_signal = (
                labels & {"bug", "regression", "incident", "data-issue"}
                or signals.get("has_repro_steps")
                or signals.get("has_logs_or_evidence")
                or signals.get("body_length", 0) >= 80
            )
            if has_failure_signal:
                results.append(FilterResult(
                    record=record,
                    track=FilterTrack.TRACK_1_CODE_EVIDENCE,
                    score=0,
                    reason="Issue 已关闭且关联 merged PR + 有技术失败信号",
                ))
                continue

        # 轨道二：边界妥协（取消 body_length 硬门槛，改为更灵活的判定）
        if signals.get("is_design_boundary"):
            results.append(FilterResult(
                record=record,
                track=FilterTrack.TRACK_2_DESIGN_BOUNDARY,
                score=0,
                reason=f"设计边界标签 + body_length={signals.get('body_length', 0)}",
            ))
            continue

        # 轨道三：信号打分
        score = _compute_signal_score(signals)
        threshold = _get_threshold(record, signals)

        if score >= threshold:
            results.append(FilterResult(
                record=record,
                track=FilterTrack.TRACK_3_SIGNAL_SCORE,
                score=score,
                reason=f"信号得分 {score:.1f} >= 阈值 {threshold}",
            ))
        else:
            results.append(FilterResult(
                record=record,
                track=FilterTrack.REJECTED,
                score=score,
                reason=f"信号得分 {score:.1f} < 阈值 {threshold}",
            ))

    return results


def _compute_signal_score(signals: dict) -> float:
    """轨道三的加权打分。"""
    score = 0.0

    if signals.get("has_repro_steps"):
        score += 2.5
    if signals.get("expert_reply"):
        score += 2.0
    if signals.get("has_logs_or_evidence"):
        score += 1.5

    labels = {l.lower() for l in signals.get("labels", [])}
    if labels & {"bug", "regression", "incident", "data-issue"}:
        score += 1.5

    # 设计边界信号在轨道三也有补偿分（轨道二可能因其他条件未命中）
    if signals.get("is_design_boundary"):
        score += 2.0

    # maintainer 关闭并给出解释
    if signals.get("closed_by_maintainer"):
        score += 1.0

    approval = signals.get("approval_score", 0)  # reactions / thumbs-up 总数
    if approval >= 3:
        score += 1.0

    reply_count = signals.get("reply_count", 0)
    if reply_count >= 3:
        score += 0.5

    body_length = signals.get("body_length", 0)
    if body_length >= 120:
        score += 0.5

    # 减分（更温和：-1.5 而非 -2.0，避免误伤带有技术信号的 feature request）
    if labels & {"feature", "enhancement", "feature-request"} and not signals.get("has_logs_or_evidence"):
        score -= 1.5
    if labels & {"question"} and not signals.get("has_repro_steps"):
        score -= 1.5

    return score


def _get_threshold(record: RawExperienceRecord, signals: dict) -> float:
    """根据类型动态调整阈值。"""
    labels = {l.lower() for l in signals.get("labels", [])}
    if labels & {"bug", "regression", "incident"}:
        return 3.0
    if record.pre_category == "bug":
        return 3.0
    if record.pre_category in ("workaround", "anti_pattern"):
        return 3.0
    if labels & {"discussion"}:
        return 3.5  # 降低：高价值维护者讨论不应被卡住
    return 4.5  # 降低：从 5.0 调到 4.5，减少误杀
```

### 2.4 extract/classifier.py — LLM 分类

```python
"""用轻量 LLM 对通过过滤的记录做精细分类。"""

from __future__ import annotations

from doramagic_shared_utils.llm_adapter import LLMAdapter, LLMMessage

from ..source_adapters.base import RawExperienceRecord

CLASSIFICATION_SYSTEM_PROMPT = """你是一个 GitHub Issue 分类专家。根据 Issue 的标题、正文和评论，将它分为以下类别之一：

- bug_confirmed: 被代码修复证实的 bug（有关联的 merged PR 或明确的修复方案）
- design_boundary: 框架设计边界/已知限制（维护者明确表示"这是预期行为"或"不会修复"）
- incident: 生产事故或严重故障报告
- workaround: 社区提出的绕过方案（不是官方修复，是用户自己的应对策略）
- anti_pattern: 社区警告不要这么做的实践
- low_value: 不包含可操作经验的讨论（纯功能请求、重复问题、信息不足）

你只需要返回一个 JSON 对象：{"category": "类别名", "reason": "一句话理由"}
不要返回其他内容。"""


CLASSIFICATION_USER_TEMPLATE = """Issue #{source_id}: {title}

正文:
{body_truncated}

评论摘要（前3条）:
{replies_truncated}

信号: has_code_fix={has_code_fix}, is_design_boundary={is_design_boundary}, reply_count={reply_count}
"""


async def classify_record(
    record: RawExperienceRecord,
    adapter: LLMAdapter,
    model: str = "sonnet",
) -> tuple[str, str]:
    """
    分类一条记录。返回 (category, reason)。
    category 是上述 6 种之一。
    """
    body_truncated = record.body[:1500] if len(record.body) > 1500 else record.body
    replies_truncated = "\n---\n".join(r[:500] for r in record.replies[:3])

    user_content = CLASSIFICATION_USER_TEMPLATE.format(
        source_id=record.source_id,
        title=record.title,
        body_truncated=body_truncated,
        replies_truncated=replies_truncated,
        has_code_fix=record.signals.get("has_code_fix", False),
        is_design_boundary=record.signals.get("is_design_boundary", False),
        reply_count=record.signals.get("reply_count", 0),
    )

    response = adapter.chat(
        messages=[LLMMessage(role="user", content=user_content)],
        system=CLASSIFICATION_SYSTEM_PROMPT,
        temperature=0.0,
        max_tokens=200,
    )

    from doramagic_judgment_schema.utils import parse_llm_json

    VALID_CATEGORIES = {"bug_confirmed", "design_boundary", "incident", "workaround", "anti_pattern", "low_value"}

    try:
        result = parse_llm_json(response.text)
        category = result.get("category", "low_value")
        if category not in VALID_CATEGORIES:
            category = "low_value"
        return category, result.get("reason", "")
    except (ValueError, AttributeError):
        return "low_value", "分类失败：LLM 返回格式错误"
```

### 2.5 extract/extractor.py — LLM 判断提取

```python
"""从分类后的记录中提取判断三元组。核心环节。"""

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


EXTRACTION_SYSTEM_PROMPT = """你是 Doramagic 的判断提取专家。你的任务是从 GitHub Issue 讨论中提取可操作的判断（Judgment）。

每颗判断必须严格遵循三元组格式：
  当 [具体条件] 时，必须/禁止 [具体行为]，否则 [可量化后果]。

约束（违反任何一条你的输出将被代码级拒绝）：
1. [条件] 必须具体到一个工作场景，不能是"开发时"这种泛泛之词
2. [行为] 必须是一个可执行指令，不能是"注意安全"这种建议
3. [后果] 必须包含可量化的影响或具体的失败表现
4. 如果无法量化后果，写明"后果程度未知，需实验验证"并建议 confidence_score < 0.6
5. 一颗判断只说一件事。如果你发现两件事，拆成两颗
6. action 中不允许出现：注意、考虑、适当、合理、尽量、可能需要
7. 区分"这个项目特有的坑"（experience 层）和"这个领域通用的坑"（knowledge 层）

输出格式：只输出一个 JSON 数组，不要添加任何解释文字。每个元素：
{
  "when": "触发条件",
  "modality": "must" | "must_not" | "should" | "should_not",
  "action": "具体行为",
  "consequence_kind": "bug" | "performance" | "data_corruption" | "service_disruption" | "financial_loss" | "operational_failure" | "compliance" | "safety" | "false_claim",
  "consequence_description": "后果描述",
  "layer": "knowledge" | "resource" | "experience",
  "severity": "fatal" | "high" | "medium" | "low",
  "confidence_score": 0.0-1.0,
  "crystal_section": "constraints" | "world_model" | "resource_profile" | "architecture" | "protocols" | "evidence",
  "evidence_summary": "引用 Issue 中的具体证据"
}

crystal_section 选择指南：
- constraints: 必须/禁止的行为规则（大多数判断属于这里）
- world_model: 关于系统/领域如何运作的事实性认知
- resource_profile: API 限制、配额、延迟、成本等资源边界
- architecture: 架构模式或反模式
- protocols: 操作步骤、最佳实践流程
- evidence: 纯证据/数据点（benchmark 结果、事故报告数据）

如果 Issue 中没有可提取的判断，返回空数组 []。
不要编造 Issue 中没有提到的信息。
最多提取 5 颗判断，优先提取 severity 最高的。"""


# 正反样例，提高提取质量
EXTRACTION_FEW_SHOT = """
示例 — 好的提取（会通过校验）：
{"when": "使用 yfinance 获取 A 股日线数据进行回测时", "modality": "must_not", "action": "直接使用 close 字段作为真实收盘价，必须使用 adj_close 字段", "consequence_kind": "data_corruption", "consequence_description": "未复权价格会导致回测收益率偏差超过 30%，在长周期策略中表现为虚假盈利", "layer": "knowledge", "severity": "high", "confidence_score": 0.85, "crystal_section": "constraints", "evidence_summary": "Issue #142 中用户展示了 3 年回测中未复权与复权价格的收益率对比图"}

示例 — 会被拒绝的提取（模糊词 + 不可量化）：
{"when": "开发时", "modality": "should", "action": "注意数据质量", "consequence_kind": "bug", "consequence_description": "可能出问题", ...}
↑ 被拒绝原因：when 太笼统、action 包含"注意"、后果不具体
"""


EXTRACTION_USER_TEMPLATE = """Issue #{source_id}: {title}
项目: {project}
分类: {category}（分类信号，供你参考判断提取方向）
URL: {url}

正文:
{body}

评论（按时间排序）:
{replies}

请从以上讨论中提取判断。"""


# 分类到 scope_level 的映射
CATEGORY_TO_SCOPE: dict[str, ScopeLevel] = {
    "bug_confirmed": ScopeLevel.CONTEXT,
    "design_boundary": ScopeLevel.DOMAIN,
    "incident": ScopeLevel.CONTEXT,
    "workaround": ScopeLevel.CONTEXT,
    "anti_pattern": ScopeLevel.DOMAIN,
}

# 分类到 crystal_section 的默认映射（LLM 输出优先）
CATEGORY_TO_SECTION: dict[str, CrystalSection] = {
    "bug_confirmed": CrystalSection.CONSTRAINTS,
    "design_boundary": CrystalSection.WORLD_MODEL,
    "incident": CrystalSection.EVIDENCE,
    "workaround": CrystalSection.PROTOCOLS,
    "anti_pattern": CrystalSection.CONSTRAINTS,
}


async def extract_judgments(
    record: RawExperienceRecord,
    category: str,
    adapter: LLMAdapter,
    domain: str,
    model: str = "sonnet",
    id_counter: int = 1,
) -> list[Judgment]:
    """
    从一条记录中提取判断。
    返回通过校验的 Judgment 列表。
    校验失败的记录写入 rejected pool（由调用方负责）。
    """
    user_content = EXTRACTION_USER_TEMPLATE.format(
        source_id=record.source_id,
        title=record.title,
        project=record.project_or_community,
        category=category,
        url=record.source_url,
        body=record.body[:3000],
        replies="\n---\n".join(record.replies[:10]),
    )

    response = adapter.chat(
        messages=[LLMMessage(role="user", content=EXTRACTION_FEW_SHOT + "\n\n" + user_content)],
        system=EXTRACTION_SYSTEM_PROMPT,
        temperature=0.0,
        max_tokens=3000,
    )

    try:
        raw_judgments = parse_llm_json(response.text)
    except ValueError as e:
        logger.warning("LLM 输出无法解析为 JSON: %s (record=%s)", e, record.source_id)
        return []

    if not isinstance(raw_judgments, list):
        logger.warning("LLM 输出不是数组: type=%s (record=%s)", type(raw_judgments), record.source_id)
        return []

    results: list[Judgment] = []
    rejected: list[dict] = []

    for i, raw_item in enumerate(raw_judgments):
        try:
            # 安全获取字段，缺失时用默认值
            layer_str = raw_item.get("layer", "experience")
            layer_initial = layer_str[0].upper() if layer_str else "E"

            # crystal_section: LLM 输出优先，否则用分类映射
            section_str = raw_item.get("crystal_section", "")
            try:
                crystal_section = CrystalSection(section_str)
            except ValueError:
                crystal_section = CATEGORY_TO_SECTION.get(category, CrystalSection.CONSTRAINTS)

            # scope_level: 根据分类动态决定
            scope_level = CATEGORY_TO_SCOPE.get(category, ScopeLevel.DOMAIN)

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
                    level=scope_level,
                    domains=[domain],
                ),
                confidence=JudgmentConfidence(
                    source=SourceLevel.S3_COMMUNITY,
                    score=raw_item.get("confidence_score", 0.7),
                    consensus=ConsensusLevel.MIXED,
                    evidence_refs=[
                        EvidenceRef(
                            type=EvidenceRefType.ISSUE,
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

            # 代码级校验
            validation = validate_judgment(judgment)
            if validation.valid:
                results.append(judgment)
            else:
                logger.info("判断校验失败: id=%s errors=%s", judgment.id, validation.errors)
                rejected.append({
                    "stage": "validate",
                    "judgment_id": judgment.id,
                    "errors": validation.errors,
                    "raw": raw_item,
                })

        except (KeyError, ValueError, TypeError) as e:
            logger.warning("构造 Judgment 失败: %s (record=%s, item=%d)", e, record.source_id, i)
            rejected.append({
                "stage": "construct",
                "error": str(e),
                "raw": raw_item,
            })
            continue

    # rejected pool 由 pipeline 层统一写入 knowledge/pipeline/rejected.jsonl
    if rejected:
        logger.info("本次提取 rejected %d 条 (record=%s)", len(rejected), record.source_id)

    return results
```

### 2.6 refine/dedup.py — 简化版去重（Sprint 2 范围）

```python
"""去重流水线。Sprint 2 实现前两步（规范化 + 分桶 + 强重复匹配）。"""

from __future__ import annotations

from dataclasses import dataclass

from doramagic_judgment_schema.types import Judgment
from doramagic_judgment_schema.normalizer import compute_signature, CanonicalSignature


@dataclass
class DedupResult:
    unique: list[Judgment]          # 去重后的判断
    duplicates: list[tuple[str, str, str]]  # (保留id, 重复id, 原因)


def dedup_judgments(judgments: list[Judgment]) -> DedupResult:
    """
    对判断列表执行去重。
    Step 1: 计算 canonical signature
    Step 2: 按 scope_sig 分桶
    Step 3: 桶内强重复匹配
    """
    # Step 1: 计算签名
    sigs: dict[str, CanonicalSignature] = {}
    for j in judgments:
        sigs[j.id] = compute_signature(j)

    # Step 2: 分桶
    buckets: dict[str, list[Judgment]] = {}
    for j in judgments:
        bucket_key = sigs[j.id].scope_sig
        buckets.setdefault(bucket_key, []).append(j)

    # Step 3: 桶内强重复匹配
    unique: list[Judgment] = []
    duplicates: list[tuple[str, str, str]] = []
    seen_rule_sigs: dict[str, str] = {}  # bucket+rule_sig → first judgment id

    for bucket_key, bucket_judgments in buckets.items():
        for j in bucket_judgments:
            sig = sigs[j.id]
            composite_key = f"{bucket_key}||{sig.rule_sig}"

            if composite_key in seen_rule_sigs:
                # 强重复：同桶 + 同 rule_sig
                duplicates.append((
                    seen_rule_sigs[composite_key],
                    j.id,
                    f"强重复：rule_sig 一致（桶 {bucket_key}）",
                ))
            else:
                # 检查 cause_sig 一致（同一根因 = 同一判断）
                cause_key = f"{bucket_key}||{sig.cause_sig}"
                if cause_key in seen_rule_sigs:
                    duplicates.append((
                        seen_rule_sigs[cause_key],
                        j.id,
                        f"根因重复：cause_sig 一致（桶 {bucket_key}）",
                    ))
                else:
                    seen_rule_sigs[composite_key] = j.id
                    seen_rule_sigs[f"{bucket_key}||{sig.cause_sig}"] = j.id
                    unique.append(j)

    return DedupResult(unique=unique, duplicates=duplicates)
```

### 2.7 store/ingester.py + linker.py

```python
# store/ingester.py
"""入库主逻辑：校验 → 去重 → 存储。"""

from doramagic_judgment_schema.serializer import JudgmentStore
from doramagic_judgment_schema.validators import validate_judgment
from doramagic_judgment_schema.types import Judgment


async def ingest_judgments(
    judgments: list[Judgment],
    store: JudgmentStore,
) -> dict:
    """
    批量入库。返回统计信息。
    """
    stats = {"stored": 0, "rejected": 0, "errors": []}

    for j in judgments:
        validation = validate_judgment(j)
        if not validation.valid:
            stats["rejected"] += 1
            stats["errors"].append({"id": j.id, "errors": validation.errors})
            continue

        store.store(j)
        stats["stored"] += 1

    return stats
```

```python
# store/linker.py
"""关系自动建立。用 LLM 识别新判断和已有判断之间的关系。"""

from __future__ import annotations

import json

from doramagic_shared_utils.llm_adapter import LLMAdapter, LLMMessage
from doramagic_judgment_schema.types import Judgment, Relation, RelationType
from doramagic_judgment_schema.serializer import JudgmentStore


LINKER_SYSTEM_PROMPT = """你是 Doramagic 的知识图谱专家。你需要判断一颗新判断和已有判断之间是否存在关系。

可能的关系类型：
- generates: 新判断成立 → 产生目标判断（因果关系）
- depends_on: 新判断依赖目标判断（前置条件）
- conflicts: 与目标判断互斥（不可同时成立）
- strengthens: 为目标判断提供额外证据
- supersedes: 新判断替代目标判断（版本迭代）
- subsumes: 新判断包含目标判断（上位规则）

对每对判断，输出 JSON：
{"relations": [{"target_id": "xxx", "type": "关系类型", "description": "因果解释"}]}

如果没有关系，返回 {"relations": []}。
不要强行建立关系。没关系就是没关系。"""


async def auto_link(
    new_judgment: Judgment,
    store: JudgmentStore,
    adapter: LLMAdapter,
    model: str = "sonnet",
    max_candidates: int = 20,
) -> list[Relation]:
    """
    为新判断自动建立和已有判断的关系。
    只在同域内匹配。
    """
    # 找候选判断（同域）
    candidates: list[Judgment] = []
    for domain in new_judgment.scope.domains:
        candidates.extend(store.list_by_domain(domain))

    # 限制候选数量
    candidates = candidates[:max_candidates]

    if not candidates:
        return []

    # 构建 LLM 请求
    candidates_text = "\n".join(
        f"- {c.id}: 当{c.core.when}时，{c.core.modality.value} {c.core.action}"
        for c in candidates
    )

    new_text = (
        f"新判断 {new_judgment.id}: "
        f"当{new_judgment.core.when}时，"
        f"{new_judgment.core.modality.value} {new_judgment.core.action}，"
        f"否则{new_judgment.core.consequence.description}"
    )

    response = adapter.chat(
        messages=[LLMMessage(role="user", content=f"{new_text}\n\n已有判断:\n{candidates_text}")],
        system=LINKER_SYSTEM_PROMPT,
        temperature=0.0,
        max_tokens=500,
    )

    from doramagic_judgment_schema.utils import parse_llm_json

    try:
        result = parse_llm_json(response.text)
        relations = []
        for r in result.get("relations", []):
            relations.append(Relation(
                type=RelationType(r["type"]),
                target_id=r["target_id"],
                description=r["description"],
            ))
        return relations
    except (json.JSONDecodeError, KeyError, ValueError):
        return []
```

### 2.8 pipeline.py — 线性编排

```python
"""判断采集流水线。线性编排：Fetch → Filter → Classify → Extract → Dedup → Store。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from doramagic_shared_utils.llm_adapter import LLMAdapter
from doramagic_judgment_schema.serializer import JudgmentStore
from doramagic_judgment_schema.types import Judgment

from .source_adapters.github import GitHubAdapter
from .extract.filter import filter_records, FilterTrack
from .extract.classifier import classify_record
from .extract.extractor import extract_judgments
from .refine.dedup import dedup_judgments
from .store.ingester import ingest_judgments
from .store.linker import auto_link


@dataclass
class PipelineResult:
    fetched: int = 0
    filtered_in: int = 0
    filtered_out: int = 0
    classified: int = 0
    extracted: int = 0
    after_dedup: int = 0
    stored: int = 0
    relations_created: int = 0
    errors: list[str] = field(default_factory=list)


async def run_pipeline(
    github_token: str,
    target: dict,
    domain: str,
    judgments_path: str | Path,
    adapter: LLMAdapter,
) -> PipelineResult:
    """
    运行完整采集流水线。

    target 示例:
    {"owner": "freqtrade", "repo": "freqtrade", "state": "closed",
     "labels": "bug", "min_comments": 3, "since": "2024-01-01", "max_pages": 5}
    """
    result = PipelineResult()

    # 1. Fetch
    github = GitHubAdapter(token=github_token)
    records = await github.fetch(target)
    result.fetched = len(records)

    # 2. Filter
    filter_results = filter_records(records)
    passed = [fr for fr in filter_results if fr.track != FilterTrack.REJECTED]
    result.filtered_in = len(passed)
    result.filtered_out = len(filter_results) - len(passed)

    # 3. Classify
    classified_records: list[tuple] = []
    for fr in passed:
        category, reason = await classify_record(fr.record, adapter)
        if category != "low_value":
            classified_records.append((fr.record, category))
    result.classified = len(classified_records)

    # 4. Extract
    all_judgments: list[Judgment] = []
    id_counter = 1
    for record, category in classified_records:
        judgments = await extract_judgments(
            record, category, adapter, domain,
            id_counter=id_counter,
        )
        all_judgments.extend(judgments)
        id_counter += len(judgments)
    result.extracted = len(all_judgments)

    # 5. Dedup
    dedup_result = dedup_judgments(all_judgments)
    result.after_dedup = len(dedup_result.unique)

    # 6. Store + Auto-link
    store = JudgmentStore(judgments_path)
    relations_count = 0
    for j in dedup_result.unique:
        # 自动建立关系
        relations = await auto_link(j, store, adapter)
        if relations:
            j.relations = relations
            relations_count += len(relations)
        # 入库
        store.store(j)

    result.stored = len(dedup_result.unique)
    result.relations_created = relations_count

    return result
```

---

## 三、Sprint 3：crystal_compiler（编译 + 检索）

### 3.1 retrieve.py — 简化版检索

```python
"""检索模块。Sprint 3 实现：直接匹配 + 1跳图谱 + 排序。"""

from __future__ import annotations

from dataclasses import dataclass

from doramagic_judgment_schema.types import Judgment, LifecycleStatus
from doramagic_judgment_schema.serializer import JudgmentStore


@dataclass
class RetrievalResult:
    judgments: list[tuple[Judgment, float]]  # (judgment, weight)
    coverage_gaps: list[str]                 # 识别到的缺口


def retrieve(
    store: JudgmentStore,
    domain: str,
    task_type: str | None = None,
    resources: list[str] | None = None,
) -> RetrievalResult:
    """
    根据领域和任务类型检索相关判断。
    Step 1: 直接匹配（domain + scope 过滤）→ P1 (权重 1.0)
    Step 2: 图谱扩展（1跳）→ P2 (权重 0.8)
    Step 3: 排序
    """
    # Step 1: 直接匹配
    p1: list[tuple[Judgment, float]] = []
    all_domain = store.list_by_domain(domain)
    for j in all_domain:
        if j.version.status != LifecycleStatus.ACTIVE and j.version.status != LifecycleStatus.DRAFT:
            continue
        # scope 过滤
        if j.scope.context_requires:
            if task_type and j.scope.context_requires.task_types:
                if task_type not in j.scope.context_requires.task_types:
                    continue
            if resources and j.scope.context_requires.resources:
                if not set(resources) & set(j.scope.context_requires.resources):
                    continue
        p1.append((j, 1.0))

    # 加入 universal 判断
    for j in store.list_by_domain("universal"):
        if j.version.status in (LifecycleStatus.ACTIVE, LifecycleStatus.DRAFT):
            p1.append((j, 0.9))

    # Step 2: 图谱扩展（1跳）
    p2: list[tuple[Judgment, float]] = []
    seen_ids = {j.id for j, _ in p1}
    for j, _ in p1:
        related = store.get_relations(j.id, max_hops=1)
        for rel_j in related:
            if rel_j.id not in seen_ids:
                seen_ids.add(rel_j.id)
                p2.append((rel_j, 0.8))

    # Step 3: 排序
    all_results = p1 + p2
    severity_order = {"fatal": 4, "high": 3, "medium": 2, "low": 1}
    all_results.sort(
        key=lambda x: (
            x[1]  # weight
            * severity_order.get(x[0].compilation.severity.value, 1)
            * x[0].confidence.score
        ),
        reverse=True,
    )

    # 简单缺口检测
    coverage_gaps = _detect_gaps(domain, task_type, all_results)

    return RetrievalResult(judgments=all_results, coverage_gaps=coverage_gaps)


def _detect_gaps(domain: str, task_type: str | None, results: list) -> list[str]:
    """简单的缺口检测。检查关键领域是否有覆盖。"""
    gaps: list[str] = []
    layers_covered = {j.layer.value for j, _ in results}

    if "knowledge" not in layers_covered:
        gaps.append(f"{domain} 领域缺少 knowledge 层判断（跨项目共性规则）")
    if "resource" not in layers_covered:
        gaps.append(f"{domain} 领域缺少 resource 层判断（工具边界约束）")
    if "experience" not in layers_covered:
        gaps.append(f"{domain} 领域缺少 experience 层判断（社区踩坑经验）")

    if len(results) < 10:
        gaps.append(f"判断数量不足（{len(results)} 颗），晶体覆盖可能不完整")

    return gaps
```

### 3.2 compiler.py — 晶体编译器

```python
"""种子晶体编译器。将判断集按 crystal_section 组装成约束文本。"""

from __future__ import annotations

from doramagic_shared_utils.llm_adapter import LLMAdapter, LLMMessage
from doramagic_judgment_schema.types import Judgment, Severity, CrystalSection

from .retrieve import RetrievalResult


CRYSTAL_TEMPLATE = """# 种子晶体：{domain} — {task_description}

> 本晶体由 Doramagic 知识系统编译，基于 {judgment_count} 颗判断。
> 知识库版本: {version} | 编译时间: {compiled_at}

{personalization_prompt}

---

## ⛔ 硬约束（违反将导致严重后果）

{hard_constraints}

## ⚠️ 软约束（强烈建议遵守）

{soft_constraints}

## 📋 资源边界

{resource_profile}

## 🔍 已知缺口

{coverage_gaps}
"""


def compile_crystal(
    retrieval: RetrievalResult,
    domain: str,
    task_description: str,
    version: str = "0.1.0",
) -> str:
    """
    将检索结果编译为种子晶体文本。
    """
    from datetime import datetime

    hard_constraints: list[str] = []
    soft_constraints: list[str] = []
    resource_profile: list[str] = []

    for judgment, weight in retrieval.judgments:
        line = _format_judgment(judgment)

        if judgment.compilation.severity in (Severity.FATAL, Severity.HIGH):
            if judgment.core.modality.value in ("must", "must_not"):
                hard_constraints.append(line)
            else:
                soft_constraints.append(line)
        elif judgment.compilation.crystal_section == CrystalSection.RESOURCE_PROFILE:
            resource_profile.append(line)
        else:
            soft_constraints.append(line)

    # 个性化提示
    personalization_prompt = (
        "> **个性化提示**：为了让本晶体更精准地约束你的工作，请告诉我：\n"
        "> 1. 你使用的具体框架和版本？\n"
        "> 2. 你的目标市场（A股/美股/加密货币）？\n"
        "> 3. 你的经验水平（新手/中级/专家）？\n"
        "> 4. 你的具体任务（回测/实盘/研究）？"
    )

    gaps_text = "\n".join(f"- {g}" for g in retrieval.coverage_gaps) if retrieval.coverage_gaps else "无已知缺口。"

    return CRYSTAL_TEMPLATE.format(
        domain=domain,
        task_description=task_description,
        judgment_count=len(retrieval.judgments),
        version=version,
        compiled_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        personalization_prompt=personalization_prompt,
        hard_constraints="\n\n".join(hard_constraints) if hard_constraints else "（暂无硬约束）",
        soft_constraints="\n\n".join(soft_constraints) if soft_constraints else "（暂无软约束）",
        resource_profile="\n\n".join(resource_profile) if resource_profile else "（暂无资源边界信息）",
        coverage_gaps=gaps_text,
    )


def _format_judgment(j: Judgment) -> str:
    """将一颗判断格式化为晶体中的约束文本。"""
    modality_prefix = {
        "must": "✅ 必须",
        "must_not": "⛔ 禁止",
        "should": "💡 应当",
        "should_not": "⚠️ 不应",
    }
    prefix = modality_prefix.get(j.core.modality.value, "")

    evidence = ""
    if j.confidence.evidence_refs:
        ref = j.confidence.evidence_refs[0]
        evidence = f"（{ref.source}: {ref.summary}）"

    return (
        f"{prefix}：当{j.core.when}时，{j.core.action}。\n"
        f"  → 否则：{j.core.consequence.description}\n"
        f"  {evidence}"
    )
```

### 3.3 CLI 入口（在根 pyproject.toml 或 scripts/ 中）

```python
# scripts/harvest.py
"""判断采集 CLI 入口。"""

import asyncio
import os
import sys

from doramagic_shared_utils.llm_adapter import LLMAdapter
from doramagic_judgment_pipeline.pipeline import run_pipeline


async def main():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("ERROR: GITHUB_TOKEN 环境变量未设置")
        sys.exit(1)

    adapter = LLMAdapter()

    target = {
        "owner": "freqtrade",
        "repo": "freqtrade",
        "state": "closed",
        "labels": "bug",
        "min_comments": 3,
        "since": "2024-01-01",
        "max_pages": 5,
    }

    result = await run_pipeline(
        github_token=token,
        target=target,
        domain="finance",
        judgments_path="knowledge/judgments",
        adapter=adapter,
    )

    print(f"\n=== 采集完成 ===")
    print(f"拉取: {result.fetched}")
    print(f"过滤通过: {result.filtered_in} / 过滤丢弃: {result.filtered_out}")
    print(f"分类有效: {result.classified}")
    print(f"提取判断: {result.extracted}")
    print(f"去重后: {result.after_dedup}")
    print(f"入库: {result.stored}")
    print(f"关系建立: {result.relations_created}")
    if result.errors:
        print(f"错误: {result.errors}")


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 四、目录结构创建清单

执行者需要创建以下目录和文件：

```bash
# 目录
mkdir -p packages/judgment_schema/doramagic_judgment_schema
mkdir -p packages/judgment_pipeline/doramagic_judgment_pipeline/source_adapters
mkdir -p packages/judgment_pipeline/doramagic_judgment_pipeline/extract
mkdir -p packages/judgment_pipeline/doramagic_judgment_pipeline/refine
mkdir -p packages/judgment_pipeline/doramagic_judgment_pipeline/store
mkdir -p packages/crystal_compiler/doramagic_crystal_compiler/templates
mkdir -p tests/judgment_schema
mkdir -p tests/judgment_pipeline
mkdir -p tests/crystal_compiler
mkdir -p knowledge/judgments/domains
mkdir -p knowledge/pipeline/raw_records
mkdir -p knowledge/pipeline/gap_reports

# 所有 __init__.py
touch packages/judgment_schema/doramagic_judgment_schema/__init__.py
touch packages/judgment_pipeline/doramagic_judgment_pipeline/__init__.py
touch packages/judgment_pipeline/doramagic_judgment_pipeline/source_adapters/__init__.py
touch packages/judgment_pipeline/doramagic_judgment_pipeline/extract/__init__.py
touch packages/judgment_pipeline/doramagic_judgment_pipeline/refine/__init__.py
touch packages/judgment_pipeline/doramagic_judgment_pipeline/store/__init__.py
touch packages/crystal_compiler/doramagic_crystal_compiler/__init__.py
touch tests/judgment_schema/__init__.py
touch tests/judgment_pipeline/__init__.py
touch tests/crystal_compiler/__init__.py
```

---

## 五、验收标准

### Sprint 1 验收
- [ ] `make check` 通过（lint + typecheck + test）
- [ ] 所有 test_types.py 测试通过
- [ ] 所有 test_validators.py 测试通过
- [ ] 所有 test_normalizer.py 测试通过
- [ ] 所有 test_serializer.py 测试通过

### Sprint 2 验收
- [ ] `python scripts/harvest.py` 能运行完成
- [ ] knowledge/judgments/domains/finance.jsonl 中有 >= 30 颗判断
- [ ] 所有判断通过 validate_judgment 校验
- [ ] 无明显重复（人工抽查）

### Sprint 3 验收
- [ ] 检索 "量化回测 + yfinance" 返回 >= 10 颗判断
- [ ] 编译产出一颗完整的种子晶体文本
- [ ] 晶体包含硬约束、软约束、资源边界、缺口报告四个区
- [ ] 缺口报告至少识别 1 个未覆盖领域
