"""判断采集 CLI 入口。"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path


def preflight_check() -> None:
    """启动前 fail-fast 检查。任何一项失败立即退出。"""
    errors: list[str] = []

    # Python 版本

    # 环境变量
    if not os.environ.get("GITHUB_TOKEN"):
        errors.append("GITHUB_TOKEN 环境变量未设置")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        errors.append("ANTHROPIC_API_KEY 环境变量未设置")

    # 存储路径可写
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
    """运行采集流水线。"""
    from doramagic_judgment_pipeline.pipeline import run_pipeline
    from doramagic_shared_utils.llm_adapter import LLMAdapter

    token = os.environ["GITHUB_TOKEN"]
    adapter = LLMAdapter()

    target = {
        "owner": "freqtrade",
        "repo": "freqtrade",
        "state": "closed",
        "labels": "bug",
        "min_comments": 3,
        "since": "2024-01-01",
        "max_pages": 5,
    }

    result = await run_pipeline(
        github_token=token,
        target=target,
        domain="finance",
        judgments_path="knowledge/judgments",
        adapter=adapter,
    )

    print("\n=== 采集完成 ===")
    print(f"拉取: {result.fetched}")
    print(f"过滤通过: {result.filtered_in} / 过滤丢弃: {result.filtered_out}")
    print(f"分类有效: {result.classified}")
    print(f"提取判断: {result.extracted}")
    print(f"去重后: {result.after_dedup}")
    print(f"入库: {result.stored}")
    print(f"关系建立: {result.relations_created}")
    if result.errors:
        print(f"错误: {result.errors}")


if __name__ == "__main__":
    preflight_check()
    asyncio.run(main())
