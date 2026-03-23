#!/usr/bin/env python3
"""Doramagic Single-Shot v8.1 — Python does everything, LLM only displays.

核心改变：不再多轮中转，Python 全程干完，OpenClaw LLM 只展示最终结果。

流程：
  1. 解析用户输入 → 构建 need_profile（无需追问）
  2. 搜索三个信息源：GitHub repos + ClawHub skills + 本地 OpenClaw skills
  3. 下载 repos + 事实提取
  4. 对每个 repo 直接调 LLM API 做灵魂提取
  5. 收集社区信号（GitHub issues/PRs）
  6. 跨 repo 综合（含社区信号）
  7. Python 编译最终 Skill
  8. 输出 JSON（message 字段给用户看）

用法（被 SKILL.md 调用）：
    python3 doramagic_singleshot.py --input "用户消息" --run-dir ~/clawd/doramagic/runs/
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

# ── LLM API Config ──
LLM_API_URL = "https://coding.dashscope.aliyuncs.com/v1/chat/completions"
LLM_MODEL = "glm-5"


def _get_api_key():
    """Read API key from openclaw.json (bailian provider)."""
    config_path = Path.home() / ".openclaw" / "openclaw.json"
    with open(config_path) as f:
        cfg = json.load(f)
    return cfg["models"]["providers"]["bailian"]["apiKey"]


def _log(msg):
    print(f"[singleshot] {msg}", file=sys.stderr)


def _output(data):
    print(json.dumps(data, ensure_ascii=False))
    sys.exit(0)


# ── LLM API ──

def call_llm(system_prompt, user_prompt, max_tokens=4096):
    """Call LLM API directly via requests. Returns response text."""
    import requests

    resp = requests.post(
        LLM_API_URL,
        headers={
            "Authorization": "Bearer " + _get_api_key(),
            "Content-Type": "application/json",
        },
        json={
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.3,
        },
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def call_llm_json(system_prompt, user_prompt, max_tokens=4096):
    """Call LLM and parse JSON from response."""
    text = call_llm(system_prompt, user_prompt, max_tokens)
    # Extract JSON from markdown code blocks
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0]
    return json.loads(text.strip())


# ── Input Parsing ──

CN_TO_EN = {
    "记账": "expense tracker accounting",
    "学习": "learning education",
    "购物": "shopping ecommerce",
    "旅居": "digital nomad living abroad",
    "助手": "assistant tool helper",
    "工具": "tool utility",
    "翻译": "translation language",
    "健康": "health fitness tracker",
    "食谱": "recipe manager cooking",
    "家居": "smart home automation",
    "笔记": "note taking knowledge",
    "日程": "calendar schedule planner",
    "清迈": "chiang mai",
    "泰国": "thailand travel",
    "生活": "lifestyle daily planner",
    "交通": "transportation commute",
    "医疗": "healthcare medical",
    "社交": "social community",
    "AI": "AI artificial intelligence",
    "数据": "data analytics",
    "管理": "management organizer",
    "自动": "automation workflow",
    "个人": "personal productivity",
}


def build_need_profile(user_input):
    """Build need profile from user input in a single pass."""
    clean = re.sub(r"^/dora\s*", "", user_input).strip()

    # Extract keywords via CN→EN mapping
    keywords = []
    for cn, en in CN_TO_EN.items():
        if cn in clean:
            keywords.extend(en.split())

    # Deduplicate
    seen = set()
    unique = []
    for kw in keywords:
        low = kw.lower()
        if low not in seen:
            seen.add(low)
            unique.append(kw)

    # Ensure minimum keywords
    if len(unique) < 3:
        unique.extend(["open source", "tool", "assistant"])

    return {
        "keywords": unique[:8],
        "domain": "general",
        "intent": clean,
        "topic": clean[:50],
        "mode": "new",
    }


# ── ClawHub Search ──

CLAWHUB_API = "https://clawhub.ai/api/search"


def search_clawhub(keywords):
    """Search ClawHub skill registry. Returns list of relevant skills."""
    from urllib.request import Request, urlopen
    from urllib.error import URLError

    query = " ".join(keywords[:4])
    url = "%s?q=%s" % (CLAWHUB_API, query.replace(" ", "+"))
    _log("Searching ClawHub: %s" % query)

    try:
        req = Request(url, headers={"User-Agent": "Doramagic/8.1"})
        resp = urlopen(req, timeout=15)
        data = json.loads(resp.read().decode())
        results = data.get("results", [])
        # Keep top 5 relevant skills
        skills = []
        for r in results[:5]:
            skills.append({
                "slug": r.get("slug", ""),
                "name": r.get("displayName", r.get("slug", "")),
                "summary": r.get("summary", "")[:200],
                "score": r.get("score", 0),
                "source": "clawhub",
            })
        _log("ClawHub: found %d skills" % len(skills))
        return skills
    except (URLError, Exception) as e:
        _log("ClawHub search failed: %s" % e)
        return []


# ── Local Skills Scan ──


def scan_local_skills(keywords):
    """Scan ~/.openclaw/skills/ for locally installed relevant skills."""
    skills_dir = Path.home() / ".openclaw" / "skills"
    if not skills_dir.exists():
        return []

    query_lower = " ".join(keywords).lower()
    found = []
    for skill_dir in skills_dir.iterdir():
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        try:
            text = skill_md.read_text(errors="ignore")[:2000]
            # Check if any keyword matches in the skill description
            text_lower = text.lower()
            matches = sum(1 for kw in keywords if kw.lower() in text_lower)
            if matches > 0:
                # Extract name and description from frontmatter
                name = skill_dir.name
                desc = ""
                for line in text.split("\n"):
                    if line.strip().startswith("description:"):
                        desc = line.split(":", 1)[1].strip()[:200]
                        break
                found.append({
                    "name": name,
                    "summary": desc,
                    "path": str(skill_dir),
                    "relevance": matches,
                    "source": "local",
                })
        except Exception:
            continue

    found.sort(key=lambda x: x["relevance"], reverse=True)
    _log("Local skills: found %d relevant" % len(found))
    return found[:5]


# ── Community Signals ──


def collect_community_signals(repo_name, repo_url, repo_path=None):
    """Collect community signals for a repo via community_signals.py."""
    script = SCRIPT_DIR / "community_signals.py"
    if not script.exists():
        _log("community_signals.py not found")
        return None

    output_file = Path("/tmp/doramagic_signals_%s.json" % repo_name.replace("/", "-"))
    cmd = ["python3", str(script), "--repo-url", repo_url, "--output", str(output_file)]
    if repo_path:
        cmd.extend(["--repo-path", str(repo_path)])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            _log("Community signals failed for %s" % repo_name)
            return None
        if output_file.exists():
            with open(output_file) as f:
                return json.load(f)
    except Exception as e:
        _log("Community signals error for %s: %s" % (repo_name, e))
    return None


# ── Soul Extraction ──

SOUL_SYSTEM = """You are a design philosophy extractor. Given a project's README and source files, extract its design soul.

