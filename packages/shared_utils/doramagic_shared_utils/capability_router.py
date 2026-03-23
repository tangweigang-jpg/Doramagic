"""模型无关能力路由器 — 管线绑定能力需求，不绑定模型品牌。

用法:
    router = CapabilityRouter.from_config("models.json")
    model_id = router.route(["deep_reasoning", "code_understanding"])
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Sequence

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


@dataclass
class ModelDeclaration:
    """用户在 models.json 中声明的可用模型。"""

    model_id: str
    provider: str  # anthropic, google, openai, zhipu, minimax, ...
    capabilities: list[str]
    cost_tier: str = "medium"  # low, medium, high
    api_key_env: str = ""  # 环境变量名
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
        """从 models.json 配置文件加载。"""
        path = Path(config_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"models.json not found: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        models = [ModelDeclaration(**m) for m in data["available_models"]]
        return cls(
            models=models,
            preference=data.get("routing_preference", "lowest_sufficient"),
            fallback_strategy=data.get("fallback_strategy", "degrade_and_warn"),
        )

    def for_task(self, task: str):
        """S1-Sonnet 兼容接口：按任务标签返回 adapter。"""
        if self._forced_adapter is not None:
            return self._forced_adapter
        # 映射 task → capabilities → route → 构建简易 adapter
        caps = _TASK_TO_CAPABILITIES.get(task, [CAPABILITY_STRUCTURED_EXTRACTION])
        result = self.route(caps)
        # 返回一个带 _default_model 的标记对象
        from doramagic_shared_utils.llm_adapter import LLMAdapter
        adapter = LLMAdapter(provider_override=result.provider)
        adapter._default_model = result.model_id
        return adapter

    def route(self, required_capabilities: Sequence[str]) -> RoutingResult:
        """选择满足能力需求的最合适模型。"""
        # 找完美匹配
        perfect = [m for m in self.models if m.has_capabilities(required_capabilities)]

        if perfect:
            selected = self._select_by_preference(perfect)
            return RoutingResult(
                model_id=selected.model_id,
                provider=selected.provider,
                cost_tier=selected.cost_tier,
            )

        # 无完美匹配 — 降级
        if self.fallback_strategy == "degrade_and_warn":
            best = max(self.models, key=lambda m: m.capability_coverage(required_capabilities))
            missing = [cap for cap in required_capabilities if cap not in best.capabilities]
            return RoutingResult(
                model_id=best.model_id,
                provider=best.provider,
                is_degraded=True,
                missing_capabilities=missing,
                cost_tier=best.cost_tier,
            )

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
                results.append(RoutingResult(
                    model_id=m.model_id,
                    provider=m.provider,
                    cost_tier=m.cost_tier,
                ))
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
        return self.route(caps)

    def _select_by_preference(self, candidates: list[ModelDeclaration]) -> ModelDeclaration:
        if self.preference == "lowest_sufficient":
            return min(candidates, key=lambda m: COST_TIER_ORDER.get(m.cost_tier, 1))
        if self.preference == "highest_available":
            return max(candidates, key=lambda m: COST_TIER_ORDER.get(m.cost_tier, 1))
        return candidates[0]
