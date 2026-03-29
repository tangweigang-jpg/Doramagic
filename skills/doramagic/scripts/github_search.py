#!/usr/bin/env python3
"""GitHub Search + Download — Doramagic 的确定性发现脚本。

用法：
    python3 github_search.py "recipe manager cooking" --top 3 --output /tmp/doramagic/discovery.json
    python3 github_search.py --download "owner/repo" --branch main --output /tmp/doramagic/repos/
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import zipfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

_USER_AGENT = "Doramagic/1.0"
_HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": _USER_AGENT,
}
_RAW_HEADERS = {
    "Accept": "application/vnd.github.v3.raw",
    "User-Agent": _USER_AGENT,
}
_STOPWORDS = {"a", "an", "and", "for", "in", "of", "the", "to", "with"}


def _http_get(url: str, *, headers: dict[str, str], timeout: int) -> bytes:
    req = Request(url, headers=headers)
    with urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _sanitize_search_qualifiers(qualifiers: str) -> str:
    # GitHub repository search supports in:name,description,readme. The caller
    # may request "topics" as part of the qualifier string; topics are handled
    # separately in ranking because there is no repository search "in:topics".
    normalized = (qualifiers or "").strip()
    if not normalized:
        return ""
    if normalized == "in:name,description,topics":
        return "in:name,description"
    return normalized


def _tokenize_query_terms(keywords: list[str]) -> list[str]:
    tokens: list[str] = []
    seen: set[str] = set()
    for raw in keywords:
        for part in str(raw).replace("/", " ").split():
            token = part.strip().lower()
            if len(token) < 2 or token in _STOPWORDS or token in seen:
                continue
            seen.add(token)
            tokens.append(token)
    return tokens


def _search_once(query: str, top_k: int) -> list[dict]:
    url = f"https://api.github.com/search/repositories?q={quote(query)}&per_page={top_k}"
    data = json.loads(_http_get(url, headers=_HEADERS, timeout=15).decode("utf-8"))
    results = []
    for item in data.get("items", [])[:top_k]:
        results.append({
            "name": item["full_name"],
            "url": item["html_url"],
            "stars": item["stargazers_count"],
            "language": item.get("language", ""),
            "description": item.get("description", "") or "",
            "default_branch": item.get("default_branch", "main"),
            "updated_at": item.get("updated_at", ""),
            "topics": item.get("topics", []),
            "search_score": item.get("score"),
        })
    return results


def search_github(
    keywords: list[str],
    top_k: int = 5,
    language: str = "",
    min_stars: int = 30,
    qualifiers: str = "in:name,description,topics",
) -> list[dict]:
    """搜索 GitHub 项目，返回候选列表。"""
    raw_terms = [(raw or "").strip() for raw in keywords if (raw or "").strip()]
    if not raw_terms:
        return []

    field_qualifier = _sanitize_search_qualifiers(qualifiers)
    query_variants: list[tuple[list[str], int]] = []
    exact_terms = [f'"{term}"' if " " in term else term for term in raw_terms]
    query_variants.append((exact_terms, min_stars))

    broad_tokens = _tokenize_query_terms(raw_terms)
    if broad_tokens:
        query_variants.append((broad_tokens, min_stars))
        if min_stars > 5:
            query_variants.append((broad_tokens, max(5, min_stars // 3)))

    results: list[dict] = []
    seen_names: set[str] = set()
    try:
        for terms, stars_floor in query_variants:
            query_parts = [" ".join(terms)]
            if field_qualifier:
                query_parts.append(field_qualifier)
            query_parts.extend(["fork:false", "archived:false"])
            if stars_floor > 0:
                query_parts.append(f"stars:>{stars_floor}")
            if language:
                query_parts.append(f"language:{language}")
            query = " ".join(part for part in query_parts if part)
            for repo in _search_once(query, top_k):
                if repo["name"] in seen_names:
                    continue
                seen_names.add(repo["name"])
                results.append(repo)
            if len(results) >= top_k:
                break
    except HTTPError as e:
        print(f"GitHub API error: {e.code}", file=sys.stderr)
        return []
    except URLError as e:
        print(f"GitHub API error: {e.reason}", file=sys.stderr)
        return []

    return results[:top_k]


def fetch_repo_readme(full_name: str) -> str:
    """通过 GitHub REST API 获取 README 原文，失败返回空字符串。"""
    url = f"https://api.github.com/repos/{full_name}/readme"
    try:
        content = _http_get(url, headers=_RAW_HEADERS, timeout=10).decode("utf-8", errors="ignore")
    except (HTTPError, URLError):
        return ""
    return content[:8000]


def fetch_repo_tree(full_name: str) -> list[dict]:
    """通过 GitHub REST API 获取文件树，只返回文件节点。"""
    url = f"https://api.github.com/repos/{full_name}/git/trees/HEAD?recursive=1"
    try:
        data = json.loads(_http_get(url, headers=_HEADERS, timeout=10).decode("utf-8"))
    except (HTTPError, URLError, json.JSONDecodeError):
        return []

    tree = []
    for item in data.get("tree", []):
        if item.get("type") != "blob":
            continue
        path = item.get("path")
        if not path:
            continue
        tree.append({
            "path": path,
            "size": item.get("size", 0),
            "sha": item.get("sha", ""),
        })
    return tree


def fetch_repo_file(full_name: str, path: str) -> str:
    """获取单个文件内容，失败返回空字符串。"""
    safe_path = quote(path.lstrip("/"), safe="/")
    url = f"https://api.github.com/repos/{full_name}/contents/{safe_path}"
    try:
        content = _http_get(url, headers=_RAW_HEADERS, timeout=8).decode("utf-8", errors="ignore")
    except (HTTPError, URLError):
        return ""
    return content[:5000]


def download_repo(full_name: str, branch: str, output_dir: str) -> str:
    """通过 GitHub codeload 下载 zip 并解压，返回解压后的目录路径。"""
    url = f"https://codeload.github.com/{full_name}/zip/refs/heads/{branch}"
    req = Request(url, headers={"User-Agent": _USER_AGENT})

    try:
        with urlopen(req, timeout=60) as resp:
            content = resp.read()
    except HTTPError as e:
        # branch 名可能不对，尝试 master
        if branch != "master":
            return download_repo(full_name, "master", output_dir)
        print(f"Download failed for {full_name}: {e.code}", file=sys.stderr)
        return ""

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        # Zip Slip 防护：验证所有路径都在目标目录内
        resolved_out = out_path.resolve()
        for member in zf.namelist():
            member_path = (out_path / member).resolve()
            if not member_path.is_relative_to(resolved_out):
                print(f"Unsafe path in zip: {member}", file=sys.stderr)
                return ""
        zf.extractall(out_path)

    # zip 解压后的目录名通常是 repo-branch
    extracted = [d for d in out_path.iterdir() if d.is_dir()]
    if extracted:
        return str(extracted[0])
    return str(out_path)


def main():
    parser = argparse.ArgumentParser(description="Doramagic GitHub Search & Download")
    parser.add_argument("keywords", nargs="*", help="搜索关键词")
    parser.add_argument("--top", type=int, default=3, help="返回前 N 个结果")
    parser.add_argument("--language", default="", help="限定编程语言")
    parser.add_argument("--min-stars", type=int, default=30, help="最低 stars 门槛")
    parser.add_argument("--qualifiers", default="in:name,description,topics", help="额外查询限定")
    parser.add_argument("--download", type=str, help="下载指定 repo (owner/repo)")
    parser.add_argument("--branch", default="main", help="下载的分支")
    parser.add_argument("--output", type=str, help="输出路径")

    args = parser.parse_args()

    if args.download:
        if not args.output:
            parser.error("--output is required with --download")
        repo_dir = download_repo(args.download, args.branch, args.output)
        result = {"status": "ok", "repo_dir": repo_dir}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        results = search_github(
            args.keywords,
            args.top,
            args.language,
            min_stars=args.min_stars,
            qualifiers=args.qualifiers,
        )
        payload = json.dumps(results, ensure_ascii=False, indent=2)
        if args.output:
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.output).write_text(payload, encoding="utf-8")
            print(f"Found {len(results)} projects, saved to {args.output}")
        else:
            print(payload)


if __name__ == "__main__":
    main()
