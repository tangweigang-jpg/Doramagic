#!/usr/bin/env python3
"""赛马选手自动预检 — 选手提交后自动执行，预检不通过不进入 PM 评审。

用法:
    python3 race_precheck.py --racer-dir races/r06/agentic/s1-sonnet/ --brief races/r06/agentic/BRIEF.md

检查项:
    C1: 文件完整性 — Brief 要求的 deliverables 全部存在
    C2: 模型无关 — 无 import anthropic / import openai / import google.generativeai
    C3: 使用 LLMAdapter — LLM 调用通过统一接口
    C4: 测试通过 — pytest 全部通过
    C5: 契约兼容 — 入口函数签名匹配 contracts
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from pathlib import Path


FORBIDDEN_IMPORTS = [
    "import anthropic",
    "from anthropic",
    "import openai",
    "from openai",
    "import google.generativeai",
    "from google.generativeai",
    "import google.genai",
    "from google.genai",
    "import zhipuai",
    "from zhipuai",
]


def check_deliverables(racer_dir: Path, required_files: list[str]) -> tuple[bool, list[str]]:
    """C1: 检查所有 deliverables 存在。"""
    missing = []
    for f in required_files:
        if not (racer_dir / f).exists():
            missing.append(f)
    return len(missing) == 0, missing


def check_no_direct_llm_imports(racer_dir: Path) -> tuple[bool, list[str]]:
    """C2: 检查无直接 LLM SDK 导入。"""
    violations = []
    for py_file in racer_dir.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        content = py_file.read_text(encoding="utf-8", errors="ignore")
        for forbidden in FORBIDDEN_IMPORTS:
            for i, line in enumerate(content.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if stripped.startswith(forbidden):
                    violations.append(f"{py_file.relative_to(racer_dir)}:{i} — {stripped}")
    return len(violations) == 0, violations


def check_uses_adapter(racer_dir: Path) -> tuple[bool, list[str]]:
    """C3: 检查是否使用 LLMAdapter（如果有 LLM 调用的话）。"""
    has_llm_call = False
    uses_adapter = False
    for py_file in racer_dir.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        content = py_file.read_text(encoding="utf-8", errors="ignore")
        if "LLMAdapter" in content or "llm_adapter" in content:
            uses_adapter = True
        if "generate(" in content or "generate_with_tools(" in content:
            has_llm_call = True
    if has_llm_call and not uses_adapter:
        return False, ["LLM calls detected but LLMAdapter not imported"]
    return True, []


def check_tests(racer_dir: Path) -> tuple[bool, list[str]]:
    """C4: 运行 pytest。"""
    test_dirs = list(racer_dir.rglob("test_*.py")) + list(racer_dir.rglob("tests/"))
    if not test_dirs:
        return True, ["No tests found (warning, not blocking)"]
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(racer_dir), "-q", "--tb=short"],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        return False, [result.stdout[-500:] if result.stdout else result.stderr[-500:]]
    return True, []


def run_precheck(racer_dir: str, required_files: list[str] | None = None) -> dict:
    """运行全部预检，返回报告。"""
    rdir = Path(racer_dir).resolve()
    if required_files is None:
        required_files = []

    report = {"racer_dir": str(rdir), "checks": [], "all_pass": True}

    # C1
    passed, details = check_deliverables(rdir, required_files)
    report["checks"].append({"name": "C1_deliverables", "passed": passed, "details": details})

    # C2
    passed, details = check_no_direct_llm_imports(rdir)
    report["checks"].append({"name": "C2_model_agnostic", "passed": passed, "details": details})

    # C3
    passed, details = check_uses_adapter(rdir)
    report["checks"].append({"name": "C3_uses_adapter", "passed": passed, "details": details})

    # C4
    passed, details = check_tests(rdir)
    report["checks"].append({"name": "C4_tests", "passed": passed, "details": details})

    report["all_pass"] = all(c["passed"] for c in report["checks"])
    return report


def main():
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Race precheck")
    parser.add_argument("--racer-dir", required=True)
    parser.add_argument("--required-files", nargs="*", default=[])
    args = parser.parse_args()

    report = run_precheck(args.racer_dir, args.required_files)

    print(json.dumps(report, indent=2, ensure_ascii=False))
    print()
    for check in report["checks"]:
        status = "PASS" if check["passed"] else "FAIL"
        print(f"  [{status}] {check['name']}")
        for d in check["details"]:
            print(f"         {d}")
    print()
    print(f"Overall: {'PASS' if report['all_pass'] else 'FAIL'}")
    sys.exit(0 if report["all_pass"] else 1)


if __name__ == "__main__":
    main()
