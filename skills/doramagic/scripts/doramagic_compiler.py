#!/usr/bin/env python3
"""Doramagic v13 — 个性化编译器入口。

用户说自然语言需求 → 匹配积木 → 注入约束 → 生成可运行工具。

Usage:
    # 编译模式（生成工具）
    python3 doramagic_compiler.py --input "监控比特币价格，跌10%提醒我"

    # 异步编译模式（后台运行，立即返回）
    python3 doramagic_compiler.py --async --input "监控比特币价格，跌10%提醒我"

    # 查看状态
    python3 doramagic_compiler.py --status
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path


def _bootstrap_venv() -> None:
    """Re-exec under ~/.doramagic/venv if running from system Python."""
    if os.environ.get("_DORAMAGIC_BOOTSTRAPPED"):
        return
    venv_python = Path.home() / ".doramagic" / "venv" / "bin" / "python"
    if venv_python.exists() and venv_python.resolve() != Path(sys.executable).resolve():
        os.environ["_DORAMAGIC_BOOTSTRAPPED"] = "1"
        os.execv(str(venv_python), [str(venv_python), *sys.argv])


_bootstrap_venv()


def setup_path() -> None:
    """设置 PYTHONPATH，兼容开发布局和独立 skill 部署两种场景。

    路径解析优先级：
    1. DORAMAGIC_ROOT 环境变量（显式覆盖）
    2. skill_root（scripts/ 的上级目录）下存在 packages/ → 独立 skill 安装
    3. 向上 3 级（开发布局：project_root/skills/doramagic/scripts/）

    副作用：
    - 将所有 packages/<pkg>/ 子目录插入 sys.path
    - 设置 DORAMAGIC_BRICKS_DIR（优先 bricks_v2，其次 bricks）
    """
    script_dir = Path(__file__).resolve().parent
    skill_root = script_dir.parent
    project_root = script_dir.parents[3]

    env_root = os.environ.get("DORAMAGIC_ROOT")
    if env_root:
        runtime_root = Path(env_root).expanduser().resolve()
    elif (
        (project_root / "packages").exists()
        and (project_root / "skills" / "doramagic").exists()
        and (
            (project_root / "pyproject.toml").exists()
            or (project_root / "Makefile").exists()
        )
    ):
        runtime_root = project_root
    elif (skill_root / "packages").exists():
        runtime_root = skill_root
    else:
        runtime_root = skill_root

    os.environ.setdefault("DORAMAGIC_ROOT", str(runtime_root))

    packages_dir = runtime_root / "packages"
    if packages_dir.exists():
        for pkg_dir in packages_dir.iterdir():
            if (
                pkg_dir.is_dir()
                and not pkg_dir.name.startswith((".", "_"))
                and str(pkg_dir) not in sys.path
            ):
                sys.path.insert(0, str(pkg_dir))

    # 统一知识目录：knowledge/ > bricks_v2/ > bricks/（向后兼容）
    for bricks_candidate in ("knowledge", "bricks_v2", "bricks"):
        bricks_dir = runtime_root / bricks_candidate
        if bricks_dir.exists():
            os.environ["DORAMAGIC_BRICKS_DIR"] = str(bricks_dir)
            break


def _init_llm_adapter():
    """尝试初始化 LLM adapter。

    优先从 OpenClaw 配置读取 API key，其次检查环境变量。
    失败时返回 None（compiler 走降级模式）。
    """
    try:
        from doramagic_shared_utils.llm_adapter import LLMAdapter
    except ImportError:
        return None

    # 1. 尝试从 OpenClaw 配置读取
    openclaw_config = Path.home() / ".openclaw" / "openclaw.json"
    if openclaw_config.exists():
        try:
            import json as _json
            config = _json.loads(openclaw_config.read_text(encoding="utf-8"))
            providers = config.get("models", {}).get("providers", {})

            # 按优先级尝试：gpt-vision > wow3-codex > wow3-aws
            for provider_name in ("gpt-vision", "wow3-codex", "wow3-aws"):
                prov = providers.get(provider_name, {})
                api_key = prov.get("apiKey", "")
                base_url = prov.get("baseUrl", "")

                # 解析环境变量引用
                if api_key.startswith("${") and api_key.endswith("}"):
                    env_var = api_key[2:-1]
                    api_key = os.environ.get(env_var, "")

                if api_key and base_url:
                    adapter = LLMAdapter(provider_override="openai")
                    adapter._base_url = base_url + "/v1"
                    adapter._api_key = api_key
                    adapter._default_model = prov.get("models", [{}])[0].get("id", "gpt-4o")
                    return adapter
        except Exception:
            pass

    # 2. 尝试环境变量
    for env_key, provider in [
        ("ANTHROPIC_API_KEY", "anthropic"),
        ("OPENAI_API_KEY", "openai"),
    ]:
        if os.environ.get(env_key):
            return LLMAdapter(provider_override=provider)

    return None


def _init_brick_store():
    """初始化 BrickStore 并导入积木目录。

    Returns:
        已初始化的 BrickStore 实例。
    """
    from doramagic_shared_utils.brick_store import BrickStore

    bricks_dir_str = os.environ.get("DORAMAGIC_BRICKS_DIR", "knowledge")
    bricks_dir = Path(bricks_dir_str)

    store = BrickStore(fallback_dir=bricks_dir)
    store.init_db()

    # 导入所有子目录（knowledge/bricks, knowledge/scenes, knowledge/api_catalog, knowledge/migrated）
    for sub in ("", "bricks", "scenes", "api_catalog", "migrated"):
        d = bricks_dir / sub if sub else bricks_dir
        if d.exists():
            try:
                store.import_dir(d)
            except Exception:
                pass  # 导入失败不中断，BrickStore 会回退到 YAML 搜索

    return store


def _build_message(result) -> str:
    """构建用户可读的结果消息。

    Args:
        result: CompileResult 对象。

    Returns:
        格式化后的结果消息字符串。
    """
    if result.success:
        lines = ["工具生成成功！"]
        lines.append(
            f"使用了 {len(result.matched_bricks)} 个知识积木，"
            f"{result.constraint_count} 条约束"
        )
        if result.verification.passed:
            lines.append("代码验证通过")
        if result.warnings:
            lines.append("注意：")
            for w in result.warnings:
                lines.append(f"  {w}")
        return "\n".join(lines)
    else:
        err = result.warnings[0] if result.warnings else "未知错误"
        return f"生成失败：{err}"


def _slugify(text: str) -> str:
    """将用户输入文本转换为合法文件名。

    Args:
        text: 原始文本。

    Returns:
        slug 化后的字符串，最多 50 字符。
    """
    text = re.sub(r"[^\w\u4e00-\u9fff-]", "_", text)
    return text.strip("_")[:50]


def main() -> None:
    """入口函数：解析参数，初始化组件，运行编译管道，输出 JSON 结果。"""
    parser = argparse.ArgumentParser(description="Doramagic v13 Personalization Compiler")
    parser.add_argument("--input", "-i", type=str, default=None, help="用户需求文本")
    parser.add_argument(
        "--async", dest="async_mode", action="store_true", help="后台运行，立即返回"
    )
    parser.add_argument("--status", action="store_true", help="查看最近一次编译状态")
    parser.add_argument("--user-id", type=str, default="default", help="用户标识")
    parser.add_argument(
        "--output-dir", type=str, default=None, help="生成代码保存目录"
    )
    parser.add_argument("--no-verify", action="store_true", help="跳过沙箱验证")
    args = parser.parse_args()

    setup_path()

    # --status 模式：展示最近生成记录
    if args.status:
        output_dir = Path(args.output_dir or "~/.doramagic/generated").expanduser()
        files = sorted(output_dir.glob("*.py"), key=lambda f: f.stat().st_mtime, reverse=True)
        if not files:
            print(json.dumps({"message": "暂无已生成的工具文件。", "files": []}, ensure_ascii=False))
        else:
            recent = [str(f) for f in files[:5]]
            print(json.dumps(
                {"message": f"最近生成的工具（共 {len(files)} 个）：\n" + "\n".join(recent), "files": recent},
                ensure_ascii=False,
            ))
        return

    if not args.input:
        parser.error("--input 参数必填（或使用 --status 查看状态）")

    # --async 模式：fork 到后台，立即返回
    if args.async_mode:
        pid = os.fork()
        if pid > 0:
            print(json.dumps(
                {
                    "message": (
                        "正在后台生成工具，预计需要 30-60 秒。\n\n"
                        "完成后可用 `python3 doramagic_compiler.py --status` 查看结果。"
                    ),
                    "async": True,
                },
                ensure_ascii=False,
            ))
            return
        # 子进程：关闭标准输出，继续运行
        sys.stdout.flush()
        os.setsid()

    from doramagic_controller.compiler import PersonalizationCompiler
    from doramagic_shared_utils.memory_manager import MemoryManager

    store = _init_brick_store()
    memory = MemoryManager()

    # Doramagic 依赖宿主 LLM（OpenClaw agent），不自己调 API。
    # compiler 的职责是：匹配积木 → 构建约束 prompt → 输出给宿主 LLM 消费。
    compiler = PersonalizationCompiler(
        brick_store=store,
        llm_adapter=None,
        memory_manager=memory,
    )

    result = asyncio.run(compiler.compile(args.input, user_id=args.user_id))

    # compiler 不生成代码（那是宿主 LLM 的事），只输出约束 prompt 供宿主消费
    output: dict = {
        "success": True,
        "message": _build_message(result),
        "matched_bricks": result.matched_bricks,
        "constraint_count": result.constraint_count,
        "constraint_prompt": result.constraint_prompt,
        "capabilities": result.capabilities,
        "limitations": result.limitations,
        "risk_report": result.risk_report,
        "evidence_sources": result.evidence_sources,
    }

    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
