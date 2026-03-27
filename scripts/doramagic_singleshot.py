#!/usr/bin/env python3
"""Doramagic Single-Shot v12.1.0 — Section-split compiler + GitHub primary + LLM retry.

v11.0 changes:
  - Domain brick integration: 278 bricks (34 domains) injected into SKILL.md and extraction prompts
  - Fast path synthesis: ClawHub-only path uses Python compilation (no LLM), 52s → 18s
  - Timing fix: debug summary no longer double-counts (was 103s, actually 52s)
  - Version bump for coordinated engine rewrite (github_search.py + doramagic_engine.py)

v10.1 changes:
  - Intent recognition with confidence, user_type, clarifying questions
  - Socratic gate: confidence < 0.7 returns questions instead of blind search
  - Fast path: ClawHub/Local first, GitHub skipped when high-relevance results found
  - GitHub engine timeout: 360s → 60s

v10.0 changes:
  - Added --debug flag with DebugLogger for full execution tracing

v9.0 changes:
  - LLM-powered keyword generation, relevance gate, actionable SKILL.md output

流程：
  1. 解析用户输入 → LLM 意图识别 + 关键词 + 置信度（fallback: 静态字典）
  1.5 苏格拉底门控：置信度低时返回追问，不盲搜
  2a. 快路径搜索：ClawHub + 本地 Skills（~1秒）
  2b. 快路径评估：有高相关结果则跳过 GitHub
  2c. 深度搜索（可选）：GitHub engine（60s 超时）
  3. 相关性门控 + 灵魂提取 + 社区信号 + 综合 + 编译
  4. 输出 JSON（message 字段给用户看）

用法（被 SKILL.md 调用）：
    python3 doramagic_singleshot.py --input "用户消息" --run-dir ~/clawd/doramagic/runs/
    python3 doramagic_singleshot.py --input "用户消息" --run-dir ~/clawd/doramagic/runs/ --debug
"""
from __future__ import annotations

import argparse
import json
import os
import random
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

# Module-level debug logger (set in main() if --debug is passed)
_debug_logger = None


def _find_engine():
    """Locate doramagic_engine.py across candidate paths.

    Search order:
      1. SCRIPT_DIR (co-located — works in OpenClaw installed layout)
      2. skills/doramagic/scripts/ (dev layout)
      3. DORAMAGIC_ROOT env var
    Returns Path or None.
    """
    candidates = [
        SCRIPT_DIR / "doramagic_engine.py",
        SCRIPT_DIR.parent / "skills" / "doramagic" / "scripts" / "doramagic_engine.py",
    ]
    root = os.environ.get("DORAMAGIC_ROOT", "")
    if root:
        candidates.append(Path(root) / "scripts" / "doramagic_engine.py")
    for c in candidates:
        if c.exists():
            return c
    return None


# ── Brick Loading ──

# Domain brick configs with affinity validation.
# triggers: keywords that suggest domain relevance
# affinity_terms: at least 1 must appear in domain/keywords to confirm (prevents cross-contamination)
# Overly broad triggers removed: "note", "knowledge", "wiki", "cloud", "server", "news", "iot", "automation"
_DOMAIN_BRICKS = {
    "domain_health": {
        "triggers": ["health", "medical", "fitness", "wellness", "exercise"],
        "affinity_terms": ["patient", "diagnosis", "workout", "calories", "heart rate", "bmi",
                           "exercise", "nutrition", "sleep", "weight"],
    },
    "domain_finance": {
        "triggers": ["finance", "accounting", "budget", "expense", "investment", "ledger"],
        "affinity_terms": ["transaction", "ledger", "balance", "currency", "payment",
                           "invoice", "tax", "portfolio", "bank"],
    },
    "domain_pkm": {
        "triggers": ["pkm", "obsidian", "logseq", "roam", "zettelkasten"],
        "affinity_terms": ["markdown", "backlink", "zettelkasten", "vault", "daily note",
                           "obsidian", "logseq", "roam", "second brain"],
    },
    "domain_private_cloud": {
        "triggers": ["selfhost", "self-host", "homelab", "nas", "self hosted"],
        "affinity_terms": ["docker", "compose", "reverse proxy", "traefik", "nginx",
                           "self-hosted", "homelab", "nas", "portainer"],
    },
    "domain_info_ingestion": {
        "triggers": ["rss", "feed reader", "scraping", "crawler", "rss reader"],
        "affinity_terms": ["rss", "atom", "scrape", "crawl", "feed", "parser", "syndication"],
    },
    "home_assistant": {
        "triggers": ["home assistant", "smart home", "hass", "home automation"],
        "affinity_terms": ["zigbee", "zwave", "mqtt", "sensor", "thermostat", "hass",
                           "home assistant", "esphome"],
    },
}

# Framework keyword → brick file mapping
_FRAMEWORK_BRICK_MAP = {
    "django": "django",
    "react": "react",
    "vue": "vuejs",
    "next": "nextjs",
    "nextjs": "nextjs",
    "flask": "fastapi_flask",
    "fastapi": "fastapi_flask",
    "spring": "java_spring_boot",
    "rails": "ruby_rails",
    "rust": "rust",
    "swift": "swift_ios",
    "kotlin": "kotlin_android",
    "langchain": "langchain",
    "llamaindex": "llamaindex",
    "typescript": "typescript_nodejs",
    "node": "typescript_nodejs",
    "python": "python_general",
    "go": "go_general",
    "golang": "go_general",
    "php": "php_laravel",
    "laravel": "php_laravel",
}


