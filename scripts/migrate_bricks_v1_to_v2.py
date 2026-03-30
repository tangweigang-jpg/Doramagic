#!/usr/bin/env python3
"""从旧版 JSONL 积木文件迁移到 v2 格式 YAML。

迁移规则：
- 提取 knowledge_type 为 failure / anti_pattern / constraint 的条目
- 同时提取包含关键词（avoid/don't/never/careful/warning/限制/限流/注意）的条目
- 以及包含 API 名称、版本号、具体配置值的条目
- 只处理 HIGH 文件列表中的 21 个文件
- 每个文件至少 3 条 constraints，否则跳过
- 输出写入 bricks_v2/migrated/
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import yaml

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ===== 配置 =====

PROJECT_ROOT = Path(__file__).parent.parent
BRICKS_DIR = PROJECT_ROOT / "bricks"
OUTPUT_DIR = PROJECT_ROOT / "bricks_v2" / "migrated"

HIGH_FILES = [
    "skill_architecture",
    "langchain",
    "langgraph",
    "fastapi_flask",
    "info_aggregation",
    "openai_sdk",
    "security_auth",
    "messaging_integration",
    "python_general",
    "email_automation",
    "huggingface_transformers",
    "web_browsing",
    "data_pipeline",
    "llamaindex",
    "multi_agent",
    "agent_evolution",
    "financial_trading",
    "api_integration",
    "django",
    "cicd_devops",
    "domain_private_cloud",
]

# 触发关键词（小写匹配）
TRIGGER_KEYWORDS = [
    "avoid",
    "don't",
    "never",
    "careful",
    "warning",
    "限制",
    "限流",
    "注意",
]

# API/版本相关关键词（触发额外提取）
API_KEYWORDS = [
    "api",
    "sdk",
    "version",
    "v1.",
    "v2.",
    "v3.",
    "rate limit",
    "timeout",
    "retry",
    "max_retries",
    "token",
    "bearer",
    "http/",
    "https://",
    "port",
    "endpoint",
]

# 文件名到中文名映射
FILE_NAME_MAP: dict[str, dict[str, str]] = {
    "skill_architecture": {
        "name": "Skill 架构约束",
        "category": ["Agent", "架构", "Skill"],
    },
    "langchain": {
        "name": "LangChain 框架约束",
        "category": ["LLM框架", "LangChain"],
    },
    "langgraph": {
        "name": "LangGraph 图编排约束",
        "category": ["LLM框架", "LangGraph", "图编排"],
    },
    "fastapi_flask": {
        "name": "FastAPI/Flask Web 框架约束",
        "category": ["Web框架", "FastAPI", "Flask"],
    },
    "info_aggregation": {
        "name": "信息聚合约束",
        "category": ["信息聚合", "数据采集"],
    },
    "openai_sdk": {
        "name": "OpenAI SDK 约束",
        "category": ["LLM", "OpenAI", "SDK"],
    },
    "security_auth": {
        "name": "安全与认证约束",
        "category": ["安全", "认证", "OAuth"],
    },
    "messaging_integration": {
        "name": "消息集成约束",
        "category": ["消息", "集成", "Webhook"],
    },
    "python_general": {
        "name": "Python 通用编程约束",
        "category": ["Python", "通用"],
    },
    "email_automation": {
        "name": "邮件自动化约束",
        "category": ["邮件", "自动化"],
    },
    "huggingface_transformers": {
        "name": "HuggingFace Transformers 约束",
        "category": ["ML", "HuggingFace", "Transformers"],
    },
    "web_browsing": {
        "name": "Web 浏览与抓取约束",
        "category": ["Web", "爬虫", "浏览器自动化"],
    },
    "data_pipeline": {
        "name": "数据管道约束",
        "category": ["数据", "管道", "ETL"],
    },
    "llamaindex": {
        "name": "LlamaIndex RAG 约束",
        "category": ["RAG", "LlamaIndex", "向量检索"],
    },
    "multi_agent": {
        "name": "多 Agent 协作约束",
        "category": ["Agent", "多Agent", "协作"],
    },
    "agent_evolution": {
        "name": "Agent 演进约束",
        "category": ["Agent", "演进", "架构"],
    },
    "financial_trading": {
        "name": "金融交易约束",
        "category": ["金融", "交易", "量化"],
    },
    "api_integration": {
        "name": "API 集成约束",
        "category": ["API", "集成", "HTTP"],
    },
    "django": {
        "name": "Django 框架约束",
        "category": ["Web框架", "Django", "ORM"],
    },
    "cicd_devops": {
        "name": "CI/CD 与 DevOps 约束",
        "category": ["DevOps", "CI/CD", "部署"],
    },
    "domain_private_cloud": {
        "name": "私有云部署约束",
        "category": ["私有云", "部署", "基础设施"],
    },
}


def parse_confidence(conf: str | float | None) -> float:
    """将 confidence 字符串转为 0-1 浮点数。"""
    if conf is None:
        return 0.5
    if isinstance(conf, (int, float)):
        return float(conf)
    mapping = {"high": 0.9, "medium": 0.65, "low": 0.4}
    return mapping.get(str(conf).lower(), 0.5)


def confidence_to_severity(conf: str | float | None) -> str:
    """将 confidence 映射到 FailurePattern severity。"""
    val = parse_confidence(conf)
    if val > 0.8:
        return "HIGH"
    if val > 0.6:
        return "MEDIUM"
    return "LOW"


def extract_evidence_urls(evidence_refs: list[dict]) -> list[str]:
    """从 evidence_refs 列表中提取 URL 字符串。"""
    urls = []
    for ref in evidence_refs or []:
        url = ref.get("source_url") or ref.get("path", "")
        if url and url.startswith("http"):
            urls.append(url)
    return urls


def is_constraint_entry(entry: dict) -> bool:
    """判断一条 entry 是否应被提取为约束/失败。"""
    kt = entry.get("knowledge_type", "")
    if kt in ("failure", "anti_pattern", "constraint"):
        return True

    stmt = entry.get("statement", "").lower()
    # 关键词匹配
    if any(kw in stmt for kw in TRIGGER_KEYWORDS):
        return True
    # API/版本关键词匹配
    return bool(any(kw in stmt for kw in API_KEYWORDS))


def build_tags(file_stem: str, meta: dict[str, list]) -> list[str]:
    """构建搜索标签列表。"""
    tags = list(meta.get("category", []))
    # 添加文件名作为标签
    tags.append(file_stem.replace("_", "-"))
    # 去重保序
    seen: set[str] = set()
    result = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result


def load_jsonl(path: Path) -> list[dict]:
    """加载 JSONL 文件，跳过空行和解析错误。"""
    entries = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError as e:
            logger.warning("  跳过第 %d 行（JSON 解析失败）: %s", line_no, e)
    return entries


def find_rationale_for_failure(failure_stmt: str, all_entries: list[dict]) -> str:
    """尝试从 rationale 条目中找到与 failure 配对的缓解方案。

    策略：找 statement 中包含 failure_stmt 前 30 字符关键词的 rationale 条目。
    """
    prefix = failure_stmt[:50].lower()
    # 提取前几个词作为关键词
    words = [w for w in prefix.split() if len(w) > 4][:5]

    best_match: str = ""
    best_score = 0
    for entry in all_entries:
        if entry.get("knowledge_type") != "rationale":
            continue
        stmt = entry.get("statement", "").lower()
        score = sum(1 for w in words if w in stmt)
        if score > best_score:
            best_score = score
            best_match = entry.get("statement", "")

    # 只有匹配分足够高才使用（避免完全不相关的 rationale）
    if best_score >= 2 and best_match:
        # 截取前 200 字符作为 mitigation
        return best_match[:200] + ("..." if len(best_match) > 200 else "")
    return ""


def migrate_file(file_stem: str) -> dict | None:
    """迁移单个 JSONL 文件，返回 v2 YAML 数据字典，失败返回 None。"""
    path = BRICKS_DIR / f"{file_stem}.jsonl"
    if not path.exists():
        logger.warning("文件不存在，跳过: %s", path)
        return None

    meta = FILE_NAME_MAP.get(
        file_stem,
        {
            "name": file_stem.replace("_", " ").title() + " 约束",
            "category": [file_stem.replace("_", " ").title()],
        },
    )

    all_entries = load_jsonl(path)
    logger.info("加载 %s: %d 条", file_stem, len(all_entries))

    # ===== 提取约束条目 =====
    constraint_entries = [e for e in all_entries if is_constraint_entry(e)]

    # ===== 分类 =====
    failure_entries = [
        e for e in constraint_entries if e.get("knowledge_type") in ("failure", "anti_pattern")
    ]
    pure_constraint_entries = [
        e for e in constraint_entries if e.get("knowledge_type") == "constraint"
    ]
    # 关键词匹配的非 failure/constraint 条目（只作 constraints，不作 failures）
    keyword_entries = [
        e
        for e in constraint_entries
        if e.get("knowledge_type") not in ("failure", "anti_pattern", "constraint")
    ]

    # ===== 构建 constraints 列表 =====
    all_constraint_stmts = (
        [e.get("statement", "") for e in pure_constraint_entries]
        + [e.get("statement", "") for e in failure_entries]
        + [e.get("statement", "") for e in keyword_entries]
    )
    # 去重（保留顺序）
    seen_stmts: set[str] = set()
    constraints: list[str] = []
    for stmt in all_constraint_stmts:
        stmt = stmt.strip()
        if stmt and stmt not in seen_stmts:
            seen_stmts.add(stmt)
            constraints.append(stmt)

    if len(constraints) < 3:
        logger.warning("  %s: 约束数量 %d < 3，跳过", file_stem, len(constraints))
        return None

    # ===== 构建 common_failures =====
    common_failures = []
    for entry in failure_entries:
        stmt = entry.get("statement", "").strip()
        if not stmt:
            continue
        severity = confidence_to_severity(entry.get("confidence"))
        mitigation = find_rationale_for_failure(stmt, all_entries)
        common_failures.append(
            {
                "severity": severity,
                "pattern": stmt,
                "mitigation": mitigation,
            }
        )

    # ===== core_capability =====
    # 优先从 best_practice 或 capability 类型找，其次从 rationale 找第一条
    core_cap = ""
    for kt in ("capability", "best_practice", "rationale"):
        matches = [e for e in all_entries if e.get("knowledge_type") == kt]
        if matches:
            core_cap = matches[0].get("statement", "")[:200]
            if len(matches[0].get("statement", "")) > 200:
                core_cap += "..."
            break
    if not core_cap and all_entries:
        core_cap = all_entries[0].get("statement", "")[:150]

    # ===== 汇总 evidence_refs =====
    all_refs: list[str] = []
    seen_refs: set[str] = set()
    for entry in constraint_entries:
        for url in extract_evidence_urls(entry.get("evidence_refs", [])):
            if url not in seen_refs:
                seen_refs.add(url)
                all_refs.append(url)

    # ===== 计算 quality_score =====
    # 基于 failure 数量、constraint 数量和平均 confidence
    avg_conf = sum(parse_confidence(e.get("confidence")) for e in constraint_entries)
    avg_conf = avg_conf / len(constraint_entries) if constraint_entries else 0.5
    quality = min(100.0, (len(constraints) * 3 + len(common_failures) * 5) * avg_conf)

    # ===== 组装 YAML 数据 =====
    brick_data = {
        "id": f"{file_stem.replace('_', '-')}-v1",
        "name": meta["name"],
        "version": "1.0.0",
        "category": meta.get("category", [file_stem]),
        "tags": build_tags(file_stem, meta),
        "capability_type": "transform",
        "data_source": None,
        "inputs": {},
        "outputs": {},
        "requires": [],
        "conflicts_with": [],
        "compatible_with": [],
        "core_capability": core_cap,
        "constraints": constraints,
        "common_failures": common_failures,
        "source": "auto-extracted",
        "freshness_date": "2026-03-29",
        "quality_score": round(quality, 1),
        "usage_count": 0,
        "evidence_refs": all_refs[:20],  # 最多保留 20 条引用
    }

    return brick_data


def write_yaml(data: dict, output_path: Path) -> None:
    """将积木数据写入 YAML 文件，添加注释头。"""
    header = f"# 知识积木 v2 — {data['name']}\n"
    header += "# 从旧版 JSONL 自动迁移，source: auto-extracted\n\n"

    yaml_str = yaml.dump(
        data,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
        width=100,
    )
    output_path.write_text(header + yaml_str, encoding="utf-8")


def main() -> None:
    """主入口：迁移所有 HIGH 文件。"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    total_files = 0
    total_constraints = 0
    total_failures = 0
    skipped_files = []

    for file_stem in HIGH_FILES:
        logger.info("处理: %s", file_stem)
        brick_data = migrate_file(file_stem)

        if brick_data is None:
            skipped_files.append(file_stem)
            continue

        output_path = OUTPUT_DIR / f"{file_stem}.yaml"
        write_yaml(brick_data, output_path)

        n_constraints = len(brick_data["constraints"])
        n_failures = len(brick_data["common_failures"])
        total_files += 1
        total_constraints += n_constraints
        total_failures += n_failures
        logger.info(
            "  -> %s: %d constraints, %d failures",
            output_path.name,
            n_constraints,
            n_failures,
        )

    print("\n========== 迁移完成 ==========")
    print(f"成功迁移文件: {total_files} 个")
    print(f"跳过文件:     {len(skipped_files)} 个 {skipped_files if skipped_files else ''}")
    print(f"总 constraints: {total_constraints} 条")
    print(f"总 failures:    {total_failures} 条")
    print(f"输出目录: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
