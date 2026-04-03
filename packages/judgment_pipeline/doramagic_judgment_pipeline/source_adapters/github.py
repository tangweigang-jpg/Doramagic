"""GitHub Issues/PRs 适配器。"""

from __future__ import annotations

import re

import httpx

from .base import BaseAdapter, RawExperienceRecord

# design boundary 标签集合
_WONTFIX_LABELS = {
    "wontfix",
    "works-as-intended",
    "known-issue",
    "by-design",
    "won't fix",
}


class GitHubAdapter(BaseAdapter):
    """从 GitHub 拉取 Issues/PRs 并转换为 RawExperienceRecord。"""

    def __init__(self, token: str) -> None:
        self.token = token
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }
        self.base_url = "https://api.github.com"

    async def fetch(self, target: dict) -> list[RawExperienceRecord]:
        """根据 target 配置拉取 Issues 并转换。"""
        owner = target["owner"]
        repo = target["repo"]
        records: list[RawExperienceRecord] = []

        issues = await self._fetch_issues(owner, repo, target)

        for issue in issues:
            if "pull_request" in issue:
                continue

            min_comments = target.get("min_comments", 0)
            if issue.get("comments", 0) < min_comments:
                continue

            comments = await self._fetch_comments(owner, repo, issue["number"])
            linked_pr_merged = await self._check_linked_pr(owner, repo, issue["number"])

            code_blocks = self._extract_code_blocks(issue.get("body", "") or "")
            for comment in comments:
                code_blocks.extend(self._extract_code_blocks(comment.get("body", "") or ""))

            labels = [lbl["name"] for lbl in issue.get("labels", [])]
            signals = {
                "has_code_fix": linked_pr_merged,
                "is_design_boundary": any(lbl in labels for lbl in _WONTFIX_LABELS),
                "has_official_resolution": issue.get("state") == "closed",
                "approval_score": issue.get("reactions", {}).get("total_count", 0),
                "reply_count": issue.get("comments", 0),
                "has_repro_steps": self._has_repro_steps(issue.get("body", "") or ""),
                "has_logs_or_evidence": self._has_logs(issue.get("body", "") or ""),
                "author_credibility": self._author_credibility(issue, owner),
                "expert_reply": self._has_maintainer_reply(comments),
                "body_length": len(issue.get("body", "") or ""),
                "contains_code": len(code_blocks) > 0,
                "labels": labels,
            }

            pre_category = self._pre_classify(labels, signals)

            records.append(
                RawExperienceRecord(
                    source_type="github_issue",
                    source_id=str(issue["number"]),
                    source_url=issue["html_url"],
                    source_platform="github",
                    project_or_community=f"{owner}/{repo}",
                    title=issue.get("title", ""),
                    body=issue.get("body", "") or "",
                    replies=[c.get("body", "") or "" for c in comments],
                    code_blocks=code_blocks,
                    signals=signals,
                    created_at=issue.get("created_at", ""),
                    resolved_at=issue.get("closed_at"),
                    pre_category=pre_category,
                )
            )

        return records

    async def _fetch_issues(self, owner: str, repo: str, target: dict) -> list[dict]:
        """分页拉取 Issues。"""
        all_issues: list[dict] = []
        max_pages = target.get("max_pages", 5)

        async with httpx.AsyncClient(headers=self.headers, timeout=30) as client:
            for page in range(1, max_pages + 1):
                params: dict = {
                    "state": target.get("state", "closed"),
                    "per_page": 100,
                    "page": page,
                    "sort": "comments",
                    "direction": "desc",
                }
                if target.get("labels"):
                    params["labels"] = target["labels"]
                if target.get("since"):
                    params["since"] = target["since"]

                resp = await client.get(
                    f"{self.base_url}/repos/{owner}/{repo}/issues",
                    params=params,
                )
                resp.raise_for_status()
                issues = resp.json()

                if not issues:
                    break
                all_issues.extend(issues)

        return all_issues

    async def _fetch_comments(self, owner: str, repo: str, issue_number: int) -> list[dict]:
        """拉取单个 Issue 的所有评论。"""
        async with httpx.AsyncClient(headers=self.headers, timeout=30) as client:
            resp = await client.get(
                f"{self.base_url}/repos/{owner}/{repo}/issues/{issue_number}/comments",
                params={"per_page": 100},
            )
            resp.raise_for_status()
            return resp.json()

    async def _check_linked_pr(self, owner: str, repo: str, issue_number: int) -> bool:
        """检查 Issue 是否有关联的 merged PR。"""
        preview = "application/vnd.github.mockingbird-preview+json"
        async with httpx.AsyncClient(headers=self.headers, timeout=30) as client:
            resp = await client.get(
                f"{self.base_url}/repos/{owner}/{repo}/issues/{issue_number}/timeline",
                headers={**self.headers, "Accept": preview},
                params={"per_page": 100},
            )
            if resp.status_code != 200:
                return False
            events = resp.json()
            for event in events:
                if event.get("event") == "cross-referenced":
                    source = event.get("source", {}).get("issue", {})
                    pr_info = source.get("pull_request")
                    if pr_info and source.get("state") == "closed":
                        pr_url = pr_info.get("url", "")
                        if pr_url:
                            pr_resp = await client.get(pr_url, headers=self.headers)
                            if pr_resp.status_code == 200 and pr_resp.json().get("merged"):
                                return True
            return False

    @staticmethod
    def _extract_code_blocks(text: str) -> list[str]:
        """从 markdown 中提取代码块。"""
        return re.findall(r"```[\w]*\n(.*?)```", text, re.DOTALL)

    @staticmethod
    def _has_repro_steps(body: str) -> bool:
        """检查是否包含复现步骤。"""
        markers = [
            "steps to reproduce",
            "how to reproduce",
            "reproduction",
            "expected behavior",
            "actual behavior",
        ]
        body_lower = body.lower()
        return any(m in body_lower for m in markers)

    @staticmethod
    def _has_logs(body: str) -> bool:
        """检查是否包含日志/堆栈信息。"""
        markers = [
            "traceback",
            "exception",
            "error:",
            "stacktrace",
            "at line",
            'file "',
            "stderr",
            "stdout",
        ]
        body_lower = body.lower()
        return any(m in body_lower for m in markers)

    @staticmethod
    def _author_credibility(issue: dict, owner: str) -> float:
        """粗略评估作者可信度。"""
        author = issue.get("user", {})
        if author.get("login") == owner:
            return 1.0
        association = issue.get("author_association", "")
        if association in ("OWNER", "MEMBER", "COLLABORATOR"):
            return 0.9
        if association == "CONTRIBUTOR":
            return 0.7
        return 0.3

    @staticmethod
    def _has_maintainer_reply(comments: list[dict]) -> bool:
        """检查是否有维护者回复。"""
        for comment in comments:
            association = comment.get("author_association", "")
            if association in ("OWNER", "MEMBER", "COLLABORATOR"):
                return True
        return False

    @staticmethod
    def _pre_classify(labels: list[str], signals: dict) -> str | None:
        """基于标签的粗分类。"""
        label_set = {lbl.lower() for lbl in labels}
        if label_set & _WONTFIX_LABELS:
            return "design_boundary"
        if label_set & {"bug", "regression", "defect"}:
            return "bug"
        if label_set & {"security", "vulnerability"}:
            return "incident"
        return None
