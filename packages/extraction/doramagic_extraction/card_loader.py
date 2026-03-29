"""卡片加载器 — 把 YAML frontmatter .md 文件解析为 confidence/DSD 可消费的 dict。

这是 Stage 3.5 增强和 Knowledge Compiler 的共享输入。
"""

import os
import re
from pathlib import Path


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """解析 YAML frontmatter，返回 (meta, body)。"""
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
            value = match.group(2).strip()
            if value == "|":
                meta[current_key] = ""
            elif value:
                value = value.strip('"').strip("'")
                try:
                    v = float(value)
                    value = int(v) if v == int(v) else v
                except (ValueError, TypeError):
                    pass
                meta[current_key] = value
            else:
                meta[current_key] = []
    return meta, body


def _sources_to_evidence_refs(sources: list) -> list[dict]:
    """将 sources 列表转换为 evidence_refs 格式。"""
    refs = []
    for src in sources:
        src_str = str(src)
        if re.search(r"#\d+|Issue\s*\d+", src_str, re.IGNORECASE):
            refs.append(
                {
                    "kind": "community_ref",
                    "path": src_str,
                    "source_url": src_str,
                }
            )
        elif ":" in src_str and not src_str.startswith("http"):
            # file:line reference like "src/dotenv/main.py:42"
            parts = src_str.split(":")
            ref = {"kind": "file_line", "path": parts[0].strip().strip('"')}
            if len(parts) > 1:
                try:
                    ref["start_line"] = int(parts[1].strip())
                    ref["end_line"] = ref["start_line"]
                except ValueError:
                    pass
            refs.append(ref)
        elif src_str.startswith("http"):
            refs.append(
                {
                    "kind": "community_ref",
                    "path": src_str,
                    "source_url": src_str,
                }
            )
        else:
            refs.append(
                {
                    "kind": "artifact_ref",
                    "path": src_str,
                    "artifact_name": src_str,
                }
            )
    return refs


def load_cards_from_dir(output_dir: str) -> list[dict]:
    """加载所有卡片 .md 文件，解析为 confidence/DSD 可消费的 dict 列表。"""
    soul_dir = os.path.join(output_dir, "soul")
    cards_dir = os.path.join(soul_dir, "cards")
    cards = []

    for subdir in ["concepts", "workflows", "rules"]:
        dirpath = os.path.join(cards_dir, subdir)
        if not os.path.isdir(dirpath):
            continue
        for fname in sorted(os.listdir(dirpath)):
            if not fname.endswith(".md"):
                continue
            filepath = os.path.join(dirpath, fname)
            text = Path(filepath).read_text(encoding="utf-8")
            meta, body = parse_frontmatter(text)

            # 构建 evidence_refs
            sources = meta.get("sources", [])
            if isinstance(sources, str):
                sources = [sources]
            evidence_refs = _sources_to_evidence_refs(sources)

            card = {
                "card_id": meta.get("card_id", fname.replace(".md", "")),
                "card_type": meta.get("card_type", "unknown"),
                "title": meta.get("title", ""),
                "severity": meta.get("severity", ""),
                "confidence": meta.get("confidence", ""),
                "rule": meta.get("rule", ""),
                "sources": sources,
                "evidence_refs": evidence_refs,
                "body": body,
                "_filepath": filepath,
                "_filename": fname,
                "_meta": meta,
            }
            cards.append(card)

    return cards
