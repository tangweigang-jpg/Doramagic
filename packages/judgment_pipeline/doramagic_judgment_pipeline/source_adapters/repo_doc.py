"""仓库文档适配器 — 从 GitHub 仓库文档中采集知识层和资源层原材料。"""

from __future__ import annotations

import base64
import logging
import re

import httpx

from .base import BaseAdapter, RawExperienceRecord

logger = logging.getLogger(__name__)


# 文档文件的采集优先级（按信息密度排序）
DOC_TARGETS = [
    {"path": "README", "source_type": "github_readme"},
    {"path": "CHANGELOG.md", "source_type": "github_changelog"},
    {"path": "docs/", "source_type": "github_doc"},
    {"path": "pyproject.toml", "source_type": "github_deps"},
    {"path": "setup.py", "source_type": "github_deps"},
    {"path": "requirements.txt", "source_type": "github_deps"},
]


class RepoDocAdapter(BaseAdapter):
    """从 GitHub 仓库文档中采集结构化内容。"""

    def __init__(self, token: str):
        self.token = token
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }
        self.base_url = "https://api.github.com"

    async def fetch(self, target: dict) -> list[RawExperienceRecord]:
        """
        target 格式:
        {
            "owner": "freqtrade",
            "repo": "freqtrade",
            "doc_paths": ["README", "CHANGELOG.md", "docs/", "pyproject.toml"],
            "max_doc_files": 20,
        }
        """
        owner = target["owner"]
        repo = target["repo"]
        doc_paths = target.get("doc_paths", [d["path"] for d in DOC_TARGETS])
        max_doc_files = target.get("max_doc_files", 20)
        records: list[RawExperienceRecord] = []

        async with httpx.AsyncClient(headers=self.headers, timeout=30) as client:
            for doc_target in DOC_TARGETS:
                if doc_target["path"] not in doc_paths:
                    continue

                path = doc_target["path"]
                source_type = doc_target["source_type"]

                try:
                    if path == "README":
                        content = await self._fetch_readme(client, owner, repo)
                        if content:
                            sections = self._split_markdown(content)
                            for section in sections:
                                records.append(
                                    self._make_record(
                                        source_type=source_type,
                                        source_id=f"readme:{section['heading_slug']}",
                                        source_url=f"https://github.com/{owner}/{repo}#readme",
                                        project=f"{owner}/{repo}",
                                        title=section["heading"],
                                        body=section["content"],
                                    )
                                )

                    elif path.endswith("/"):
                        dir_path = path.rstrip("/")
                        files = await self._list_directory(client, owner, repo, dir_path)
                        md_files = [
                            f for f in files if f["name"].endswith(".md") and f["type"] == "file"
                        ][:max_doc_files]

                        for file_info in md_files:
                            content = await self._fetch_file(client, owner, repo, file_info["path"])
                            if content:
                                sections = self._split_markdown(content)
                                for section in sections:
                                    records.append(
                                        self._make_record(
                                            source_type=source_type,
                                            source_id=f"doc:{file_info['path']}:{section['heading_slug']}",
                                            source_url=f"https://github.com/{owner}/{repo}/blob/main/{file_info['path']}",
                                            project=f"{owner}/{repo}",
                                            title=f"{file_info['name']} > {section['heading']}",
                                            body=section["content"],
                                        )
                                    )

                    elif path in ("pyproject.toml", "setup.py", "requirements.txt"):
                        content = await self._fetch_file(client, owner, repo, path)
                        if content:
                            records.append(
                                self._make_record(
                                    source_type=source_type,
                                    source_id=f"deps:{path}",
                                    source_url=f"https://github.com/{owner}/{repo}/blob/main/{path}",
                                    project=f"{owner}/{repo}",
                                    title=f"Dependencies: {path}",
                                    body=content,
                                )
                            )

                    else:
                        content = await self._fetch_file(client, owner, repo, path)
                        if content:
                            sections = self._split_markdown(content)
                            for section in sections:
                                records.append(
                                    self._make_record(
                                        source_type=source_type,
                                        source_id=f"{path}:{section['heading_slug']}",
                                        source_url=f"https://github.com/{owner}/{repo}/blob/main/{path}",
                                        project=f"{owner}/{repo}",
                                        title=f"{path} > {section['heading']}",
                                        body=section["content"],
                                    )
                                )

                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 404:
                        logger.info("文件不存在，跳过: %s/%s/%s", owner, repo, path)
                    else:
                        logger.warning(
                            "拉取文件失败: %s/%s/%s status=%d",
                            owner,
                            repo,
                            path,
                            e.response.status_code,
                        )
                except httpx.HTTPError as e:
                    logger.warning("网络错误: %s/%s/%s error=%s", owner, repo, path, e)

        logger.info("RepoDocAdapter 采集完成: %s/%s → %d 条记录", owner, repo, len(records))
        return records

    # ── 内部方法 ──

    async def _fetch_readme(self, client: httpx.AsyncClient, owner: str, repo: str) -> str | None:
        """拉取 README（GitHub 自动识别 README.md / README.rst 等）。"""
        resp = await client.get(
            f"{self.base_url}/repos/{owner}/{repo}/readme",
            headers={"Accept": "application/vnd.github.v3+json"},
        )
        resp.raise_for_status()
        data = resp.json()
        return base64.b64decode(data["content"]).decode("utf-8")

    async def _fetch_file(
        self, client: httpx.AsyncClient, owner: str, repo: str, path: str
    ) -> str | None:
        """拉取单个文件内容。"""
        resp = await client.get(f"{self.base_url}/repos/{owner}/{repo}/contents/{path}")
        resp.raise_for_status()
        data = resp.json()
        if data.get("type") != "file":
            return None
        return base64.b64decode(data["content"]).decode("utf-8")

    async def _list_directory(
        self, client: httpx.AsyncClient, owner: str, repo: str, path: str
    ) -> list[dict]:
        """列出目录内容。"""
        resp = await client.get(f"{self.base_url}/repos/{owner}/{repo}/contents/{path}")
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list):
            return []
        return data

    def _split_markdown(self, content: str) -> list[dict]:
        """按 markdown 标题（## 或 ###）拆分为语义段落。"""
        sections: list[dict] = []
        pattern = re.compile(r"^(#{2,3})\s+(.+)$", re.MULTILINE)
        matches = list(pattern.finditer(content))

        if not matches:
            stripped = content.strip()
            if len(stripped) >= 50:
                sections.append(
                    {
                        "heading": "Overview",
                        "heading_slug": "overview",
                        "content": stripped,
                    }
                )
            return sections

        preamble = content[: matches[0].start()].strip()
        if len(preamble) >= 50:
            sections.append(
                {
                    "heading": "Overview",
                    "heading_slug": "overview",
                    "content": preamble,
                }
            )

        for i, match in enumerate(matches):
            heading = match.group(2).strip()
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            body = content[start:end].strip()

            if len(body) < 50:
                continue

            slug = re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-")[:60]
            sections.append(
                {
                    "heading": heading,
                    "heading_slug": slug or f"section-{i}",
                    "content": f"## {heading}\n\n{body}",
                }
            )

        return sections

    def _make_record(
        self,
        source_type: str,
        source_id: str,
        source_url: str,
        project: str,
        title: str,
        body: str,
    ) -> RawExperienceRecord:
        """构建标准记录。"""
        return RawExperienceRecord(
            source_type=source_type,
            source_id=source_id,
            source_url=source_url,
            source_platform="github",
            project_or_community=project,
            title=title,
            body=body,
            replies=[],
            code_blocks=self._extract_code_blocks(body),
            signals={
                "is_documentation": True,
                "source_type": source_type,
                "body_length": len(body),
                "has_code_blocks": bool(self._extract_code_blocks(body)),
                "has_warnings": bool(
                    re.search(
                        r"(?i)(warning|caution|note|important|limitation|caveat|\u26a0)", body
                    )
                ),
                "has_api_boundaries": bool(
                    re.search(
                        r"(?i)(limit|quota|rate.?limit|deprecat|breaking.?change|not.?support|does.?not)",
                        body,
                    )
                ),
                "has_domain_rules": bool(
                    re.search(
                        r"(?i)(must|shall|require|always|never|invariant|constraint|rule)", body
                    )
                ),
            },
            created_at="",
            resolved_at=None,
            pre_category=None,
        )

    @staticmethod
    def _extract_code_blocks(text: str) -> list[str]:
        """提取 markdown 代码块。"""
        pattern = re.compile(r"```[\w]*\n(.*?)```", re.DOTALL)
        return [m.group(1).strip() for m in pattern.finditer(text)]
