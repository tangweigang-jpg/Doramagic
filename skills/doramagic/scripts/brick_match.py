#!/usr/bin/env python3
"""从 BrickStore 搜索相关积木，返回约束文本供宿主 AI 注入 LLM prompt。

用法：
    python3 brick_match.py --query "监控比特币价格跌10%" --limit 5
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _find_project_root(start: Path) -> Path | None:
    """从 start 向上查找项目根目录（含 packages/ + pyproject.toml 的目录）。"""
    for d in [start, *start.parents]:
        if (
            (d / "packages").exists()
            and (d / "skills" / "doramagic").exists()
            and ((d / "pyproject.toml").exists() or (d / "Makefile").exists())
        ):
            return d
    return None


def setup_path() -> None:
    """配置 sys.path，使脚本可独立运行。

    解析顺序：DORAMAGIC_ROOT 环境变量 → 项目开发布局 → skill-only 安装。
    """
    script_dir = Path(__file__).resolve().parent
    skill_root = script_dir.parent

    env_root = os.environ.get("DORAMAGIC_ROOT")
    if env_root:
        runtime_root = Path(env_root).expanduser().resolve()
    else:
        project_root = _find_project_root(script_dir)
        runtime_root = project_root if project_root else skill_root

    os.environ.setdefault("DORAMAGIC_ROOT", str(runtime_root))

    packages_dir = runtime_root / "packages"
    if packages_dir.exists():
        for pkg_dir in packages_dir.iterdir():
            if pkg_dir.is_dir() and not pkg_dir.name.startswith((".", "_")):
                if str(pkg_dir) not in sys.path:
                    sys.path.insert(0, str(pkg_dir))

    for candidate in ("knowledge", "bricks_v2", "bricks"):
        bricks_dir = runtime_root / candidate
        if bricks_dir.exists():
            os.environ["DORAMAGIC_BRICKS_DIR"] = str(bricks_dir)
            break


def main() -> None:
    """搜索积木并输出 JSON 结果。"""
    parser = argparse.ArgumentParser(description="搜索 BrickStore，返回积木约束文本")
    parser.add_argument("--query", "-q", required=True, help="搜索关键词")
    parser.add_argument("--limit", "-l", type=int, default=5, help="最多返回积木数，默认 5")
    args = parser.parse_args()

    setup_path()

    try:
        from doramagic_shared_utils.brick_store import BrickStore
    except ImportError as e:
        print(json.dumps({"error": f"无法导入 BrickStore：{e}", "bricks": [], "brick_count": 0}))
        sys.exit(1)

    # 初始化 BrickStore，fallback_dir 指向 knowledge/
    runtime_root = Path(os.environ.get("DORAMAGIC_ROOT", ""))
    fallback_dir: Path | None = None
    for candidate in ("knowledge", "bricks_v2", "bricks"):
        d = runtime_root / candidate
        if d.exists():
            fallback_dir = d
            break
    if fallback_dir is None:
        alt = Path(__file__).resolve().parents[1] / "knowledge"
        if not alt.exists():
            alt = Path(__file__).resolve().parents[1] / "bricks"
        fallback_dir = alt if alt.exists() else None

    store = BrickStore(fallback_dir=fallback_dir)
    try:
        store.init_db()
    except Exception as e:
        print(json.dumps({"error": f"初始化数据库失败：{e}", "bricks": [], "brick_count": 0}),
              ensure_ascii=False)
        sys.exit(1)

    # 第一轮：全文搜索
    results = store.search(args.query, limit=args.limit)
    existing_ids = {b.id for b in results}

    # 第二轮：中文子词搜索（FTS5 不支持中文分词，手动切片）
    if len(results) < args.limit:
        for length in (4, 3, 2):
            for i in range(len(args.query) - length + 1):
                sub = args.query[i:i + length]
                if not any("\u4e00" <= c <= "\u9fff" for c in sub):
                    continue
                for b in store.search(sub, limit=args.limit):
                    if b.id not in existing_ids:
                        results.append(b)
                        existing_ids.add(b.id)
                    if len(results) >= args.limit:
                        break
                if len(results) >= args.limit:
                    break

    # 第三轮：按能力类型补充
    cap_hints = {
        "监控": "poll", "monitor": "poll", "轮询": "poll",
        "通知": "notify", "提醒": "notify", "notify": "notify",
        "分析": "transform", "analyze": "transform", "发送": "notify",
    }
    cap_hint = next((v for k, v in cap_hints.items() if k in args.query.lower()), None)
    if cap_hint and len(results) < args.limit:
        for b in store.search_by_capability(cap_hint):
            if b.id not in existing_ids and len(results) < args.limit:
                results.append(b)
                existing_ids.add(b.id)

    brick_ids = [b.id for b in results]
    constraints_text = store.to_prompt_constraints(brick_ids)
    total_constraints = sum(len(b.constraints) for b in results)

    print(json.dumps({
        "bricks": brick_ids,
        "brick_count": len(brick_ids),
        "constraint_count": total_constraints,
        "constraints_text": constraints_text,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(json.dumps({"error": "Interrupted"}))
        sys.exit(1)
    except Exception as exc:
        import traceback
        print(traceback.format_exc(), file=sys.stderr)
        print(json.dumps({"error": str(exc), "bricks": [], "brick_count": 0}))
        sys.exit(1)
