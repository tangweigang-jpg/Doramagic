"""FlowController 服务层 — 进度通知、事件发布、状态持久化、知识积累。"""

from __future__ import annotations

import contextlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from doramagic_contracts.adapter import PlatformAdapter, ProgressUpdate
from doramagic_contracts.base import NeedProfile
from doramagic_contracts.envelope import ModuleResultEnvelope

from .budget_manager import BudgetManager
from .event_bus import EventBus
from .flow_controller_state import ControllerState
from .state_definitions import Phase


def store_result(state: ControllerState, executor_name: str, result: ModuleResultEnvelope) -> None:
    """将 executor 结果存入 phase_artifacts。"""
    key_map = {
        "NeedProfileBuilder": "need_profile",
        "DiscoveryRunner": "discovery_result",
        "BrickStitcher": "brick_stitch_result",
        "WorkerSupervisor": "extraction_aggregate",
        "SynthesisRunner": "synthesis_bundle",
        "SkillCompiler": "compile_bundle",
        "Validator": "validation_report",
        "DeliveryPackager": "delivery_manifest",
    }
    key = key_map.get(executor_name, executor_name)
    if result.data is None:
        state.phase_artifacts[key] = None
    elif hasattr(result.data, "model_dump"):
        state.phase_artifacts[key] = result.data.model_dump()
    else:
        state.phase_artifacts[key] = result.data
    state.phase_artifacts[f"_{executor_name}_status"] = result.status


def infer_delivery_tier(phase: Phase, current_tier: str) -> str:
    """根据失败的阶段推断降级交付层级。"""
    mapping = {
        Phase.PHASE_B: "candidate_brief",
        Phase.BRICK_STITCH: "draft_skill",
        Phase.PHASE_C: "repo_reports",
        Phase.PHASE_D: "repo_reports",
        Phase.PHASE_E: "synthesis_pack",
        Phase.PHASE_F: "draft_skill",
    }
    return mapping.get(phase, current_tier or "candidate_brief")


def clarification_question(profile: NeedProfile, result: ModuleResultEnvelope) -> str:
    """生成用户澄清问题。"""
    if profile.questions:
        return profile.questions[0]
    for warning in result.warnings or []:
        if warning.message.startswith("CLARIFY:"):
            return warning.message.replace("CLARIFY:", "", 1).strip()
    return "你更想分析具体项目,还是想让我先帮你找这个领域里最值得参考的项目?"


# ---------------------------------------------------------------------------
# 进度与事件
# ---------------------------------------------------------------------------


def phase_progress_pct(phase: Phase) -> int:
    """返回阶段完成百分比。"""
    return {
        Phase.INIT: 0,
        Phase.PHASE_A: 5,
        Phase.PHASE_A_CLARIFY: 10,
        Phase.PHASE_B: 18,
        Phase.BRICK_STITCH: 28,
        Phase.PHASE_C: 42,
        Phase.PHASE_D: 60,
        Phase.PHASE_E: 76,
        Phase.PHASE_F: 88,
        Phase.PHASE_G: 96,
        Phase.DONE: 100,
        Phase.DEGRADED: 100,
        Phase.ERROR: 100,
    }.get(phase, 0)


def phase_start_message(phase: Phase) -> str:
    """返回阶段启动消息（中文）。"""
    messages = {
        Phase.INIT: "准备运行计划和目录结构",
        Phase.PHASE_A: "分析输入并确定路由路径",
        Phase.PHASE_B: "执行发现阶段, 寻找候选项目",
        Phase.BRICK_STITCH: "检查积木覆盖率并执行直缝",
        Phase.PHASE_C: "并行提取候选项目的设计灵魂",
        Phase.PHASE_D: "合成跨项目共识, 分歧和编译摘要",
        Phase.PHASE_E: "分 section 编译 SKILL 草稿",
        Phase.PHASE_F: "执行质量门禁并定位最弱 section",
        Phase.PHASE_G: "整理交付物并生成最终包",
    }
    return messages.get(phase, f"Starting {phase.value}")


def phase_complete_message(phase: Phase, state: ControllerState) -> str:
    """返回阶段完成消息（中文）。"""
    if phase == Phase.PHASE_C:
        return f"提取完成: {state.successful_extractions} 个 repo 成功"
    if phase == Phase.BRICK_STITCH:
        brick_stitch = state.phase_artifacts.get("brick_stitch_result", {})
        if isinstance(brick_stitch, dict):
            return (
                f"直缝完成: {brick_stitch.get('bricks_used', 0)} 个积木, "
                f"{len(brick_stitch.get('categories_matched', []))} 个类别"
            )
    if phase == Phase.PHASE_D:
        synthesis = state.phase_artifacts.get("synthesis_bundle", {})
        if isinstance(synthesis, dict):
            why_count = len(synthesis.get("global_theses", []))
            trap_count = len(synthesis.get("divergences", []))
            return f"合成完成: {why_count} 条 WHY, 共 {trap_count} 条风险/分歧"
    if phase == Phase.PHASE_E:
        compile_bundle = state.phase_artifacts.get("compile_bundle", {})
        if isinstance(compile_bundle, dict):
            return f"编译完成: {len(compile_bundle.get('section_drafts', {}))} 个 section 已生成"
    if phase == Phase.PHASE_F:
        return f"质量评分: {state.quality_score:.1f}/100"
    return f"{phase.value} completed"


