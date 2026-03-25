#!/usr/bin/env python3
"""Doramagic Single-Shot v9.0 — LLM-powered discovery + actionable skill output.

v9.0 changes:
  - build_need_profile() uses LLM to generate GitHub search keywords (fixes "WiFi密码管理" bug)
  - Relevance gate after discovery: irrelevant repos are filtered, honest "not found" report
  - compile_skill() outputs AI agent instruction set, not research report

流程：
  1. 解析用户输入 → LLM 生成搜索关键词 + 相关性判定词（fallback: 静态字典）
  2. 搜索三个信息源：GitHub repos + ClawHub skills + 本地 OpenClaw skills
  3. 相关性门控：过滤不相关结果，搜不到就诚实报告
  4. 对每个 repo 直接调 LLM API 做灵魂提取
  5. 收集社区信号（GitHub issues/PRs）
  6. 跨 repo 综合（含社区信号）
  7. Python 编译最终 Skill（可用道具，不是设计文档）
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

NEED_PROFILE_SYSTEM = """You generate GitHub search queries from user requests. The user wants to find open-source projects to learn from.

Output valid JSON only, no other text. Schema:
{
  "domain": "software domain in English (e.g., 'password management', 'fitness tracking')",
  "intent_en": "what the user wants, translated to English (1 sentence)",
  "github_queries": ["query1", "query2", "query3"],
  "relevance_terms": ["term1", "term2", "term3", "term4", "term5"]
}

Rules:
- github_queries: 3 different search strings (2-4 words each) optimized for GitHub search API.
  Think about what developers actually NAME their repos and write in descriptions.
  Example: for "WiFi密码管理" → ["wifi password manager", "network credential manager", "wifi qr code share"]
  Example: for "记账app" → ["expense tracker", "personal finance manager", "budget tracking app"]
- relevance_terms: 5 English keywords that a RELEVANT repo would mention in its README or description.
  These are used to filter out irrelevant search results.
  Example: for "WiFi密码管理" → ["wifi", "password", "credential", "network", "ssid"]
- domain: the software domain, NOT a generic label. Be specific.
- intent_en: precise translation of the user's goal."""

# Fallback: static CN→EN mapping (used when LLM is unavailable)
_CN_TO_EN_FALLBACK = {
    "记账": ["expense tracker", "personal finance", "bookkeeping"],
    "学习": ["learning platform", "education app", "study tool"],
    "购物": ["shopping app", "e-commerce", "price comparison"],
    "翻译": ["translation tool", "translator", "i18n"],
    "健康": ["health tracker", "fitness app", "wellness"],
    "食谱": ["recipe manager", "cookbook app", "meal planner"],
    "家居": ["smart home", "home automation", "IoT"],
    "笔记": ["note taking", "knowledge base", "markdown editor"],
    "日程": ["calendar app", "schedule planner", "task manager"],
    "密码": ["password manager", "credential manager", "security vault"],
    "天气": ["weather app", "forecast", "weather API"],
    "音乐": ["music player", "audio streaming", "playlist manager"],
    "视频": ["video player", "streaming app", "media player"],
    "社交": ["social network", "chat app", "messaging"],
    "地图": ["map navigation", "location service", "GPS tracker"],
    "备份": ["backup tool", "file sync", "cloud storage"],
    "监控": ["monitoring tool", "alerting system", "observability"],
    "自动化": ["automation workflow", "task automation", "pipeline"],
    "AI": ["AI tool", "machine learning", "LLM application"],
    "数据": ["data analytics", "data visualization", "dashboard"],
}


def build_need_profile(user_input):
    """Build need profile using LLM for keyword generation, with static fallback."""
    clean = re.sub(r"^/?dora\s*", "", user_input).strip()

    if not clean:
        return {
            "keywords": [],
            "domain": "general",
            "intent": "",
            "topic": "",
            "relevance_terms": [],
            "github_queries": [],
            "mode": "new",
        }

    # Try LLM-powered keyword generation
    try:
        _log("Generating search keywords via LLM...")
        profile_data = call_llm_json(NEED_PROFILE_SYSTEM, clean, max_tokens=500)

        domain = profile_data.get("domain", "general")
        intent_en = profile_data.get("intent_en", clean)
        github_queries = profile_data.get("github_queries", [])
        relevance_terms = profile_data.get("relevance_terms", [])

        # Build keywords from github_queries (split multi-word queries into individual terms too)
        keywords = []
        seen = set()
        for q in github_queries:
            for word in q.split():
                wl = word.lower()
                if wl not in seen and len(wl) >= 2:
                    keywords.append(word)
                    seen.add(wl)

        _log("LLM keywords: %s" % keywords[:8])
        _log("LLM relevance_terms: %s" % relevance_terms)

        return {
            "keywords": keywords[:8],
            "domain": domain,
            "intent": clean,
            "intent_en": intent_en,
            "topic": clean[:50],
            "relevance_terms": relevance_terms,
            "github_queries": github_queries[:3],
            "mode": "new",
        }

    except Exception as e:
        _log("LLM keyword generation failed (%s), using fallback" % e)
        return _build_need_profile_fallback(clean)


