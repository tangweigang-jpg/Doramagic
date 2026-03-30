"""Doramagic orchestration package.

.. deprecated::
    此包已废弃，将被 controller + executors 架构取代。
    唯一仍在使用的公开 API 是 ``run_single_project_pipeline``，
    由 executors 的 worker_supervisor / repo_worker / soul_extractor_batch 调用。
    新代码禁止引入对此包的新依赖。迁移完成后整包删除。
"""

from __future__ import annotations

import warnings as _warnings

from .phase_runner import run_single_project_pipeline

_warnings.warn(
    "doramagic_orchestration 已废弃，请勿新增引用。"
    "run_single_project_pipeline 将迁移到 doramagic_executors。",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["run_single_project_pipeline"]
