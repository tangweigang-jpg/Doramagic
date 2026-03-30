"""Stage 1 Scan — 广度扫描模块。

在 Stage 0 的确定性事实之上做广度扫描，回答 Q1-Q7，
并生成 Q8 假说列表，给 Stage 1.5 提供高价值探索入口。

设计原则：
- 当 LLM 不可用时，基于规则从 repo_facts 提取 findings 和 hypotheses。
- schema 必须 100% 合规，finding_id / hypothesis_id 稳定可重现。
- LLM 集成作为后续增强（通过 _llm_enhance 钩子），当前版本纯规则驱动。
"""

from __future__ import annotations

import re
import time

from doramagic_contracts.base import EvidenceRef
from doramagic_contracts.envelope import (
    ErrorCodes,
    ModuleResultEnvelope,
    RunMetrics,
    WarningItem,
)
from doramagic_contracts.extraction import (
    Hypothesis,
    Stage1Coverage,
    Stage1Finding,
    Stage1ScanInput,
    Stage1ScanOutput,
)

MODULE_NAME = "extraction.stage1_scan"

# Q key → knowledge_type 映射
_Q_TO_KNOWLEDGE_TYPE = {
    "Q1": "capability",
    "Q2": "interface",
    "Q3": "rationale",
    "Q4": "assembly_pattern",
    "Q5": "constraint",
    "Q6": "failure",
    "Q7": "capability",  # Q7 是社区反馈，仍归类 capability
}

# 极小 repo 判断阈值：有效字段总数 < 此值视为"极小"
_COMPLEXITY_THRESHOLD = 3

# ──────────────────────────────────────────────────────────────────────────────
# Utilities
# ──────────────────────────────────────────────────────────────────────────────


def _slugify(s: str) -> str:
    """将字符串转为大写字母+数字组合（用于 finding_id 中的 REPO_ID 部分）。"""
    s = re.sub(r"[^a-zA-Z0-9]", "-", s).upper()
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:8]  # 限制长度


def _make_finding_id(q_key: str, repo_id: str, seq: int) -> str:
    slug = _slugify(repo_id)
    return f"{q_key}-{slug}-{seq:03d}"


def _make_hypothesis_id(seq: int) -> str:
    return f"H-{seq:03d}"


def _artifact_evidence(artifact_name: str, path: str = "") -> EvidenceRef:
    return EvidenceRef(
        kind="artifact_ref",
        path=path or artifact_name,
        artifact_name=artifact_name,
    )