def _build_need_profile_fallback(clean):
    """Fallback: static CN→EN mapping when LLM is unavailable."""
    keywords = []
    seen = set()

    for cn, en_list in _CN_TO_EN_FALLBACK.items():
        if cn in clean:
            for en in en_list:
                if en.lower() not in seen:
                    keywords.append(en)
                    seen.add(en.lower())

    # Extract English words from input
    en_words = re.findall(r"[a-zA-Z]{3,}", clean)
    for w in en_words:
        wl = w.lower()
        if wl not in seen:
            keywords.append(w)
            seen.add(wl)

    if not keywords:
        keywords = ["open source tool"]

    return {
        "keywords": keywords[:8],
        "domain": "general",
        "intent": clean,
        "topic": clean[:50],
        "relevance_terms": [],
        "github_queries": [],
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


# ── Relevance Gate ──


def check_relevance(repos, profile):
    """Filter repos by relevance to user intent. Returns (relevant, rejected).

    Uses relevance_terms from the LLM-generated profile. A repo is relevant if
    its name, description, or topics mention at least 1 relevance term.
    If no relevance_terms available (fallback mode), passes all repos through.
    """
    relevance_terms = profile.get("relevance_terms", [])
    if not relevance_terms:
        _log("No relevance_terms available, skipping relevance gate")
        return repos, []

    terms_lower = [t.lower() for t in relevance_terms]
    relevant = []
    rejected = []

    for repo in repos:
        # Build searchable text from repo metadata
        name = repo.get("name", "").lower()
        desc = repo.get("description", "").lower() if repo.get("description") else ""
        topics = " ".join(repo.get("topics", [])).lower() if repo.get("topics") else ""
        searchable = f"{name} {desc} {topics}"

        # Count how many relevance terms match
        matches = sum(1 for t in terms_lower if t in searchable)

        if matches >= 1:
            relevant.append(repo)
            _log("  ✓ %s (matched %d terms)" % (repo.get("name", "?"), matches))
        else:
            rejected.append(repo)
            _log("  ✗ %s (0 matches, desc: %s)" % (repo.get("name", "?"), desc[:80]))

    _log("Relevance gate: %d/%d repos passed" % (len(relevant), len(repos)))
    return relevant, rejected


# ── Community Signals ──


def collect_community_signals(repo_name, repo_url, repo_path=None):
    """Collect community signals for a repo via community_signals.py."""
    script = SCRIPT_DIR / "community_signals.py"
    if not script.exists():
        _log("community_signals.py not found")
        return None

    output_file = Path("/tmp/doramagic_signals_%s.json" % repo_name.replace("/", "-"))
    cmd = [sys.executable, str(script), "--repo-url", repo_url, "--output", str(output_file)]
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
    """Compile into an actionable SKILL.md — an AI agent instruction set, not a report.

    Doramagic 产品之魂：不教用户做事，给他工具。
    SKILL.md 是注入 AI 助手的指令集，让助手在特定领域变聪明。
    """
    contract = synthesis.get("skill_contract", {})
    purpose = contract.get("purpose", profile.get("intent", ""))
    capabilities = contract.get("capabilities", [])
    workflow = contract.get("workflow_steps", [])
    consensus = synthesis.get("consensus_whys", [])
    divergent = synthesis.get("divergent_whys", [])
    traps = synthesis.get("combined_traps", [])
    recommendation = synthesis.get("recommendation", "")
    domain = profile.get("domain", "general")
    intent_en = profile.get("intent_en", purpose)

    # Sanitize topic for skill name
    topic = profile.get("topic", "custom-skill")
    skill_name = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff_-]", "-", topic)[:30].strip("-")

    lines = [
        "---",
        "name: %s" % skill_name,
        "description: |",
        "  %s" % (intent_en or purpose),
        "version: 1.0.0",
        "domain: %s" % domain,
        "tags: [doramagic-generated]",
        "---\n",
    ]

    # ── Section 1: Role & Mission (the agent's identity) ──
    lines.append("# %s\n" % topic)
    lines.append("## Role\n")
    lines.append("You are a domain expert in **%s**. " % domain)
    lines.append("When the user asks about %s, " % topic)
    lines.append("apply the knowledge below to give informed, practical advice.\n")

    # ── Section 2: Domain Knowledge (the WHY — what makes you an expert) ──
    if consensus:
        lines.append("## Domain Knowledge — Design Principles\n")
        lines.append("These principles are extracted from real-world open-source projects in this domain.\n")
        for w in consensus:
            src = ", ".join(w.get("sources", []))
            lines.append("- **%s** — learned from: %s" % (w["statement"], src))
        lines.append("")

    # ── Section 3: Decision Framework (when approaches conflict) ──
    if divergent:
        lines.append("## Decision Framework — Trade-offs\n")
        lines.append("When advising on architecture choices, consider these known trade-offs:\n")
        for d in divergent:
            lines.append("- **%s**" % d.get("statement", ""))
            lines.append("  - Approach A (%s): %s" % (d.get("side_a", "?"), d.get("side_a", "")))
            lines.append("  - Approach B (%s): %s" % (d.get("side_b", "?"), d.get("side_b", "")))
        lines.append("")

    # ── Section 4: Anti-patterns (the UNSAID — protect the user) ──
    if traps:
        lines.append("## Anti-patterns — UNSAID Warnings\n")
        lines.append("These are pitfalls that documentation doesn't warn about. "
                     "Proactively warn the user when they're heading toward one.\n")
        for t in traps:
            sev = t.get("severity", "medium").upper()
            lines.append("- **[%s]** %s" % (sev, t["trap"]))
        lines.append("")

    # ── Section 5: Capabilities (what you can help with) ──
    if capabilities:
        lines.append("## Capabilities\n")
        lines.append("You can help the user with:\n")
        for c in capabilities:
            lines.append("- %s" % c)
        lines.append("")

    # ── Section 6: Workflow (how to approach tasks) ──
    if workflow:
        lines.append("## Recommended Workflow\n")
        lines.append("When the user starts a new task in this domain, follow these steps:\n")
        for i, step in enumerate(workflow, 1):
            lines.append("%d. %s" % (i, step))
        lines.append("")

    # ── Section 7: Key Insight ──
    if recommendation:
        lines.append("## Key Insight\n")
        lines.append("> %s\n" % recommendation)

    # ── Section 8: Mental Models (quick reference) ──
    repo_souls = [s for s in souls if s.get("source") not in ("clawhub", "local")]
    if repo_souls:
        lines.append("## Source Projects — Mental Models\n")
        for soul in repo_souls:
            name = soul.get("project_name", "?")
            model = soul.get("mental_model", "")
            if model:
                lines.append("- **%s**: %s" % (name, model))
        lines.append("")

    lines.append("---")
    lines.append(
        "*Generated by Doramagic v9.0 — 不教用户做事，给他工具。*"
    )
    return "\n".join(lines)


