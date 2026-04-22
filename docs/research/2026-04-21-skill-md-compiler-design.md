# SKILL.md Compiler Design for V6.1 seed.yaml

> Research date: 2026-04-21
> Author: Claude Sonnet 4.6 (sub-agent)
> Task: Design the Doramagic "seed → SKILL.md bundle" compiler pipeline aligned to agentskills.io spec.

---

## 1. agentskills.io Spec — Field清单、类型、长度限制

Source: https://agentskills.io/specification (WebFetch verified 2026-04-21)

### 1.1 YAML Frontmatter Fields

| Field | Required | Type | Constraints |
|---|---|---|---|
| `name` | YES | string | 1–64 chars; `[a-z0-9-]` only; no leading/trailing hyphen; no consecutive `--`; **MUST match parent directory name** |
| `description` | YES | string | 1–1024 chars; describes what the skill does AND when to use it; should include trigger keywords |
| `license` | No | string | Short (license name or bundled file reference) |
| `compatibility` | No | string | 1–500 chars if present; environment requirements only; spec says most skills don't need it |
| `metadata` | No | object (map<string,string>) | Arbitrary key-value; use unique key prefixes to avoid conflicts |
| `allowed-tools` | No | string | Space-separated tool names; experimental; support varies by agent impl |

### 1.2 Body Content

- No format restrictions on the Markdown body after frontmatter
- Recommended sections: step-by-step instructions, input/output examples, common edge cases
- **Recommended length**: < 500 lines / < 5000 tokens
- SKILL.md is loaded **in full** when a skill is activated → keep lean

### 1.3 Optional Directory Structure

```
skill-name/           # dir name must match frontmatter `name` exactly
├── SKILL.md          # REQUIRED
├── scripts/          # executable code (Python/Bash/JS)
├── references/       # docs loaded on demand (REFERENCE.md, FORMS.md, domain-specific *.md)
└── assets/           # templates, images, data files
```

### 1.4 Progressive Disclosure Tiers

| Tier | What | Approx tokens | When loaded |
|---|---|---|---|
| 1 | `name` + `description` frontmatter | ~100 | Always, at startup |
| 2 | Full `SKILL.md` body | <5000 recommended | When skill activated |
| 3 | `references/`, `scripts/`, `assets/` | unbounded | On demand (agent reads explicitly) |

### 1.5 Spec Constraints That Bite Doramagic

1. **`name` must match dir name** — dir naming convention `finance-bp-009-zvt.skill` contains a `.`, which makes the dir name non-compliant as a skill name. Correct dir name is `finance-bp-009-zvt` (no `.skill` suffix). The `.skill` suffix can only work as a wrapper/container that holds the actual compliant skill dir inside it (see Section 4).
2. **Description ≤1024 chars** — must synthesize from seed; the tagline alone (149 chars) + keyword terms easily fits within budget.
3. **`name` lowercase-only** — blueprint ID `finance-bp-009` needs no change (already compliant). Append `-zvt` for the tool slug.

---

## 2. 真实 Skill 样例分析（4个，来自 anthropics/skills 官方 repo）

### 2.1 `pdf` skill

**Description亮点**: Triggers declaratively — "Use this skill whenever the user wants to do anything with PDF files" + exhaustive verb list (reading/extracting/combining/merging/splitting/rotating...). No ambiguity on scope.

**Body结构**: Overview → Quick Start → Library chapters (pypdf / pdfplumber / reportlab) → CLI tools → Common Tasks → Quick Reference table → Next Steps (pointers to `REFERENCE.md` and `FORMS.md`). Body stays under 200 lines; implementation detail overflows to `references/`.

**优点 (100字)**: 触发词极精确（"the user mentions a .pdf file"），body仅含核心速查表，重体积内容全部交给`references/REFERENCE.md`和`FORMS.md`按需加载，完美示范 progressive disclosure；code snippets精到一个 use-case 一段，不堆砌。

---

### 2.2 `mcp-builder` skill