def _resolve_bricks_dir():
    """Find bricks directory across candidate paths."""
    candidates = [
        SCRIPT_DIR.parent / "bricks",
        SCRIPT_DIR.parent.parent / "bricks",
        Path(os.environ.get("DORAMAGIC_ROOT", "")) / "bricks",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def _load_bricks_from_jsonl(jsonl_path):
    """Load brick dicts from a JSONL file."""
    bricks = []
    if not jsonl_path.exists():
        return bricks
    try:
        with open(jsonl_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    bricks.append(json.loads(line))
    except Exception:
        pass
    return bricks


def _match_best_domain(domain, keywords):
    """Find the single best-matching domain brick, with affinity validation.

    Returns brick filename or None. Max-1-domain guard prevents cross-contamination.
    """
    domain_lower = (domain or "").lower()
    all_text = domain_lower + " " + " ".join(kw.lower() for kw in (keywords or []))

    best_domain = None
    best_score = 0

    for brick_file, config in _DOMAIN_BRICKS.items():
        # Check if any trigger matches
        trigger_hits = sum(1 for t in config["triggers"] if t in all_text)
        if trigger_hits == 0:
            continue

        # Affinity validation: at least 1 affinity term must appear
        affinity_hits = sum(1 for t in config["affinity_terms"] if t in all_text)
        if affinity_hits == 0:
            continue

        score = trigger_hits + affinity_hits
        if score > best_score:
            best_score = score
            best_domain = brick_file

    return best_domain


def load_matching_bricks(domain, keywords=None, bricks_dir=None):
    """Load bricks matching the domain and/or detected frameworks.

    Safeguards:
    - Domain bricks: max-1-domain guard + affinity_terms validation
    - Framework bricks: exact keyword match only (safe)
    Returns list of brick dicts.
    """
    if bricks_dir is None:
        bricks_dir = _resolve_bricks_dir()
    if bricks_dir is None:
        return []

    bricks_dir = Path(bricks_dir)
    matched_files = set()

    # Domain bricks: max-1, affinity-validated
    best_domain = _match_best_domain(domain, keywords)
    if best_domain:
        matched_files.add(best_domain)

    # Framework bricks: exact keyword match (safe)
    for kw in (keywords or []):
        kw_lower = kw.lower()
        if kw_lower in _FRAMEWORK_BRICK_MAP:
            matched_files.add(_FRAMEWORK_BRICK_MAP[kw_lower])

    # Load
    all_bricks = []
    for brick_file in matched_files:
        jsonl_path = bricks_dir / ("%s.jsonl" % brick_file)
        all_bricks.extend(_load_bricks_from_jsonl(jsonl_path))

    return all_bricks


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


# ── Debug Logger ──

class DebugLogger:
    """Debug logger for singleshot.py. Writes to debug.log and stderr.

    Activated only when --debug flag is passed. When not activated, all calls
    are no-ops and behavior is identical to non-debug mode.
    """

    def __init__(self, run_dir: Path, run_id: str):
        self._run_dir = run_dir
        self._run_id = run_id
        self._log_path = run_dir / run_id / "debug.log"
        self._traces_dir = run_dir / run_id / "llm_traces"
        self._traces_dir.mkdir(parents=True, exist_ok=True)
        self._log_file = open(self._log_path, "w", encoding="utf-8")
        self._stage_timings: list[dict] = []
        self._current_stage: str = ""
        self._stage_start: float = 0.0
        self._write("=" * 72)
        self._write("Doramagic Single-Shot v12.1.0 — Debug Log")
        self._write("Run ID: %s" % run_id)
        self._write("Started: %s" % datetime.now().isoformat())
        self._write("=" * 72)
        self._write("")

    def _write(self, msg: str):
        """Write to both debug.log and stderr."""
        print(msg, file=self._log_file)
        self._log_file.flush()
        print("[DEBUG] %s" % msg, file=sys.stderr)

    def stage(self, name: str):
        """Log a prominent stage header with timestamp. Also records timing for previous stage."""
        now = time.time()
        # Record timing for previous stage if there was one
        if self._current_stage:
            elapsed = (now - self._stage_start) * 1000
            self._stage_timings.append({
                "stage": self._current_stage,
                "elapsed_ms": round(elapsed, 1),
            })
        self._current_stage = name
        self._stage_start = now
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self._write("")
        self._write("┌" + "─" * 70 + "┐")
        self._write("│  [%s]  STAGE: %-50s │" % (ts, name))
        self._write("└" + "─" * 70 + "┘")

    def detail(self, msg: str):
        """Log a detail line."""
        self._write("  » %s" % msg)

    def llm_call(
        self,
        stage: str,
        system_prompt: str,
        user_prompt: str,
        response: str,
        elapsed_ms: float,
        model: str = LLM_MODEL,
        tokens: dict | None = None,
    ):
        """Log an LLM call: summary to debug.log + full trace to llm_traces/."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        trace_name = "%s_%s.json" % (re.sub(r"[^a-zA-Z0-9_-]", "_", stage), ts)
        trace_path = self._traces_dir / trace_name

        trace = {
            "stage": stage,
            "model": model,
            "elapsed_ms": round(elapsed_ms, 1),
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "raw_response": response,
        }
        if tokens:
            trace["tokens"] = tokens
        # Try to parse JSON response for convenience
        try:
            parsed = json.loads(response)
            trace["parsed_response"] = parsed
        except Exception:
            pass

        with open(trace_path, "w", encoding="utf-8") as f:
            json.dump(trace, f, ensure_ascii=False, indent=2)

        # Summary to debug.log
        sys_preview = system_prompt[:120].replace("\n", " ")
        user_preview = user_prompt[:120].replace("\n", " ")
        resp_preview = response[:120].replace("\n", " ")
        self._write("  [LLM] stage=%s model=%s elapsed=%.0fms" % (stage, model, elapsed_ms))
        self._write("    system: %s…" % sys_preview)
        self._write("    user:   %s…" % user_preview)
        self._write("    resp:   %s…" % resp_preview)
        self._write("    trace → %s" % trace_path)

    def timing(self, stage: str, elapsed_ms: float):
        """Explicitly record a timing entry (for sub-steps not tracked by stage())."""
        self._stage_timings.append({
            "stage": stage,
            "elapsed_ms": round(elapsed_ms, 1),
        })
        self._write("  [TIMING] %s: %.0f ms" % (stage, elapsed_ms))

    def summary(self):
        """Print a table of all stages with timing at the end.

        Deduplicates: stage() auto-records outer timing, timing() records sub-step.
        Only show stage-level entries (those starting with "Step") to avoid double-counting.
        """
        # Record final stage timing
        if self._current_stage:
            elapsed = (time.time() - self._stage_start) * 1000
            self._stage_timings.append({
                "stage": self._current_stage,
                "elapsed_ms": round(elapsed, 1),
            })
        self._write("")
        self._write("=" * 72)
        self._write("TIMING SUMMARY")
        self._write("=" * 72)
        total = 0.0
        for entry in self._stage_timings:
            stage_name = entry["stage"]
            # Only count stage-level entries (set by stage() call) for the total
            # Sub-step timings (set by timing() call) are logged but not summed
            is_stage_level = stage_name.startswith("Step ")
            if is_stage_level:
                self._write("  %-40s %8.0f ms" % (stage_name, entry["elapsed_ms"]))
                total += entry["elapsed_ms"]
        self._write("-" * 72)
        self._write("  %-40s %8.0f ms" % ("TOTAL", total))
        self._write("=" * 72)
        self._log_file.close()


# ── LLM API ──

def _is_retryable_status(status_code):
    """Classify HTTP status: 429/5xx are retryable, 400/401/403 are fatal."""
    if status_code == 429:
        return True
    if 500 <= status_code < 600:
        return True
    return False


def call_llm(system_prompt, user_prompt, max_tokens=4096, stage_name=None, timeout=None,
             max_retries=3):
    """Call LLM API with retry + exponential backoff + jitter.

    Retry policy (AWS SRE recommended):
      - 3 attempts with full jitter: sleep = random(0, base * 2^attempt)
      - 429/5xx → retryable; 400/401/403 → fatal (no retry)
      - Adaptive timeout: base 30s + max_tokens / 10 (conservative for GLM-5)
    """
    import requests

    if timeout is None:
        timeout = max(30, 30 + max_tokens // 10)

    last_error = None
    for attempt in range(max_retries):
        t0 = time.time()
        try:
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
                timeout=timeout,
            )

            if resp.status_code != 200:
                if _is_retryable_status(resp.status_code) and attempt < max_retries - 1:
                    backoff = random.uniform(0, min(30, 2 ** attempt * 2))
                    _log("LLM API %d (attempt %d/%d), retrying in %.1fs..." % (
                        resp.status_code, attempt + 1, max_retries, backoff))
                    time.sleep(backoff)
                    continue
                resp.raise_for_status()

            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            elapsed_ms = (time.time() - t0) * 1000

            if _debug_logger is not None and stage_name:
                tokens = data.get("usage")
                _debug_logger.llm_call(
                    stage=stage_name,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response=text,
                    elapsed_ms=elapsed_ms,
                    tokens=tokens,
                )
                if attempt > 0:
                    _debug_logger.detail("LLM call succeeded on attempt %d/%d" % (attempt + 1, max_retries))

            return text

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            last_error = e
            if attempt < max_retries - 1:
                backoff = random.uniform(0, min(30, 2 ** attempt * 2))
                _log("LLM timeout/connection error (attempt %d/%d), retrying in %.1fs..." % (
                    attempt + 1, max_retries, backoff))
                time.sleep(backoff)
            else:
                _log("LLM failed after %d attempts: %s" % (max_retries, e))
                raise
        except requests.exceptions.HTTPError:
            raise
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                backoff = random.uniform(0, min(30, 2 ** attempt * 2))
                _log("LLM unexpected error (attempt %d/%d): %s, retrying..." % (
                    attempt + 1, max_retries, e))
                time.sleep(backoff)
            else:
                raise

    raise last_error or RuntimeError("call_llm failed after %d retries" % max_retries)


def _repair_json(text):
    """Attempt to repair common LLM JSON mistakes."""
    # Remove trailing commas before } or ]
    text = re.sub(r",\s*([}\]])", r"\1", text)
    # Replace single quotes with double quotes (simple heuristic)
    if "'" in text and '"' not in text:
        text = text.replace("'", '"')
    return text


def _extract_json_text(raw):
    """Extract JSON string from LLM response (handles markdown blocks)."""
    if "```json" in raw:
        return raw.split("```json", 1)[1].split("```", 1)[0].strip()
    if "```" in raw:
        return raw.split("```", 1)[1].split("```", 1)[0].strip()
    # Try to find raw JSON object/array
    for ch, end in [("{", "}"), ("[", "]")]:
        start = raw.find(ch)
        if start >= 0:
            # Find matching close from the end
            close = raw.rfind(end)
            if close > start:
                return raw[start:close + 1].strip()
    return raw.strip()


def call_llm_json(system_prompt, user_prompt, max_tokens=4096, stage_name=None):
    """Call LLM and parse JSON from response, with repair on failure."""
    text = call_llm(system_prompt, user_prompt, max_tokens, stage_name=stage_name)
    json_text = _extract_json_text(text)
    try:
        return json.loads(json_text)
    except json.JSONDecodeError:
        repaired = _repair_json(json_text)
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            _log("JSON parse failed even after repair, raw: %s" % json_text[:300])
            raise


# ── Input Parsing ──

NEED_PROFILE_SYSTEM = """You are Doramagic's need interpreter. Analyze the user's request and produce a structured understanding.

Output valid JSON only, no other text. Schema:
{
  "domain": "software domain in English (e.g., 'password management', 'fitness tracking')",
  "intent_en": "what the user wants, translated to English (1 sentence)",
  "github_queries": ["query1", "query2", "query3"],
  "relevance_terms": ["term1", "term2", "term3", "term4", "term5"],
  "confidence": 0.9,
  "user_type": "developer",
  "questions": []
}

Field rules:
- github_queries: 3 search strings (2-4 words each) for GitHub search API.
  Think about what developers actually NAME their repos and write in descriptions.
  Example: "WiFi密码管理" → ["wifi password manager", "network credential manager", "wifi qr code share"]
  Example: "记账app" → ["expense tracker", "personal finance manager", "budget tracking app"]
- relevance_terms: 5 English keywords a RELEVANT repo would mention in README/description.
  Example: "WiFi密码管理" → ["wifi", "password", "credential", "network", "ssid"]
- domain: the software domain, NOT a generic label. Be specific.
- intent_en: precise translation of the user's goal.
- confidence: 0.0 to 1.0 — how clearly you understand what the user needs.
  Set HIGH (>= 0.7) when the request is specific enough to search immediately.
  Set LOW (< 0.7) when critical details are missing that would change search direction.
  Examples of HIGH: "WiFi密码管理工具" (0.9), "PDF转PPT" (0.85), "个人记账app" (0.9)
  Examples of LOW: "帮我做个网站" (0.3), "学点什么" (0.2), "AI相关的" (0.4)
- user_type: infer from context clues in the message.
  "developer" — mentions code, API, library, framework, CLI, deploy
  "non_developer" — mentions 办公/文员/日常/工具/app, or no technical terms
  "unknown" — not enough signal
- questions: ONLY fill when confidence < 0.7. List 1-2 high-value clarifying questions in Chinese.
  Each question must change the search direction if answered differently.
  Bad question: "你确定吗？" (doesn't change search)
  Good question: "你需要命令行工具还是带界面的应用？" (changes search direction)
  Good question: "你的PDF是扫描版（图片）还是文字版？" (changes tool selection)"""

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
        profile_data = call_llm_json(
            NEED_PROFILE_SYSTEM, clean, max_tokens=500,
            stage_name="build_need_profile",
        )

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

        # New fields: confidence, user_type, questions
        confidence = profile_data.get("confidence", 1.0)
        user_type = profile_data.get("user_type", "unknown")
        questions = profile_data.get("questions", [])

        # Ensure confidence is a float
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = 1.0

        _log("LLM keywords: %s" % keywords[:8])
        _log("LLM relevance_terms: %s" % relevance_terms)
        _log("LLM confidence: %.2f, user_type: %s" % (confidence, user_type))

        if _debug_logger is not None:
            _debug_logger.detail("domain=%s" % domain)
            _debug_logger.detail("keywords=%s" % keywords[:8])
            _debug_logger.detail("relevance_terms=%s" % relevance_terms)
            _debug_logger.detail("github_queries=%s" % github_queries)
            _debug_logger.detail("confidence=%.2f" % confidence)
            _debug_logger.detail("user_type=%s" % user_type)
            if questions:
                _debug_logger.detail("questions=%s" % questions)

        return {
            "keywords": keywords[:8],
            "domain": domain,
            "intent": clean,
            "intent_en": intent_en,
            "topic": clean[:50],
            "relevance_terms": relevance_terms,
            "github_queries": github_queries[:3],
            "confidence": confidence,
            "user_type": user_type,
            "questions": questions,
            "mode": "new",
        }

    except Exception as e:
        _log("LLM keyword generation failed (%s), using fallback" % e)
        if _debug_logger is not None:
            _debug_logger.detail("LLM failed: %s — using static fallback" % e)
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
        req = Request(url, headers={"User-Agent": "Doramagic/10.0"})
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
        if _debug_logger is not None:
            _debug_logger.detail("ClawHub query=%r → %d skills" % (query, len(skills)))
            for s in skills:
                _debug_logger.detail("  clawhub skill: %s (score=%s)" % (s["slug"], s["score"]))
        return skills
    except (URLError, Exception) as e:
        _log("ClawHub search failed: %s" % e)
        if _debug_logger is not None:
            _debug_logger.detail("ClawHub FAILED: %s" % e)
        return []


# ── Local Skills Scan ──


def scan_local_skills(keywords):
    """Scan ~/.openclaw/skills/ for locally installed relevant skills."""
    skills_dir = Path.home() / ".openclaw" / "skills"
    if not skills_dir.exists():
        if _debug_logger is not None:
            _debug_logger.detail("local skills dir not found: %s" % skills_dir)
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
    if _debug_logger is not None:
        _debug_logger.detail("local skills: %d relevant found" % len(found))
        for s in found:
            _debug_logger.detail("  local skill: %s (relevance=%d)" % (s["name"], s["relevance"]))
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
        if _debug_logger is not None:
            _debug_logger.detail("relevance gate SKIPPED (no relevance_terms)")
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
            if _debug_logger is not None:
                _debug_logger.detail("  PASS %s (matched %d/%d terms)" % (
                    repo.get("name", "?"), matches, len(terms_lower)))
        else:
            rejected.append(repo)
            _log("  ✗ %s (0 matches, desc: %s)" % (repo.get("name", "?"), desc[:80]))
            if _debug_logger is not None:
                _debug_logger.detail("  REJECT %s — 0 of %d terms matched (desc: %s)" % (
                    repo.get("name", "?"), len(terms_lower), desc[:80]))

    _log("Relevance gate: %d/%d repos passed" % (len(relevant), len(repos)))
    if _debug_logger is not None:
        _debug_logger.detail("relevance gate result: %d/%d passed" % (len(relevant), len(repos)))
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
            if _debug_logger is not None:
                _debug_logger.detail("community_signals FAILED for %s: %s" % (
                    repo_name, result.stderr[:200]))
            return None
        if output_file.exists():
            with open(output_file) as f:
                data = json.load(f)
            if _debug_logger is not None:
                count = len(data.get("signals", []))
                _debug_logger.detail("community_signals %s: %d signals" % (repo_name, count))
            return data
    except Exception as e:
        _log("Community signals error for %s: %s" % (repo_name, e))
        if _debug_logger is not None:
            _debug_logger.detail("community_signals ERROR for %s: %s" % (repo_name, e))
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


def extract_soul(repo_name, repo_dir, facts, bricks=None, repo_type=None):
    """Extract soul from one repo via LLM API.

    bricks: optional list of domain bricks to inject as context.
    repo_type: "CATALOG", "TOOL", or "FRAMEWORK". CATALOG gets shallow extraction.
    """
    is_catalog = (repo_type == "CATALOG")
    focus = facts.get("focus_files", [])

    # CATALOG repos: README only, no deep code analysis
    if is_catalog:
        content = read_repo_files(repo_dir, [], max_chars=8000)
        max_tokens = 1000
    else:
        content = read_repo_files(repo_dir, focus)
        max_tokens = 2000

    if not content:
        _log("No readable files for %s" % repo_name)
        if _debug_logger is not None:
            _debug_logger.detail("soul extraction SKIP %s — no readable files" % repo_name)
        return None

    # Build system prompt, optionally enriched with domain bricks
    system_prompt = SOUL_SYSTEM
    if is_catalog:
        system_prompt += "\n\nNOTE: This is a CATALOG/awesome-list, not a code project. Extract only curated knowledge and recommendations, not code architecture."
    if bricks:
        brick_lines = ["\n\nYou already know these baseline facts about this domain:"]
        for b in bricks[:5]:  # Cap at 5 to avoid prompt bloat
            stmt = b.get("statement", "")[:200]
            if stmt:
                brick_lines.append("- %s" % stmt)
        brick_lines.append("\nUse this knowledge to ask deeper questions and extract non-obvious insights.")
        system_prompt += "\n".join(brick_lines)

    stage_name = "soul_extraction_%s" % re.sub(r"[^a-zA-Z0-9_-]", "_", repo_name)[:40]
    try:
        soul = call_llm_json(
            system_prompt,
            "Project: %s\n\n%s" % (repo_name, content),
            max_tokens=max_tokens,
            stage_name=stage_name,
        )
        soul["project_name"] = repo_name
        soul["repo_type"] = repo_type or "TOOL"
        if _debug_logger is not None:
            ndec = len(soul.get("why_decisions", []))
            ntraps = len(soul.get("unsaid_traps", []))
            _debug_logger.detail("soul %s (%s): %d why_decisions, %d traps" % (
                repo_name, repo_type or "?", ndec, ntraps))
        return soul
    except Exception as e:
        _log("Soul extraction failed for %s: %s" % (repo_name, e))
        if _debug_logger is not None:
            _debug_logger.detail("soul extraction FAILED %s: %s" % (repo_name, e))
        return None


def synthesize(souls, intent):
    """Cross-repo synthesis via LLM API."""
    try:
        result = call_llm_json(
            SYNTHESIS_SYSTEM,
            "User intent: %s\n\nProject souls:\n%s"
            % (intent, json.dumps(souls, ensure_ascii=False, indent=2)),
            max_tokens=3000,
            stage_name="synthesis",
        )
        if _debug_logger is not None:
            nconsensus = len(result.get("consensus_whys", []))
            ndiverge = len(result.get("divergent_whys", []))
            ntraps = len(result.get("combined_traps", []))
            _debug_logger.detail("synthesis: %d consensus, %d divergent, %d traps" % (
                nconsensus, ndiverge, ntraps))
        return result
    except Exception as e:
        _log("Synthesis failed: %s" % e)
        if _debug_logger is not None:
            _debug_logger.detail("synthesis FAILED: %s" % e)
        return None


# ── Reference Skill Loading ──

_REFERENCE_LEVELS = {
    "simple": "simple.md",      # code-review-expert, 156 lines — tool skills
    "medium": "medium.md",      # script-writer, 570 lines — platform/integration skills
    "complex": "complex.md",    # n8n (truncated 300 lines) — high-risk/complex domains
}

_HIGH_RISK_DOMAINS = [
    "health", "medical", "fitness", "wellness", "diagnosis", "symptom",
    "finance", "accounting", "investment", "trading", "tax",
    "security", "auth", "encryption", "credential",
    "legal", "compliance", "regulation",
]


def _select_reference_level(domain, user_type):
    """Select reference skill complexity based on domain risk and user type."""
    domain_lower = (domain or "").lower()
    if any(k in domain_lower for k in _HIGH_RISK_DOMAINS):
        return "complex"
    if user_type == "developer":
        return "medium"
    return "simple"


def _load_reference_skill(level):
    """Load reference SKILL.md content. Returns first 80 lines to keep prompt compact."""
    filename = _REFERENCE_LEVELS.get(level, "simple.md")
    candidates = [
        SCRIPT_DIR.parent / "references" / filename,
        SCRIPT_DIR.parent.parent / "references" / filename,
    ]
    for path in candidates:
        if path.exists():
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
                return "\n".join(lines[:80])
            except Exception:
                pass
    return ""


# ── Skill Architect (LLM-powered compile) ──

SKILL_ARCHITECT_SYSTEM = """You are a Skill Architect. Your job is to compile raw materials into a high-quality SKILL.md — an AI agent instruction set that makes an AI assistant genuinely smarter in a specific domain.

## What you receive

1. A REFERENCE SKILL — a gold-standard example of what a good SKILL.md looks like. Your output MUST match its structural depth and quality.
2. RAW MATERIALS — synthesis results, soul extractions from real projects, and domain baseline knowledge (bricks).
3. USER CONTEXT — domain, intent, user type.

## Output format

Output ONLY the SKILL.md content as raw markdown. No code fences, no explanations, no preamble.

## Required sections (all mandatory)

1. **YAML Frontmatter** — name (concise, max 40 chars), description (1-2 sentences, trigger-oriented: "Use when...")
2. **# Title** — the skill's display name
3. **## Role** — who the AI becomes, specific to this domain
4. **## When to Use** — concrete trigger phrases and scenarios (3-5 bullets)
5. **## Domain Knowledge** — design principles with source attribution. Only use knowledge from the provided materials. Never invent.
6. **## Decision Framework** — at least 2 trade-off pairs with "When to choose A vs B" guidance
7. **## Recommended Workflow** — at least 5 actionable steps the user should follow
8. **## Anti-patterns & UNSAID Warnings** — at least 3 pitfalls. Bricks with [RISK] or [CONSTRAINT] tags are highest priority — include their UNSAID content COMPLETELY, never truncate.
9. **## Safety Boundaries** — what this skill does NOT do, when to escalate/refuse
10. **## Capabilities** — concrete things the AI can help with (5-8 bullets)
11. **## Source Projects** — list of projects/skills that contributed knowledge, with what each contributed

## Domain safety rules (MANDATORY for high-risk domains)

- Health/Medical: MUST include "This is not medical advice. For serious symptoms, consult a healthcare professional." in Safety Boundaries. MUST include emergency triage guidance.
- Finance/Investment: MUST include "This does not constitute financial or investment advice." in Safety Boundaries.
- Security: MUST include "Never handle real credentials or secrets in this context." in Safety Boundaries.
- Legal: MUST include "This is not legal advice. Consult a qualified attorney." in Safety Boundaries.

## Quality standards

- Total length: 80-250 lines
- Workflow: ≥ 5 steps with clear actions
- Decision Framework: ≥ 2 trade-off analyses
- Anti-patterns: ≥ 3 items with severity labels [HIGH/MEDIUM/LOW]
- Every knowledge claim must cite its source (project name or brick ID)

## Critical rules

- NEVER invent knowledge. Only compile from the provided materials.
- Bricks are expert-curated domain facts — treat them as highest-confidence knowledge.
- ClawHub skills in the "Reference Tools" section are market context, NOT knowledge sources. List them in Source Projects but don't extract design principles from their summaries.
- If materials are sparse, produce a shorter but accurate skill. Do NOT pad with generic advice.
- Output in the same language as the user's original intent (Chinese intent → Chinese skill, English → English)."""


def _build_compile_prompt(synthesis, souls, profile, bricks, reference_content,
                          max_chars=16000):
    """[LEGACY — kept for reference] Single-shot compile prompt (v12.0).

    Superseded by _build_shared_compile_packet() + per-section calls in v12.1.0.
    max_chars: hard cap on total prompt size to avoid context window overflow.
    """
    parts = []

    # Section 1: User context
    parts.append("## User Context")
    parts.append("- Domain: %s" % profile.get("domain", "general"))
    parts.append("- Intent: %s" % profile.get("intent", ""))
    parts.append("- Intent (English): %s" % profile.get("intent_en", ""))
    parts.append("- User type: %s" % profile.get("user_type", "unknown"))
    parts.append("")

    # Section 2: Reference skill (few-shot example)
    if reference_content:
        parts.append("## Reference Skill (gold standard — match this quality)")
        parts.append(reference_content)
        parts.append("")

    # Section 3: Synthesis results
    if synthesis:
        parts.append("## Synthesis Results")
        consensus = synthesis.get("consensus_whys", [])
        if consensus:
            parts.append("### Consensus Design Principles")
            for c in consensus:
                sources = ", ".join(c.get("sources", []))
                parts.append("- %s (from: %s)" % (c.get("statement", ""), sources))

        divergent = synthesis.get("divergent_whys", [])
        if divergent:
            parts.append("### Divergent Approaches (trade-offs)")
            for d in divergent:
                parts.append("- %s" % json.dumps(d, ensure_ascii=False))

        traps = synthesis.get("combined_traps", [])
        if traps:
            parts.append("### Known Traps")
            for t in traps:
                parts.append("- [%s] %s (source: %s)" % (
                    t.get("severity", "medium").upper(), t.get("trap", ""), t.get("source", "")))

        contract = synthesis.get("skill_contract", {})
        if contract:
            parts.append("### Skill Contract")
            parts.append("- Purpose: %s" % contract.get("purpose", ""))
            caps = contract.get("capabilities", [])
            if caps:
                parts.append("- Capabilities: %s" % ", ".join(caps))
            rec = synthesis.get("recommendation", "")
            if rec:
                parts.append("- Key Insight: %s" % rec)
        parts.append("")

    # Section 4: Soul details (from GitHub repos — real extractions)
    repo_souls = [s for s in souls if s.get("source") not in ("clawhub", "local", "clawhub_ref")]
    if repo_souls:
        parts.append("## Soul Extractions (from real project source code)")
        for soul in repo_souls:
            parts.append("### %s" % soul.get("project_name", "unknown"))
            parts.append("- Philosophy: %s" % soul.get("design_philosophy", ""))
            parts.append("- Mental Model: %s" % soul.get("mental_model", ""))
            for d in soul.get("why_decisions", []):
                parts.append("- WHY: %s (evidence: %s, confidence: %s)" % (
                    d.get("decision", ""), d.get("evidence", ""), d.get("confidence", "")))
            for t in soul.get("unsaid_traps", []):
                parts.append("- UNSAID: [%s] %s" % (t.get("severity", "medium"), t.get("trap", "")))
            parts.append("")

    # Section 5: Domain bricks (FULL content, never truncated)
    if bricks:
        parts.append("## Domain Baseline Knowledge (expert-curated bricks)")
        parts.append("These are verified domain facts. Include them COMPLETELY in the output, especially UNSAID content.")
        parts.append("")
        for brick in bricks[:20]:  # Cap at 20 bricks
            stmt = brick.get("statement", "")
            ktype = brick.get("knowledge_type", "fact")
            brick_id = brick.get("brick_id", "")
            confidence = brick.get("confidence", "medium")
            label = {"failure": "RISK", "constraint": "CONSTRAINT", "capability": "CAPABILITY"}.get(ktype, "FACT")
            parts.append("- [%s] (id: %s, confidence: %s) %s" % (label, brick_id, confidence, stmt))
        parts.append("")

    # Section 6: Reference tools (ClawHub/Local — market context only)
    clawhub_souls = [s for s in souls if s.get("source") in ("clawhub", "clawhub_ref")]
    local_souls = [s for s in souls if s.get("source") == "local"]
    if clawhub_souls or local_souls:
        parts.append("## Reference Tools (market context, NOT knowledge sources)")
        for s in clawhub_souls:
            name = s.get("project_name", "").replace("clawhub:", "")
            desc = s.get("design_philosophy", "")
            parts.append("- ClawHub: %s — %s" % (name, desc))
        for s in local_souls[:3]:
            name = s.get("project_name", "").replace("local:", "")
            desc = s.get("design_philosophy", "")
            if desc:
                parts.append("- Local: %s — %s" % (name, desc))
        parts.append("")

    prompt = "\n".join(parts)
    if len(prompt) > max_chars:
        prompt = prompt[:max_chars] + "\n\n...[prompt truncated to %d chars]" % max_chars
        if _debug_logger is not None:
            _debug_logger.detail("compile prompt TRUNCATED to %d chars" % max_chars)
    return prompt


def _strip_code_fences(text):
    """Remove markdown code fence wrappers if LLM wraps entire output in ```markdown...```.

    Only strips if the FIRST line is a code fence opener AND the LAST line is ```.
    This avoids accidentally removing code blocks that are part of the SKILL.md content.
    """
    text = text.strip()
    lines = text.split("\n")
    if len(lines) >= 3 and lines[0].startswith("```") and lines[-1].strip() == "```":
        text = "\n".join(lines[1:-1])
    return text


def _validate_skill_md(skill_md, domain):
    """Validate generated SKILL.md. Returns list of issues (empty = pass).

    Checks structure (sections), content (safety boundaries per domain),
    and minimum quality (line count).
    """
    issues = []
    lines = skill_md.strip().splitlines()
    lower = skill_md.lower()

    # Frontmatter check
    if not skill_md.strip().startswith("---"):
        issues.append("Missing YAML frontmatter")

    # Must have safety-related section
    has_safety = ("## Safety Boundaries" in skill_md
                  or "## Safety" in skill_md
                  or "## Anti-Patterns & Safety" in skill_md
                  or "## Anti-Patterns" in skill_md)
    if not has_safety:
        issues.append("Missing safety section (## Safety Boundaries or ## Anti-Patterns & Safety)")

    # Section count
    h2_count = sum(1 for line in lines if line.startswith("## "))
    if h2_count < 5:
        issues.append("Only %d sections (need >= 5)" % h2_count)

    # Length check
    if len(lines) < 50:
        issues.append("Only %d lines (need >= 50)" % len(lines))

    # Domain-specific safety checks (strict per-domain rules)
    domain_lower = (domain or "").lower()

    # Health/Medical — requires BOTH disclaimer AND emergency triage
    if any(k in domain_lower for k in ("health", "medical", "diagnosis", "symptom")):
        if not ("not medical advice" in lower or "非医疗建议" in lower
                or "consult a healthcare professional" in lower or "请咨询医疗专业人员" in lower):
            issues.append("Health domain missing required medical disclaimer")
        if not any(t in lower for t in ("emergency", "急诊", "chest pain", "胸痛",
                                         "difficulty breathing", "呼吸困难", "请立即就医",
                                         "call emergency", "seek immediate")):
            issues.append("Health domain missing emergency triage guidance")

    # Finance — requires disclaimer
    if any(k in domain_lower for k in ("finance", "investment", "trading", "tax")):
        if not ("not financial advice" in lower or "不构成投资建议" in lower
                or "not investment advice" in lower or "非投资建议" in lower):
            issues.append("Finance domain missing financial disclaimer")

    # Legal — requires disclaimer
    if any(k in domain_lower for k in ("legal", "compliance", "regulation")):
        if not ("not legal advice" in lower or "非法律建议" in lower):
            issues.append("Legal domain missing legal disclaimer")

    return issues


# ── YAML name slugify ──


def _slugify(value, max_len=40):
    """Semantic slug: handles CJK, truncates at word boundaries, max 40 chars.

    Examples:
      "WiFi password manager" → "wifi-password-manager"
      "记账app" → "记账app"
      "A very long title that exceeds forty characters limit" → "a-very-long-title-that-exceeds-forty"
    """
    import unicodedata
    normalized = unicodedata.normalize("NFKC", str(value)).strip()
    # Replace separators with space
    normalized = re.sub(r"[\s_/|]+", " ", normalized)

    # Split into semantic tokens (CJK runs stay together, Latin words separate)
    tokens = []
    buf = []
    cjk_buf = []
    for ch in normalized:
        cp = ord(ch)
        is_cjk = (0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF
                   or 0x3040 <= cp <= 0x30FF or 0xAC00 <= cp <= 0xD7AF)
        if is_cjk:
            if buf:
                tokens.extend(re.findall(r"[A-Za-z0-9]+", "".join(buf)))
                buf = []
            cjk_buf.append(ch)
        else:
            if cjk_buf:
                tokens.append("".join(cjk_buf))
                cjk_buf = []
            buf.append(ch)
    if cjk_buf:
        tokens.append("".join(cjk_buf))
    if buf:
        tokens.extend(re.findall(r"[A-Za-z0-9]+", "".join(buf)))

    if not tokens:
        return "compiled-skill"

    # Build slug by adding tokens until max_len
    parts = []
    for token in tokens:
        lower = token.lower() if re.search(r"[A-Za-z0-9]", token) else token
        candidate = lower if not parts else "-".join(parts) + "-" + lower
        if len(candidate) > max_len:
            break
        parts.append(lower)

    if not parts:
        return tokens[0][:max_len].lower() if re.search(r"[A-Za-z]", tokens[0]) else tokens[0][:max_len]

    return "-".join(parts).strip("-") or "compiled-skill"


# ── Quality Gate (60-point scoring) ──

_REQUIRED_HEADINGS = ["Role", "Domain Knowledge", "Decision Framework",
                      "Recommended Workflow", "Anti-Patterns"]
_WHY_RE = re.compile(r"\b(because|why|rather than|instead of|trade[- ]?off|constraint|rationale)\b", re.I)
_GENERIC_RE = re.compile(r"\b(best practice|industry standard|scalable solution|robust system)\b", re.I)


def _score_quality(skill_md):
    """Score SKILL.md on 5 dimensions (100-point scale). Returns dict with total + breakdown.

    Dimensions: Coverage (30%), Evidence (25%), DSD Health (20%), WHY Density (15%), Substance (10%).
    """
    lines = skill_md.strip().splitlines()
    lower = skill_md.lower()
    blockers = []

    # Extract H2 sections
    sections = {}
    h2_lines = [(i, line[3:].strip()) for i, line in enumerate(lines) if line.startswith("## ")]
    for idx, (line_no, heading) in enumerate(h2_lines):
        end = h2_lines[idx + 1][0] if idx + 1 < len(h2_lines) else len(lines)
        sections[heading] = "\n".join(lines[line_no + 1:end])

    # --- Coverage (30%) ---
    present = sum(1 for h in _REQUIRED_HEADINGS if any(h.lower() in sh.lower() for sh in sections))
    cov_raw = (present / len(_REQUIRED_HEADINGS)) * 100.0
    if not skill_md.strip().startswith("---"):
        cov_raw -= 12
        blockers.append("missing_yaml_frontmatter")
    workflow_text = next((v for k, v in sections.items() if "workflow" in k.lower()), "")
    anti_text = next((v for k, v in sections.items() if "anti-pattern" in k.lower()), "")
    wf_bullets = sum(1 for l in workflow_text.splitlines() if l.strip().startswith(("-", "*", "1", "2", "3", "4", "5")))
    ap_bullets = sum(1 for l in anti_text.splitlines() if l.strip().startswith(("-", "*")))
    if wf_bullets < 4:
        cov_raw -= 10
    if ap_bullets < 2:
        cov_raw -= 8
    cov_raw = max(0, min(100, cov_raw))

    # --- Evidence Quality (25%) ---
    knowledge_text = next((v for k, v in sections.items() if "knowledge" in k.lower()), "")
    evidence_hits = len(re.findall(r"\[(CODE|CATALOG|BASELINE)\]|github\.com|source:|README", knowledge_text, re.I))
    kb_bullets = max(1, sum(1 for l in knowledge_text.splitlines() if l.strip().startswith(("-", "*"))))
    ev_raw = min(100, (evidence_hits / kb_bullets) * 100)
    if evidence_hits == 0:
        ev_raw -= 25
    ev_raw = max(0, min(100, ev_raw))

    # --- DSD Health (20%) — Design-Soul Differentiation ---
    combined = " ".join(sections.get(k, "") for k in sections if any(
        w in k.lower() for w in ("knowledge", "framework", "anti-pattern", "safety")))
    specific = len(re.findall(r"\b(prefer|avoid|unless|except|trade[- ]?off|failure|trap|constraint)\b", combined, re.I))
    generic = len(_GENERIC_RE.findall(combined))
    dsd_raw = min(100, specific * 9.0) - min(25, generic * 5.0)
    dsd_raw = max(0, dsd_raw)

    # --- WHY Density (15%) ---
    sentences = [s.strip() for s in re.split(r"[.!?\n]+", skill_md) if s.strip()]
    why_hits = sum(1 for s in sentences if _WHY_RE.search(s))
    why_ratio = why_hits / max(1, len(sentences))
    why_raw = min(100, why_ratio * 220)

    # --- Substance (10%) ---
    tokens = re.findall(r"[A-Za-z0-9_\-\u4e00-\u9fff]+", skill_md)
    unique_ratio = len(set(tokens)) / max(1, len(tokens))
    sub_raw = min(100, len(tokens) / 12.0) + min(25, unique_ratio * 40)
    if len(tokens) < 220:
        sub_raw -= 20
    sub_raw = max(0, min(100, sub_raw))

    # --- Total ---
    total = round(cov_raw * 0.30 + ev_raw * 0.25 + dsd_raw * 0.20 + why_raw * 0.15 + sub_raw * 0.10, 1)

    if present < 3:
        blockers.append("fewer_than_3_required_sections")

    return {
        "total": total,
        "passed": total >= 60.0 and not blockers,
        "blockers": blockers,
        "coverage": round(cov_raw, 1),
        "evidence": round(ev_raw, 1),
        "dsd_health": round(dsd_raw, 1),
        "why_density": round(why_raw, 1),
        "substance": round(sub_raw, 1),
    }


# ── Fast Path Synthesis (Python-only, no LLM) ──


def _synthesize_fast(souls, profile):
    """Synthesize from souls without LLM call.

    Only REAL repo souls contribute to consensus knowledge.
    ClawHub/Local are reference tools only — NOT knowledge sources.
    """
    # Only repo souls contribute knowledge (not ClawHub marketing copy)
    repo_souls = [s for s in souls if s.get("source") not in ("clawhub", "local", "clawhub_ref")]

    # Collect design philosophies as consensus — ONLY from real repos
    consensus = []
    seen_statements = set()
    for soul in repo_souls:
        phil = soul.get("design_philosophy", "").strip()
        if phil and phil not in seen_statements:
            consensus.append({
                "statement": phil,
                "sources": [soul["project_name"]],
            })
            seen_statements.add(phil)

    # Collect traps — ONLY from real repos
    traps = []
    for soul in repo_souls:
        for trap in soul.get("unsaid_traps", []):
            trap_text = trap.get("trap", "")
            if trap_text:
                traps.append({
                    "trap": trap_text,
                    "severity": trap.get("severity", "medium"),
                    "source": soul["project_name"],
                })

    # Collect capabilities — ONLY from real repos
    capabilities = []
    for soul in repo_souls:
        for d in soul.get("why_decisions", []):
            decision = d.get("decision", "")
            if decision:
                capabilities.append(decision)

    return {
        "consensus_whys": consensus[:5],
        "divergent_whys": [],
        "combined_traps": traps[:7],
        "recommendation": "",
        "skill_contract": {
            "purpose": profile.get("intent", ""),
            "capabilities": capabilities[:5],
            "workflow_steps": [],
        },
    }


# ── Compilation ──


# ── Section-split compile specs ──

_COMPILE_SECTIONS = [
    {"key": "role", "heading": "## Role",
     "goal": "Define the AI's persona, specialization, and decision posture in this domain.",
     "max_tokens": 700},
    {"key": "knowledge", "heading": "## Domain Knowledge",
     "goal": "Compile the strongest evidence-backed WHY knowledge from synthesis, repos, and bricks.",
     "max_tokens": 1500},
    {"key": "framework", "heading": "## Decision Framework",
     "goal": "Explain the core trade-offs and when-to-choose-A-vs-B rules. At least 2 pairs.",
     "max_tokens": 1100},
    {"key": "workflow", "heading": "## Recommended Workflow",
     "goal": "Provide a concrete step sequence (5+ steps) using the extracted design philosophy.",
     "max_tokens": 1100},
    {"key": "anti_patterns", "heading": "## Anti-Patterns & Safety",
     "goal": "List traps, failure modes (3+), and safety boundaries. Prefer specific over generic.",
     "max_tokens": 1100},
]


def _build_shared_compile_packet(synthesis, souls, profile, bricks, reference_content,
                                  max_chars=12000):
    """Build a compact shared context packet for per-section compile calls."""
    parts = []
    parts.append("## User Context")
    parts.append("- Domain: %s" % profile.get("domain", "general"))
    parts.append("- Intent: %s" % profile.get("intent", ""))
    parts.append("- Intent (English): %s" % profile.get("intent_en", ""))
    parts.append("- User type: %s" % profile.get("user_type", "unknown"))
    parts.append("")

    if reference_content:
        parts.append("## Reference Skill (gold standard)")
        parts.append(reference_content[:2500])
        parts.append("")

    contract = synthesis.get("skill_contract", {})
    parts.append("## Synthesis Contract")
    parts.append("- Purpose: %s" % contract.get("purpose", ""))
    caps = contract.get("capabilities", [])[:6]
    if caps:
        parts.append("- Capabilities: %s" % ", ".join(caps))
    parts.append("")

    consensus = synthesis.get("consensus_whys", [])
    if consensus:
        parts.append("## Consensus WHYs")
        for c in consensus[:8]:
            stmt = c.get("statement", "") if isinstance(c, dict) else str(c)
            parts.append("- %s" % stmt)
        parts.append("")

    traps = synthesis.get("combined_traps", [])
    if traps:
        parts.append("## Combined Traps")
        for t in traps[:8]:
            trap_text = t.get("trap", "") if isinstance(t, dict) else str(t)
            parts.append("- %s" % trap_text)
        parts.append("")

    repo_souls = [s for s in souls if s.get("source") not in ("clawhub", "local", "clawhub_ref")]
    if repo_souls:
        parts.append("## Repo Souls")
        for soul in repo_souls[:8]:
            parts.append("- %s: philosophy=%s | model=%s" % (
                soul.get("project_name", "?"),
                str(soul.get("design_philosophy", ""))[:220],
                str(soul.get("mental_model", ""))[:140],
            ))
        parts.append("")

    if bricks:
        parts.append("## Baseline Bricks")
        for brick in bricks[:8]:
            parts.append("- %s: %s" % (
                brick.get("brick_id", "brick"),
                str(brick.get("statement", ""))[:220],
            ))
        parts.append("")

    packet = "\n".join(parts)
    return packet[:max_chars]


def _compile_one_section(spec, shared_packet, profile):
    """Generate one section via a small LLM call. Returns markdown string."""
    language = "Chinese" if re.search(r"[\u4e00-\u9fff]", str(profile.get("intent", ""))) else "English"
    prompt = (
        "Write only the markdown content for the section `%s`.\n"
        "Goal: %s\n"
        "Language: %s\n"
        "Hard rules:\n"
        "- Output only this one section.\n"
        "- Start with the exact heading line.\n"
        "- Be concrete and evidence-backed.\n"
        "- Do not include YAML frontmatter or title.\n\n"
        "%s"
    ) % (spec["heading"], spec["goal"], language, shared_packet)

    text = call_llm(
        SKILL_ARCHITECT_SYSTEM, prompt,
        max_tokens=spec["max_tokens"],
        stage_name="compile_%s" % spec["key"],
    )
    text = _strip_code_fences(text).strip()
    if not text.startswith(spec["heading"]):
        text = "%s\n%s" % (spec["heading"], text)
    return text


def _section_fallback(spec, synthesis, profile):
    """Deterministic fallback for a single section."""
    if spec["key"] == "role":
        return "## Role\nYou are a specialist assistant for %s. Prioritize extracted project rationale over generic best practices." % profile.get("domain", "this domain")
    if spec["key"] == "knowledge":
        whys = synthesis.get("consensus_whys", [])
        bullets = "\n".join("- %s" % (w.get("statement", w) if isinstance(w, dict) else str(w)) for w in whys[:6])
        return "## Domain Knowledge\n%s" % (bullets or "- Use the strongest evidence-backed design rationale available.")
    if spec["key"] == "framework":
        return "## Decision Framework\n- Prefer approaches aligned with extracted design philosophy.\n- Choose simpler paths before adding abstractions.\n- Reject patterns contradicting observed repo constraints."
    if spec["key"] == "workflow":
        return "## Recommended Workflow\n1. Read the user goal and constraints.\n2. Match to extracted philosophy.\n3. Pick the closest decision pattern.\n4. Warn about highest-risk traps.\n5. Produce the smallest viable next step."
    return "## Anti-Patterns & Safety\n- Do not replace extracted WHY knowledge with generic advice.\n- Do not recommend workflows violating repo constraints.\n- Flag missing evidence before giving strong recommendations."


def compile_skill(synthesis, souls, profile, bricks=None):
    """Section-split Skill Architect: 5 small LLM calls + targeted repair.

    v12.1.0: Replaces single-shot 6000-token call (60s timeout, 72% fallback)
    with 5 focused calls (~700-1500 tokens each). Failed sections get individual
    retry or deterministic fallback. Template fallback only if ALL sections fail.
    """
    domain = profile.get("domain", "general")
    user_type = profile.get("user_type", "unknown")

    # 1. Reference skill
    ref_level = _select_reference_level(domain, user_type)
    ref_content = _load_reference_skill(ref_level)
    if _debug_logger is not None:
        _debug_logger.detail("reference skill: level=%s, loaded=%d chars" % (ref_level, len(ref_content)))

    # 2. Build shared packet (compact context for all section calls)
    shared_packet = _build_shared_compile_packet(synthesis, souls, profile, bricks, ref_content)

    # 3. Generate each section with individual retry
    sections = {}
    failed_sections = []
    for spec in _COMPILE_SECTIONS:
        try:
            sections[spec["key"]] = _compile_one_section(spec, shared_packet, profile)
            if _debug_logger is not None:
                _debug_logger.detail("section %s: %d lines" % (spec["key"], len(sections[spec["key"]].splitlines())))
        except Exception as e:
            _log("Section %s failed: %s — using fallback" % (spec["key"], e))
            sections[spec["key"]] = _section_fallback(spec, synthesis, profile)
            failed_sections.append(spec["key"])

    if _debug_logger is not None:
        _debug_logger.detail("compile: %d/%d sections via LLM, %d fallback" % (
            len(_COMPILE_SECTIONS) - len(failed_sections), len(_COMPILE_SECTIONS), len(failed_sections)))

    # 4. Assemble
    intent = profile.get("intent_en", profile.get("intent", "compiled skill"))
    title = re.sub(r"\s+", " ", str(intent)).strip()[:80]
    slug = _slugify(title)

    when_to_use = (
        "## When to Use\n"
        "- Use when the user needs help with %s.\n"
        "- Use when repo-specific design trade-offs matter more than generic advice.\n"
        "- Use when explicit traps, constraints, and decision guidance are needed."
    ) % profile.get("intent", "this task")

    skill_md = "\n\n".join([
        "---\nname: %s\ndescription: >\n  %s\n---" % (slug, intent),
        "# %s" % title,
        when_to_use,
        sections["role"],
        sections["knowledge"],
        sections["framework"],
        sections["workflow"],
        sections["anti_patterns"],
    ]).strip()

    # 5. Validate and targeted repair
    issues = _validate_skill_md(skill_md, domain)
    if _debug_logger is not None:
        if issues:
            _debug_logger.detail("validation issues: %s" % issues)
        else:
            _debug_logger.detail("validation PASSED")

    if issues:
        # Map issues to sections for targeted repair
        issue_map = {
            "safety": "anti_patterns", "anti-pattern": "anti_patterns",
            "workflow": "workflow", "decision framework": "framework",
            "role": "role", "knowledge": "knowledge",
        }
        to_repair = set()
        for issue in issues:
            lowered = issue.lower()
            for needle, section_key in issue_map.items():
                if needle in lowered:
                    to_repair.add(section_key)

        for spec in _COMPILE_SECTIONS:
            if spec["key"] not in to_repair:
                continue
            _log("Repairing section: %s" % spec["key"])
            try:
                sections[spec["key"]] = _compile_one_section(spec, shared_packet, profile)
            except Exception:
                pass  # Keep existing version

        # Re-assemble
        skill_md = "\n\n".join([
            "---\nname: %s\ndescription: >\n  %s\n---" % (slug, intent),
            "# %s" % title,
            when_to_use,
            sections["role"],
            sections["knowledge"],
            sections["framework"],
            sections["workflow"],
            sections["anti_patterns"],
        ]).strip()

        # High-risk domain safety check
        is_high_risk = any(k in domain.lower() for k in _HIGH_RISK_DOMAINS)
        if is_high_risk:
            remaining = _validate_skill_md(skill_md, domain)
            safety_missing = any("safety" in i.lower() for i in remaining)
            if safety_missing:
                _log("HIGH-RISK domain '%s' missing safety after repair — template fallback" % domain)
                return _compile_skill_template(synthesis, souls, profile, bricks)

    # Append generation footer
    if "*Generated by Doramagic" not in skill_md:
        skill_md += "\n\n---\n*Generated by Doramagic v12.1.0 — 不教用户做事，给他工具。*"

    return skill_md


def _compile_skill_template(synthesis, souls, profile, bricks=None):
    """Fallback: Python template compilation (v11.0 style). Used when LLM fails."""
    contract = synthesis.get("skill_contract", {})
    purpose = contract.get("purpose", profile.get("intent", ""))
    capabilities = contract.get("capabilities", [])
    consensus = synthesis.get("consensus_whys", [])
    traps = synthesis.get("combined_traps", [])
    domain = profile.get("domain", "general")
    intent_en = profile.get("intent_en", purpose)
    topic = profile.get("topic", "custom-skill")
    skill_name = _slugify(topic)

    lines = [
        "---",
        "name: %s" % skill_name,
        "description: |",
        "  %s" % (intent_en or purpose),
        "version: 1.0.0",
        "domain: %s" % domain,
        "tags: [doramagic-generated]",
        "---\n",
        "# %s\n" % topic,
        "## Role\n",
        "You are a domain expert in **%s**.\n" % domain,
    ]

    if consensus:
        lines.append("## Domain Knowledge\n")
        for w in consensus:
            src = ", ".join(w.get("sources", []))
            lines.append("- %s (from: %s)" % (w.get("statement", ""), src))
        lines.append("")

    if bricks:
        lines.append("## Domain Baseline Knowledge\n")
        for brick in bricks[:10]:
            stmt = brick.get("statement", "")
            if stmt:
                lines.append("- %s" % stmt)  # No truncation in fallback either
        lines.append("")

    if traps:
        lines.append("## Warnings\n")
        for t in traps:
            lines.append("- [%s] %s" % (t.get("severity", "medium").upper(), t.get("trap", "")))
        lines.append("")

    if capabilities:
        lines.append("## Capabilities\n")
        for c in capabilities:
            lines.append("- %s" % c)
        lines.append("")

    lines.append("---")
    lines.append("*Generated by Doramagic v12.1.0 (template fallback) — 不教用户做事，给他工具。*")
    return "\n".join(lines)


# ── Main ──



def _sanitize_input(raw: str) -> str:
    """Sanitize user input to prevent shell metacharacter injection.

    Doramagic expects natural language queries (e.g. "WiFi密码管理").
    Strip shell-dangerous characters that have no place in such input.
    """
    dangerous = set('`$;|&><\\')
    sanitized = "".join(c for c in raw if c not in dangerous)
    sanitized = sanitized.replace('"', "'")
    return sanitized.strip()


def _save_checkpoint(rd, step, data):
    """Atomic checkpoint write (POSIX write-then-rename)."""
    cp_dir = rd / "checkpoints"
    cp_dir.mkdir(parents=True, exist_ok=True)
    tmp = cp_dir / ("%s.tmp" % step)
    final = cp_dir / ("%s.json" % step)
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.rename(final)


def _load_checkpoint(rd, step):
    """Load checkpoint if it exists. Returns data dict or None."""
    cp_file = rd / "checkpoints" / ("%s.json" % step)
    if cp_file.exists():
        try:
            return json.loads(cp_file.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def main():
    parser = argparse.ArgumentParser(description="Doramagic Single-Shot v12.1.0")
    parser.add_argument("--input", required=True, help="User input text")
    parser.add_argument("--run-dir", required=True, help="Base run directory")
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Enable debug logging: writes debug.log and LLM traces to run directory",
    )
    parser.add_argument(
        "--resume",
        default=None,
        help="Resume from a previous run directory (e.g. 20260327_143000). Skips completed steps.",
    )
    args = parser.parse_args()

    args.input = _sanitize_input(args.input)

    run_dir = Path(os.path.expanduser(args.run_dir))
    if args.resume:
        run_id = args.resume
        rd = run_dir / run_id
        if not rd.exists():
            _log("Resume directory not found: %s" % rd)
            sys.exit(1)
        _log("Resuming run %s" % run_id)
    else:
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        rd = run_dir / run_id
        rd.mkdir(parents=True, exist_ok=True)

    # Initialize debug logger if requested
    global _debug_logger
    if args.debug:
        _debug_logger = DebugLogger(run_dir, run_id)

    _log("Starting run %s" % run_id)
    if _debug_logger is not None:
        _debug_logger.detail("run_dir=%s" % rd)
        _debug_logger.detail("input=%r" % args.input)

    # ── Step 1: Build profile ──
    cached_profile = _load_checkpoint(rd, "step1_profile")
    if cached_profile:
        profile = cached_profile
        _log("Resumed Step 1 from checkpoint")
    else:
        if _debug_logger is not None:
            _debug_logger.stage("Step 1: build_need_profile")
        t0 = time.time()
        profile = build_need_profile(args.input)
        with open(rd / "need_profile.json", "w") as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)
        _save_checkpoint(rd, "step1_profile", profile)
        _log("Profile: keywords=%s" % profile["keywords"])
        if _debug_logger is not None:
            _debug_logger.timing("build_need_profile", (time.time() - t0) * 1000)
            _debug_logger.detail("profile saved to need_profile.json")

    # ── Step 1.5: Socratic gate ──
    confidence = profile.get("confidence", 1.0)
    questions = profile.get("questions", [])
    if confidence < 0.7 and questions:
        if _debug_logger is not None:
            _debug_logger.stage("Step 1.5: Socratic gate — ASKING")
            _debug_logger.detail("confidence=%.2f < 0.7, returning questions" % confidence)
            _debug_logger.summary()

        intent_hint = profile.get("intent_en", profile.get("intent", ""))
        msg_parts = ["为了锻造最精准的道具，我想先确认：\n"]
        for q in questions[:2]:
            msg_parts.append("• %s" % q)
        msg_parts.append("\n确认后直接发：")
        msg_parts.append("/dora %s <你的补充>" % profile.get("intent", "").strip())
        _output({"message": "\n".join(msg_parts), "run_id": run_id})

    if _debug_logger is not None:
        _debug_logger.detail("confidence=%.2f >= 0.7, proceeding to search" % confidence)

    # ── Step 2: Search all sources ──

    # 2a: ClawHub skill registry
    if _debug_logger is not None:
        _debug_logger.stage("Step 2a: search_clawhub")

    t0 = time.time()
    clawhub_skills = search_clawhub(profile["keywords"])
    with open(rd / "clawhub_results.json", "w") as f:
        json.dump(clawhub_skills, f, ensure_ascii=False, indent=2)
    if _debug_logger is not None:
        _debug_logger.timing("search_clawhub", (time.time() - t0) * 1000)

    # 2b: Local OpenClaw skills
    if _debug_logger is not None:
        _debug_logger.stage("Step 2b: scan_local_skills")

    t0 = time.time()
    local_skills = scan_local_skills(profile["keywords"])
    with open(rd / "local_skills.json", "w") as f:
        json.dump(local_skills, f, ensure_ascii=False, indent=2)
    if _debug_logger is not None:
        _debug_logger.timing("scan_local_skills", (time.time() - t0) * 1000)

    # 2c: GitHub Primary + ClawHub as depth control (never skip GitHub)
    if _debug_logger is not None:
        _debug_logger.stage("Step 2c: GitHub primary discovery")

    # ClawHub controls depth, not skip: strong catalog → top=2, else top=3
    strong_clawhub = [s for s in clawhub_skills if s.get("score", 0) >= 1.10]
    github_top_k = 2 if len(strong_clawhub) >= 2 else 3

    if _debug_logger is not None:
        _debug_logger.detail("strong_clawhub=%d (score>=1.10), github_top_k=%d" % (
            len(strong_clawhub), github_top_k))

    repos = []
    engine_out = {}

    # Always attempt GitHub — build engine profile
    engine_profile = dict(profile)
    if profile.get("github_queries"):
        gq_keywords = []
        seen = set()
        for q in profile["github_queries"]:
            for word in q.split():
                wl = word.lower()
                if wl not in seen and len(wl) >= 2:
                    gq_keywords.append(word)
                    seen.add(wl)
        engine_profile["keywords"] = gq_keywords[:6]
        if _debug_logger is not None:
            _debug_logger.detail("engine keywords: %s" % engine_profile["keywords"])

    engine_need_path = rd / "need_profile_engine.json"
    with open(engine_need_path, "w") as f:
        json.dump(engine_profile, f, ensure_ascii=False, indent=2)

    # Try engine subprocess first
    engine = _find_engine()
    engine_timeout = 120
    t0 = time.time()

    if engine is not None:
        _log("GitHub primary: engine at %s (top=%d, timeout=%ds)" % (engine, github_top_k, engine_timeout))
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
                    str(github_top_k),
                    "--timeout",
                    str(engine_timeout),
                ],
                capture_output=True,
                text=True,
                timeout=engine_timeout,
            )

            if _debug_logger is not None:
                (rd / "engine_stdout.txt").write_text(result.stdout, encoding="utf-8")
                (rd / "engine_stderr.txt").write_text(result.stderr, encoding="utf-8")
                _debug_logger.detail("engine returncode=%d, stdout=%d bytes" % (
                    result.returncode, len(result.stdout)))

            if result.returncode == 0 and result.stdout.strip():
                engine_out = json.loads(result.stdout)
                repos = engine_out.get("repos", engine_out.get("repos_analyzed", []))
                if _debug_logger is not None:
                    _debug_logger.detail("engine found %d repos" % len(repos))
            else:
                _log("Engine returned no repos, falling back to API search")
                if _debug_logger is not None:
                    _debug_logger.detail("engine no repos — stderr: %s" % result.stderr[-200:])
        except subprocess.TimeoutExpired:
            _log("Engine timed out (%ds), falling back to API search" % engine_timeout)
        except Exception as e:
            _log("Engine error: %s, falling back to API search" % e)
    else:
        _log("Engine not found, using direct API search")

    # API fallback: if engine returned no repos, try package-level github_search
    if not repos:
        if _debug_logger is not None:
            _debug_logger.detail("attempting direct GitHub API fallback")
        try:
            # Import package-level search
            pkg_community = SCRIPT_DIR.parent / "packages" / "community"
            if str(pkg_community) not in sys.path:
                sys.path.insert(0, str(pkg_community))
            from doramagic_community.github_search import search_github
            query_terms = engine_profile.get("keywords", profile.get("relevance_terms", []))
            query_terms = [str(t).strip() for t in query_terms if str(t).strip()][:4]
            if query_terms:
                repos = search_github(query_terms, top_k=github_top_k)
                _log("API fallback found %d repos" % len(repos))
                if _debug_logger is not None:
                    _debug_logger.detail("API fallback repos: %d" % len(repos))
        except Exception as e:
            _log("API fallback failed: %s" % e)
            if _debug_logger is not None:
                _debug_logger.detail("API fallback error: %s" % e)

    if _debug_logger is not None:
        _debug_logger.timing("github_discovery", (time.time() - t0) * 1000)

    # ── Step 2.5: Relevance gate ──
    if _debug_logger is not None:
        _debug_logger.stage("Step 2.5: relevance gate")

    t0 = time.time()
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

    if _debug_logger is not None:
        _debug_logger.timing("relevance_gate", (time.time() - t0) * 1000)

    total_sources = len(repos) + len(clawhub_skills) + len(local_skills)
    _log("Sources after relevance gate: %d repos, %d ClawHub skills, %d local skills" % (
        len(repos), len(clawhub_skills), len(local_skills)
    ))

    if total_sources == 0:
        # Honest report: nothing relevant found
        if _debug_logger is not None:
            _debug_logger.detail("EARLY EXIT: no sources found after relevance gate")
            _debug_logger.summary()
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

    # ── Step 2.7: Repo type classification ──
    # Deterministic classifier: CATALOG (awesome-lists), TOOL (apps/libs), FRAMEWORK
    # CATALOG repos get shallow extraction (README only, no deep code analysis)
    for repo in repos:
        name = (repo.get("name") or "").lower()
        desc = (repo.get("description") or "").lower()
        readme = (repo.get("readme_text") or repo.get("readme") or "").lower()[:3000]

        # CATALOG signals
        is_catalog = False
        if name.startswith("awesome-") or name.startswith("awesome_"):
            is_catalog = True
        elif readme:
            # High external link density + no source code = catalog
            link_count = readme.count("http://") + readme.count("https://")
            text_len = max(len(readme), 1)
            if link_count > 20 and link_count / text_len > 0.01:
                is_catalog = True

        # Source code presence check
        has_code = bool(repo.get("facts", {}).get("languages") or repo.get("facts", {}).get("focus_files"))

        if is_catalog:
            repo["_repo_type"] = "CATALOG"
        elif has_code:
            # Check framework signals
            frameworks = repo.get("facts", {}).get("frameworks", [])
            if frameworks:
                repo["_repo_type"] = "FRAMEWORK"
            else:
                repo["_repo_type"] = "TOOL"
        else:
            repo["_repo_type"] = "TOOL"

        if _debug_logger is not None:
            _debug_logger.detail("repo %s classified as %s" % (repo.get("name", "?"), repo["_repo_type"]))

    # ── Step 3: Soul extraction ──
    if _debug_logger is not None:
        _debug_logger.stage("Step 3: soul extraction")

    # Pre-load domain bricks for extraction enrichment
    extraction_bricks = load_matching_bricks(
        profile.get("domain", ""),
        profile.get("keywords", []),
    )
    if extraction_bricks and _debug_logger is not None:
        _debug_logger.detail("extraction bricks: %d loaded for soul extraction prompts" % len(extraction_bricks))

    t0 = time.time()
    souls = []

    def _extract_one(repo):
        """Extract soul for one repo (thread-safe: LLM calls are I/O-bound)."""
        name = repo.get("name", "unknown")
        local_dir = repo.get("local_dir") or repo.get("local_path", "")
        facts = repo.get("facts", {})
        repo_type = repo.get("_repo_type", "TOOL")
        _log("Extracting soul: %s (%s)" % (name, repo_type))
        return extract_soul(name, local_dir, facts, bricks=extraction_bricks, repo_type=repo_type)

    if len(repos) > 1:
        # Parallel extraction for multiple repos
        from concurrent.futures import ThreadPoolExecutor, as_completed
        _log("Parallel soul extraction for %d repos" % len(repos))
        with ThreadPoolExecutor(max_workers=min(3, len(repos))) as pool:
            future_to_repo = {pool.submit(_extract_one, repo): repo for repo in repos}
            for future in as_completed(future_to_repo):
                repo = future_to_repo[future]
                name = repo.get("name", "unknown")
                try:
                    soul = future.result()
                    if soul:
                        souls.append(soul)
                        staging = rd / "staging" / name.replace("/", "-")
                        staging.mkdir(parents=True, exist_ok=True)
                        with open(staging / "repo_soul.json", "w") as f:
                            json.dump(soul, f, ensure_ascii=False, indent=2)
                except Exception as e:
                    _log("Soul extraction thread failed for %s: %s" % (name, e))
    else:
        # Single repo: no threading overhead
        for repo in repos:
            soul = _extract_one(repo)
            if soul:
                name = repo.get("name", "unknown")
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

    if _debug_logger is not None:
        _debug_logger.timing("soul_extraction_total", (time.time() - t0) * 1000)
        _debug_logger.detail("souls built: %d total (repos=%d clawhub=%d local=%d)" % (
            len(souls), len(souls) - len(clawhub_skills) - len(local_skills),
            len(clawhub_skills), len(local_skills)))

    if not souls:
        if _debug_logger is not None:
            _debug_logger.detail("EARLY EXIT: all sources yielded no souls")
            _debug_logger.summary()
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

    # Checkpoint after soul extraction (most expensive step)
    _save_checkpoint(rd, "step3_souls", {"souls": souls, "repos_count": len(repos)})

    # ── Step 4: Community signals ──
    if _debug_logger is not None:
        _debug_logger.stage("Step 4: community signals")

    t0 = time.time()
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
    if _debug_logger is not None:
        _debug_logger.timing("community_signals_total", (time.time() - t0) * 1000)
        _debug_logger.detail("community signals total: %d" % len(all_signals))

    # ── Step 5: Synthesis ──
    if _debug_logger is not None:
        _debug_logger.stage("Step 5: synthesis")

    t0 = time.time()

    # Fast path: if no real repo souls, use Python-only synthesis (no LLM)
    has_repo_souls = any(s.get("source") not in ("clawhub", "local", "clawhub_ref") for s in souls)
    if not has_repo_souls:
        _log("Fast path synthesis: Python-only (no LLM)")
        syn = _synthesize_fast(souls, profile)
        if _debug_logger is not None:
            _debug_logger.detail("FAST PATH synthesis — no LLM, Python-only from %d souls" % len(souls))
    else:
        _log("Synthesizing via LLM...")
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
        if _debug_logger is not None:
            _debug_logger.detail("synthesis FAILED — using best-soul fallback: %s" % best["project_name"])

    if _debug_logger is not None:
        _debug_logger.timing("synthesis", (time.time() - t0) * 1000)

    (rd / "staging").mkdir(parents=True, exist_ok=True)
    with open(rd / "staging" / "synthesis.json", "w") as f:
        json.dump(syn, f, ensure_ascii=False, indent=2)

    # ── Step 5.5: Load domain bricks ──
    domain_bricks = load_matching_bricks(
        profile.get("domain", ""),
        profile.get("keywords", []),
    )
    if domain_bricks:
        _log("Loaded %d domain bricks" % len(domain_bricks))
        if _debug_logger is not None:
            _debug_logger.detail("domain bricks loaded: %d from domain=%s" % (
                len(domain_bricks), profile.get("domain", "")))
    elif _debug_logger is not None:
        _debug_logger.detail("no matching domain bricks found")

    # ── Step 6: Compile ──
    if _debug_logger is not None:
        _debug_logger.stage("Step 6: compile")

    _log("Compiling skill...")
    t0 = time.time()
    skill_md = compile_skill(syn, souls, profile, bricks=domain_bricks)

    if _debug_logger is not None:
        _debug_logger.timing("compile_skill", (time.time() - t0) * 1000)
        _debug_logger.detail("SKILL.md compiled: %d bytes, %d lines" % (
            len(skill_md), skill_md.count("\n")))

    # ── Step 6.5: Quality gate (60-point minimum) ──
    quality_score = _score_quality(skill_md)
    quality_passed = quality_score["total"] >= 60.0 and not quality_score["blockers"]

    if _debug_logger is not None:
        _debug_logger.detail("quality gate: %.1f/100, passed=%s, blockers=%s" % (
            quality_score["total"], quality_passed, quality_score["blockers"]))

    # Save quality report
    (rd / "quality_gate.json").write_text(
        json.dumps(quality_score, ensure_ascii=False, indent=2), encoding="utf-8")

    if not quality_passed:
        _log("Quality gate FAILED (%.1f/100) — falling back to template" % quality_score["total"])
        skill_md = _compile_skill_template(syn, souls, profile, bricks=domain_bricks)
        # Re-score template output (for logging)
        template_score = _score_quality(skill_md)
        if _debug_logger is not None:
            _debug_logger.detail("template fallback score: %.1f/100" % template_score["total"])
    else:
        _log("Quality gate PASSED (%.1f/100)" % quality_score["total"])

    delivery = rd / "delivery"
    delivery.mkdir(parents=True, exist_ok=True)
    with open(delivery / "SKILL.md", "w") as f:
        f.write(skill_md)

    # ── Step 7: Output with completeness tier ──
    if _debug_logger is not None:
        _debug_logger.stage("Step 7: output")

    _log("Done!")

    contract = syn.get("skill_contract", {})
    capabilities = contract.get("capabilities", [])
    consensus = syn.get("consensus_whys", [])
    traps = syn.get("combined_traps", [])

    # Categorize sources
    repo_souls = [s for s in souls if s.get("source") != "clawhub" and s.get("source") != "local"]
    ch_souls = [s for s in souls if s.get("source") == "clawhub"]
    local_souls = [s for s in souls if s.get("source") == "local"]

    # Determine completeness tier
    if repo_souls and quality_passed:
        completeness_tier = "FULL"
        completeness_pct = 100
    elif repo_souls and not quality_passed:
        completeness_tier = "PARTIAL_SOULS"
        completeness_pct = 70
    elif not repo_souls and (ch_souls or local_souls):
        completeness_tier = "FAST_PATH"
        completeness_pct = 55
    else:
        completeness_tier = "TEMPLATE"
        completeness_pct = 20

    if _debug_logger is not None:
        _debug_logger.detail("completeness: %s (%d%%)" % (completeness_tier, completeness_pct))

    msg = []
    if completeness_pct == 100:
        msg.append("**Doramagic 道具锻造完成！**\n")
    elif completeness_pct >= 55:
        msg.append("**Doramagic 道具锻造完成！**（完整度 %d%%）\n" % completeness_pct)
    else:
        msg.append("**Doramagic 道具（基础版）**（完整度 %d%%）\n" % completeness_pct)
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

    if _debug_logger is not None:
        _debug_logger.detail("output JSON ready, message length=%d chars" % len("\n".join(msg)))
        _debug_logger.summary()

    _output(
        {
            "message": "\n".join(msg),
            "delivery_path": str(delivery),
            "run_id": run_id,
            "repos_analyzed": len(souls),
            "completeness_tier": completeness_tier,
            "completeness_pct": completeness_pct,
            "quality_score": quality_score["total"],
        }
    )


if __name__ == "__main__":
    main()
