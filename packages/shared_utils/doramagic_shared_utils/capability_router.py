"""模型无关能力路由器 — 管线绑定能力需求，不绑定模型品牌。

用法:
    router = CapabilityRouter.from_config("models.json")
    model_id = router.route(["deep_reasoning", "code_understanding"])
"""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

# 管线使用的能力标签
CAPABILITY_DEEP_REASONING = "deep_reasoning"
CAPABILITY_STRUCTURED_EXTRACTION = "structured_extraction"
CAPABILITY_TOOL_CALLING = "tool_calling"
CAPABILITY_CODE_UNDERSTANDING = "code_understanding"

# S1-Sonnet 风格的任务标签（映射到能力标签）
TASK_TOOL_SELECTION = "tool_selection"
TASK_HYPOTHESIS_EVALUATION = "hypothesis_evaluation"
TASK_EVIDENCE_EXTRACTION = "evidence_extraction"
TASK_CLAIM_SYNTHESIS = "claim_synthesis"
TASK_GENERAL = "general"

_TASK_TO_CAPABILITIES = {
    TASK_TOOL_SELECTION: [CAPABILITY_TOOL_CALLING, CAPABILITY_CODE_UNDERSTANDING],
    TASK_HYPOTHESIS_EVALUATION: [CAPABILITY_DEEP_REASONING],
    TASK_EVIDENCE_EXTRACTION: [CAPABILITY_CODE_UNDERSTANDING],
    TASK_CLAIM_SYNTHESIS: [CAPABILITY_DEEP_REASONING],
    TASK_GENERAL: [CAPABILITY_STRUCTURED_EXTRACTION],
}

COST_TIER_ORDER = {"low": 0, "medium": 1, "high": 2}

from datetime import UTC, datetime

# ─── Routing Decision Log ────────────────────────────────────────


@dataclass
class RoutingDecision:
    """Records a single model routing decision for transparency."""

    stage: str
    required_capabilities: list[str]
    selected_model: str
    provider: str
    cost_tier: str
    is_degraded: bool
    reason: str
    alternatives: list[str]
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(UTC).isoformat(timespec="seconds")


# Module-level routing log (reset between runs)
_routing_log: list[RoutingDecision] = []


def reset_routing_log() -> None:
    """Clear the routing log. Call at the start of each pipeline run."""
    _routing_log.clear()


def get_routing_log() -> list[RoutingDecision]:
    """Return the current routing log (read-only copy)."""
    return list(_routing_log)


def get_routing_summary() -> str:
    """Return a markdown summary of all routing decisions made in this run."""
    if not _routing_log:
        return ""

    lines = [
        "## Model Routing Decisions",
        "",
        "| Stage | Capabilities | Selected | Provider | Cost | Degraded | Reason |",
        "|-------|-------------|----------|----------|------|----------|--------|",
    ]
    for d in _routing_log:
        caps = ", ".join(d.required_capabilities) if d.required_capabilities else "deterministic"
        deg = "yes" if d.is_degraded else "no"
        lines.append(
            f"| {d.stage} | {caps} | {d.selected_model} | {d.provider} | {d.cost_tier} | {deg} | {d.reason} |"
        )

    lines.append("")
    lines.append(
        f"*Decisions: {len(_routing_log)} | "
        f"Degraded: {sum(1 for d in _routing_log if d.is_degraded)}*"
    )
    return "\n".join(lines)


@dataclass
class ModelDeclaration:
    """用户在 models.json 中声明的可用模型。"""

    model_id: str
    provider: str  # anthropic, google, openai, zhipu, minimax, ...
    capabilities: list[str]
    cost_tier: str = "medium"  # low, medium, high
    api_key_env: str = ""  # 环境变量名
    api_key: str = ""  # 解析后的 API key 值（优先于 api_key_env）
    base_url: str = ""  # OpenAI-compatible endpoint (GLM/Qwen/Kimi/DeepSeek/...)
    max_context_tokens: int = 128000
    supports_tool_use: bool = True

    def has_capabilities(self, required: Sequence[str]) -> bool:
        return all(cap in self.capabilities for cap in required)

    def capability_coverage(self, required: Sequence[str]) -> float:
        if not required:
            return 1.0
        matched = sum(1 for cap in required if cap in self.capabilities)
        return matched / len(required)


@dataclass
class RoutingResult:
    """路由结果。"""

    model_id: str
    provider: str
    is_degraded: bool = False  # True = 没有完美匹配，用了最接近的
    missing_capabilities: list[str] = field(default_factory=list)
    cost_tier: str = "medium"


