"""判断采集 CLI 入口 — 支持三层完整采集。"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

# 预置 harvest 目标
DEFAULT_TARGETS: dict[str, list[dict]] = {
    "ai_tooling": [
        {"owner": "anthropics", "repo": "anthropic-sdk-python", "domain": "ai_tooling"},
        {"owner": "openai", "repo": "openai-python", "domain": "ai_tooling"},
        {"owner": "langchain-ai", "repo": "langchain", "domain": "ai_tooling"},
        {"owner": "run-llama", "repo": "llama_index", "domain": "ai_tooling"},
        {"owner": "crewAIInc", "repo": "crewAI", "domain": "ai_tooling"},
        {"owner": "anthropics", "repo": "claude-code", "domain": "ai_tooling"},
    ],
    "finance": [
        {"owner": "freqtrade", "repo": "freqtrade", "domain": "finance"},
        {"owner": "stefan-jansen", "repo": "zipline-reloaded", "domain": "finance"},
        {"owner": "vnpy", "repo": "vnpy", "domain": "finance"},
    ],
}


def preflight_check() -> None:
    """启动前 fail-fast 检查。任何一项失败立即退出。"""
    errors: list[str] = []

    if not os.environ.get("GITHUB_TOKEN"):
        errors.append("GITHUB_TOKEN 环境变量未设置")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        errors.append("ANTHROPIC_API_KEY 环境变量未设置")

    store_path = Path("knowledge/judgments/domains")
    try:
        store_path.mkdir(parents=True, exist_ok=True)
        test_file = store_path / ".write_test"
        test_file.write_text("ok")
        test_file.unlink()
    except OSError as e:
        errors.append(f"存储路径不可写: {store_path} ({e})")

    if errors:
        for err in errors:
            print(f"[PREFLIGHT FAIL] {err}", file=sys.stderr)
        sys.exit(1)

    print("[PREFLIGHT] All checks passed.")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Doramagic 判断采集器")
    parser.add_argument(
        "--mode",
        choices=["issue", "doc", "full"],
        default="full",
        help="采集模式: issue=仅 Issue 经验层, doc=仅文档知识/资源层, full=三层完整采集（默认）",
    )
    parser.add_argument(
        "--domain",
        default="finance",
        help="领域标签（默认: finance）",
    )
    parser.add_argument(
        "--owner",
        default="freqtrade",
        help="GitHub 仓库 owner（默认: freqtrade）",
    )
    parser.add_argument(
        "--repo",
        default="freqtrade",
        help="GitHub 仓库名（默认: freqtrade）",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="晶体 token 预算上限（默认: 不限制）",
    )
    parser.add_argument(
        "--preset",
        choices=list(DEFAULT_TARGETS.keys()),
        default=None,
        help="使用预置目标列表（ai_tooling / finance），覆盖 --owner/--repo",
    )
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("ERROR: GITHUB_TOKEN 环境变量未设置")
        sys.exit(1)

    preflight_check()

    from doramagic_shared_utils.llm_adapter import LLMAdapter

    adapter = LLMAdapter()

    if args.preset:
        # 预置目标模式：遍历多个仓库
        targets = DEFAULT_TARGETS[args.preset]
        for t in targets:
            print(f"\n{'=' * 60}")
            print(f"  采集: {t['owner']}/{t['repo']} (domain={t['domain']})")
            print(f"{'=' * 60}")
            await _run_single_target(
                token=token,
                owner=t["owner"],
                repo=t["repo"],
                domain=t["domain"],
                mode=args.mode,
                adapter=adapter,
                max_tokens=args.max_tokens,
            )
        return

    await _run_single_target(
        token=token,
        owner=args.owner,
        repo=args.repo,
        domain=args.domain,
        mode=args.mode,
        adapter=adapter,
        max_tokens=args.max_tokens,
    )


async def _run_single_target(
    token: str,
    owner: str,
    repo: str,
    domain: str,
    mode: str,
    adapter: object,
    max_tokens: int | None,
) -> None:
    """运行单个仓库的采集。"""
    issue_target = {
        "owner": owner,
        "repo": repo,
        "state": "closed",
        "labels": "bug",
        "min_comments": 3,
        "since": "2024-01-01",
        "max_pages": 5,
    }

    doc_target = {
        "owner": owner,
        "repo": repo,
        "doc_paths": ["README", "CHANGELOG.md", "docs/", "pyproject.toml"],
        "max_doc_files": 20,
        "language": "python",
        "max_code_results": 10,
        "domain": domain,
    }

    judgments_path = "knowledge/judgments"

    if mode == "issue":
        from doramagic_judgment_pipeline.pipeline import run_pipeline

        result = await run_pipeline(
            github_token=token,
            target=issue_target,
            domain=domain,
            judgments_path=judgments_path,
            adapter=adapter,
        )
        _print_issue_result(result)

    elif mode == "doc":
        from doramagic_judgment_pipeline.pipeline import run_doc_pipeline

        result = await run_doc_pipeline(
            github_token=token,
            target=doc_target,
            domain=domain,
            judgments_path=judgments_path,
            adapter=adapter,
        )
        _print_doc_result(result)

    elif mode == "full":
        from doramagic_judgment_pipeline.pipeline import run_full_pipeline

        result = await run_full_pipeline(
            github_token=token,
            issue_target=issue_target,
            doc_target=doc_target,
            domain=domain,
            task_description=f"{domain} 领域工具",
            judgments_path=judgments_path,
            adapter=adapter,
            max_tokens=max_tokens,
        )
        _print_full_result(result, domain)


def _print_issue_result(result: object) -> None:
    print("\n=== Issue 采集完成 ===")
    print(f"拉取: {result.fetched}")
    print(f"过滤通过: {result.filtered_in} / 过滤丢弃: {result.filtered_out}")
    print(f"分类有效: {result.classified}")
    print(f"提取判断: {result.extracted}")
    print(f"去重后: {result.after_dedup}")
    print(f"入库: {result.stored}")
    if result.errors:
        print(f"错误: {result.errors}")


def _print_doc_result(result: object) -> None:
    print("\n=== 文档采集完成 ===")
    print(f"拉取: {result.fetched}")
    print(f"过滤通过: {result.filtered_in} / 过滤丢弃: {result.filtered_out}")
    print(f"提取判断: {result.extracted}")
    print(f"去重后: {result.after_dedup}")
    print(f"入库: {result.stored}")
    if result.errors:
        print(f"错误: {result.errors}")


def _print_full_result(result: object, domain: str) -> None:
    print(f"\n{'=' * 60}")
    print("  三层完整采集结果")
    print(f"{'=' * 60}")

    if result.issue_result:
        print("\n[经验层 — Issue]")
        print(f"  拉取: {result.issue_result.fetched}")
        print(f"  入库: {result.issue_result.stored}")

    if result.doc_result:
        print("\n[知识+资源层 — 文档]")
        print(f"  拉取: {result.doc_result.fetched}")
        print(f"  入库: {result.doc_result.stored}")

    print("\n[汇总]")
    print(f"  总入库: {result.total_stored}")
    print(f"  三层覆盖: {result.layer_coverage}")

    if result.crystal_text:
        print("\n[晶体预览（前 500 字符）]")
        print(result.crystal_text[:500])
        print("...")

        crystal_path = f"knowledge/judgments/crystals/{domain}_crystal.md"
        os.makedirs(os.path.dirname(crystal_path), exist_ok=True)
        with open(crystal_path, "w") as f:
            f.write(result.crystal_text)
        print(f"\n晶体已保存: {crystal_path}")


if __name__ == "__main__":
    asyncio.run(main())
