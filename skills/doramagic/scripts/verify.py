#!/usr/bin/env python3
"""验证 Python 代码的语法和基础可运行性。

只做静态检查，不实际执行脚本，避免副作用（如网络请求、文件写入）。

用法：
    python3 verify.py --code /path/to/generated.py
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from pathlib import Path


def check_syntax(code: str) -> tuple[bool, str]:
    """用 ast.parse 检查 Python 语法。

    参数：
        code: 待检查的 Python 源代码字符串。

    返回：
        (syntax_ok, error_message) 元组。语法正确时 error_message 为空字符串。
    """
    try:
        ast.parse(code)
        return True, ""
    except SyntaxError as e:
        return False, f"SyntaxError at line {e.lineno}: {e.msg}"
    except Exception as e:
        return False, str(e)


def check_syntax_subprocess(path: str) -> tuple[bool, str, str]:
    """用子进程 ast.parse 做二次语法确认，捕获 stdout/stderr。

    不实际执行脚本，仅解析 AST，不触发任何副作用。
    字段名用 syntax_ok 而非 import_ok，明确表示这只是语法检查，不代表 import 可用。

    参数：
        path: Python 文件的绝对路径。

    返回：
        (ok, stdout, stderr) 元组。
    """
    cmd = [
        sys.executable,
        "-c",
        f"import ast, sys; ast.parse(open({path!r}, encoding='utf-8').read()); print('OK')",
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5,
        )
        ok = result.returncode == 0 and "OK" in result.stdout
        return ok, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "", "Timeout: AST parse took too long (>5s)"
    except Exception as e:
        return False, "", str(e)


def main() -> None:
    """主函数：验证指定 Python 文件并输出 JSON 结果。"""
    parser = argparse.ArgumentParser(description="验证 Python 代码语法与可运行性")
    parser.add_argument("--code", required=True, help="待验证的 Python 文件路径")
    args = parser.parse_args()

    code_path = Path(args.code).expanduser().resolve()

    if not code_path.exists():
        result = {
            "passed": False,
            "syntax_ok": False,
            "stdout": "",
            "stderr": f"文件不存在：{code_path}",
            "exit_code": 1,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(1)

    try:
        code = code_path.read_text(encoding="utf-8")
    except Exception as e:
        result = {
            "passed": False,
            "syntax_ok": False,
            "stdout": "",
            "stderr": f"读取文件失败：{e}",
            "exit_code": 1,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(1)

    # 第一步：本进程内 ast.parse 快速检查
    syntax_ok, syntax_err = check_syntax(code)

    # 第二步：子进程二次语法确认（捕获 subprocess 层面的错误）
    # 注意：这里只验证 AST 语法，不执行 import，syntax_ok_subprocess 为 False 时
    # 说明文件本身无法被 Python 解析，而非 import 依赖缺失。
    if syntax_ok:
        syntax_ok_subprocess, stdout, stderr = check_syntax_subprocess(str(code_path))
        exit_code = 0 if syntax_ok_subprocess else 1
        if syntax_err:
            stderr = syntax_err + ("\n" + stderr if stderr else "")
    else:
        syntax_ok_subprocess = False
        stdout = ""
        stderr = syntax_err
        exit_code = 1

    passed = syntax_ok and syntax_ok_subprocess

    output = {
        "passed": passed,
        "syntax_ok": syntax_ok and syntax_ok_subprocess,
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": exit_code,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(json.dumps({"error": "Interrupted", "passed": False}))
        sys.exit(1)
    except Exception as exc:
        import traceback
        print(traceback.format_exc(), file=sys.stderr)
        print(json.dumps({"error": str(exc), "passed": False, "exit_code": 1}))
        sys.exit(1)
