"""community_signals.py — 通过 GitHub API 获取 issues/PRs，输出结构化社区信号。

参考 skills/soul-extractor/scripts/collect-community-signals.py 实现。
改进：支持 DSD 指标计算（Support-Desk Share、Exception Dominance Ratio）。

输出 signals.json 格式：
    {
        "repo": "owner/repo",
        "signals": [
            {
                "id": "SIG-001",
                "type": "high_comment_issue|bug|wont_fix|breaking_change|security",
                "title": "...",
                "issue_number": 42,
                "comment_count": 15,
                "reactions": 8,
                "labels": ["bug"],
                "url": "https://github.com/...",
                "tier": 1|2|3
            }
        ],
        "dsd_metrics": {
            "support_desk_share": 0.35,
            "exception_dominance_ratio": 0.25,
            "maintainer_boundary_statements": [...],
            "high_frequency_issues": [...]
        },
        "summary": "...",
        "skipped": false,
        "skip_reason": null
    }
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from math import log1p
from pathlib import Path

MAX_ISSUES = 50
TOP_SIGNALS = 15
CONNECT_TIMEOUT = 10
REQUEST_TIMEOUT = 15


def extract_github_slug(repo_url: str) -> str | None:
    match = re.search(r"github\.com[:/]([^/]+/[^/.]+)", repo_url)
    return match.group(1) if match else None


def github_api_get(endpoint: str, token: str | None = None) -> list | dict | None:
    url = f"https://api.github.com{endpoint}"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "DoramagicS1/2.0",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
        print(f"  [warn] GitHub API failed: {endpoint} -> {e}", file=sys.stderr)
        return None


def fetch_github_issues(slug: str, token: str | None = None) -> list[dict]:
    """Fetch issues sorted by comments, filter out PRs."""
    data = github_api_get(
        f"/repos/{slug}/issues?state=all&sort=comments&direction=desc&per_page={MAX_ISSUES}",
        token=token,
    )
    if not data or not isinstance(data, list):
        return []
    return [i for i in data if "pull_request" not in i]


def collect_changelog_signals(repo_path: str) -> list[dict]:
    """Extract breaking changes and boundary statements from CHANGELOG."""
    signals = []
    changelog_file = None
    for name in ["CHANGELOG.md", "CHANGELOG", "CHANGELOG.rst", "CHANGES.md", "HISTORY.md"]:
        p = os.path.join(repo_path, name)
        if os.path.isfile(p):
            changelog_file = p
            break

    if not changelog_file:
        return signals

    try:
        with open(changelog_file, encoding="utf-8", errors="replace") as f:
            content = f.read()
    except OSError:
        return signals

    # Look for breaking changes and boundary statements
    breaking_patterns = [
        r"(?i)(breaking[\s_]change|BREAKING)",
        r"(?i)(won'?t\s+(?:fix|implement)|by\s+design|not\s+a\s+bug|wontfix)",
        r"(?i)(rewrite|overhaul|migration|deprecat)",
        r"(?i)(security|vulnerability|CVE-\d+)",
    ]

    lines = content.splitlines()
    for i, line in enumerate(lines):
        for pattern in breaking_patterns:
            if re.search(pattern, line):
                context = " ".join(lines[max(0, i - 1) : min(len(lines), i + 2)]).strip()
                signal_type = (
                    "breaking_change"
                    if re.search(r"(?i)breaking|rewrite|overhaul|migration", line)
                    else "boundary_statement"
                    if re.search(r"(?i)won'?t|by design|not a bug", line)
                    else "security"
                    if re.search(r"(?i)security|CVE", line)
                    else "deprecation"
                )
                signals.append(
                    {
                        "type": signal_type,
                        "content": context[:200],
                        "source": "CHANGELOG",
                        "tier": 1 if signal_type in ("breaking_change", "security") else 2,
                    }
                )
                break

    return signals[:10]  # Cap at 10 changelog signals


def score_issue(issue: dict) -> float:
    """Score an issue by relevance/importance."""
    comments = issue.get("comments", 0)
    reactions = (
        issue.get("reactions", {}).get("total_count", 0)
        if isinstance(issue.get("reactions"), dict)
        else 0
    )
    labels = [lb.get("name", "").lower() for lb in issue.get("labels", [])]

    score = log1p(comments) * 2 + log1p(reactions)
    if any(l in ("bug", "security", "critical", "high") for l in labels):
        score *= 1.5
    if any(l in ("wontfix", "by design", "intended") for l in labels):
        score *= 1.3  # maintainer boundary = high value
    return score


def classify_issue(issue: dict) -> str:
    """Classify issue type for DSD metrics."""
    title = issue.get("title", "").lower()
    labels = [lb.get("name", "").lower() for lb in issue.get("labels", [])]
    body = (issue.get("body") or "").lower()[:500]

    if any(l in ("wontfix", "by design", "intended", "not a bug") for l in labels):
        return "wont_fix"
    if any(
        k in title or k in body
        for k in ["how to", "how do i", "help", "getting started", "setup", "install"]
    ):
        return "support_desk"
    if any(l in ("bug", "defect", "regression") for l in labels):
        if any(k in title for k in ["edge case", "rare", "specific", "only when", "unusual"]):
            return "exception"
        return "bug"
    if any(l in ("security", "vulnerability", "cve") for l in labels):
        return "security"
    if any(k in title for k in ["feature request", "enhancement", "add support for"]):
        return "feature"
    return "general"


def compute_dsd_metrics(issues: list[dict], signals_from_issues: list[dict]) -> dict:
    """Compute DSD (Deceptive Source Detection) metrics from issues."""
    if not issues:
        return {
            "support_desk_share": 0.0,
            "exception_dominance_ratio": 0.0,
            "maintainer_boundary_statements": [],
            "high_frequency_issues": [],
            "dsd_warnings": [],
        }

    classifications = [classify_issue(i) for i in issues]
    total = len(classifications)

    support_desk_count = classifications.count("support_desk")
    exception_count = classifications.count("exception")
    wont_fix_count = classifications.count("wont_fix")

    support_desk_share = support_desk_count / total if total > 0 else 0.0
    exception_dominance = exception_count / total if total > 0 else 0.0

    # Extract maintainer boundary statements (wont_fix issues)
    boundary_statements = []
    for i, issue in enumerate(issues):
        if classifications[i] == "wont_fix":
            boundary_statements.append(
                {
                    "issue_number": issue.get("number"),
                    "title": issue.get("title", ""),
                    "url": issue.get("html_url", ""),
                    "comments": issue.get("comments", 0),
                }
            )
    boundary_statements = sorted(boundary_statements, key=lambda x: -x["comments"])[:5]

    # High frequency issue patterns (extract keywords)
    title_words: dict[str, int] = {}
    for issue in issues:
        title = issue.get("title", "").lower()
        words = re.findall(r"\b[a-z]{4,}\b", title)
        for w in words:
            if w not in {
                "with",
                "when",
                "that",
                "this",
                "from",
                "have",
                "does",
                "been",
                "will",
                "using",
                "after",
            }:
                title_words[w] = title_words.get(w, 0) + 1
    high_freq = [(w, c) for w, c in sorted(title_words.items(), key=lambda x: -x[1]) if c >= 2][:10]

    # DSD warnings
    dsd_warnings = []
    if support_desk_share > 0.70:
        dsd_warnings.append(
            f"Support-Desk Share = {support_desk_share:.0%} (> 70% threshold). "
            "Project has high usage difficulty — extracted knowledge may reflect struggles, not design."
        )
    if exception_dominance > 0.60:
        dsd_warnings.append(
            f"Exception Dominance Ratio = {exception_dominance:.0%} (> 60% threshold). "
            "Most discussions are about edge cases — core use case knowledge may be sparse."
        )

    return {
        "support_desk_share": round(support_desk_share, 3),
        "exception_dominance_ratio": round(exception_dominance, 3),
        "wont_fix_count": wont_fix_count,
        "maintainer_boundary_statements": boundary_statements,
        "high_frequency_issues": [{"keyword": w, "count": c} for w, c in high_freq],
        "dsd_warnings": dsd_warnings,
    }


def process_issues_to_signals(issues: list[dict]) -> list[dict]:
    """Convert raw issues to structured signals, scored and ranked."""
    scored = [(score_issue(i), i) for i in issues]
    scored.sort(key=lambda x: -x[0])

    signals = []
    for rank, (score, issue) in enumerate(scored[:TOP_SIGNALS]):
        labels = [lb.get("name", "") for lb in issue.get("labels", [])]
        issue_type = classify_issue(issue)

        # Determine tier
        tier = 3
        if issue_type in ("bug", "wont_fix", "security") and score > 3.0:
            tier = 2
        if issue_type == "security" or score > 6.0:
            tier = 1

        signals.append(
            {
                "id": f"SIG-{rank + 1:03d}",
                "type": issue_type,
                "title": issue.get("title", ""),
                "issue_number": issue.get("number"),
                "comment_count": issue.get("comments", 0),
                "reactions": issue.get("reactions", {}).get("total_count", 0)
                if isinstance(issue.get("reactions"), dict)
                else 0,
                "state": issue.get("state", ""),
                "labels": labels,
                "url": issue.get("html_url", ""),
                "tier": tier,
                "relevance_score": round(score, 2),
            }
        )

    return signals


def collect_community_signals(
    repo_url: str | None,
    repo_path: str | None = None,
    token: str | None = None,
) -> dict:
    """Main function: collect and structure community signals."""
    slug = extract_github_slug(repo_url) if repo_url else None

    result: dict = {
        "repo": slug or repo_url or "unknown",
        "repo_url": repo_url or "",
        "signals": [],
        "changelog_signals": [],
        "dsd_metrics": {},
        "summary": "",
        "skipped": False,
        "skip_reason": None,
    }

    # Collect GitHub issues
    issues: list[dict] = []
    if slug:
        issues = fetch_github_issues(slug, token=token)
        if not issues:
            result["skipped"] = True
            result["skip_reason"] = "GitHub API returned no issues (may be rate limited or private)"

    # Collect changelog signals
    changelog_sigs: list[dict] = []
    if repo_path and os.path.isdir(repo_path):
        changelog_sigs = collect_changelog_signals(repo_path)

    # Process issues to signals
    issue_signals = process_issues_to_signals(issues) if issues else []
    result["signals"] = issue_signals
    result["changelog_signals"] = changelog_sigs

    # Compute DSD metrics
    result["dsd_metrics"] = compute_dsd_metrics(issues, issue_signals)

    # Build summary
    tier1_count = sum(1 for s in issue_signals if s["tier"] == 1)
    tier2_count = sum(1 for s in issue_signals if s["tier"] == 2)
    wont_fix_count = sum(1 for s in issue_signals if s["type"] == "wont_fix")
    warnings = result["dsd_metrics"].get("dsd_warnings", [])

    result["summary"] = (
        f"Collected {len(issue_signals)} signals from {len(issues)} issues. "
        f"Tier 1 (critical): {tier1_count}, Tier 2 (high): {tier2_count}. "
        f"Maintainer boundary statements: {wont_fix_count}. "
        f"Changelog signals: {len(changelog_sigs)}. "
        f"DSD warnings: {len(warnings)}."
    )

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Doramagic S1 community_signals — 采集 GitHub 社区信号 + DSD 暗雷指标"
    )
    parser.add_argument("--repo-url", help="GitHub 仓库 URL（如 https://github.com/owner/repo）")
    parser.add_argument("--repo-path", help="本地仓库目录路径（用于 CHANGELOG 分析）")
    parser.add_argument("--output", required=True, help="输出 JSON 文件路径")
    parser.add_argument(
        "--token", default=None, help="GitHub Personal Access Token（可选，提高 API 限制）"
    )
    args = parser.parse_args()

    if not args.repo_url and not args.repo_path:
        print("ERROR: Must provide at least --repo-url or --repo-path", file=sys.stderr)
        sys.exit(1)

    token = args.token or os.environ.get("GITHUB_TOKEN")
    result = collect_community_signals(args.repo_url, args.repo_path, token=token)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(result["summary"])
    dsd_warnings = result["dsd_metrics"].get("dsd_warnings", [])
    if dsd_warnings:
        print("\nDSD Warnings:")
        for w in dsd_warnings:
            print(f"  ! {w}")
    print(f"Saved to: {args.output}")

    sys.exit(0 if not result["skipped"] else 1)
