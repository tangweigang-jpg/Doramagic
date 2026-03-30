#!/usr/bin/env python3
"""部署生成的 Python 脚本并执行一次获取第一个结果。

脚本复制到 ~/.doramagic/active/，执行一次捕获结果，
并配置 launchd（macOS）或输出 crontab 命令（Linux）。

用法：
    python3 deploy.py --code /path/to/generated.py --interval 300 --name "btc-monitor"
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

_ACTIVE_DIR = Path.home() / ".doramagic" / "active"
_LAUNCHAGENTS_DIR = Path.home() / "Library" / "LaunchAgents"


def _first_run(script_path: Path) -> tuple[str, str, int]:
    """执行脚本一次，超时 30s，返回 (stdout, stderr, returncode)。"""
    try:
        r = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True, text=True, timeout=30,
        )
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return "", "执行超时（>30s）", 1
    except Exception as e:
        return "", str(e), 1


def _parse_first_result(stdout: str, stderr: str, returncode: int) -> str:
    """从执行结果中提取人类可读的摘要。

    参数：
        stdout: 脚本标准输出。
        stderr: 脚本错误输出。
        returncode: 退出码。

    返回：
        简短结果描述。
    """
    if returncode != 0:
        env_keywords = ["environ", "API_KEY", "TOKEN", "KeyError", "not found", "未设置"]
        if any(kw in stderr for kw in env_keywords):
            env_vars = re.findall(r"[A-Z][A-Z0-9_]{3,}", stderr)
            if env_vars:
                return f"需要配置环境变量：{', '.join(set(env_vars[:3]))}"
            return "需要配置环境变量，请检查脚本注释"
        return f"执行错误：{stderr[:200]}" if stderr else "执行失败（无输出）"
    return stdout[:300] if stdout else "脚本执行成功（无输出）"


def _write_launchd_plist(name: str, script_path: Path, interval: int) -> Path:
    """在 ~/Library/LaunchAgents/ 写入 launchd plist 文件。

    参数：
        name: 任务名称。
        script_path: 已部署的脚本绝对路径。
        interval: 执行间隔（秒）。

    返回：
        写入的 plist 文件路径。
    """
    label = f"com.doramagic.{name}"
    log_dir = Path.home() / ".doramagic" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    _LAUNCHAGENTS_DIR.mkdir(parents=True, exist_ok=True)

    plist_path = _LAUNCHAGENTS_DIR / f"{label}.plist"
    plist_path.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>{label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{sys.executable}</string>
        <string>{script_path}</string>
    </array>
    <key>StartInterval</key><integer>{interval}</integer>
    <key>RunAtLoad</key><false/>
    <key>StandardOutPath</key><string>{log_dir}/{name}.log</string>
    <key>StandardErrorPath</key><string>{log_dir}/{name}.err</string>
</dict>
</plist>
""", encoding="utf-8")
    return plist_path


def main() -> None:
    """部署脚本并输出 JSON 结果。"""
    parser = argparse.ArgumentParser(description="部署生成的 Python 脚本")
    parser.add_argument("--code", required=True, help="待部署的脚本路径")
    parser.add_argument("--interval", type=int, default=300, help="执行间隔（秒），默认 300")
    parser.add_argument("--name", default="doramagic-task", help="任务名称")
    args = parser.parse_args()

    src_path = Path(args.code).expanduser().resolve()
    if not src_path.exists():
        print(json.dumps({"deployed": False, "error": f"脚本不存在：{src_path}"},
                         ensure_ascii=False))
        sys.exit(1)

    _ACTIVE_DIR.mkdir(parents=True, exist_ok=True)
    deploy_path = _ACTIVE_DIR / f"{args.name}.py"
    shutil.copy2(src_path, deploy_path)

    stdout, stderr, returncode = _first_run(deploy_path)
    first_result = _parse_first_result(stdout, stderr, returncode)

    interval_minutes = max(1, args.interval // 60)
    schedule_desc = f"每 {interval_minutes} 分钟检查一次"

    extra: dict = {}
    if platform.system() == "Darwin":
        try:
            plist_path = _write_launchd_plist(args.name, deploy_path, args.interval)
            schedule_method = "launchd"
            extra = {
                "plist_path": str(plist_path),
                "load_command": f"launchctl load {plist_path}",
                "unload_command": f"launchctl unload {plist_path}",
            }
        except Exception as e:
            schedule_method = "launchd_failed"
            extra = {"error": str(e)}
    else:
        cron_line = f"*/{interval_minutes} * * * * {sys.executable} {deploy_path}"
        schedule_method = "cron"
        extra = {
            "cron_line": cron_line,
            "add_command": f'(crontab -l 2>/dev/null; echo "{cron_line}") | crontab -',
        }

    print(json.dumps({
        "deployed": True,
        "deploy_path": str(deploy_path),
        "first_result": first_result,
        "schedule": schedule_desc,
        "schedule_method": schedule_method,
        **extra,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(json.dumps({"deployed": False, "error": "Interrupted"}))
        sys.exit(1)
    except Exception as exc:
        import traceback
        print(traceback.format_exc(), file=sys.stderr)
        print(json.dumps({"deployed": False, "error": str(exc)}))
        sys.exit(1)
