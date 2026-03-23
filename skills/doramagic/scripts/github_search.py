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
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen


def search_github(keywords: list[str], top_k: int = 5, language: str = "") -> list[dict]:
    """搜索 GitHub 项目，返回候选列表。"""
    query = "+".join(quote(k) for k in keywords)
    if language:
        query += f"+language:{quote(language)}"
    url = f"https://api.github.com/search/repositories?q={query}&sort=stars&per_page={top_k}"

    req = Request(url, headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "Doramagic/1.0"})
    try:
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        print(f"GitHub API error: {e.code}", file=sys.stderr)
        return []

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
        })
    return results


def download_repo(full_name: str, branch: str, output_dir: str) -> str:
    """通过 GitHub codeload 下载 zip 并解压，返回解压后的目录路径。"""
    url = f"https://codeload.github.com/{full_name}/zip/refs/heads/{branch}"
    req = Request(url, headers={"User-Agent": "Doramagic/1.0"})

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
    parser.add_argument("--download", type=str, help="下载指定 repo (owner/repo)")
    parser.add_argument("--branch", default="main", help="下载的分支")
    parser.add_argument("--output", type=str, required=True, help="输出路径")

    args = parser.parse_args()

    if args.download:
        repo_dir = download_repo(args.download, args.branch, args.output)
        result = {"status": "ok", "repo_dir": repo_dir}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        results = search_github(args.keywords, args.top, args.language)
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Found {len(results)} projects, saved to {args.output}")


if __name__ == "__main__":
    main()
