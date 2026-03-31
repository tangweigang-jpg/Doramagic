"""session_store 模块的单元测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from doramagic_shared_utils.session_store import (
    SessionState,
    create_session,
    load_session,
    save_session,
    update_session_build,
    update_session_match,
)


@pytest.fixture(autouse=True)
def _tmp_sessions_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """将 session 目录重定向到临时目录。"""
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    latest = sessions_dir / "latest.json"
    monkeypatch.setattr("doramagic_shared_utils.session_store.SESSIONS_DIR", sessions_dir)
    monkeypatch.setattr("doramagic_shared_utils.session_store.LATEST_SESSION", latest)


class TestSessionState:
    """SessionState Pydantic 模型测试。"""

    def test_default_values(self) -> None:
        state = SessionState()
        assert state.phase == "init"
        assert state.requirement == ""
        assert state.matched_bricks == []
        assert state.constraint_count == 0
        assert state.session_id.startswith("session-")

    def test_custom_values(self) -> None:
        state = SessionState(
            requirement="监控特斯拉股价",
            phase="clarified",
        )
        assert state.requirement == "监控特斯拉股价"
        assert state.phase == "clarified"

    def test_serialization_roundtrip(self) -> None:
        state = SessionState(
            requirement="提醒喝水",
            phase="matched",
            constraint_count=5,
            matched_bricks=["b1", "b2"],
        )
        json_str = state.model_dump_json()
        restored = SessionState(**json.loads(json_str))
        assert restored.requirement == state.requirement
        assert restored.matched_bricks == state.matched_bricks


class TestSaveAndLoad:
    """save_session / load_session 测试。"""

    def test_save_and_load(self) -> None:
        state = SessionState(requirement="test", phase="clarified")
        save_session(state)
        loaded = load_session()
        assert loaded is not None
        assert loaded.requirement == "test"
        assert loaded.phase == "clarified"
        assert loaded.updated_at != ""

    def test_load_missing_file(self) -> None:
        result = load_session()
        assert result is None

    def test_load_corrupted_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        latest = tmp_path / "sessions" / "latest.json"
        latest.parent.mkdir(parents=True, exist_ok=True)
        latest.write_text("not valid json")
        monkeypatch.setattr("doramagic_shared_utils.session_store.LATEST_SESSION", latest)
        result = load_session()
        assert result is None


class TestCreateSession:
    """create_session 测试。"""

    def test_create(self) -> None:
        state = create_session("做一个提醒工具")
        assert state.requirement == "做一个提醒工具"
        assert state.phase == "clarified"
        # 验证文件确实存在
        loaded = load_session()
        assert loaded is not None
        assert loaded.requirement == "做一个提醒工具"


class TestUpdateSessionMatch:
    """update_session_match 测试。"""

    def test_update_match(self) -> None:
        create_session("监控股价")
        result = update_session_match(
            constraint_prompt="Must use yfinance API",
            constraint_count=3,
            matched_bricks=["finance-001", "api-002"],
            capabilities=["real-time price"],
            limitations=["15min delay on free tier"],
            risk_report={"api_limit": "5 requests/min"},
            evidence_sources=["https://docs.yfinance.com"],
        )
        assert result is not None
        assert result.phase == "matched"
        assert result.constraint_count == 3
        assert len(result.matched_bricks) == 2

        # 验证持久化
        loaded = load_session()
        assert loaded is not None
        assert loaded.constraint_prompt == "Must use yfinance API"

    def test_update_without_session(self) -> None:
        result = update_session_match(
            constraint_prompt="",
            constraint_count=0,
            matched_bricks=[],
            capabilities=[],
            limitations=[],
            risk_report={},
            evidence_sources=[],
        )
        assert result is None


class TestUpdateSessionBuild:
    """update_session_build 测试。"""

    def test_update_build(self) -> None:
        create_session("做工具")
        update_session_match(
            constraint_prompt="rule",
            constraint_count=1,
            matched_bricks=["b1"],
            capabilities=[],
            limitations=[],
            risk_report={},
            evidence_sources=[],
        )
        result = update_session_build(
            tool_name="reminder",
            generated_code_path="/tmp/reminder.py",
            syntax_verified=True,
        )
        assert result is not None
        assert result.phase == "built"
        assert result.tool_name == "reminder"
        assert result.syntax_verified is True

    def test_update_build_without_session(self) -> None:
        result = update_session_build(
            tool_name="test",
            generated_code_path="/tmp/test.py",
            syntax_verified=False,
        )
        assert result is None


class TestSessionPhaseFlow:
    """完整 session 生命周期测试。"""

    def test_full_lifecycle(self) -> None:
        # 1. /dora 创建 session
        state = create_session("每40分钟提醒喝水")
        assert state.phase == "clarified"

        # 2. /dora-match 匹配积木
        state = update_session_match(
            constraint_prompt="Use schedule library for periodic tasks",
            constraint_count=5,
            matched_bricks=["scheduling-001", "notification-002"],
            capabilities=["periodic reminders"],
            limitations=["no calendar integration"],
            risk_report={"reliability": "process must stay running"},
            evidence_sources=["https://schedule.readthedocs.io"],
        )
        assert state is not None
        assert state.phase == "matched"
        assert state.requirement == "每40分钟提醒喝水"

        # 3. /dora-build 生成代码
        state = update_session_build(
            tool_name="water_reminder",
            generated_code_path="/tmp/water_reminder.py",
            syntax_verified=True,
        )
        assert state is not None
        assert state.phase == "built"
        # 确认之前的数据没丢
        assert state.constraint_count == 5
        assert state.requirement == "每40分钟提醒喝水"
