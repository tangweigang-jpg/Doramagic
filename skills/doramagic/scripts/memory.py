#!/usr/bin/env python3
"""读写用户画像，复用 MemoryManager。

用法：
    python3 memory.py --load --user-id default
    python3 memory.py --update --user-id default \\
        --input "监控比特币" --bricks "financial-analysis-v1" --success true
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


def main() -> None:
    """解析参数并分发到 load/update 命令。"""
    parser = argparse.ArgumentParser(description="读写 Doramagic 用户画像")
    parser.add_argument("--user-id", default="default", help="用户 ID，默认 default")

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--load", action="store_true", help="读取用户画像")
    mode.add_argument("--update", action="store_true", help="更新用户画像")

    parser.add_argument("--input", default="", help="（update）用户输入文本")
    parser.add_argument("--bricks", default="", help="（update）命中积木 ID，逗号分隔")
    parser.add_argument("--success", default="true", help="（update）是否成功，true/false")
    args = parser.parse_args()

    setup_path()

    try:
        from doramagic_shared_utils.memory_manager import MemoryManager
    except ImportError as e:
        msg = f"无法导入 MemoryManager：{e}"
        print(msg, file=sys.stderr)
        if args.load:
            print(json.dumps({
                "user_id": args.user_id,
                "technical_level": "unknown",
                "domain_interests": [],
                "preferred_language": "auto",
                "interaction_count": 0,
                "prompt_context": "",
            }, ensure_ascii=False, indent=2))
        else:
            print(json.dumps({"updated": False, "error": msg}, ensure_ascii=False))
        sys.exit(1)

    mgr = MemoryManager()

    if args.load:
        profile = mgr.load(args.user_id)
        prompt_context = mgr.to_prompt_context(args.user_id)
        data = profile.model_dump()
        data["prompt_context"] = prompt_context
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        bricks = [b.strip() for b in args.bricks.split(",") if b.strip()] if args.bricks else []
        _success_val = args.success.lower().strip()
        if _success_val in ("true", "1", "yes"):
            success = True
        elif _success_val in ("false", "0", "no"):
            success = False
        else:
            print(json.dumps({
                "updated": False,
                "error": f"--success 只接受 true/false/1/0/yes/no，收到：{args.success!r}",
            }, ensure_ascii=False))
            sys.exit(1)
        updated = mgr.update_from_interaction(
            user_id=args.user_id,
            user_input=args.input,
            intent={},
            matched_bricks=bricks,
            result_success=success,
        )
        print(json.dumps({"updated": True, "interaction_count": updated.interaction_count},
                         ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(json.dumps({"error": "Interrupted"}))
        sys.exit(1)
    except Exception as exc:
        import traceback
        print(traceback.format_exc(), file=sys.stderr)
        print(json.dumps({"error": str(exc)}))
        sys.exit(1)
