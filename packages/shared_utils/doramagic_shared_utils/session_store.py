"""技能间 session 状态管理。

Doramagic v13 拆分为多个单职责技能后，技能之间通过 session 文件
传递状态（需求、约束、匹配结果等）。

存储位置: ~/.doramagic/sessions/latest.json
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

SESSIONS_DIR = Path.home() / ".doramagic" / "sessions"
LATEST_SESSION = SESSIONS_DIR / "latest.json"


class SessionState(BaseModel):
    """技能间共享的 session 状态。"""

    session_id: str = Field(
        default_factory=lambda: f"session-{datetime.now(tz=UTC).strftime('%Y%m%d-%H%M%S')}"
    )
    requirement: str = ""
    phase: str = "init"  # init → clarified → matched → built

    # /dora-match 写入
    matched_bricks: list[str] = Field(default_factory=list)
    constraint_count: int = 0
    constraint_prompt: str = ""
    capabilities: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    risk_report: dict[str, Any] = Field(default_factory=dict)
    evidence_sources: list[str] = Field(default_factory=list)

    # /dora-build 写入
    tool_name: str = ""
    generated_code_path: str = ""
    syntax_verified: bool = False

    # 元数据
    created_at: str = Field(default_factory=lambda: datetime.now(tz=UTC).isoformat())
    updated_at: str = ""


def save_session(state: SessionState) -> Path:
    """保存 session 状态到文件。

    参数:
        state: 要保存的 session 状态

    返回:
        保存的文件路径
    """
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    state.updated_at = datetime.now(tz=UTC).isoformat()
    LATEST_SESSION.write_text(
        state.model_dump_json(indent=2),
        encoding="utf-8",
    )
    logger.info("Session saved: %s (phase=%s)", state.session_id, state.phase)
    return LATEST_SESSION


def load_session() -> SessionState | None:
    """加载最新的 session 状态。

    返回:
        SessionState 对象，文件不存在或无法解析时返回 None
    """
    if not LATEST_SESSION.exists():
        logger.warning("No session file found at %s", LATEST_SESSION)
        return None
    try:
        data = json.loads(LATEST_SESSION.read_text(encoding="utf-8"))
        return SessionState(**data)
    except (json.JSONDecodeError, ValueError) as e:
        logger.error("Failed to parse session file: %s", e)
        return None


def create_session(requirement: str) -> SessionState:
    """创建新 session 并保存。

    参数:
        requirement: 用户确认后的需求描述

    返回:
        新创建的 SessionState
    """
    state = SessionState(requirement=requirement, phase="clarified")
    save_session(state)
    return state


def update_session_match(
    constraint_prompt: str,
    constraint_count: int,
    matched_bricks: list[str],
    capabilities: list[str],
    limitations: list[str],
    risk_report: dict[str, Any],
    evidence_sources: list[str],
) -> SessionState | None:
    """更新 session 的积木匹配结果。

    参数:
        constraint_prompt: 约束提示词
        constraint_count: 约束数量
        matched_bricks: 匹配到的积木 ID 列表
        capabilities: 能力列表
        limitations: 限制列表
        risk_report: 风险报告
        evidence_sources: 知识来源 URL 列表

    返回:
        更新后的 SessionState，加载失败时返回 None
    """
    state = load_session()
    if state is None:
        return None
    state.phase = "matched"
    state.constraint_prompt = constraint_prompt
    state.constraint_count = constraint_count
    state.matched_bricks = matched_bricks
    state.capabilities = capabilities
    state.limitations = limitations
    state.risk_report = risk_report
    state.evidence_sources = evidence_sources
    save_session(state)
    return state


def update_session_build(
    tool_name: str,
    generated_code_path: str,
    syntax_verified: bool,
) -> SessionState | None:
    """更新 session 的代码生成结果。

    参数:
        tool_name: 工具名称
        generated_code_path: 生成代码的文件路径
        syntax_verified: 语法验证是否通过

    返回:
        更新后的 SessionState，加载失败时返回 None
    """
    state = load_session()
    if state is None:
        return None
    state.phase = "built"
    state.tool_name = tool_name
    state.generated_code_path = generated_code_path
    state.syntax_verified = syntax_verified
    save_session(state)
    return state