class CapabilityRouter:
    """
    根据用户声明的可用模型和能力需求，选择最合适的模型。

    路由策略:
    - lowest_sufficient: 满足所有能力的最便宜模型
    - highest_available: 满足所有能力的最强模型
    - 如无完美匹配: 选覆盖最多能力的，标记 degraded
    """

    def __init__(
        self,
        models: list[ModelDeclaration] | None = None,
        preference: str = "lowest_sufficient",
        fallback_strategy: str = "degrade_and_warn",
        forced_adapter=None,  # S1-Sonnet 兼容：传入 adapter 后所有路由返回该 adapter
    ):
        self.models = models or []
        self.preference = preference
        self.fallback_strategy = fallback_strategy
        self._forced_adapter = forced_adapter

    @classmethod
    def from_config(cls, config_path: str | Path) -> CapabilityRouter:
        """从 models.json 配置文件加载。

        Resolution order for config_path:
        1. Use config_path as-is if it is absolute or exists as-is.
        2. If relative and not found, try DORAMAGIC_ROOT/models.json.
        """
        path = Path(config_path).expanduser()

        # Resolve relative paths: try DORAMAGIC_ROOT fallback if the path doesn't exist
        if not path.is_absolute() and not path.exists():
            root = os.environ.get("DORAMAGIC_ROOT")
            if root:
                candidate = Path(root) / "models.json"
                if candidate.exists():
                    path = candidate

        path = path.resolve()
        if not path.exists():
            raise FileNotFoundError(f"models.json not found: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        models = [ModelDeclaration(**m) for m in data["available_models"]]
        return cls(
            models=models,
            preference=data.get("routing_preference", "lowest_sufficient"),
            fallback_strategy=data.get("fallback_strategy", "degrade_and_warn"),
        )

    @classmethod
    def from_openclaw_config(cls, config_path: str | Path | None = None) -> CapabilityRouter:
        """从 OpenClaw 的 openclaw.json 读取模型配置。

        Doramagic 作为 OpenClaw skill，直接复用平台的 LLM 配置，
        不需要维护自己的 models.json。
        """
        if config_path is None:
            config_path = Path("~/.openclaw/openclaw.json").expanduser()
        path = Path(config_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"openclaw.json not found: {path}")

        cls._load_openclaw_env(path.parent / ".env")

        data = json.loads(path.read_text(encoding="utf-8"))
        providers_data = data.get("models", {}).get("providers", {})
        if not providers_data:
            raise ValueError("No model providers found in openclaw.json")

        all_caps = [
            CAPABILITY_DEEP_REASONING,
            CAPABILITY_STRUCTURED_EXTRACTION,
            CAPABILITY_TOOL_CALLING,
            CAPABILITY_CODE_UNDERSTANDING,
        ]
        api_type_to_provider = {
            "anthropic-messages": "anthropic",
            "openai-completions": "openai",
        }

        models: list[ModelDeclaration] = []
        for _provider_name, provider_cfg in providers_data.items():
            api_type = provider_cfg.get("api", "")
            doramagic_provider = api_type_to_provider.get(api_type)
            if not doramagic_provider:
                continue

            base_url = provider_cfg.get("baseUrl", "")
            raw_key = provider_cfg.get("apiKey", "")
            resolved_key = cls._resolve_openclaw_api_key(raw_key)
            if not resolved_key:
                continue

            for model_cfg in provider_cfg.get("models", []):
                model_id = model_cfg.get("id", "")
                if not model_id:
                    continue
                output_cost = model_cfg.get("cost", {}).get("output", 0)
                if output_cost == 0:
                    cost_tier = "low"
                elif output_cost < 5:
                    cost_tier = "medium"
                else:
                    cost_tier = "high"

                models.append(
                    ModelDeclaration(
                        model_id=model_id,
                        provider=doramagic_provider,
                        capabilities=list(all_caps),
                        cost_tier=cost_tier,
                        api_key=resolved_key,
                        base_url=base_url,
                        max_context_tokens=model_cfg.get("contextWindow", 128000),
                        supports_tool_use=True,
                    )
                )

        if not models:
            raise ValueError("No usable models found in openclaw.json (no valid API keys)")

        return cls(
            models=models,
            preference="lowest_sufficient",
            fallback_strategy="degrade_and_warn",
        )

    @staticmethod
    def _load_openclaw_env(env_path: Path) -> None:
        """加载 OpenClaw 的 .env 文件到 os.environ（不覆盖已有值）。"""
        if not env_path.exists():
            return
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if key and key not in os.environ:
                os.environ[key] = value

    @staticmethod
    def _resolve_openclaw_api_key(raw: str) -> str:
        """解析 OpenClaw 的 apiKey 格式: "${ENV_VAR}" 或字面量。"""
        if not raw:
            return ""
        if raw.startswith("${") and raw.endswith("}"):
            env_name = raw[2:-1]
            return os.environ.get(env_name, "")
        return raw

    def for_task(self, task: str):
        """S1-Sonnet 兼容接口：按任务标签返回 adapter。"""
        if self._forced_adapter is not None:
            return self._forced_adapter
        caps = _TASK_TO_CAPABILITIES.get(task, [CAPABILITY_STRUCTURED_EXTRACTION])
        self._current_stage = f"task:{task}"
        result = self.route(caps)
        from doramagic_shared_utils.llm_adapter import LLMAdapter

        adapter = LLMAdapter(provider_override=result.provider)
        adapter._default_model = result.model_id
        matched_model = next((m for m in self.models if m.model_id == result.model_id), None)
        if matched_model:
            if matched_model.base_url:
                adapter._base_url = matched_model.base_url
            if matched_model.api_key:
                adapter._api_key = matched_model.api_key
        return adapter

    def route(self, required_capabilities: Sequence[str]) -> RoutingResult:
        """选择满足能力需求的最合适模型。"""
        if not hasattr(self, "_current_stage"):
            self._current_stage = "unknown"
        # 找完美匹配
        perfect = [m for m in self.models if m.has_capabilities(required_capabilities)]

        if perfect:
            selected = self._select_by_preference(perfect)
            alternatives = [m.model_id for m in perfect if m.model_id != selected.model_id]
            result = RoutingResult(
                model_id=selected.model_id,
                provider=selected.provider,
                cost_tier=selected.cost_tier,
            )
            _routing_log.append(
                RoutingDecision(
                    stage=getattr(self, "_current_stage", "unknown"),
                    required_capabilities=list(required_capabilities),
                    selected_model=selected.model_id,
                    provider=selected.provider,
                    cost_tier=selected.cost_tier,
                    is_degraded=False,
                    reason=self.preference,
                    alternatives=alternatives,
                )
            )
            return result

        # 无完美匹配 — 降级
        if self.fallback_strategy == "degrade_and_warn":
            best = max(self.models, key=lambda m: m.capability_coverage(required_capabilities))
            missing = [cap for cap in required_capabilities if cap not in best.capabilities]
            result = RoutingResult(
                model_id=best.model_id,
                provider=best.provider,
                is_degraded=True,
                missing_capabilities=missing,
                cost_tier=best.cost_tier,
            )
            _routing_log.append(
                RoutingDecision(
                    stage=getattr(self, "_current_stage", "unknown"),
                    required_capabilities=list(required_capabilities),
                    selected_model=best.model_id,
                    provider=best.provider,
                    cost_tier=best.cost_tier,
                    is_degraded=True,
                    reason=f"degraded: missing {missing}",
                    alternatives=[],
                )
            )
            return result

        # strict 模式：无匹配则报错
        raise RuntimeError(
            f"No model satisfies capabilities {required_capabilities}. "
            f"Available: {[(m.model_id, m.capabilities) for m in self.models]}"
        )

    def get_all_capable(self, required_capabilities: Sequence[str]) -> list[RoutingResult]:
        """返回所有满足能力需求的模型（用于 GDS 多模型融合）。"""
        results = []
        for m in self.models:
            if m.has_capabilities(required_capabilities):
                results.append(
                    RoutingResult(
                        model_id=m.model_id,
                        provider=m.provider,
                        cost_tier=m.cost_tier,
                    )
                )
        return results

    def route_for_stage(self, stage_name: str) -> RoutingResult:
        """按 Stage 名称路由 — 预定义的能力需求映射。"""
        stage_requirements = {
            "stage0": [],  # 确定性，无 LLM
            "stage1": [CAPABILITY_DEEP_REASONING, CAPABILITY_CODE_UNDERSTANDING],
            "stage1.5": [CAPABILITY_TOOL_CALLING, CAPABILITY_CODE_UNDERSTANDING],
            "stage2": [CAPABILITY_STRUCTURED_EXTRACTION],
            "stage3": [CAPABILITY_STRUCTURED_EXTRACTION],
            "stage3.5": [],  # 确定性验证
            "stage4": [CAPABILITY_DEEP_REASONING],
            "stage5": [],  # 确定性组装
            "phase_e": [CAPABILITY_DEEP_REASONING],  # 跨源权衡
            "phase_f": [CAPABILITY_STRUCTURED_EXTRACTION],  # 格式编译
        }
        caps = stage_requirements.get(stage_name, [])
        if not caps:
            # 确定性 stage，返回任意模型（不会实际调用）
            return RoutingResult(model_id="deterministic", provider="none")
        self._current_stage = stage_name
        return self.route(caps)

    def build_adapter_for_stage(self, stage_name: str) -> LLMAdapter:
        """Route a stage and return a configured LLMAdapter ready to call."""
        result = self.route_for_stage(stage_name)
        if result.provider == "none":
            return None  # deterministic stage, no LLM needed
        from doramagic_shared_utils.llm_adapter import LLMAdapter

        adapter = LLMAdapter(provider_override=result.provider)
        adapter._default_model = result.model_id
        matched = next((m for m in self.models if m.model_id == result.model_id), None)
        if matched:
            if matched.base_url:
                adapter._base_url = matched.base_url
            if matched.api_key:
                adapter._api_key = matched.api_key
        return adapter

    def _select_by_preference(self, candidates: list[ModelDeclaration]) -> ModelDeclaration:
        if self.preference == "lowest_sufficient":
            return min(candidates, key=lambda m: COST_TIER_ORDER.get(m.cost_tier, 1))
        if self.preference == "highest_available":
            return max(candidates, key=lambda m: COST_TIER_ORDER.get(m.cost_tier, 1))
        return candidates[0]