Output MUST be valid JSON with this exact schema:
{
  "project_name": "string",
  "design_philosophy": "string (2-4 sentences: the core BELIEF behind all design decisions, not a feature list)",
  "mental_model": "string (1-2 sentences: an analogy that makes the whole project click)",
  "why_decisions": [
    {"decision": "string", "evidence": "string (file/line reference or quote)", "confidence": "high|medium|low"}
  ],
  "unsaid_traps": [
    {"trap": "string (what the docs DON'T warn about)", "severity": "high|medium|low"}
  ]
}

Rules:
- design_philosophy: a BELIEF, not a feature description. Like the creator talking to a senior engineer.
- mental_model: an analogy or "aha" insight. If you could only tell someone ONE thing to make them "get" this project.
- why_decisions: 3-5 items with real evidence from the code/docs.
- unsaid_traps: 2-4 items users learn the hard way.
- Output ONLY valid JSON, no other text."""

SYNTHESIS_SYSTEM = """You are a cross-project knowledge synthesizer. Given soul extractions from multiple projects, find patterns.

Output MUST be valid JSON with this schema:
{
  "consensus_whys": [
    {"statement": "string (design principle most projects share)", "sources": ["repo1", "repo2"]}
  ],
  "divergent_whys": [
    {"statement": "string", "side_a": "repo1 approach", "side_b": "repo2 approach"}
  ],
  "combined_traps": [
    {"trap": "string", "severity": "high|medium|low", "source": "repo_name"}
  ],
  "recommendation": "string (50+ chars, actionable advice for a newcomer)",
  "skill_contract": {
    "purpose": "string (what the skill does for the user)",
    "capabilities": ["string (specific things the skill enables)"],
    "workflow_steps": ["string (how to use the skill)"]
  }
}

