"""提取管线相关模型 — Stage 0/1/1.5/3/3.5。"""

from __future__ import annotations

from typing import Optional, Literal

from pydantic import BaseModel, Field

from doramagic_contracts.base import (
    Confidence,
    EvidenceRef,
    EvidenceTag,
    KnowledgeType,
    PolicyAction,
    Priority,
    RepoRef,
    Verdict,
)

# --- Stage 0 ---


class RepoFacts(BaseModel):
    """Stage 0 确定性提取输出。"""

    schema_version: str = "dm.repo-facts.v1"
    repo: RepoRef
    languages: list[str]
    frameworks: list[str]
    entrypoints: list[str]
    commands: list[str]
    storage_paths: list[str]
    dependencies: list[str]
    repo_summary: str
    project_narrative: str = ""  # v1.1: 50-100 词确定性叙事摘要，所有子代理共享上下文


# --- Stage 1 ---


class Stage1ScanConfig(BaseModel):
    max_llm_calls: int = Field(default=8, ge=1, le=16)
    max_prompt_tokens: int = Field(default=24000, ge=1000)
    generate_hypotheses: bool = True
    include_domain_bricks: bool = False


class Stage1ScanInput(BaseModel):
    schema_version: str = "dm.stage1-scan-input.v1"
    repo_facts: RepoFacts
    domain_bricks: list[str] | None = None
    config: Stage1ScanConfig


class Stage1Finding(BaseModel):
    finding_id: str
    question_key: Literal["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7"]
    knowledge_type: KnowledgeType
    title: str
    statement: str
    confidence: Confidence
    evidence_refs: list[EvidenceRef]
    # 置信度体系 (v1.1)
    evidence_tags: list[EvidenceTag] = []
    verdict: Optional[Verdict] = None
    policy_action: Optional[PolicyAction] = None


class Hypothesis(BaseModel):
    hypothesis_id: str
    statement: str
    reason: str
    priority: Priority
    search_hints: list[str]
    related_finding_ids: list[str] = []


class Stage1Coverage(BaseModel):
    answered_questions: list[str]
    partial_questions: list[str]
    uncovered_questions: list[str]


class WHYRecoverability(BaseModel):
    """WHY 可恢复性评估 — Stage 1 Q6 前置判断。"""

    recoverable: bool
    reason: str
    confidence: Confidence = "medium"


class Stage1ScanOutput(BaseModel):
    schema_version: str = "dm.stage1-scan-output.v1"
    repo: RepoRef
    findings: list[Stage1Finding]
    hypotheses: list[Hypothesis]
    coverage: Stage1Coverage
    recommended_for_stage15: bool
    why_recoverability: Optional[WHYRecoverability] = None  # v1.1


# --- Stage 1.5 ---


class Stage15Budget(BaseModel):
    max_rounds: int = Field(default=5, ge=1, le=10)
    max_tool_calls: int = Field(default=30, ge=5, le=60)
    max_prompt_tokens: int = Field(default=60000, ge=5000)
    stop_after_no_gain_rounds: int = Field(default=2, ge=1, le=5)


class Stage15Toolset(BaseModel):
    allow_read_artifact: bool = True
    allow_list_tree: bool = True
    allow_search_repo: bool = True
    allow_read_file: bool = True
    allow_append_finding: bool = True


class Stage15AgenticInput(BaseModel):
    schema_version: str = "dm.stage15-input.v1"
    repo: RepoRef
    repo_facts: RepoFacts
    stage1_output: Stage1ScanOutput
    budget: Stage15Budget
    toolset: Stage15Toolset


class ExplorationLogEntry(BaseModel):
    step_id: str
    round_index: int = Field(ge=1)
    tool_name: Literal[
        "read_artifact", "list_tree", "search_repo", "read_file", "append_finding"
    ]
    tool_input: dict
    observation: str
    produced_evidence_refs: list[EvidenceRef] = []


class ClaimRecord(BaseModel):
    claim_id: str
    statement: str
    status: Literal["confirmed", "rejected", "pending", "inference"]
    confidence: Confidence
    hypothesis_id: Optional[str] = None
    supporting_step_ids: list[str]
    evidence_refs: list[EvidenceRef]
    # 置信度体系 (v1.1)
    evidence_tags: list[EvidenceTag] = []
    verdict: Optional[Verdict] = None
    policy_action: Optional[PolicyAction] = None


class Stage15Summary(BaseModel):
    resolved_hypotheses: list[str]
    unresolved_hypotheses: list[str]
    termination_reason: Literal[
        "all_hypotheses_resolved",
        "no_information_gain",
        "budget_exhausted",
        "manual_skip",
    ]


class Stage15AgenticOutput(BaseModel):
    schema_version: str = "dm.stage15-output.v1"
    repo: RepoRef
    hypotheses_path: str
    exploration_log_path: str
    claim_ledger_path: str
    evidence_index_path: str
    context_digest_path: str
    promoted_claims: list[ClaimRecord]
    summary: Stage15Summary
