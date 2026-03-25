#!/usr/bin/env python3
"""生成自包含的 Gemini 赛马 prompt — 把 Brief + 关键 contracts 内联。

Gemini 不主动深度阅读引用文件，所以把必要上下文直接塞进 prompt。

Usage:
    python3 generate_gemini_prompt.py --race injection --racer s3-gemini
    python3 generate_gemini_prompt.py --race runner --racer s3-gemini
"""

import argparse
import os
from pathlib import Path

DORAMAGIC = Path(__file__).parent.parent.parent

def read_file(path):
    p = DORAMAGIC / path
    if p.exists():
        return p.read_text(encoding="utf-8")
    return f"[FILE NOT FOUND: {path}]"

CONTEXT_FILES = {
    "injection": [
        "races/r06/injection/BRIEF.md",
        "packages/contracts/doramagic_contracts/domain_graph.py",
        "packages/contracts/doramagic_contracts/base.py",
    ],
    "runner": [
        "races/r06/runner/BRIEF.md",
        "packages/contracts/doramagic_contracts/extraction.py",
        "packages/contracts/doramagic_contracts/envelope.py",
        "packages/shared_utils/doramagic_shared_utils/llm_adapter.py",
        "packages/shared_utils/doramagic_shared_utils/capability_router.py",
    ],
    "compiler": [
        "races/r06/compiler/BRIEF.md",
        "packages/contracts/doramagic_contracts/base.py",
    ],
    "confidence": [
        "races/r06/confidence/BRIEF.md",
        "packages/contracts/doramagic_contracts/base.py",
        "packages/contracts/doramagic_contracts/extraction.py",
    ],
}

def generate_prompt(race: str, racer: str) -> str:
    files = CONTEXT_FILES.get(race, [])
    sections = []
    sections.append(f"# 赛马任务: {race} (选手: {racer})")
    sections.append("")
    sections.append("以下是完整的任务说明和所有需要的上下文。请直接开始编码。")
    sections.append(f"所有输出文件写到: races/r06/{race}/{racer}/")
    sections.append("")

    for fpath in files:
        content = read_file(fpath)
        sections.append(f"--- FILE: {fpath} ---")
        sections.append(content)
        sections.append(f"--- END FILE ---")
        sections.append("")

    sections.append("## 关键约束")
    sections.append("1. 不能 import anthropic / import openai / from google.generativeai")
    sections.append("2. 所有 LLM 调用通过 LLMAdapter（如果需要 LLM 的话）")
    sections.append("3. 纯确定性模块不需要 LLM")
    sections.append(f"4. 输出路径: races/r06/{race}/{racer}/")
    sections.append("")
    sections.append("## 验收清单")
    sections.append("- [ ] 主实现 .py 文件")
    sections.append("- [ ] tests/ 目录下的测试文件")
    sections.append("- [ ] DECISIONS.md 设计决策文档")
    sections.append("- [ ] 所有测试通过")
    sections.append(f"- [ ] 文件都在 races/r06/{race}/{racer}/ 下（不要写到其他位置）")

    return "\n".join(sections)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--race", required=True, choices=list(CONTEXT_FILES.keys()))
    parser.add_argument("--racer", default="s3-gemini")
    args = parser.parse_args()

    prompt = generate_prompt(args.race, args.racer)
    out_path = DORAMAGIC / f"races/r06/{args.race}/{args.racer}_prompt.md"
    out_path.write_text(prompt, encoding="utf-8")
    print(f"Prompt written to: {out_path}")
    print(f"Length: {len(prompt)} chars, ~{len(prompt)//4} tokens")
    print(f"\n用法: 把 {out_path} 的内容粘贴给 Gemini")


if __name__ == "__main__":
    main()