**Description亮点**: 单句说清 Who + What + When："Guide for creating high-quality MCP servers... Use when building MCP servers to integrate external APIs or services, whether in Python (FastMCP) or Node/TypeScript."

**Body结构**: 4-Phase process (Research → Implementation → Review → Evaluations)，每个 phase 再分 sub-steps，所有 SDK reference 通过 `[link](./reference/xxx.md)` 延迟加载。结构极深但 SKILL.md 本身 body 约 150 行。

**优点 (100字)**: 证明复杂 multi-phase 流程可以在 500 行内全程导航——体量来自引用而非内联。`reference/` 目录高度分层（mcp_best_practices / python_mcp_server / node_mcp_server / evaluation）每份聚焦单一主题，agent 只按需拉取。是 Doramagic 引用分层的最佳参照。

---

### 2.3 `webapp-testing` skill

**Description亮点**: Tight and tool-specific: "Toolkit for interacting with and testing local web applications using Playwright." Keywords: Playwright, frontend functionality, browser screenshots, browser logs.

**Body结构**: Decision Tree flowchart（用 ``` 块内纯文本决策树） → Example: Using with_server.py → Reconnaissance-Then-Action Pattern → Common Pitfall → Best Practices → Reference Files。极简，约 70 行。

**优点 (100字)**: Decision Tree 模式是亮点——把"什么情况下走哪条路"做成 ASCII 树嵌在 body 里，agent 第一次读就拿到完整的路由逻辑，不需要二次 fetch。Pitfall 单独一节（❌/✅格式），显著降低幻觉错误率。Doramagic anti-pattern section 可借鉴此格式。

---

### 2.4 `xlsx` skill

**Description亮点**: 最长的 description，约 800 chars，精心列举所有触发场景（open/read/edit/fix/create/convert/clean），并有**负向排除规则**："Do NOT trigger when the primary deliverable is a Word document, HTML report, standalone Python script, database pipeline, or Google Sheets API integration."

**Body结构**: Requirements (All Excel / Financial models) → XLSX Creation/Editing/Analysis → Critical Requirement 加粗 → Code examples → Verification Checklist。

**优点 (100字)**: description 的负向排除规则是学到的最重要的范式——明确告诉 agent 不该激活的场景，比只写正向触发条件的 skill 精确度高一个量级。finance-bp-009 description 必须加"Do NOT use for US equities serious analysis"（对应 human_summary tagline 中的 US stocks half-baked 警告）。

---

## 3. V6.1 seed → SKILL.md 字段映射表

### 3.1 Cardinality 决策：per-blueprint（一个 seed → 一个 skill bundle）

Seed 的 `skill_crystallization.slug_template = {blueprint_id_short}-{uc_id_lower}` 暗示过 per-UC 方案，但任务说明的 bundle 示例 `finance-bp-009-zvt.skill/` 明确是 per-blueprint。**本设计选 per-blueprint**，理由：

- 用户对 ZVT 的认知单元是整个框架，不是某一 UC；
- 8+ 个细分 UC 如果各自发布 skill，ClawHub 首页噪声大，slot 冲突概率高；
- `intent_router` 在 SKILL.md 内部已提供 UC 路由，无需拆发布单元；
- `skill_crystallization.slug_template` 属 per-execution 子技能保存逻辑（run 完保存 .skill 文件），与 bundle 发布层不在同一概念层次。

**Tech debt**: 编译器生成 bundle 后，可在 `references/` 下按 UC 拆出 `USE_CASES.md` 供 per-UC 子技能引用；未来若要 per-UC 发布，在 `references/UC-{id}.md` 基础上极低成本拆分。

> **与 seed 现有约定的冲突**: seed 的 `skill_crystallization.output_path_template` 使用 `.skill` 后缀（`{workspace}/../skills/{slug}.skill`），这是 Doramagic per-UC 运行时子技能的保存格式。本设计有意区分两个层次：**发布 bundle**（本文档定义，`.skill` 作为 wrapper 后缀，内含合规 skill dir）和**运行时子技能**（seed 原有逻辑，per-UC `.skill` 文件）。发布 bundle 命名为 `finance-bp-009-zvt.skill/`，内部包含 `finance-bp-009-zvt/SKILL.md`，与 agentskills.io `name` = dir 的规范兼容。

---

### 3.2 SKILL.md Frontmatter 映射

| SKILL.md 字段 | 来源 seed 路径 | 合成方式 | 需 LLM？ |
|---|---|---|---|
| `name` | `meta.blueprint_id` + 固定后缀 `-zvt` | `f"{meta['blueprint_id']}-zvt"` → `finance-bp-009-zvt` | **否** |
| `description` | `human_summary.what_i_can_do.tagline` + `intent_router.uc_entries[].positive_terms` | 1. tagline 为主句 2. 拼接 "Use when: " + top-6 术语 3. 追加负向排除句（US stocks warning） 4. 截断 ≤1000 chars | **否**（确定性拼接） |
| `license` | `meta` 中无声明，默认 Doramagic 私有 | 硬编码: `"Proprietary. See LICENSE.txt"` | **否** |
| `compatibility` | `meta.target_host` + `resources.packages[]` | `f"Designed for {meta['target_host']}. Requires Python 3.12+, uv."` | **否** |
| `metadata.version` | `meta.version` | 直接取 `meta['version']` → `"v6.1"` | **否** |
| `metadata.blueprint_id` | `meta.blueprint_id` | 直接取 | **否** |
| `metadata.compiled_at` | `meta.compiled_at` | 直接取 | **否** |
| `metadata.capability_tags` | `meta.capability_tags` | `json.dumps(meta['capability_tags'])` | **否** |
| `allowed-tools` | `meta.execution_protocol` 中无显式声明 | 按规范推断：`Bash Read WebFetch` | **否**（可选，不影响功能） |

### 3.3 SKILL.md Body 映射

| SKILL.md Section | 来源 seed 路径 | 合成方式 | 需 LLM？ |
|---|---|---|---|
| **Persona + Tagline** | `human_summary.what_i_can_do.tagline` | 直接嵌入 | **否** |
| **Pipeline One-Liner** | `architecture.pipeline` | `data_collection → data_storage → factor_computation → target_selection → trading_execution → visualization` | **否** |
| **Use Cases** (top-3) | `post_install_notice.message_template.groups[].ucs[]` | 取前3 UC，格式：`{name}: {short_description} (triggers: {sample_triggers})` | **否** |
| **Install Trigger** | `meta.execution_protocol.install_trigger[]` | 列表转 Markdown steps | **否** |
| **What I Ask You** | `human_summary.what_i_ask_you[]` | 直接转 Markdown 列表 | **否** |
| **Spec Locks Summary Table** | `spec_lock_registry.semantic_locks[]` | id + description + violation_is 三列表格（仅 fatal 项） | **否** |
| **Key Constraints** | `constraints.fatal[]` 前 5 条 | id + when + action 三列，链接到 `references/CONSTRAINTS.md` | **否** |
| **Anti-Patterns Quick Ref** | `anti_patterns[]` 前 3 条（high severity） | id + title + 一句话摘要，链接到 `references/ANTI_PATTERNS.md` | **否** |
| **Evidence Quality Notice** | `evidence_quality.user_disclosure_template` | 直接嵌入（含 verify_ratio / audit_fail_total） | **否** |
| **References Section** | 固定模板 | 列出 `references/*.md` 文件及其内容说明 | **否** |

### 3.4 不能直接映射、需要 LLM 辅助的字段

经核查，**没有必须用 LLM 的字段**。以下字段有 LLM 辅助可以提升质量，但 deterministic 方案已足够发布：

| 场景 | 确定性方案（够用） | LLM 方案（更好） |
|---|---|---|
| `description` 中的负向排除句 | 硬编码模板 + market 字段判断 | LLM 根据 human_summary 生成更自然的排除说明 |
| Spec Locks 摘要 | 截取 description 前 80 chars | LLM 压缩为一行动作短语 |
| 多 UC 时的 "Use Cases" section | 取 uc.name + short_description | LLM 合成跨 UC 的能力全景句 |

结论：**V6.1 seed 的 body 段设计已经高度"SKILL.md-ready"**——`human_summary`, `post_install_notice`, `intent_router` 三段几乎是现成的 SKILL.md 内容，设计者显然预留了这条路。

---

## 4. Bundle 目录结构建议

### 4.1 名称规范问题（Critical Fix）

任务原始示例 `finance-bp-009-zvt.skill/` 含 `.` 字符，违反 agentskills.io `name` 字段规范（only `[a-z0-9-]`）。

**推荐方案：wrapper 容器 + 内部合规目录**

```
finance-bp-009-zvt.skill/           # 发布 bundle 容器（与 Doramagic .skill 后缀约定对齐）；非 skill dir
└── finance-bp-009-zvt/             # 合规 skill 目录，name = "finance-bp-009-zvt"
    ├── SKILL.md                    # host 首读；frontmatter + ≤200行 body
    ├── references/
    │   ├── ANTI_PATTERNS.md        # anti_patterns[] 全量（目前 ~20条，≈400行）
    │   ├── WISDOM.md               # cross_project_wisdom[] 全量
    │   ├── CONSTRAINTS.md          # domain_constraints_injected[] + constraints.fatal[]
    │   ├── USE_CASES.md            # known_use_cases[] 全量（最大单文件，≈3000行）
    │   ├── LOCKS.md                # spec_lock_registry + preconditions + implementation_hints
    │   ├── COMPONENTS.md           # component_capability_map（AST mind map，≈7000行）
    │   └── seed.yaml               # V6.1 全量（权威 source-of-truth）
    ├── scripts/
    │   └── install.sh              # pip install + requirements from resources.packages[]
    └── human_summary.md            # 给人看的 human_summary，非 agent 消费
```

### 4.2 拆 vs 不拆决策矩阵

| 维度 | 全量内联 | 按文件拆分（推荐） |
|---|---|---|
| **Context 消耗** | 每次激活消耗 ~50k tokens（571KB≈140k tokens 的 seed） | 激活仅消耗 ~1k tokens（SKILL.md body）；按需再 fetch |
| **维护成本** | seed 一变就重新发布一个大文件 | 各 reference 文件可独立更新；seed 更新时仅重新生成 changed 部分 |
| **引用精确度** | Agent 必须扫描全文找相关段 | Agent 按 section 名称直接定位 |
| **ClawHub 兼容** | 单 SKILL.md 体积超出 host 软限制风险 | 符合 agentskills.io progressive disclosure 设计意图 |
| **决定** | ❌ 不适用 | ✅ 推荐 |

### 4.3 COMPONENTS.md 特殊处理

`component_capability_map` 含 424 个 class 的 AST 地图（约 7000 行），是最大的单节点。建议：
- 生成时按 module 拆子文件：`references/components/recorder.md`、`references/components/factor.md`、`references/components/trader.md` 等；
- SKILL.md body 只列模块名和行数，不引用具体 class。

---

## 5. SKILL.md 模板骨架（Jinja2）

```jinja2
---
name: {{ blueprint_id }}-{{ project_slug }}
description: >-
  {{ human_summary.what_i_can_do.tagline }}
  Use when: {{ uc_keywords | join(", ") }}.
  Do NOT use for: {{ negative_scope }}.
license: Proprietary. See LICENSE.txt
compatibility: Designed for {{ meta.target_host }}. Requires Python 3.12+, uv.
metadata:
  version: "{{ meta.version }}"
  blueprint_id: "{{ meta.blueprint_id }}"
  compiled_at: "{{ meta.compiled_at }}"
  capability_markets: "{{ meta.capability_tags.markets | join(', ') }}"
---

# {{ skill_display_name }}

> {{ human_summary.what_i_can_do.tagline }}

## Pipeline

`{{ architecture.pipeline }}`

## Top Use Cases

{% for uc in top_ucs[:3] %}
### {{ uc.name }} (`{{ uc.uc_id }}`)
{{ uc.short_description }}
**Triggers**: {{ uc.sample_triggers | join(", ") }}

{% endfor %}
For all {{ total_uc_count }} use cases, see [references/USE_CASES.md](references/USE_CASES.md).

## Install

```bash
# Run once before first use
bash scripts/install.sh
```

Execute trigger: `{{ meta.execution_protocol.execute_trigger }}`

## What I'll Ask You

{% for q in human_summary.what_i_ask_you %}
- {{ q }}
{% endfor %}

## Semantic Locks (Fatal)

| ID | Rule | Violation |
|---|---|---|
{% for sl in spec_locks if sl.violation_is == "fatal" %}
| `{{ sl.id }}` | {{ sl.description }} | fatal |
{% endfor %}

Full lock definitions: [references/LOCKS.md](references/LOCKS.md)

## Top Anti-Patterns

{% for ap in anti_patterns[:3] if ap.severity == "high" %}
- **{{ ap.id }}**: {{ ap.title }} → [details](references/ANTI_PATTERNS.md#{{ ap.id | lower }})
{% endfor %}

All {{ total_ap_count }} anti-patterns: [references/ANTI_PATTERNS.md](references/ANTI_PATTERNS.md)

## Evidence Quality Notice

> {{ evidence_quality.user_disclosure_template }}

## Reference Files

| File | Contents | When to Load |
|---|---|---|
| [seed.yaml](references/seed.yaml) | V6.1 全量权威 source-of-truth | 有行为决策争议时必读 |
| [ANTI_PATTERNS.md](references/ANTI_PATTERNS.md) | {{ total_ap_count }} 条跨项目反模式（ZVT/Qlib/vnpy/zipline） | 开始实现前 |
| [WISDOM.md](references/WISDOM.md) | 跨项目精华借鉴（backtrader/vnpy/qlib） | 架构决策时 |
| [CONSTRAINTS.md](references/CONSTRAINTS.md) | domain_constraints + fatal constraints | 规则冲突时 |
| [USE_CASES.md](references/USE_CASES.md) | 全量 KUC-* 业务场景 | 需要完整示例时 |
| [LOCKS.md](references/LOCKS.md) | SL-01~SL-12 + preconditions + hints | 回测/交易代码生成前 |
| [COMPONENTS.md](references/COMPONENTS.md) | 424 ZVT classes AST 地图 | 查 API 时 |
```

---

## 6. 实现伪代码

```python
"""
emit_skill_bundle(seed_path, out_dir)
核心逻辑：seed.yaml → agentskills.io 合规 bundle 目录
"""
from pathlib import Path
import yaml
from jinja2 import Environment, FileSystemLoader

SKILL_MD_TEMPLATE = "skill_md.jinja2"  # Section 5 的模板
PROJECT_SLUG = None  # 派生自 seed_path 的目录名：finance-bp-009--zvt → "zvt"（split("--")[1]）


def emit_skill_bundle(seed_path: str, out_dir: str) -> Path:
    seed = yaml.safe_load(Path(seed_path).read_text())

    # 1. 解析 blueprint_id → name；project_slug 从目录名派生
    bp_id = seed["meta"]["blueprint_id"]                    # "finance-bp-009"
    seed_dir = Path(seed_path).parent.name                  # "finance-bp-009--zvt"
    project_slug = seed_dir.split("--")[1] if "--" in seed_dir else seed_dir
    skill_name = f"{bp_id}-{project_slug}"                  # "finance-bp-009-zvt"
    _validate_skill_name(skill_name)                        # raise if non-compliant

    # 2. 确定输出路径（wrapper.skill/skill_name/，与 Doramagic .skill 后缀约定对齐）
    bundle_root = Path(out_dir) / f"{skill_name}.skill"
    skill_dir = bundle_root / skill_name
    refs_dir = skill_dir / "references"
    scripts_dir = skill_dir / "scripts"
    for d in [refs_dir, scripts_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # 3. 合成 description (确定性，不调 LLM)
    tagline = seed["human_summary"]["what_i_can_do"]["tagline"]
    uc_keywords = _collect_uc_keywords(seed["intent_router"]["uc_entries"], top_n=6)
    negative_scope = _build_negative_scope(seed)            # US stocks warning + non-backtest warning
    description = _build_description(tagline, uc_keywords, negative_scope, max_chars=1000)

    # 4. 渲染 SKILL.md
    env = Environment(loader=FileSystemLoader("templates/"))
    template = env.get_template(SKILL_MD_TEMPLATE)
    skill_md = template.render(
        blueprint_id=bp_id,
        project_slug=PROJECT_SLUG,
        skill_display_name=f"ZVT A-Share Quant ({bp_id})",
        description=description,
        meta=seed["meta"],
        architecture=seed["architecture"],
        human_summary=seed["human_summary"],
        top_ucs=_get_top_ucs(seed, n=3),
        total_uc_count=len(seed["intent_router"]["uc_entries"]),
        spec_locks=seed["spec_lock_registry"]["semantic_locks"],
        anti_patterns=seed["anti_patterns"],
        total_ap_count=len(seed["anti_patterns"]),
        evidence_quality=seed["evidence_quality"],
    )
    (skill_dir / "SKILL.md").write_text(skill_md)

    # 5. 生成 references/ 文件（每个函数独立，按需扩展）
    _write_anti_patterns_md(refs_dir, seed["anti_patterns"])
    _write_wisdom_md(refs_dir, seed.get("cross_project_wisdom", []))
    _write_constraints_md(refs_dir, seed)
    _write_use_cases_md(refs_dir, seed.get("known_use_cases", []))
    _write_locks_md(refs_dir, seed["spec_lock_registry"], seed["preconditions"])
    _write_components_md(refs_dir, seed.get("component_capability_map", {}))

    # 6. 复制 seed.yaml（权威副本）
    import shutil
    shutil.copy(seed_path, refs_dir / "seed.yaml")

    # 7. 生成 install.sh
    _write_install_sh(scripts_dir, seed["resources"]["packages"])

    # 8. 生成 human_summary.md（直接从 seed 渲染）
    _write_human_summary_md(skill_dir, seed["human_summary"])

    # 9. 验证 SKILL.md 合规（可选，调 skills-ref CLI）
    # subprocess.run(["skills-ref", "validate", str(skill_dir)])

    return bundle_root


# ─── Helper 函数签名 ─────────────────────────────────────────────────────────

def _validate_skill_name(name: str) -> None:
    """断言 name 满足 agentskills.io 规则：[a-z0-9-], 1-64 chars, no leading/trailing/consecutive hyphen"""
    import re
    assert (
        re.fullmatch(r"[a-z0-9]([a-z0-9-]*[a-z0-9])?", name) is not None
        and len(name) <= 64
        and "--" not in name   # 显式拒绝连续连字符（regex 不覆盖此情况）
    ), f"Invalid skill name: {name!r}"

def _collect_uc_keywords(uc_entries: list, top_n: int = 6) -> list[str]:
    """从所有 UC 的 positive_terms 里去重，取前 top_n 个最高频词"""
    from collections import Counter
    all_terms = [t for uc in uc_entries for t in uc["positive_terms"]]
    return [t for t, _ in Counter(all_terms).most_common(top_n)]

def _build_description(tagline: str, keywords: list, negative: str, max_chars: int = 1000) -> str:
    """组装 description，在最近词边界截断，不截断到词中间"""
    body = f"{tagline} Use when: {', '.join(keywords)}. Do NOT use for: {negative}."
    if len(body) <= max_chars:
        return body
    # 在 max_chars 处向前找最近空格，避免截断词中间
    truncated = body[:max_chars]
    last_space = truncated.rfind(" ")
    return (truncated[:last_space] if last_space > 0 else truncated) + "..."

def _build_negative_scope(seed: dict) -> str:
    """从 human_summary tagline 中的警告语提取负向范围"""
    # 示例：ZVT tagline 含 "US stocks — half-baked; don't bother for serious work"
    return "US equities serious analysis (ZVT coverage is half-baked for US market)"

def _get_top_ucs(seed: dict, n: int = 3) -> list:
    """从 post_install_notice 里取前 n 个 UC（含 short_description）"""
    ucs = []
    for group in seed.get("post_install_notice", {}).get("message_template", {}).get("groups", []):
        ucs.extend(group.get("ucs", []))
    return ucs[:n]

def _write_anti_patterns_md(refs_dir: Path, items: list) -> None:
    """每条 AP-* 写为 ### 标题 + id + description + severity + issue_link"""
    lines = ["# Anti-Patterns\n"]
    for ap in items:
        lines += [
            f"### {ap['id']}: {ap['title']}\n",
            f"**Severity**: {ap['severity']}  ",
            f"**Source**: {ap['project_source']}  ",
            f"**Issue**: {ap.get('issue_link', 'N/A')}\n",
            f"{ap['description']}\n\n---\n",
        ]
    (refs_dir / "ANTI_PATTERNS.md").write_text("\n".join(lines))

def _write_install_sh(scripts_dir: Path, packages: list) -> None:
    lines = ["#!/usr/bin/env bash", "# Auto-generated install script from seed.yaml resources.packages", ""]
    for pkg in packages:
        pin = pkg.get("version_pin", "latest")
        name_ver = pkg["name"] if pin in ("latest", None) else f'{pkg["name"]}{pin}'
        lines.append(f"pip install '{name_ver}'")
    (scripts_dir / "install.sh").write_text("\n".join(lines))
    (scripts_dir / "install.sh").chmod(0o755)
```

---

## 7. 实现复杂度评估

### 7.1 工作量分解

| 任务 | 预估时间 | 依赖 |
|---|---|---|
| Jinja2 模板编写（SKILL.md body） | 2h | Section 5 已基本完成 |
| `emit_skill_bundle()` 主函数 | 1h | 伪代码已给出 |
| 5个 `_write_*_md()` helper 函数 | 2h | 格式已知，逐节转换 |
| `_validate_skill_name()` + 单元测试 | 0.5h | |
| COMPONENTS.md 按 module 拆子文件 | 1h | 需要查 component_capability_map 的 module 键名 |
| ClawHub `clawhub.yaml` sibling 文件 | 0.5h | |
| 集成测试（跑一次 bp-009，验证输出） | 1h | |
| **合计** | **约 8h** | 主线程今天能完成核心实现 |

### 7.2 技术债记录

1. **per-UC 子技能保存逻辑**：`skill_crystallization.slug_template` 在 seed 里用于 run-time 生成 `.skill` 文件，与 bundle 发布不冲突，但未来需要明确文档说明两者语义差异。
2. **COMPONENTS.md 大小**：424 class × 平均 15 行 ≈ 6000 行，按 module 拆子文件是必选项，不能整体内联。
3. **ClawHub slug 字段位置**：ClawHub publish 的 `slug/version/tags/changelog` 是 CLI args，不是 SKILL.md frontmatter。推荐在 bundle 根添加 `clawhub.yaml` sibling 文件（版本元数据与 SKILL.md 解耦），内容：
   ```yaml
   slug: finance-bp-009-zvt
   version: "6.1.0"
   tags: latest,finance,cn-astock,backtesting
   changelog: ""
   ```
4. **`allowed-tools` 字段**：Seed 未声明显式工具列表；发布时建议填 `Read Bash WebFetch`（实验性功能，不影响合规性）。

---

*Generated by Claude Sonnet 4.6 sub-agent for Doramagic — 2026-04-21*
