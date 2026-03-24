"""积木注入 — 加载框架积木并注入 Stage 1/2/3 prompts。

纯确定性模块，不调用 LLM。
逻辑：
1. 根据 repo_facts.frameworks 匹配 bricks/ 目录下的 JSONL 文件
2. 加载匹配的 DomainBrick 对象
3. 生成注入文本（告知 LLM "你已知这些基线知识"）
4. 将合并后的积木写入 output/artifacts/domain_bricks.jsonl
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# 路径设置：支持独立运行和从 worktree 运行
# ---------------------------------------------------------------------------

_HERE = Path(__file__).parent.resolve()
# 尝试找到 contracts 包（从 worktree 根目录或主仓库根目录）
for _candidate in [
    _HERE.parent.parent.parent.parent / "packages" / "contracts",
    _HERE.parent.parent.parent.parent.parent / "packages" / "contracts",
    Path(__file__).resolve().parent.parent.parent.parent.parent.parent
    / "packages" / "contracts",
]:
    if _candidate.exists() and str(_candidate) not in sys.path:
        sys.path.insert(0, str(_candidate))
        break

try:
    from doramagic_contracts.domain_graph import DomainBrick
    _CONTRACTS_AVAILABLE = True
except ImportError:
    _CONTRACTS_AVAILABLE = False
    DomainBrick = None  # type: ignore[assignment,misc]

# ---------------------------------------------------------------------------
# 框架名称 → 积木文件名的规范化映射
# 保持与 bricks/ 目录实际文件名一致
# ---------------------------------------------------------------------------

_FRAMEWORK_TO_BRICK_FILE: dict[str, str] = {
    # 直接对应
    "django": "django",
    "react": "react",
    # fastapi 和 flask 合并在一个文件中
    "fastapi": "fastapi_flask",
    "flask": "fastapi_flask",
    # 通用语言层
    "python": "python_general",
    "go": "go_general",
    "go module": "go_general",
    # 领域类
    "home assistant": "home_assistant",
    "obsidian": "obsidian_logseq",
    "logseq": "obsidian_logseq",
    "obsidian/logseq": "obsidian_logseq",
    # 纯领域（不直接来自框架检测，但保留以便手动传入）
    # AI frameworks
    "langchain": "langchain",
    "llamaindex": "llamaindex",
    "llama_index": "llamaindex",
    "llama-index": "llamaindex",
    "huggingface": "huggingface_transformers",
    "hugging face": "huggingface_transformers",
    "transformers": "huggingface_transformers",
    "vllm": "vllm",
    "crewai": "crewai",
    "crew ai": "crewai",
    "litellm": "litellm",
    "lite llm": "litellm",
    "ollama": "ollama",
    "langgraph": "langgraph",
    "lang graph": "langgraph",
    "llama.cpp": "llama_cpp",
    "llama cpp": "llama_cpp",
    "llamacpp": "llama_cpp",
    "diffusers": "diffusers",
    "openai": "openai_sdk",
    "openai sdk": "openai_sdk",
    "langfuse": "langfuse",
    "dspy": "dspy",
    # Web frameworks (non-AI first tier)
    "typescript": "typescript_nodejs",
    "nodejs": "typescript_nodejs",
    "node.js": "typescript_nodejs",
    "node": "typescript_nodejs",
    "nextjs": "nextjs",
    "next.js": "nextjs",
    "next js": "nextjs",
    "vuejs": "vuejs",
    "vue.js": "vuejs",
    "vue": "vuejs",
    "spring boot": "java_spring_boot",
    "spring": "java_spring_boot",
    "java": "java_spring_boot",
    # Second tier
    "ruby": "ruby_rails",
    "rails": "ruby_rails",
    "ruby on rails": "ruby_rails",
    "rust": "rust",
    "php": "php_laravel",
    "laravel": "php_laravel",
    "swift": "swift_ios",
    "ios": "swift_ios",
    "swiftui": "swift_ios",
    "kotlin": "kotlin_android",
    "android": "kotlin_android",
    "jetpack compose": "kotlin_android",
    "finance": "domain_finance",
    "health": "domain_health",
    "pkm": "domain_pkm",
    "private cloud": "domain_private_cloud",
    "info ingestion": "domain_info_ingestion",
    "self-hosted": "domain_private_cloud",
}

# 框架名称中包含这些子串时映射到对应文件
_FRAMEWORK_SUBSTRING_MAP: list[tuple[str, str]] = [
    # AI frameworks
    ("langchain", "langchain"),
    ("llamaindex", "llamaindex"),
    ("llama_index", "llamaindex"),
    ("huggingface", "huggingface_transformers"),
    ("transformers", "huggingface_transformers"),
    ("vllm", "vllm"),
    ("crewai", "crewai"),
    ("litellm", "litellm"),
    ("ollama", "ollama"),
    ("langgraph", "langgraph"),
    ("llama.cpp", "llama_cpp"),
    ("diffusers", "diffusers"),
    ("openai", "openai_sdk"),
    ("langfuse", "langfuse"),
    ("dspy", "dspy"),
    # Web frameworks
    ("typescript", "typescript_nodejs"),
    ("node.js", "typescript_nodejs"),
    ("nodejs", "typescript_nodejs"),
    ("next.js", "nextjs"),
    ("nextjs", "nextjs"),
    ("vue.js", "vuejs"),
    ("vuejs", "vuejs"),
    ("spring boot", "java_spring_boot"),
    ("spring", "java_spring_boot"),
    # Second tier
    ("ruby on rails", "ruby_rails"),
    ("rails", "ruby_rails"),
    ("laravel", "php_laravel"),
    ("swift", "swift_ios"),
    ("swiftui", "swift_ios"),
    ("kotlin", "kotlin_android"),
    ("android", "kotlin_android"),
    ("rust", "rust"),
    ("django", "django"),
    ("react", "react"),
    ("fastapi", "fastapi_flask"),
    ("flask", "fastapi_flask"),
    ("python", "python_general"),
    ("go", "go_general"),
    ("home_assistant", "home_assistant"),
    ("home assistant", "home_assistant"),
    ("obsidian", "obsidian_logseq"),
    ("logseq", "obsidian_logseq"),
]


# ---------------------------------------------------------------------------
# 结果数据类
# ---------------------------------------------------------------------------


@dataclass
class BrickInjectionResult:
    """积木注入结果。"""

    bricks_loaded: int
    """已成功加载的积木总数。"""

    frameworks_matched: list[str]
    """在积木库中找到对应文件的框架名称列表。"""

    frameworks_not_matched: list[str]
    """未找到对应积木文件的框架名称列表。"""

    injection_text: str
    """供注入 Stage 1/2/3 prompt 的文本。"""

    bricks_path: Optional[str]
    """domain_bricks.jsonl 的完整路径；若 output_dir=None 则为 None。"""

    raw_bricks: list[dict]
    """所有已加载积木的原始字典（未经 pydantic 验证）。"""


# ---------------------------------------------------------------------------
# 内部工具函数
# ---------------------------------------------------------------------------


def _normalize_framework_name(framework: str) -> str:
    """将框架名转为小写，去掉多余空格。"""
    return framework.strip().lower()


def _resolve_brick_filename(framework: str) -> str:
    """将框架名映射到积木文件名（不含 .jsonl 扩展名）。

    对于已知框架，返回精确文件名。对于未知框架，返回基于框架名的候选文件名（slug）。
    调用方应检查对应文件是否实际存在于 bricks/ 目录。
    """
    normalized = _normalize_framework_name(framework)

    # 精确匹配
    if normalized in _FRAMEWORK_TO_BRICK_FILE:
        return _FRAMEWORK_TO_BRICK_FILE[normalized]

    # 子串匹配（顺序重要：先匹配更具体的）
    for substr, filename in _FRAMEWORK_SUBSTRING_MAP:
        if substr in normalized:
            return filename

    # 尝试直接将框架名转换成文件名（下划线化）
    candidate = normalized.replace(" ", "_").replace("/", "_").replace("-", "_")
    return candidate  # 调用方会检查文件是否存在


def _load_bricks_from_file(jsonl_path: Path) -> list[dict]:
    """从 JSONL 文件加载积木原始字典列表。

    Args:
        jsonl_path: 积木 JSONL 文件的完整路径。

    Returns:
        积木字典列表；文件不存在或解析失败时返回空列表（不抛异常）。
    """
    if not jsonl_path.exists():
        return []

    bricks: list[dict] = []
    try:
        text = jsonl_path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                bricks.append(obj)
            except json.JSONDecodeError:
                # 跳过损坏行，继续加载其余行
                pass
    except OSError:
        # 文件读取失败（权限等），静默返回空列表
        pass

    return bricks


def _generate_injection_text(
    bricks: list[dict],
    frameworks_matched: list[str],
) -> str:
    """生成注入文本。

    格式：
    你已经知道以下框架基线知识（来自 Doramagic 积木库）：

    [Django] <statement>
    [React]  <statement>
    ...

    你的任务是发现这个具体项目在基线之上的独特做法。不要重复以上知识。
    """
    if not bricks:
        return ""

    lines: list[str] = [
        "你已经知道以下框架基线知识（来自 Doramagic 积木库）：",
        "",
    ]

    for brick in bricks:
        domain_id = brick.get("domain_id", "unknown")
        statement = brick.get("statement", "")
        if statement:
            # 用 domain_id 作为标签（如 [django]），首字母大写以便可读
            label = domain_id.replace("_", "-").replace("domain-", "").title()
            # 截断过长的 statement（保留前 200 字符）
            if len(statement) > 200:
                statement = statement[:197] + "..."
            lines.append(f"[{label}] {statement}")

    lines.append("")
    lines.append("你的任务是发现这个具体项目在基线之上的独特做法。不要重复以上知识。")

    return "\n".join(lines)


def _write_merged_bricks(
    bricks: list[dict],
    output_dir: str,
) -> str:
    """将合并后的积木写入 <output_dir>/artifacts/domain_bricks.jsonl。

    Args:
        bricks: 所有已加载积木的原始字典列表。
        output_dir: 输出根目录。

    Returns:
        写入文件的完整路径字符串。

    Raises:
        OSError: 写入失败时向上传播（调用方可决定是否处理）。
    """
    artifacts_dir = Path(output_dir) / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    output_path = artifacts_dir / "domain_bricks.jsonl"
    lines = [json.dumps(brick, ensure_ascii=False) for brick in bricks]
    output_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    return str(output_path)


# ---------------------------------------------------------------------------
# 主公开接口
# ---------------------------------------------------------------------------


def load_and_inject_bricks(
    frameworks: list[str],
    bricks_dir: str = "bricks/",
    output_dir: Optional[str] = None,
) -> BrickInjectionResult:
    """匹配框架 → 加载积木 → 写入 artifacts → 返回注入文本。

    Args:
        frameworks: 来自 repo_facts.frameworks 的框架名称列表，如 ["Django", "React"]。
        bricks_dir: 积木 JSONL 文件所在目录，默认为 "bricks/"（相对路径相对 CWD）。
        output_dir: 若提供，将合并积木写入 <output_dir>/artifacts/domain_bricks.jsonl。
                    若为 None，则不写文件。

    Returns:
        BrickInjectionResult 实例，包含加载统计、注入文本和文件路径。
    """
    bricks_path_obj = Path(bricks_dir).resolve()

    all_bricks: list[dict] = []
    frameworks_matched: list[str] = []
    frameworks_not_matched: list[str] = []
    # 用 set 避免重复加载同一文件（如 FastAPI + Flask 都映射到 fastapi_flask.jsonl）
    loaded_files: set[str] = set()

    for framework in frameworks:
        brick_filename = _resolve_brick_filename(framework)
        jsonl_path = bricks_path_obj / f"{brick_filename}.jsonl"

        if str(jsonl_path) in loaded_files:
            # 文件已加载过（如 FastAPI + Flask 同指一个文件），仍记录为已匹配
            if jsonl_path.exists():
                frameworks_matched.append(framework)
            else:
                frameworks_not_matched.append(framework)
            continue

        bricks = _load_bricks_from_file(jsonl_path)

        if bricks:
            all_bricks.extend(bricks)
            frameworks_matched.append(framework)
            loaded_files.add(str(jsonl_path))
        else:
            frameworks_not_matched.append(framework)

    # 生成注入文本
    injection_text = _generate_injection_text(all_bricks, frameworks_matched)

    # 写文件（若 output_dir 已提供）
    bricks_file_path: Optional[str] = None
    if output_dir is not None:
        bricks_file_path = _write_merged_bricks(all_bricks, output_dir)

    return BrickInjectionResult(
        bricks_loaded=len(all_bricks),
        frameworks_matched=frameworks_matched,
        frameworks_not_matched=frameworks_not_matched,
        injection_text=injection_text,
        bricks_path=bricks_file_path,
        raw_bricks=all_bricks,
    )


# ---------------------------------------------------------------------------
# CLI 入口（可选，便于调试）
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="积木注入 CLI")
    parser.add_argument(
        "--frameworks",
        nargs="+",
        default=["Django", "React"],
        help="框架名称列表，如 --frameworks Django React",
    )
    parser.add_argument(
        "--bricks-dir",
        default="bricks/",
        help="积木目录路径（默认: bricks/）",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="输出目录，若提供则写 domain_bricks.jsonl",
    )
    args = parser.parse_args()

    result = load_and_inject_bricks(
        frameworks=args.frameworks,
        bricks_dir=args.bricks_dir,
        output_dir=args.output_dir,
    )

    print(f"Bricks loaded: {result.bricks_loaded}")
    print(f"Frameworks matched: {result.frameworks_matched}")
    print(f"Frameworks not matched: {result.frameworks_not_matched}")
    if result.bricks_path:
        print(f"Output: {result.bricks_path}")
    print()
    print(result.injection_text)