Output ONLY valid JSON, no other text."""


def read_repo_files(repo_dir, focus_files=None, max_chars=30000):
    """Read key files from a repo directory."""
    repo_path = Path(repo_dir)
    if not repo_path.exists():
        return ""

    parts = []
    total = 0

    # README first
    for name in ["README.md", "README.rst", "README.txt", "README"]:
        fp = repo_path / name
        if fp.exists():
            text = fp.read_text(errors="ignore")[:8000]
            parts.append("=== %s ===\n%s" % (name, text))
            total += len(text)
            break

    # Focus files
    for f in (focus_files or [])[:5]:
        fp = repo_path / f
        if fp.exists() and fp.stat().st_size < 50000:
            text = fp.read_text(errors="ignore")[:5000]
            if total + len(text) > max_chars:
                break
            parts.append("=== %s ===\n%s" % (f, text))
            total += len(text)

    return "\n\n".join(parts)


def extract_soul(repo_name, repo_dir, facts):
    """Extract soul from one repo via LLM API."""
    focus = facts.get("focus_files", [])
    content = read_repo_files(repo_dir, focus)
    if not content:
        _log("No readable files for %s" % repo_name)
        return None

    try:
        soul = call_llm_json(
            SOUL_SYSTEM,
            "Project: %s\n\n%s" % (repo_name, content),
            max_tokens=2000,
        )
        soul["project_name"] = repo_name
        return soul
    except Exception as e:
        _log("Soul extraction failed for %s: %s" % (repo_name, e))
        return None


def synthesize(souls, intent):
    """Cross-repo synthesis via LLM API."""
    try:
        return call_llm_json(
            SYNTHESIS_SYSTEM,
            "User intent: %s\n\nProject souls:\n%s"
            % (intent, json.dumps(souls, ensure_ascii=False, indent=2)),
            max_tokens=3000,
        )
    except Exception as e:
        _log("Synthesis failed: %s" % e)
        return None


# ── Compilation ──


def compile_skill(synthesis, souls, profile):
    """Compile into final SKILL.md content."""
    contract = synthesis.get("skill_contract", {})
    purpose = contract.get("purpose", profile.get("intent", ""))
    capabilities = contract.get("capabilities", [])
    workflow = contract.get("workflow_steps", [])
    consensus = synthesis.get("consensus_whys", [])
    traps = synthesis.get("combined_traps", [])
    recommendation = synthesis.get("recommendation", "")

    # Sanitize topic for skill name
    topic = profile.get("topic", "custom-skill")
    skill_name = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff_-]", "-", topic)[:30].strip("-")

    lines = [
        "---",
        "name: %s" % skill_name,
        "description: |",
        "  %s" % purpose,
        "version: 1.0.0",
        "tags: [doramagic-generated]",
        "---\n",
        "# %s\n" % topic,
        "## Purpose\n%s\n" % purpose,
    ]

    if capabilities:
        lines.append("## Capabilities")
        for c in capabilities:
            lines.append("- %s" % c)
        lines.append("")

    if consensus:
        lines.append("## WHY — Design Wisdom")
        for w in consensus:
            src = ", ".join(w.get("sources", []))
            lines.append("- **%s** (from: %s)" % (w["statement"], src))
        lines.append("")

    if traps:
        lines.append("## UNSAID — Hidden Traps")
        for t in traps:
            sev = t.get("severity", "medium").upper()
            lines.append(
                "- [%s] %s (source: %s)" % (sev, t["trap"], t.get("source", "?"))
            )
        lines.append("")

    if workflow:
        lines.append("## Workflow")
        for i, step in enumerate(workflow, 1):
            lines.append("%d. %s" % (i, step))
        lines.append("")

    if recommendation:
        lines.append("## Recommendation\n%s\n" % recommendation)

    lines.append("## Provenance")
    lines.append("| Project | Philosophy | Mental Model |")
    lines.append("|---------|-----------|-------------|")
    for soul in souls:
        name = soul.get("project_name", "?")
        phil = soul.get("design_philosophy", "?")[:80]
        model = soul.get("mental_model", "?")[:80]
        lines.append("| %s | %s | %s |" % (name, phil, model))
    lines.append("")

    lines.append("---")
    lines.append(
        "*Generated by Doramagic v8.0 — \u4e0d\u6559\u7528\u6237\u505a\u4e8b\uff0c\u7ed9\u4ed6\u5de5\u5177\u3002*"
    )
    return "\n".join(lines)


# ── Main ──


def main():
    parser = argparse.ArgumentParser(description="Doramagic Single-Shot v8.0")
    parser.add_argument("--input", required=True, help="User input text")
    parser.add_argument("--run-dir", required=True, help="Base run directory")
    args = parser.parse_args()

    run_dir = Path(os.path.expanduser(args.run_dir))
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    rd = run_dir / run_id
    rd.mkdir(parents=True, exist_ok=True)

    _log("Starting run %s" % run_id)

    # ── Step 1: Build profile ──
    profile = build_need_profile(args.input)
    with open(rd / "need_profile.json", "w") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)
    _log("Profile: keywords=%s" % profile["keywords"])

    # ── Step 2: Search all sources ──

    # 2a: ClawHub skill registry
    clawhub_skills = search_clawhub(profile["keywords"])
    with open(rd / "clawhub_results.json", "w") as f:
        json.dump(clawhub_skills, f, ensure_ascii=False, indent=2)

    # 2b: Local OpenClaw skills
    local_skills = scan_local_skills(profile["keywords"])
    with open(rd / "local_skills.json", "w") as f:
        json.dump(local_skills, f, ensure_ascii=False, indent=2)

    # 2c: GitHub repos via engine
    engine = SCRIPT_DIR / "doramagic_engine.py"
    _log("Running engine...")

    repos = []
    engine_out = {}
    try:
        result = subprocess.run(
            [
                "python3",
                str(engine),
                "--need",
                str(rd / "need_profile.json"),
                "--output",
                str(rd),
                "--top",
                "3",
            ],
            capture_output=True,
            text=True,
            timeout=360,
        )
        if result.returncode == 0 and result.stdout.strip():
            engine_out = json.loads(result.stdout)
            repos = engine_out.get("repos", engine_out.get("repos_analyzed", []))
        else:
            _log("Engine returned no repos: %s" % result.stderr[-200:])
    except subprocess.TimeoutExpired:
        _log("Engine timed out, continuing with other sources")
    except Exception as e:
        _log("Engine error: %s, continuing with other sources" % e)

    total_sources = len(repos) + len(clawhub_skills) + len(local_skills)
    _log("Sources: %d repos, %d ClawHub skills, %d local skills" % (
        len(repos), len(clawhub_skills), len(local_skills)
    ))

    if total_sources == 0:
        _output(
            {"message": "三个信息源（GitHub、ClawHub、本地 Skills）都没有找到相关内容。试试换个描述？", "error": True}
        )

    # ── Step 3: Soul extraction ──
    souls = []
    for repo in repos:
        name = repo.get("name", "unknown")
        local_dir = repo.get("local_dir") or repo.get("local_path", "")
        facts = repo.get("facts", {})

        _log("Extracting soul: %s" % name)
        soul = extract_soul(name, local_dir, facts)
        if soul:
            souls.append(soul)
            staging = rd / "staging" / name.replace("/", "-")
            staging.mkdir(parents=True, exist_ok=True)
            with open(staging / "repo_soul.json", "w") as f:
                json.dump(soul, f, ensure_ascii=False, indent=2)

    # Also treat ClawHub skills as lightweight "souls"
    for skill in clawhub_skills:
        souls.append({
            "project_name": "clawhub:%s" % skill["slug"],
            "design_philosophy": skill.get("summary", ""),
            "mental_model": "ClawHub skill: %s" % skill.get("name", ""),
            "why_decisions": [],
            "unsaid_traps": [],
            "source": "clawhub",
        })

    # Also include relevant local skills
    for skill in local_skills:
        souls.append({
            "project_name": "local:%s" % skill["name"],
            "design_philosophy": skill.get("summary", ""),
            "mental_model": "Locally installed skill: %s" % skill.get("name", ""),
            "why_decisions": [],
            "unsaid_traps": [],
            "source": "local",
        })

    if not souls:
        _output(
            {
                "message": "所有信息源都无法提取有效内容。找到了 %d 个项目但无法分析。" % total_sources,
                "error": True,
            }
        )

    _log("Total souls: %d (repos=%d, clawhub=%d, local=%d)" % (
        len(souls), len(souls) - len(clawhub_skills) - len(local_skills),
        len(clawhub_skills), len(local_skills)
    ))

    # ── Step 4: Community signals ──
    all_signals = []
    for repo in repos:
        repo_url = repo.get("url", "")
        repo_name = repo.get("name", "")
        local_dir = repo.get("local_dir") or repo.get("local_path", "")
        if repo_url:
            _log("Collecting community signals: %s" % repo_name)
            signals = collect_community_signals(repo_name, repo_url, local_dir)
            if signals and signals.get("signals"):
                all_signals.extend(signals["signals"][:5])
                # Enrich the corresponding soul with community data
                for soul in souls:
                    if soul["project_name"] == repo_name:
                        for sig in signals["signals"][:3]:
                            soul.setdefault("unsaid_traps", []).append({
                                "trap": "Community issue: %s (comments: %s)"
                                % (sig.get("title", ""), sig.get("comment_count", 0)),
                                "severity": "medium" if sig.get("tier", 3) > 1 else "high",
                            })

    if all_signals:
        with open(rd / "community_signals.json", "w") as f:
            json.dump(all_signals, f, ensure_ascii=False, indent=2)
    _log("Community signals: %d collected" % len(all_signals))

    # ── Step 5: Synthesis ──
    _log("Synthesizing...")
    syn = synthesize(souls, profile["intent"])

    if not syn:
        # Fallback: use best soul
        best = max(souls, key=lambda s: len(s.get("why_decisions", [])))
        syn = {
            "consensus_whys": [
                {
                    "statement": best.get("design_philosophy", ""),
                    "sources": [best["project_name"]],
                }
            ],
            "divergent_whys": [],
            "combined_traps": [
                {"trap": t["trap"], "severity": t.get("severity", "medium"), "source": best["project_name"]}
                for t in best.get("unsaid_traps", [])
            ],
            "recommendation": best.get("mental_model", ""),
            "skill_contract": {
                "purpose": profile["intent"],
                "capabilities": [
                    d["decision"] for d in best.get("why_decisions", [])[:3]
                ],
                "workflow_steps": [],
            },
        }

    with open(rd / "staging" / "synthesis.json", "w") as f:
        json.dump(syn, f, ensure_ascii=False, indent=2)

    # ── Step 6: Compile ──
    _log("Compiling skill...")
    skill_md = compile_skill(syn, souls, profile)

    delivery = rd / "delivery"
    delivery.mkdir(parents=True, exist_ok=True)
    with open(delivery / "SKILL.md", "w") as f:
        f.write(skill_md)

    # ── Step 7: Output ──
    _log("Done!")

    contract = syn.get("skill_contract", {})
    capabilities = contract.get("capabilities", [])
    consensus = syn.get("consensus_whys", [])
    traps = syn.get("combined_traps", [])

    # Categorize sources
    repo_souls = [s for s in souls if s.get("source") != "clawhub" and s.get("source") != "local"]
    ch_souls = [s for s in souls if s.get("source") == "clawhub"]
    local_souls = [s for s in souls if s.get("source") == "local"]

    msg = []
    msg.append("**Doramagic 道具锻造完成！**\n")
    msg.append("**主题**: %s" % profile.get("topic", ""))

    source_parts = []
    if repo_souls:
        source_parts.append("%d 个 GitHub 项目" % len(repo_souls))
    if ch_souls:
        source_parts.append("%d 个 ClawHub Skills" % len(ch_souls))
    if local_souls:
        source_parts.append("%d 个本地 Skills" % len(local_souls))
    if all_signals:
        source_parts.append("%d 条社区信号" % len(all_signals))
    msg.append("**信息源**: %s\n" % "、".join(source_parts))

    if repo_souls:
        msg.append("**GitHub**: %s" % ", ".join(s["project_name"] for s in repo_souls))
    if ch_souls:
        msg.append("**ClawHub**: %s" % ", ".join(s["project_name"].replace("clawhub:", "") for s in ch_souls))

    if capabilities:
        msg.append("\n**核心能力**:")
        for c in capabilities[:5]:
            msg.append("  - %s" % c)

    if consensus:
        msg.append("\n**WHY — 设计智慧**:")
        for w in consensus[:3]:
            msg.append("  - %s" % w["statement"])

    if traps:
        msg.append("\n**UNSAID — 暗雷**:")
        for t in traps[:5]:
            msg.append(
                "  - [%s] %s" % (t.get("severity", "?").upper(), t["trap"])
            )

    msg.append("\n完整 Skill 已保存: `%s/SKILL.md`" % delivery)
    msg.append("\n这是一个**道具**（Skill），可以注入你的 AI 助手，让它在相关领域变得更聪明。")

    _output(
        {
            "message": "\n".join(msg),
            "delivery_path": str(delivery),
            "run_id": run_id,
            "repos_analyzed": len(souls),
        }
    )


if __name__ == "__main__":
    main()