def build_plan_preview() -> str:
    """返回执行计划预览。"""
    return (
        "执行计划:\n"
        "1. 输入路由与必要追问\n"
        "2. 项目发现或直达提取\n"
        "3. 并行提取 WHY + UNSAID\n"
        "4. 合成并分段编译\n"
        "5. 质量门禁与打包交付\n"
        "预计耗时: 2-5 分钟"
    )


async def send_progress(
    adapter: PlatformAdapter,
    budget: BudgetManager,
    *,
    phase: str,
    status: str,
    message: str,
    percent: int,
) -> None:
    """发送进度更新到平台适配器。"""
    with contextlib.suppress(Exception):
        await adapter.send_progress(
            ProgressUpdate(
                phase=phase,
                status=status,
                message=message,
                elapsed_ms=budget.elapsed_ms(),
                percent_complete=percent,
            )
        )


def emit_event(
    event_bus: EventBus,
    event_type: str,
    message: str,
    *,
    phase: str,
    worker_id: str | None = None,
    status: str | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    """发送结构化事件。"""
    event_bus.emit(
        event_type,
        message,
        phase=phase,
        worker_id=worker_id,
        status=status,
        meta=meta,
    )


# ---------------------------------------------------------------------------
# 状态持久化
# ---------------------------------------------------------------------------


def save_state(state: ControllerState, run_dir: Path) -> None:
    """持久化控制器状态到 JSON。"""
    state_path = run_dir / "controller_state.json"
    payload = json.dumps(state.to_dict(), ensure_ascii=False, indent=2)
    with open(state_path, "w", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def load_state(run_dir: Path) -> ControllerState | None:
    """从 JSON 恢复控制器状态。"""
    state_file = run_dir / "controller_state.json"
    if not state_file.exists():
        return None
    try:
        return ControllerState.from_dict(json.loads(state_file.read_text(encoding="utf-8")))
    except Exception:
        return None


def setup_directories(run_dir: Path) -> None:
    """初始化运行目录结构。"""
    for name in ("staging", "delivery", "leases", "workers", "checkpoints"):
        (run_dir / name).mkdir(parents=True, exist_ok=True)


def create_error_state(message: str) -> ControllerState:
    """创建错误状态。"""
    state = ControllerState(run_id="error", phase=Phase.ERROR)
    state.degradation_log.append(message)
    return state


# ---------------------------------------------------------------------------
# 知识积累
# ---------------------------------------------------------------------------


def accumulated_file(domain: str) -> Path:
    """返回领域知识积累文件路径。"""
    slug = re.sub(r"[^a-z0-9]+", "-", domain.lower()).strip("-") or "general"
    return Path.home() / ".doramagic" / "accumulated" / f"{slug}.jsonl"


def load_accumulated_knowledge(domain: str) -> list[dict[str, Any]]:
    """加载领域历史知识。"""
    path = accumulated_file(domain)
    if not path.exists():
        return []
    items: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines()[-20:]:
        try:
            items.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return items


def persist_accumulated_knowledge(state: ControllerState) -> None:
    """将本次运行的合成知识持久化到领域知识库。"""
    need_profile = state.phase_artifacts.get("need_profile", {})
    if not isinstance(need_profile, dict):
        return
    domain = need_profile.get("domain") or "general"
    synthesis = state.phase_artifacts.get("synthesis_bundle", {})
    if not isinstance(synthesis, dict):
        return
    statements: list[dict[str, Any]] = []
    for decision in synthesis.get("selected_knowledge", [])[:10]:
        if not isinstance(decision, dict):
            continue
        statement = decision.get("statement", "").strip()
        if not statement:
            continue
        statements.append(
            {
                "statement": statement,
                "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "source_repo": ",".join(decision.get("source_refs", [])[:3]),
                "source_commit": "",
                "confidence": "medium",
            }
        )
    if not statements:
        return
    path = accumulated_file(domain)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                existing.add(json.loads(line).get("statement", ""))
            except json.JSONDecodeError:
                continue
    with open(path, "a", encoding="utf-8") as handle:
        for item in statements:
            if item["statement"] in existing:
                continue
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


# ---------------------------------------------------------------------------
# 运行日志
# ---------------------------------------------------------------------------


def log_event(
    run_log: list[dict[str, Any]], event_type: str, data: dict[str, Any], phase: Phase
) -> None:
    """记录结构化事件到运行日志。"""
    run_log.append(
        {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "event": event_type,
            "phase": phase.value,
            **data,
        }
    )


def write_run_log(run_log: list[dict[str, Any]], run_dir: Path) -> None:
    """刷新运行日志到磁盘。"""
    log_path = run_dir / "run_log.jsonl"
    with open(log_path, "a", encoding="utf-8") as handle:
        for entry in run_log:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    run_log.clear()