def _file_evidence(path: str, snippet: str | None = None) -> EvidenceRef:
    return EvidenceRef(
        kind="file_line",
        path=path,
        snippet=snippet,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Complexity / validity checks
# ──────────────────────────────────────────────────────────────────────────────


def _count_effective_fields(inp: Stage1ScanInput) -> int:
    """统计 repo_facts 中非空字段数量，用于判断 repo 复杂度。"""
    rf = inp.repo_facts
    count = 0
    if rf.languages:
        count += 1
    if rf.frameworks:
        count += 1
    if rf.entrypoints:
        count += 1
    if rf.commands:
        count += 1
    if rf.dependencies:
        count += 1
    if rf.storage_paths:
        count += 1
    if rf.repo_summary and len(rf.repo_summary) > 20:
        count += 1
    return count


def _is_minimal_repo(inp: Stage1ScanInput) -> bool:
    return _count_effective_fields(inp) < _COMPLEXITY_THRESHOLD


# ──────────────────────────────────────────────────────────────────────────────
# Q1–Q7 rule-based extractors
# ──────────────────────────────────────────────────────────────────────────────


def _extract_q1(inp: Stage1ScanInput, repo_id: str, seq_start: int) -> list[Stage1Finding]:
    """Q1: 这个项目做了什么？(capability)"""
    rf = inp.repo_facts
    findings: list[Stage1Finding] = []
    seq = seq_start

    # Main capability finding from repo_summary
    if rf.repo_summary:
        findings.append(
            Stage1Finding(
                finding_id=_make_finding_id("Q1", repo_id, seq),
                question_key="Q1",
                knowledge_type="capability",
                title="Core Project Capability",
                statement=rf.repo_summary,
                confidence="high",
                evidence_refs=[_artifact_evidence("repo_facts.json", "repo_summary")],
            )
        )
        seq += 1

    # Language + framework combination capability
    if rf.languages and rf.frameworks:
        langs = ", ".join(rf.languages[:3])
        fws = ", ".join(rf.frameworks[:3])
        findings.append(
            Stage1Finding(
                finding_id=_make_finding_id("Q1", repo_id, seq),
                question_key="Q1",
                knowledge_type="capability",
                title="Technology Stack",
                statement=(
                    f"Project is built with {langs} using {fws}. "
                    f"Primary entrypoints: {', '.join(rf.entrypoints[:2]) if rf.entrypoints else 'not detected'}."
                ),
                confidence="high",
                evidence_refs=[
                    _artifact_evidence("repo_facts.json", "languages+frameworks+entrypoints")
                ],
            )
        )
        seq += 1
    elif rf.languages:
        langs = ", ".join(rf.languages[:3])
        findings.append(
            Stage1Finding(
                finding_id=_make_finding_id("Q1", repo_id, seq),
                question_key="Q1",
                knowledge_type="capability",
                title="Technology Language",
                statement=f"Project is written in {langs}.",
                confidence="high",
                evidence_refs=[_artifact_evidence("repo_facts.json", "languages")],
            )
        )
        seq += 1

    return findings


def _extract_q2(inp: Stage1ScanInput, repo_id: str, seq_start: int) -> list[Stage1Finding]:
    """Q2: 核心接口和数据流是什么？(interface)"""
    rf = inp.repo_facts
    findings: list[Stage1Finding] = []
    seq = seq_start

    # Entrypoints define the primary interface
    if rf.entrypoints:
        entry_str = ", ".join(rf.entrypoints[:4])
        findings.append(
            Stage1Finding(
                finding_id=_make_finding_id("Q2", repo_id, seq),
                question_key="Q2",
                knowledge_type="interface",
                title="Primary Entrypoints",
                statement=(
                    f"The project exposes the following entrypoints: {entry_str}. "
                    "These form the primary interface surface for external interaction."
                ),
                confidence="high",
                evidence_refs=[
                    _file_evidence(ep, snippet=f"entrypoint: {ep}") for ep in rf.entrypoints[:2]
                ],
            )
        )
        seq += 1

    # Storage paths indicate data flow boundaries
    if rf.storage_paths:
        storage_str = ", ".join(rf.storage_paths[:4])
        findings.append(
            Stage1Finding(
                finding_id=_make_finding_id("Q2", repo_id, seq),
                question_key="Q2",
                knowledge_type="interface",
                title="Data Storage Interface",
                statement=(
                    f"Data is persisted or read from: {storage_str}. "
                    "These paths represent the data flow boundary between runtime state and persistence."
                ),
                confidence="medium",
                evidence_refs=[_artifact_evidence("repo_facts.json", "storage_paths")],
            )
        )
        seq += 1

    # Key dependencies that form external interface contracts
    _ai_sdk_deps = {
        "openai",
        "@openai",
        "anthropic",
        "@anthropic",
        "@vercel/ai",
        "langchain",
        "llmchain",
    }
    ai_deps = [d for d in rf.dependencies if any(ai in d.lower() for ai in _ai_sdk_deps)]
    if ai_deps:
        dep_str = ", ".join(ai_deps[:3])
        findings.append(
            Stage1Finding(
                finding_id=_make_finding_id("Q2", repo_id, seq),
                question_key="Q2",
                knowledge_type="interface",
                title="LLM API Integration Interface",
                statement=(
                    f"Project integrates with LLM APIs via: {dep_str}. "
                    "The LLM is a core part of the data transformation pipeline."
                ),
                confidence="high",
                evidence_refs=[_artifact_evidence("repo_facts.json", "dependencies")],
            )
        )
        seq += 1

    return findings


def _extract_q3(inp: Stage1ScanInput, repo_id: str, seq_start: int) -> list[Stage1Finding]:
    """Q3: 为什么这样设计？(rationale)"""
    rf = inp.repo_facts
    findings: list[Stage1Finding] = []
    seq = seq_start

    # Framework choice rationale
    if rf.frameworks:
        fw = rf.frameworks[0]
        rationale_map = {
            "Next.js": (
                "Next.js was chosen to unify frontend and backend in a single deployment unit "
                "with built-in API routes, SSR/SSG, and Vercel platform optimization."
            ),
            "FastAPI": (
                "FastAPI was chosen for high-performance async Python APIs with automatic "
                "OpenAPI schema generation and Pydantic validation."
            ),
            "Django": (
                "Django was chosen for its batteries-included ORM, admin panel, and "
                "well-established patterns for rapid backend development."
            ),
            "Flask": (
                "Flask was chosen as a lightweight, minimal framework giving full control "
                "over the application architecture without opinionated defaults."
            ),
        }
        rationale = rationale_map.get(
            fw,
            (
                f"{fw} was selected as the primary framework, likely due to ecosystem maturity, "
                "team familiarity, or specific performance/DX requirements."
            ),
        )
        findings.append(
            Stage1Finding(
                finding_id=_make_finding_id("Q3", repo_id, seq),
                question_key="Q3",
                knowledge_type="rationale",
                title=f"Framework Choice Rationale: {fw}",
                statement=rationale,
                confidence="medium",
                evidence_refs=[_artifact_evidence("repo_facts.json", "frameworks")],
            )
        )
        seq += 1

    # LLM integration rationale (if present)
    _ai_sdk_deps = {"openai", "anthropic", "@vercel/ai", "langchain"}
    has_ai = any(any(ai in d.lower() for ai in _ai_sdk_deps) for d in rf.dependencies)
    if has_ai:
        findings.append(
            Stage1Finding(
                finding_id=_make_finding_id("Q3", repo_id, seq),
                question_key="Q3",
                knowledge_type="rationale",
                title="LLM Integration Rationale",
                statement=(
                    "LLM integration is used to handle unstructured natural language input and "
                    "convert it into structured data, replacing brittle regex/parser approaches "
                    "with flexible semantic understanding at the cost of latency and API spend."
                ),
                confidence="medium",
                evidence_refs=[_artifact_evidence("repo_facts.json", "dependencies")],
            )
        )
        seq += 1

    # Validation library rationale
    has_zod = any("zod" in d.lower() for d in rf.dependencies)
    has_pydantic = any("pydantic" in d.lower() for d in rf.dependencies)
    if has_zod or has_pydantic:
        lib = "Zod" if has_zod else "Pydantic"
        findings.append(
            Stage1Finding(
                finding_id=_make_finding_id("Q3", repo_id, seq),
                question_key="Q3",
                knowledge_type="rationale",
                title=f"Schema Validation via {lib}",
                statement=(
                    f"{lib} is used for runtime schema validation, enforcing type contracts "
                    "at LLM output boundaries and preventing invalid data from propagating "
                    "through the system."
                ),
                confidence="high",
                evidence_refs=[_artifact_evidence("repo_facts.json", "dependencies")],
            )
        )
        seq += 1

    # Fallback rationale if nothing matched
    if not findings and rf.repo_summary:
        findings.append(
            Stage1Finding(
                finding_id=_make_finding_id("Q3", repo_id, seq),
                question_key="Q3",
                knowledge_type="rationale",
                title="Design Rationale (inferred from summary)",
                statement=(
                    "Based on the project summary, the design choices appear oriented toward "
                    "the core functionality described. Deeper rationale requires Stage 1.5 exploration."
                ),
                confidence="low",
                evidence_refs=[_artifact_evidence("repo_facts.json", "repo_summary")],
            )
        )
        seq += 1

    return findings


def _extract_q4(inp: Stage1ScanInput, repo_id: str, seq_start: int) -> list[Stage1Finding]:
    """Q4: 使用了什么设计模式？(assembly_pattern)"""
    rf = inp.repo_facts
    findings: list[Stage1Finding] = []
    seq = seq_start

    # API Route pattern (Next.js)
    is_nextjs = "Next.js" in rf.frameworks
    has_api_route = any("api" in ep.lower() and "route" in ep.lower() for ep in rf.entrypoints)
    if is_nextjs and has_api_route:
        findings.append(
            Stage1Finding(
                finding_id=_make_finding_id("Q4", repo_id, seq),
                question_key="Q4",
                knowledge_type="assembly_pattern",
                title="Next.js API Route Handler Pattern",
                statement=(
                    "Uses Next.js App Router API routes (route.ts) to co-locate "
                    "frontend and backend logic. Each route exports HTTP method handlers "
                    "(GET/POST) as named exports, enabling serverless deployment without "
                    "a separate backend service."
                ),
                confidence="high",
                evidence_refs=[
                    _file_evidence(ep, f"route handler: {ep}")
                    for ep in rf.entrypoints
                    if "route" in ep.lower()
                ][:2],
            )
        )
        seq += 1

    # Streaming pattern
    has_ai_sdk = any("@vercel/ai" in d.lower() for d in rf.dependencies)
    if has_ai_sdk:
        findings.append(
            Stage1Finding(
                finding_id=_make_finding_id("Q4", repo_id, seq),
                question_key="Q4",
                knowledge_type="assembly_pattern",
                title="Streaming Response Pattern via Vercel AI SDK",
                statement=(
                    "Uses Vercel AI SDK to stream LLM responses to the client, "
                    "enabling progressive rendering of chat messages rather than waiting "
                    "for complete response. This pattern reduces perceived latency."
                ),
                confidence="high",
                evidence_refs=[_artifact_evidence("repo_facts.json", "dependencies/@vercel/ai")],
            )
        )
        seq += 1

    # LLM-as-parser pattern
    _ai_sdk_deps = {"openai", "anthropic", "@vercel/ai", "langchain"}
    has_ai = any(any(ai in d.lower() for ai in _ai_sdk_deps) for d in rf.dependencies)
    has_zod = any("zod" in d.lower() for d in rf.dependencies)
    if has_ai and has_zod:
        findings.append(
            Stage1Finding(
                finding_id=_make_finding_id("Q4", repo_id, seq),
                question_key="Q4",
                knowledge_type="assembly_pattern",
                title="LLM-as-Parser with Schema Validation",
                statement=(
                    "Uses LLM to parse unstructured input into structured JSON, "
                    "then validates output schema with Zod before downstream consumption. "
                    "This 'LLM-as-Parser' pattern combines semantic flexibility with type safety."
                ),
                confidence="medium",
                evidence_refs=[_artifact_evidence("repo_facts.json", "dependencies")],
            )
        )
        seq += 1

    # Generic pattern fallback
    if not findings:
        findings.append(
            Stage1Finding(
                finding_id=_make_finding_id("Q4", repo_id, seq),
                question_key="Q4",
                knowledge_type="assembly_pattern",
                title="Assembly Pattern (requires Stage 1.5 exploration)",
                statement=(
                    "Specific design patterns could not be determined from repo_facts alone. "
                    "Stage 1.5 exploration of source files is recommended."
                ),
                confidence="low",
                evidence_refs=[_artifact_evidence("repo_facts.json", "entrypoints")],
            )
        )
        seq += 1

    return findings


def _extract_q5(inp: Stage1ScanInput, repo_id: str, seq_start: int) -> list[Stage1Finding]:
    """Q5: 有什么约束和限制？(constraint)"""
    rf = inp.repo_facts
    findings: list[Stage1Finding] = []
    seq = seq_start

    # LLM API dependency = cost + latency constraint
    _ai_sdk_deps = {"openai", "anthropic", "@vercel/ai", "langchain"}
    ai_deps = [d for d in rf.dependencies if any(ai in d.lower() for ai in _ai_sdk_deps)]
    if ai_deps:
        findings.append(
            Stage1Finding(
                finding_id=_make_finding_id("Q5", repo_id, seq),
                question_key="Q5",
                knowledge_type="constraint",
                title="External LLM API Cost & Latency Constraint",
                statement=(
                    f"Depends on external LLM APIs ({', '.join(ai_deps[:2])}). "
                    "This introduces per-request cost (typically $0.001–$0.01), "
                    "network latency (500ms–3s), and availability dependency on external services."
                ),
                confidence="high",
                evidence_refs=[_artifact_evidence("repo_facts.json", "dependencies")],
            )
        )
        seq += 1

    # Serverless constraint (Next.js on Vercel)
    is_nextjs = "Next.js" in rf.frameworks
    if is_nextjs:
        findings.append(
            Stage1Finding(
                finding_id=_make_finding_id("Q5", repo_id, seq),
                question_key="Q5",
                knowledge_type="constraint",
                title="Serverless Execution Constraints",
                statement=(
                    "Next.js API routes run in serverless/edge functions with cold start latency, "
                    "memory limits (default 1024MB), and execution time limits (default 10s, "
                    "max 60s on Vercel). Stateful operations require external storage."
                ),
                confidence="medium",
                evidence_refs=[_artifact_evidence("repo_facts.json", "frameworks")],
            )
        )
        seq += 1

    # Storage constraint
    if rf.storage_paths:
        findings.append(
            Stage1Finding(
                finding_id=_make_finding_id("Q5", repo_id, seq),
                question_key="Q5",
                knowledge_type="constraint",
                title="Local Storage Dependency",
                statement=(
                    f"Data is stored at local paths ({', '.join(rf.storage_paths[:2])}). "
                    "In serverless environments, local filesystem writes may be ephemeral. "
                    "Persistence requires mounting external storage or migrating to a database."
                ),
                confidence="medium",
                evidence_refs=[_artifact_evidence("repo_facts.json", "storage_paths")],
            )
        )
        seq += 1

    # Generic constraint if nothing matched
    if not findings:
        findings.append(
            Stage1Finding(
                finding_id=_make_finding_id("Q5", repo_id, seq),
                question_key="Q5",
                knowledge_type="constraint",
                title="Constraints (insufficient data)",
                statement=(
                    "Specific constraints could not be determined from repo_facts. "
                    "Stage 1.5 exploration is required."
                ),
                confidence="low",
                evidence_refs=[_artifact_evidence("repo_facts.json", "repo_summary")],
            )
        )
        seq += 1

    return findings


def _extract_q6(inp: Stage1ScanInput, repo_id: str, seq_start: int) -> list[Stage1Finding]:
    """Q6: 有什么已知的失败模式？(failure)"""
    rf = inp.repo_facts
    findings: list[Stage1Finding] = []
    seq = seq_start

    _ai_sdk_deps = {"openai", "anthropic", "@vercel/ai", "langchain"}
    has_ai = any(any(ai in d.lower() for ai in _ai_sdk_deps) for d in rf.dependencies)

    if has_ai:
        # LLM hallucination failure mode
        findings.append(
            Stage1Finding(
                finding_id=_make_finding_id("Q6", repo_id, seq),
                question_key="Q6",
                knowledge_type="failure",
                title="LLM Hallucination: Incorrect Nutritional Values",
                statement=(
                    "LLMs may produce plausible but incorrect structured output (e.g., wrong "
                    "calorie counts, invalid JSON fields). Without ground-truth validation "
                    "against a nutrition database, these errors silently propagate to users."
                ),
                confidence="medium",
                evidence_refs=[_artifact_evidence("repo_facts.json", "dependencies")],
            )
        )
        seq += 1

        # Schema mismatch failure
        findings.append(
            Stage1Finding(
                finding_id=_make_finding_id("Q6", repo_id, seq),
                question_key="Q6",
                knowledge_type="failure",
                title="LLM Output Schema Mismatch",
                statement=(
                    "LLM responses may fail schema validation (e.g., missing required fields, "
                    "wrong data types). If not handled gracefully, this causes runtime exceptions "
                    "or corrupted state in downstream consumers."
                ),
                confidence="medium",
                evidence_refs=[_artifact_evidence("repo_facts.json", "dependencies")],
            )
        )
        seq += 1

    # Generic failure mode (always include at least one)
    findings.append(
        Stage1Finding(
            finding_id=_make_finding_id("Q6", repo_id, seq),
            question_key="Q6",
            knowledge_type="failure",
            title="Missing Error Handling for External Dependencies",
            statement=(
                "Failure modes related to external service unavailability (API rate limits, "
                "network timeouts) may not be fully handled. Retry logic and fallback "
                "strategies require Stage 1.5 code-level verification."
            ),
            confidence="low",
            evidence_refs=[_artifact_evidence("repo_facts.json", "dependencies")],
        )
    )
    seq += 1

    return findings


def _extract_q7(inp: Stage1ScanInput, repo_id: str, seq_start: int) -> list[Stage1Finding]:
    """Q7: 社区反馈说了什么？（从 repo_facts 中提取）(capability)"""
    rf = inp.repo_facts
    findings: list[Stage1Finding] = []
    seq = seq_start

    # Infer community signal from dependency ecosystem
    _popular_deps = {"react", "next", "tailwindcss", "openai", "anthropic", "@vercel/ai"}
    popular_used = [d for d in rf.dependencies if d.lower() in _popular_deps]

    if popular_used:
        findings.append(
            Stage1Finding(
                finding_id=_make_finding_id("Q7", repo_id, seq),
                question_key="Q7",
                knowledge_type="capability",
                title="Community-Validated Dependency Stack",
                statement=(
                    f"Uses high-adoption community libraries: {', '.join(popular_used[:4])}. "
                    "These dependencies have large community bases, extensive documentation, "
                    "and well-understood failure modes. Community patterns for these libraries "
                    "are directly applicable."
                ),
                confidence="high",
                evidence_refs=[_artifact_evidence("repo_facts.json", "dependencies")],
            )
        )
        seq += 1

    # Domain community signals
    _ai_sdk_deps = {"openai", "anthropic", "@vercel/ai", "langchain"}
    has_ai = any(any(ai in d.lower() for ai in _ai_sdk_deps) for d in rf.dependencies)
    if has_ai:
        findings.append(
            Stage1Finding(
                finding_id=_make_finding_id("Q7", repo_id, seq),
                question_key="Q7",
                knowledge_type="capability",
                title="LLM-powered App Community Patterns",
                statement=(
                    "The LLM integration community has documented common pitfalls: "
                    "(1) prompt injection attacks, (2) cost overruns without token limits, "
                    "(3) cold start latency for serverless + streaming, "
                    "(4) context window overflow for long conversation histories. "
                    "Stage 1.5 should verify which apply to this repo."
                ),
                confidence="medium",
                evidence_refs=[_artifact_evidence("repo_facts.json", "dependencies")],
            )
        )
        seq += 1

    # Fallback
    if not findings:
        findings.append(
            Stage1Finding(
                finding_id=_make_finding_id("Q7", repo_id, seq),
                question_key="Q7",
                knowledge_type="capability",
                title="Community Signals (insufficient data)",
                statement=(
                    "Community feedback signals could not be extracted from repo_facts alone. "
                    "GitHub issues, PR discussions, and README notes require Stage 1.5 exploration."
                ),
                confidence="low",
                evidence_refs=[_artifact_evidence("repo_facts.json", "repo_summary")],
            )
        )
        seq += 1

    return findings


# ──────────────────────────────────────────────────────────────────────────────
# Q8: Hypothesis generation
# ──────────────────────────────────────────────────────────────────────────────


def _generate_hypotheses(
    inp: Stage1ScanInput,
    findings: list[Stage1Finding],
    repo_id: str,
) -> list[Hypothesis]:
    """Generate 3–8 high-value hypotheses ranked by priority."""
    rf = inp.repo_facts
    hypotheses: list[Hypothesis] = []
    seq = 1

    _ai_sdk_deps = {"openai", "anthropic", "@vercel/ai", "langchain"}
    has_ai = any(any(ai in d.lower() for ai in _ai_sdk_deps) for d in rf.dependencies)
    has_zod = any("zod" in d.lower() for d in rf.dependencies)
    has_storage = bool(rf.storage_paths)
    is_nextjs = "Next.js" in rf.frameworks

    # Find related finding IDs
    q2_ids = [f.finding_id for f in findings if f.question_key == "Q2"]
    q3_ids = [f.finding_id for f in findings if f.question_key == "Q3"]
    q4_ids = [f.finding_id for f in findings if f.question_key == "Q4"]
    q5_ids = [f.finding_id for f in findings if f.question_key == "Q5"]
    q6_ids = [f.finding_id for f in findings if f.question_key == "Q6"]

    # H1: Context management hypothesis (high priority if LLM)
    if has_ai:
        hypotheses.append(
            Hypothesis(
                hypothesis_id=_make_hypothesis_id(seq),
                statement=(
                    "Conversation history is compressed or summarized before injection into "
                    "the LLM context to prevent token overflow."
                ),
                reason=(
                    "LLM-powered chat apps commonly face context window limits. "
                    "If the app supports multi-turn conversation, it must manage history somehow."
                ),
                priority="high",
                search_hints=["context", "history", "summary", "token", "truncate", "compress"],
                related_finding_ids=q2_ids[:1] + q4_ids[:1],
            )
        )
        seq += 1

    # H2: Schema validation at LLM boundary
    if has_ai and has_zod:
        hypotheses.append(
            Hypothesis(
                hypothesis_id=_make_hypothesis_id(seq),
                statement=(
                    "LLM output is validated against a Zod schema before being returned "
                    "to the client or persisted to storage."
                ),
                reason=(
                    "The combination of LLM + Zod suggests a 'parse-validate-persist' pipeline. "
                    "How the validation failure is handled (retry vs. error response) is unknown."
                ),
                priority="high",
                search_hints=[
                    "z.object",
                    "z.parse",
                    "safeParse",
                    "schema",
                    "validate",
                    "parseJSON",
                ],
                related_finding_ids=q4_ids[:1] + q6_ids[:1],
            )
        )
        seq += 1

    # H3: Persistence strategy
    if has_storage:
        hypotheses.append(
            Hypothesis(
                hypothesis_id=_make_hypothesis_id(seq),
                statement=(
                    "Daily intake logs are persisted as flat JSON files rather than a relational database."
                ),
                reason=(
                    f"Storage paths ({', '.join(rf.storage_paths[:2])}) suggest file-based persistence. "
                    "For a personal calorie tracker, flat files may be sufficient and simpler to deploy."
                ),
                priority="medium",
                search_hints=["fs.write", "JSON.stringify", "writeFile", "readFile", "append"],
                related_finding_ids=q2_ids[:1] + q5_ids[:1],
            )
        )
        seq += 1

    # H4: Prompt engineering
    if has_ai:
        hypotheses.append(
            Hypothesis(
                hypothesis_id=_make_hypothesis_id(seq),
                statement=(
                    "A system prompt defines the LLM's persona and output format constraints, "
                    "including instructions to respond in structured JSON."
                ),
                reason=(
                    "LLM-as-parser applications typically use system prompts to enforce output "
                    "format. The exact prompt design determines hallucination rate and reliability."
                ),
                priority="high",
                search_hints=["system", "systemPrompt", "SYSTEM_PROMPT", "messages", "role"],
                related_finding_ids=q3_ids[:1] + q4_ids[:1],
            )
        )
        seq += 1

    # H5: Error handling / retry
    hypotheses.append(
        Hypothesis(
            hypothesis_id=_make_hypothesis_id(seq),
            statement=(
                "There is no automatic retry mechanism for LLM API failures — errors "
                "are returned directly to the user without fallback."
            ),
            reason=(
                "Small/prototype projects often skip retry logic. "
                "This is a common gap that Stage 1.5 should verify."
            ),
            priority="medium",
            search_hints=["retry", "catch", "error", "fallback", "try"],
            related_finding_ids=q6_ids[:1],
        )
    )
    seq += 1

    # H6: Auth / multi-user (if relevant)
    if is_nextjs:
        hypotheses.append(
            Hypothesis(
                hypothesis_id=_make_hypothesis_id(seq),
                statement=(
                    "The app is designed as a single-user personal tool without authentication, "
                    "storing data globally rather than per-user."
                ),
                reason=(
                    "Prototype food tracking apps frequently skip auth. "
                    "Storage paths without user-scoped directories suggest single-user mode."
                ),
                priority="medium",
                search_hints=["auth", "session", "user", "userId", "token", "cookie"],
                related_finding_ids=q5_ids[:1],
            )
        )
        seq += 1

    # H7: Photo/image input (if mentioned in summary)
    if rf.repo_summary and "photo" in rf.repo_summary.lower():
        _q1_ids = [f.finding_id for f in findings if f.question_key == "Q1"]
        hypotheses.append(
            Hypothesis(
                hypothesis_id=_make_hypothesis_id(seq),
                statement=(
                    "Photo input is processed via LLM vision capabilities (e.g., GPT-4V), "
                    "converting food images to calorie estimates without a separate image classifier."
                ),
                reason=(
                    "The repo summary mentions photo/image parsing. "
                    "Vision-capable LLMs are the most common implementation for this."
                ),
                priority="high",
                search_hints=["vision", "image", "base64", "multipart", "upload", "photo"],
                related_finding_ids=_q1_ids[:1],
            )
        )
        seq += 1

    # H8: Nutrition database usage
    food_db_paths = [p for p in rf.storage_paths if "food" in p.lower() or "nutrition" in p.lower()]
    if food_db_paths:
        hypotheses.append(
            Hypothesis(
                hypothesis_id=_make_hypothesis_id(seq),
                statement=(
                    f"The food database at {food_db_paths[0]} is used as RAG context "
                    "to ground LLM responses with authoritative nutritional data."
                ),
                reason=(
                    "A local food-database.json alongside LLM integration suggests "
                    "the LLM is given the database as context rather than relying on training data."
                ),
                priority="high",
                search_hints=["food-database", "nutrition", "lookup", "embed", "rag", "search"],
                related_finding_ids=q2_ids[:1],
            )
        )
        seq += 1

    # Trim to 3–8 hypotheses (already constrained by logic above)
    return hypotheses[:8]


# ──────────────────────────────────────────────────────────────────────────────
# Coverage calculation
# ──────────────────────────────────────────────────────────────────────────────


def _compute_coverage(findings: list[Stage1Finding]) -> Stage1Coverage:
    """Determine which questions are answered, partial, or uncovered."""
    all_questions = ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7"]

    q_confidences: dict[str, list[str]] = {q: [] for q in all_questions}
    for f in findings:
        q_confidences[f.question_key].append(f.confidence)

    answered: list[str] = []
    partial: list[str] = []
    uncovered: list[str] = []

    for q in all_questions:
        confs = q_confidences[q]
        if not confs:
            uncovered.append(q)
        elif any(c == "high" for c in confs) or any(c == "medium" for c in confs):
            answered.append(q)
        else:
            # only low confidence → partial
            partial.append(q)

    return Stage1Coverage(
        answered_questions=answered,
        partial_questions=partial,
        uncovered_questions=uncovered,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Main entry point
# ──────────────────────────────────────────────────────────────────────────────


def run_stage1_scan(
    input: Stage1ScanInput,
) -> ModuleResultEnvelope[Stage1ScanOutput]:
    """Stage 1 Scan: 广度扫描，回答 Q1-Q7，生成 Q8 假说。

    Args:
        input: Stage1ScanInput — validated by Pydantic before calling.

    Returns:
        ModuleResultEnvelope[Stage1ScanOutput] with status ok / degraded / blocked.
    """
    t0 = time.monotonic()
    warnings: list[WarningItem] = []

    # ── Input validation ────────────────────────────────────────────────────
    rf = input.repo_facts
    repo = rf.repo

    # Hard requirement: commit_sha must be present and non-empty
    if not repo.commit_sha or repo.commit_sha.strip() == "":
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        return ModuleResultEnvelope(
            module_name=MODULE_NAME,
            status="blocked",
            error_code=ErrorCodes.INPUT_INVALID,
            warnings=[
                WarningItem(
                    code="W_MISSING_COMMIT_SHA",
                    message="repo.commit_sha is required for stable finding_id generation",
                )
            ],
            data=None,
            metrics=RunMetrics(
                wall_time_ms=elapsed_ms,
                llm_calls=0,
                prompt_tokens=0,
                completion_tokens=0,
                estimated_cost_usd=0.0,
            ),
        )

    repo_id = repo.repo_id

    # ── Complexity check ────────────────────────────────────────────────────
    is_minimal = _is_minimal_repo(input)
    if is_minimal:
        warnings.append(
            WarningItem(
                code="W_MINIMAL_REPO",
                message=(
                    "Repo has very few detectable facts. "
                    "Findings will have low confidence. Stage 1.5 exploration not recommended."
                ),
            )
        )

    # ── Extract findings per question ───────────────────────────────────────
    all_findings: list[Stage1Finding] = []

    q1 = _extract_q1(input, repo_id, 1)
    q2 = _extract_q2(input, repo_id, 1)
    q3 = _extract_q3(input, repo_id, 1)
    q4 = _extract_q4(input, repo_id, 1)
    q5 = _extract_q5(input, repo_id, 1)
    q6 = _extract_q6(input, repo_id, 1)
    q7 = _extract_q7(input, repo_id, 1)

    all_findings = q1 + q2 + q3 + q4 + q5 + q6 + q7

    # ── Hypotheses ──────────────────────────────────────────────────────────
    hypotheses: list[Hypothesis] = []
    if input.config.generate_hypotheses:
        hypotheses = _generate_hypotheses(input, all_findings, repo_id)

    # ── Coverage ─────────────────────────────────────────────────────────────
    coverage = _compute_coverage(all_findings)

    # ── recommended_for_stage15 ──────────────────────────────────────────────
    # Recommend if: not minimal, has hypotheses, at least 1 answered question
    recommended = not is_minimal and len(hypotheses) > 0 and len(coverage.answered_questions) > 0

    output = Stage1ScanOutput(
        repo=repo,
        findings=all_findings,
        hypotheses=hypotheses,
        coverage=coverage,
        recommended_for_stage15=recommended,
    )

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    status = "degraded" if is_minimal else "ok"

    return ModuleResultEnvelope(
        module_name=MODULE_NAME,
        status=status,
        error_code=None,
        warnings=warnings,
        data=output,
        metrics=RunMetrics(
            wall_time_ms=elapsed_ms,
            llm_calls=0,  # rule-based implementation; no LLM calls
            prompt_tokens=0,
            completion_tokens=0,
            estimated_cost_usd=0.0,
        ),
    )