# ── Main ──


def main():
    parser = argparse.ArgumentParser(description="Doramagic Single-Shot v9.0")
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
    # Use github_queries from LLM if available (better than raw keywords)
    engine = SCRIPT_DIR / "doramagic_engine.py"
    _log("Running engine...")

    # Write an engine-optimized need_profile with github_queries as keywords
    engine_profile = dict(profile)
    if profile.get("github_queries"):
        # Use the first github_query's words as keywords for the engine
        # Engine takes top 3 keywords and joins with "+" for GitHub API
        gq_keywords = []
        seen = set()
        for q in profile["github_queries"]:
            for word in q.split():
                wl = word.lower()
                if wl not in seen and len(wl) >= 2:
                    gq_keywords.append(word)
                    seen.add(wl)
        engine_profile["keywords"] = gq_keywords[:6]
        _log("Engine keywords (from github_queries): %s" % engine_profile["keywords"])

    engine_need_path = rd / "need_profile_engine.json"
    with open(engine_need_path, "w") as f:
        json.dump(engine_profile, f, ensure_ascii=False, indent=2)

    repos = []
    engine_out = {}
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(engine),
                "--need",
                str(engine_need_path),
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

    # ── Step 2.5: Relevance gate ──
    rejected_repos = []
    if repos:
        _log("Running relevance gate on %d repos..." % len(repos))
        repos, rejected_repos = check_relevance(repos, profile)
        if rejected_repos:
            with open(rd / "rejected_repos.json", "w") as f:
                json.dump(
                    [{"name": r.get("name"), "reason": "failed relevance gate"} for r in rejected_repos],
                    f, ensure_ascii=False, indent=2,
                )

    total_sources = len(repos) + len(clawhub_skills) + len(local_skills)
    _log("Sources after relevance gate: %d repos, %d ClawHub skills, %d local skills" % (
        len(repos), len(clawhub_skills), len(local_skills)
    ))

    if total_sources == 0:
        # Honest report: nothing relevant found
        rejected_names = [r.get("name", "?") for r in rejected_repos]
        if rejected_repos:
            msg = (
                "搜索了 GitHub、ClawHub、本地 Skills，找到了 %d 个项目但都和「%s」不相关。\n\n"
                "被过滤的项目：%s\n\n"
                "建议：\n"
                "- 试试更具体的描述（比如「WiFi密码分享和管理工具」）\n"
                "- 或者用英文描述（比如「WiFi password manager」）"
            ) % (len(rejected_repos), profile["intent"], ", ".join(rejected_names))
        else:
            msg = "三个信息源（GitHub、ClawHub、本地 Skills）都没有找到相关内容。试试换个描述？"
        _output({"message": msg, "error": True})

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
