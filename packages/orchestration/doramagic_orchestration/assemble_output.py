#!/usr/bin/env python3
"""
Doramagic v1.1: 统一组装脚本（Python 版，替代 assemble-output.sh）
组装 CLAUDE.md / .cursorrules / advisor-brief.md / project_soul.md

所有模型均可调用此脚本（解决 MiniMax 跳过 shell 导致 FEATURE INVENTORY 丢失的问题）。

Usage:
    python3 assemble_output.py --output-dir <output_dir>
"""

import argparse
import json
import os
import re
import sys
from datetime import date


def load_json(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def load_text(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    return None


def parse_card_frontmatter(text):
    """解析 YAML frontmatter（最小实现，无外部依赖）。"""
    if not text.startswith("---"):
        return {}, text
    end = text.find("---", 3)
    if end == -1:
        return {}, text
    yaml_block = text[3:end].strip()
    body = text[end + 3 :].strip()
    meta = {}
    current_key = None
    for line in yaml_block.split("\n"):
        stripped = line.strip()
        if stripped.startswith("- ") and current_key:
            if current_key not in meta:
                meta[current_key] = []
            item = stripped[2:].strip().strip('"').strip("'")
            if isinstance(meta[current_key], list):
                meta[current_key].append(item)
            continue
        match = re.match(r"^([a-z_]+):\s*(.*)", line)
        if match:
            current_key = match.group(1)
            value = match.group(2).strip().strip('"').strip("'")
            if value and value != "|":
                try:
                    v = float(value)
                    value = int(v) if v == int(v) else v
                except (ValueError, TypeError):
                    pass
                meta[current_key] = value
            elif not value:
                meta[current_key] = []
    return meta, body


def check_validation_gate(soul_dir):
    """检查 validation_report.json 是否 PASS。"""
    report_path = os.path.join(soul_dir, "validation_report.json")
    if not os.path.exists(report_path):
        print("ERROR: No validation report found. Run Stage 3.5 first.", file=sys.stderr)
        return False
    report = load_json(report_path)
    if not report or not report.get("summary", {}).get("overall_pass", False):
        print(
            "ERROR: Validation did not pass. Fix errors in Stage 3.5 before assembling.",
            file=sys.stderr,
        )
        return False
    return True


def load_cards(soul_dir):
    """加载所有卡片的 frontmatter + body。"""
    cards_dir = os.path.join(soul_dir, "cards")
    cards = []
    for subdir in ["concepts", "workflows", "rules"]:
        dirpath = os.path.join(cards_dir, subdir)
        if not os.path.isdir(dirpath):
            continue
        for fname in sorted(os.listdir(dirpath)):
            if not fname.endswith(".md"):
                continue
            text = load_text(os.path.join(dirpath, fname))
            if text:
                meta, body = parse_card_frontmatter(text)
                meta["_filename"] = fname
                cards.append((meta, body))
    return cards


def build_critical_rules(cards):
    """构建 CRITICAL RULES section。"""
    lines = [
        "## CRITICAL RULES",
        "",
        "以下规则从代码分析和社区经验中提取，按严重度排序。",
        "",
    ]
    for severity in ["CRITICAL", "HIGH"]:
        for meta, body in cards:
            if meta.get("card_type") != "decision_rule_card":
                continue
            card_sev = str(meta.get("severity", "")).upper()
            if card_sev != severity:
                continue
            title = meta.get("title", meta.get("_filename", ""))
            rule = str(meta.get("rule", ""))
            # 取 rule 的前两行
            rule_lines = [l.strip() for l in rule.split("\n") if l.strip()][:2]
            rule_text = " ".join(rule_lines)
            lines.append(f"- **[{severity}]** {title} — {rule_text}")
    lines.append("")
    return "\n".join(lines)


def build_feature_inventory(output_dir):
    """构建 FEATURE INVENTORY section（从 repo_facts.json）。"""
    facts = load_json(os.path.join(output_dir, "artifacts", "repo_facts.json"))
    if not facts:
        return ""
    lines = ["## FEATURE INVENTORY", ""]
    skills = facts.get("skills") or facts.get("entrypoints", [])
    commands = facts.get("commands", [])
    config_keys = facts.get("config_keys") or facts.get("storage_paths", [])
    if skills:
        lines.append("**Skills / Features:**")
        for s in skills:
            lines.append(f"- `{s}`")
        lines.append("")
    if commands:
        lines.append("**Commands:**")
        for c in commands[:20]:
            lines.append(f"- `{c}`")
        lines.append("")
    if config_keys:
        lines.append("**Config Keys:**")
        for k in config_keys[:15]:
            lines.append(f"- `{k}`")
        lines.append("")
    return "\n".join(lines)


def build_quick_reference(cards):
    """构建 QUICK REFERENCE 速查表。"""
    lines = [
        "## QUICK REFERENCE",
        "",
        "| 规则 | 严重度 |",
        "|------|--------|",
    ]
    for meta, body in cards:
        if meta.get("card_type") != "decision_rule_card":
            continue
        title = meta.get("title", meta.get("_filename", ""))
        sev = str(meta.get("severity", "-")).upper()
        lines.append(f"| {title} | {sev} |")
    lines.append("")
    return "\n".join(lines)


def build_card_index(cards):
    """构建知识卡片索引表。"""
    lines = [
        "## 知识卡片索引",
        "",
        "| ID | 类型 | 标题 | 严重度 |",
        "|----|------|------|--------|",
    ]
    type_map = {"CC": "概念", "WF": "工作流", "DR": "规则"}
    for meta, body in cards:
        card_id = str(meta.get("card_id", meta.get("_filename", "")))
        prefix = card_id.split("-")[0] if "-" in card_id else ""
        card_type = type_map.get(prefix, "其他")
        title = meta.get("title", card_id)
        sev = str(meta.get("severity", "-"))
        lines.append(f"| {card_id} | {card_type} | {title} | {sev} |")
    lines.append("")
    return "\n".join(lines)


def build_advisor_brief(soul_dir, repo_name):
    """构建 advisor-brief.md（非技术用户简介）。"""
    soul_content = load_text(os.path.join(soul_dir, "00-soul.md")) or ""

    # 提取核心承诺（Q3）
    promise = ""
    m = re.search(
        r"(?:核心承诺|Core Promise|3\.|Q3)[^\n]*\n+(.*?)(?=\n##|\n\d\.|\Z)", soul_content, re.DOTALL
    )
    if m:
        promise = m.group(1).strip()[:200]

    # 提取一句话总结（Q5）
    oneliner = ""
    m = re.search(
        r"(?:一句话总结|One.liner|5\.|Q5)[^\n]*\n+(.*?)(?=\n##|\n\d\.|\Z)", soul_content, re.DOTALL
    )
    if m:
        oneliner = m.group(1).strip()[:200]

    # 统计
    module_map = load_text(os.path.join(soul_dir, "module-map.md")) or ""
    module_count = len(re.findall(r"^### M-\d+", module_map, re.MULTILINE))
    community = load_text(os.path.join(soul_dir, "community-wisdom.md")) or ""
    pain_count = len(re.findall(r"^### 痛点", community, re.MULTILINE))

    # 统计 CRITICAL 规则
    cards_dir = os.path.join(soul_dir, "cards", "rules")
    critical_count = 0
    if os.path.isdir(cards_dir):
        for fname in os.listdir(cards_dir):
            if not fname.endswith(".md"):
                continue
            text = load_text(os.path.join(cards_dir, fname)) or ""
            if re.search(r"severity:\s*CRITICAL", text, re.IGNORECASE):
                critical_count += 1

    lines = [
        f"# {repo_name} — AI 顾问简介",
        "",
        f"> 由 Doramagic 从 {repo_name} 开源项目中提取，注入AI，生成专属顾问。",
        "",
        "## 这位顾问能帮你做什么",
        "",
    ]
    if oneliner:
        lines.append(f"**一句话**：{oneliner}")
        lines.append("")
    if promise:
        lines.append(f"**核心承诺**：{promise}")
        lines.append("")
    lines.append("这位 AI 顾问掌握了：")
    lines.append('- 项目的设计哲学和心智模型（知道"为什么"，不只是"怎么用"）')
    if module_count:
        lines.append(f"- {module_count} 个核心模块的边界和接口")
    if critical_count:
        lines.append(f"- {critical_count} 个最高风险陷阱（遇到前主动提醒你）")
    if pain_count:
        lines.append(f"- {pain_count} 个社区反复踩坑的模式")
    lines += [
        "",
        "## 适合问这位顾问的问题",
        "",
        "- \u201c我应该用 [A 方案] 还是 [B 方案]？\u201d",
        "- \u201c我遇到了 [报错]，这是什么问题，怎么排查？\u201d",
        "- \u201c[某功能] 有什么限制或注意事项？\u201d",
        "- \u201c我想做 [X]，这个项目支持吗？最佳做法是什么？\u201d",
        "",
        "---",
        "*由 Doramagic v1.1 自动生成*",
    ]
    return "\n".join(lines)


def assemble(output_dir):
    """主组装逻辑。"""
    soul_dir = os.path.join(output_dir, "soul")
    inject_dir = os.path.join(output_dir, "inject")
    os.makedirs(inject_dir, exist_ok=True)
    repo_name = os.path.basename(os.path.abspath(output_dir))

    # 检查验证门
    if not check_validation_gate(soul_dir):
        return False

    # 检查必需文件
    narrative_path = os.path.join(soul_dir, "expert_narrative.md")
    compiled_path = os.path.join(soul_dir, "compiled_knowledge.md")
    module_map_path = os.path.join(soul_dir, "module-map.md")
    community_path = os.path.join(soul_dir, "community-wisdom.md")

    # 优先用 compiled_knowledge.md（Knowledge Compiler 输出），fallback 到 expert_narrative.md
    knowledge_content = load_text(compiled_path) or load_text(narrative_path)
    if not knowledge_content:
        print(
            "ERROR: Neither compiled_knowledge.md nor expert_narrative.md found.", file=sys.stderr
        )
        return False
    if not os.path.exists(module_map_path):
        print("ERROR: module-map.md not found. Run Stage M first.", file=sys.stderr)
        return False
    if not os.path.exists(community_path):
        print("ERROR: community-wisdom.md not found. Run Stage C first.", file=sys.stderr)
        return False

    module_map = load_text(module_map_path)
    community = load_text(community_path)
    cards = load_cards(soul_dir)

    # 构建各段
    critical_rules = build_critical_rules(cards)
    feature_inventory = build_feature_inventory(output_dir)
    quick_reference = build_quick_reference(cards)

    # 模块段（去掉 H1 标题）
    module_lines = module_map.split("\n")
    module_body = "\n".join(module_lines[2:]) if len(module_lines) > 2 else module_map

    # 社区段（去掉 H1 标题）
    community_lines = community.split("\n")
    community_body = "\n".join(community_lines[2:]) if len(community_lines) > 2 else community

    # 组装 CLAUDE.md
    claude_md = "\n".join(
        [
            f"# {repo_name} — Doramagic AI Advisor Pack",
            "# Generated by Doramagic v1.1 | Three-module: Soul + Architecture + Community",
            "# Structure: CRITICAL RULES → FEATURE INVENTORY → MODULE MAP → EXPERT KNOWLEDGE → COMMUNITY WISDOM → QUICK REFERENCE",
            "",
            critical_rules,
            feature_inventory,
            "## MODULE MAP",
            "",
            module_body,
            "",
            "## EXPERT KNOWLEDGE",
            "",
            knowledge_content,
            "",
            "## COMMUNITY WISDOM",
            "",
            community_body,
            "",
            quick_reference,
        ]
    )

    # 写文件
    claude_path = os.path.join(inject_dir, "CLAUDE.md")
    with open(claude_path, "w", encoding="utf-8") as f:
        f.write(claude_md)
    print(f"  -> {claude_path}")

    # .cursorrules
    cursorrules_path = os.path.join(inject_dir, ".cursorrules")
    with open(cursorrules_path, "w", encoding="utf-8") as f:
        f.write(claude_md)
    print(f"  -> {cursorrules_path}")

    # advisor-brief.md
    brief_content = build_advisor_brief(soul_dir, repo_name)
    brief_path = os.path.join(inject_dir, "advisor-brief.md")
    with open(brief_path, "w", encoding="utf-8") as f:
        f.write(brief_content)
    print(f"  -> {brief_path}")

    # project_soul.md
    card_index = build_card_index(cards)
    soul_summary = (
        claude_md
        + "\n---\n\n"
        + card_index
        + f"\n---\n*Generated by Doramagic v1.1 {date.today()}*\n"
    )
    soul_path = os.path.join(soul_dir, "project_soul.md")
    with open(soul_path, "w", encoding="utf-8") as f:
        f.write(soul_summary)
    print(f"  -> {soul_path}")

    # 统计
    cc = sum(1 for m, _ in cards if str(m.get("card_id", "")).startswith("CC"))
    wf = sum(1 for m, _ in cards if str(m.get("card_id", "")).startswith("WF"))
    dr = sum(1 for m, _ in cards if str(m.get("card_id", "")).startswith("DR"))
    print("\n=== DORAMAGIC ASSEMBLY COMPLETE ===")
    print(f"repo={repo_name}")
    print(f"output_size={len(claude_md)} bytes")
    print(f"concepts={cc} workflows={wf} rules={dr}")
    print(f"inject={inject_dir}")
    print(
        f"knowledge_source={'compiled_knowledge.md' if os.path.exists(compiled_path) else 'expert_narrative.md'}"
    )
    return True


def main():
    parser = argparse.ArgumentParser(description="Doramagic: Assemble final output")
    parser.add_argument("--output-dir", required=True, help="Path to extraction output directory")
    args = parser.parse_args()

    print(
        f"=== Doramagic v1.1: Assembling output for {os.path.basename(os.path.abspath(args.output_dir))} ==="
    )
    success = assemble(args.output_dir)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
