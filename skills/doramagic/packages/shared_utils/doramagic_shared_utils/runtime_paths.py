"""统一运行时路径解析 — 同时支持自包含 Skill 安装和开发布局。

自包含布局（cp -r 安装后）：
    <root>/
        packages/
        bricks/
        scripts/
        platform_rules.json
        models.json

开发布局（仓库根目录）：
    <root>/
        packages/
        bricks/
        skills/doramagic/
            scripts/
            platform_rules.json   (可选)

所有路径解析优先级统一为：
    1. 显式参数
    2. 环境变量
    3. runtime_root 下的默认位置
    4. 不使用 CWD 作为默认路径语义
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------


def _is_candidate_root(path: Path) -> bool:
    """判断 path 是否满足运行根目录的最低条件。

    必要条件：path 下存在 packages/ 目录。
    充分条件（二选一）：
      - 自包含布局：还存在 bricks/ 或 scripts/
      - 开发布局：还存在 skills/ 目录（内含 doramagic/scripts/）
    """
    if not (path / "packages").is_dir():
        return False
    has_bricks = (path / "bricks").is_dir()
    has_scripts = (path / "scripts").is_dir()
    has_skills = (path / "skills").is_dir()
    return has_bricks or has_scripts or has_skills


def _walk_up_for_root(start: Path) -> Path | None:
    """从 start 逐级向上查找满足 _is_candidate_root() 的目录。"""
    current = start if start.is_dir() else start.parent
    # 最多向上查找 10 层，避免无限遍历到文件系统根
    for _ in range(10):
        if _is_candidate_root(current):
            return current
        parent = current.parent
        if parent == current:
            # 已到达文件系统根目录
            break
        current = parent
    return None


# ---------------------------------------------------------------------------
# 公共 API
# ---------------------------------------------------------------------------


def find_runtime_root(anchor_file: str | Path | None = None) -> Path:
    """找到运行根目录。

    优先级：
    1. 环境变量 DORAMAGIC_ROOT
    2. 从 anchor_file 位置向上自动探测：
       - 自包含布局：anchor 在 {root}/scripts/ 或 {root}/packages/*/
       - 开发布局：anchor 在 {root}/skills/doramagic/scripts/ 或 {root}/packages/*/
       探测启发式：向上遍历，第一个同时包含 packages/ 和（bricks/ 或 scripts/ 或 skills/）
         的目录即为 root。
    3. 如果 anchor_file 未提供，以此模块自身路径作为 anchor。

    Raises:
        RuntimeError: 无法确定运行根目录时抛出。
    """
    # 1. 环境变量优先
    env_root = os.environ.get("DORAMAGIC_ROOT")
    if env_root:
        root = Path(env_root).resolve()
        if root.is_dir():
            logger.debug("runtime_root from DORAMAGIC_ROOT: %s", root)
            return root
        logger.warning(
            "DORAMAGIC_ROOT=%s is not a valid directory, falling back to auto-detect",
            env_root,
        )

    # 2. 从 anchor 向上探测
    if anchor_file is not None:
        anchor = Path(anchor_file).resolve()
    else:
        anchor = Path(__file__).resolve()

    root = _walk_up_for_root(anchor)
    if root is not None:
        logger.debug("runtime_root auto-detected from %s: %s", anchor, root)
        return root

    raise RuntimeError(
        f"Cannot determine Doramagic runtime root. "
        f"Searched upward from: {anchor}. "
        f"Set DORAMAGIC_ROOT environment variable to override."
    )


def resolve_bricks_dir(
    explicit: str | Path | None = None,
    root: Path | None = None,
) -> Path | None:
    """解析积木目录路径。

    优先级：
    1. explicit 参数（显式传入）
    2. 环境变量 DORAMAGIC_BRICKS_DIR
    3. root/bricks/
    4. None（未找到）
    """
    # 1. 显式参数
    if explicit is not None:
        p = Path(explicit).resolve()
        if p.is_dir():
            return p
        logger.warning("Explicit bricks_dir not found: %s", p)
        return p  # 仍然返回，由调用方决定是否报错

    # 2. 环境变量
    env_val = os.environ.get("DORAMAGIC_BRICKS_DIR")
    if env_val:
        p = Path(env_val).resolve()
        if p.is_dir():
            logger.debug("bricks_dir from DORAMAGIC_BRICKS_DIR: %s", p)
            return p
        logger.warning("DORAMAGIC_BRICKS_DIR=%s is not a valid directory", env_val)

    # 3. root/bricks/ or root/knowledge/bricks/
    if root is not None:
        for subpath in ("knowledge/bricks", "bricks"):
            candidate = root / subpath
            if candidate.is_dir():
                logger.debug("bricks_dir resolved under root: %s", candidate)
                return candidate

    # 4. pip-installed package data (doramagic_knowledge/bricks/)
    try:
        from importlib.resources import files

        pkg_bricks = files("doramagic_knowledge") / "bricks"
        if pkg_bricks.is_dir():  # type: ignore[union-attr]
            logger.debug("bricks_dir from pip package data: %s", pkg_bricks)
            return Path(str(pkg_bricks))
    except (ImportError, TypeError, FileNotFoundError, ModuleNotFoundError):
        pass

    return None


def resolve_platform_rules(
    explicit: str | Path | None = None,
    root: Path | None = None,
) -> Path | None:
    """解析 platform_rules.json 路径。

    优先级：
    1. explicit 参数
    2. root/platform_rules.json
    3. None（未找到）
    """
    # 1. 显式参数
    if explicit is not None:
        p = Path(explicit).resolve()
        return p  # 调用方负责判断是否存在

    # 2. root/platform_rules.json
    if root is not None:
        candidate = root / "platform_rules.json"
        if candidate.is_file():
            logger.debug("platform_rules resolved under root: %s", candidate)
            return candidate

        # 开发布局兜底：root/skills/doramagic/platform_rules.json
        dev_candidate = root / "skills" / "doramagic" / "platform_rules.json"
        if dev_candidate.is_file():
            logger.debug("platform_rules resolved under dev skills dir: %s", dev_candidate)
            return dev_candidate

    return None


def resolve_models_config(
    explicit: str | Path | None = None,
    root: Path | None = None,
) -> Path | None:
    """解析 models.json 路径。

    优先级：
    1. explicit 参数
    2. 环境变量 DORAMAGIC_MODELS_CONFIG
    3. root/models.json
    4. root/models.json.example（示例文件兜底）
    5. None（未找到）
    """
    # 1. 显式参数
    if explicit is not None:
        p = Path(explicit).resolve()
        return p

    # 2. 环境变量
    env_val = os.environ.get("DORAMAGIC_MODELS_CONFIG")
    if env_val:
        p = Path(env_val).resolve()
        if p.is_file():
            logger.debug("models_config from DORAMAGIC_MODELS_CONFIG: %s", p)
            return p
        logger.warning("DORAMAGIC_MODELS_CONFIG=%s is not a valid file", env_val)

    # 3. root/models.json
    if root is not None:
        candidate = root / "models.json"
        if candidate.is_file():
            logger.debug("models_config resolved under root: %s", candidate)
            return candidate

        # 4. 示例文件兜底
        example = root / "models.json.example"
        if example.is_file():
            logger.debug("models_config falling back to example: %s", example)
            return example

    return None


def resolve_scripts_dir(root: Path | None = None) -> Path | None:
    """解析 scripts 目录路径。

    自包含布局：root/scripts/
    开发布局：  root/skills/doramagic/scripts/
    """
    if root is None:
        return None

    # 自包含布局：root/scripts/ contains doramagic_main.py
    self_contained = root / "scripts"
    if self_contained.is_dir() and (self_contained / "doramagic_main.py").exists():
        logger.debug("scripts_dir resolved (self-contained): %s", self_contained)
        return self_contained

    # 开发布局：root/skills/doramagic/scripts/
    dev_layout = root / "skills" / "doramagic" / "scripts"
    if dev_layout.is_dir():
        logger.debug("scripts_dir resolved (dev layout): %s", dev_layout)
        return dev_layout

    return None


def bootstrap_sys_path(root: Path | None = None) -> Path:
    """将 root/packages/ 下所有包目录加入 sys.path，返回 root。

    如果 root 未提供，先调用 find_runtime_root() 自动探测。
    已在 sys.path 中的目录不会重复添加。

    Returns:
        root: 实际使用的运行根目录。

    Raises:
        RuntimeError: 无法确定 root 时透传 find_runtime_root() 的异常。
    """
    if root is None:
        root = find_runtime_root()

    packages_dir = root / "packages"
    if not packages_dir.is_dir():
        logger.warning("packages/ not found under runtime root: %s", root)
        return root

    added: list[str] = []
    for pkg_dir in sorted(packages_dir.iterdir()):
        if not pkg_dir.is_dir():
            continue
        pkg_str = str(pkg_dir)
        if pkg_str not in sys.path:
            sys.path.insert(0, pkg_str)
            added.append(pkg_str)

    if added:
        logger.debug(
            "bootstrap_sys_path added %d package dir(s) to sys.path: %s",
            len(added),
            added,
        )
    else:
        logger.debug("bootstrap_sys_path: all package dirs already in sys.path")

    return root
