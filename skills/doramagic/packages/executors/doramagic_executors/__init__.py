"""Doramagic Executors — Inner layer of the dual-layer fusion architecture.

Thin wrappers around existing packages, conforming to the PhaseExecutor protocol.
Each executor: typed input → call existing function → ModuleResultEnvelope[T].
"""

from doramagic_executors.need_profile_builder import NeedProfileBuilder
from doramagic_executors.discovery_runner import DiscoveryRunner
from doramagic_executors.soul_extractor_batch import SoulExtractorBatch
from doramagic_executors.community_harvester import CommunityHarvester
from doramagic_executors.synthesis_runner import SynthesisRunner
from doramagic_executors.skill_compiler_executor import SkillCompilerExecutor
from doramagic_executors.validator_executor import ValidatorExecutor
from doramagic_executors.delivery_packager import DeliveryPackager

ALL_EXECUTORS = {
    "NeedProfileBuilder": NeedProfileBuilder,
    "DiscoveryRunner": DiscoveryRunner,
    "SoulExtractorBatch": SoulExtractorBatch,
    "CommunityHarvester": CommunityHarvester,
    "SynthesisRunner": SynthesisRunner,
    "SkillCompiler": SkillCompilerExecutor,
    "Validator": ValidatorExecutor,
    "DeliveryPackager": DeliveryPackager,
}

__all__ = [
    "NeedProfileBuilder", "DiscoveryRunner", "SoulExtractorBatch",
    "CommunityHarvester", "SynthesisRunner", "SkillCompilerExecutor",
    "ValidatorExecutor", "DeliveryPackager", "ALL_EXECUTORS",
]
