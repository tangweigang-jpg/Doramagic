"""Package JSON assembler.

Reads the four PhaseResult objects from PhaseContext and assembles them
into the Crystal Package dict ready for POST to /api/publish/crystal.

Field group mapping:
  content    → A (slug, name, name_en, definition, definition_en,
                  description, description_en, category_slug, tags, version)
               E (known_gaps)
               G (changelog, changelog_en, contributors)
  constraints → D (constraints)
  faq         → F (faqs)
  evaluator   → B provenance (from manifest, not LLM)
               C (seed_content, from ctx)
               H (sample_output, applicable_scenarios, inapplicable_scenarios, host_adapters)
               I (required_inputs)
               J (creator_proof, model_compatibility)
               K (tier, is_flagship, parent_flagship_slug, presets)
               L (core_keywords, meta_title_suffix, og_image_fields)

Note: Group B (blueprint_id, blueprint_source, blueprint_commit) comes from
ctx.manifest (not from LLM), and Group C (seed_content) comes from ctx.seed_content.
"""

from __future__ import annotations

import logging
from typing import Any

from doramagic_web_publisher.errors import AssemblyError
from doramagic_web_publisher.runtime.models import PhaseContext

logger = logging.getLogger(__name__)

# Fields that must be present in the final package.
# These are split by source: phase results vs manifest.
_REQUIRED_FROM_CONTENT = [
    "slug",
    "name",
    "name_en",
    "definition",
    "definition_en",
    "description",
    "description_en",
    "category_slug",
    "tags",
    "version",
    "known_gaps",
    "changelog",
    "changelog_en",
    "contributors",
]

_REQUIRED_FROM_CONSTRAINTS = ["constraints"]

_REQUIRED_FROM_FAQ = ["faqs"]

_REQUIRED_FROM_EVALUATOR = [
    "applicable_scenarios",
    "inapplicable_scenarios",
    "required_inputs",
    "model_compatibility",
    "tier",
    "is_flagship",
    "parent_flagship_slug",
    "core_keywords",
    "og_image_fields",
]


class Assembler:
    """Assembles Crystal Package JSON from pipeline phase results."""

    def assemble(self, ctx: PhaseContext) -> dict[str, Any]:
        """Build and return the complete Crystal Package dict.

        Args:
            ctx: PhaseContext with all four phase results populated.

        Returns:
            Dict matching the Crystal Package schema (§1.2).

        Raises:
            AssemblyError: If any required fields are missing from phase results.
        """
        missing: list[str] = []

        content_fields = ctx.phase_fields("content")
        constraints_fields = ctx.phase_fields("constraints")
        faq_fields = ctx.phase_fields("faq")
        evaluator_fields = ctx.phase_fields("evaluator")

        # Validate required fields from each phase.
        for field in _REQUIRED_FROM_CONTENT:
            if field not in content_fields:
                missing.append(f"content.{field}")
        for field in _REQUIRED_FROM_CONSTRAINTS:
            if field not in constraints_fields:
                missing.append(f"constraints.{field}")
        for field in _REQUIRED_FROM_FAQ:
            if field not in faq_fields:
                missing.append(f"faq.{field}")
        for field in _REQUIRED_FROM_EVALUATOR:
            if field not in evaluator_fields:
                missing.append(f"evaluator.{field}")

        # Validate provenance fields from manifest.
        if not ctx.manifest.blueprint_id:
            missing.append("manifest.blueprint_id")
        if not ctx.manifest.blueprint_source:
            missing.append("manifest.blueprint_source")
        if not ctx.manifest.blueprint_commit:
            missing.append("manifest.blueprint_commit")

        # Validate seed_content from context.
        if not ctx.seed_content:
            missing.append("ctx.seed_content")

        if missing:
            raise AssemblyError(missing)

        # Build the package dict, following SOP §1.2 field group order.
        package: dict[str, Any] = {}

        # ---- A. Basic identification (from content phase) ----
        package["slug"] = content_fields["slug"]
        package["name"] = content_fields["name"]
        package["name_en"] = content_fields["name_en"]
        package["definition"] = content_fields["definition"]
        package["definition_en"] = content_fields["definition_en"]
        package["description"] = content_fields["description"]
        package["description_en"] = content_fields["description_en"]
        package["category_slug"] = content_fields["category_slug"]
        package["tags"] = content_fields["tags"]
        package["version"] = content_fields["version"]

        # ---- B. Provenance (from manifest, not LLM) ----
        package["blueprint_id"] = ctx.manifest.blueprint_id
        package["blueprint_source"] = ctx.manifest.blueprint_source
        package["blueprint_commit"] = ctx.manifest.blueprint_commit

        # ---- C. Recipe file (from ctx) ----
        package["seed_content"] = ctx.seed_content

        # ---- D. Constraints (from constraints phase) ----
        package["constraints"] = constraints_fields["constraints"]

        # ---- E. Known gaps (from content phase) ----
        package["known_gaps"] = content_fields.get("known_gaps", [])

        # ---- F. FAQ (from faq phase) ----
        package["faqs"] = faq_fields["faqs"]

        # ---- G. Changelog (from content phase) ----
        package["changelog"] = content_fields["changelog"]
        package["changelog_en"] = content_fields["changelog_en"]
        package["contributors"] = content_fields["contributors"]

        # ---- H. Consumer evaluation data (from evaluator phase + static injection) ----
        package["applicable_scenarios"] = evaluator_fields["applicable_scenarios"]
        package["inapplicable_scenarios"] = evaluator_fields["inapplicable_scenarios"]

        # H. host_adapters: static injection from Crystal IR (Fix #3b)
        _ir = ctx.crystal_ir or {}
        _harness = _ir.get("harness", {}) or {}
        _ir_ha_raw = _harness.get("host_adapters", _ir.get("host_adapters", {}))
        _valid_hosts = {"openclaw", "claude_code", "codex_cli", "gemini_cli"}
        if isinstance(_ir_ha_raw, dict):
            package["host_adapters"] = [
                {
                    "host": host_name,
                    "load_method": spec.get(
                        "load_method",
                        "SKILL file load" if host_name == "openclaw" else "CLAUDE.md paste",
                    ),
                    "notes": spec.get("notes", None),
                }
                for host_name, spec in _ir_ha_raw.items()
                if host_name in _valid_hosts and isinstance(spec, dict)
            ]
        elif isinstance(_ir_ha_raw, list):
            package["host_adapters"] = [
                ha if isinstance(ha, dict) else {"host": ha, "load_method": "", "notes": None}
                for ha in _ir_ha_raw
                if (ha.get("host") if isinstance(ha, dict) else ha) in _valid_hosts
            ]
        else:
            package["host_adapters"] = []
        logger.info(
            "Assembler: injected host_adapters from Crystal IR: %d hosts",
            len(package["host_adapters"]),
        )

        # H. sample_output: derived from creator_proof[0] (Fix #3b)
        first_proof = ctx.creator_proof[0] if ctx.creator_proof else {}
        package["sample_output"] = {
            "format": first_proof.get("evidence_type", "trace_url"),
            "primary_url": first_proof.get("evidence_url"),
            "text_preview": None,
            "caption": first_proof.get("summary", "")[:40] if first_proof.get("summary") else "",
            "caption_en": first_proof.get("summary_en", "")[:80]
            if first_proof.get("summary_en")
            else "",
        }

        # ---- I. Variable injection (from evaluator phase) ----
        package["required_inputs"] = evaluator_fields["required_inputs"]

        # ---- J. Trust data: creator_proof pass-through + model_compatibility from evaluator ----
        package["creator_proof"] = ctx.creator_proof  # direct pass-through from context
        package["model_compatibility"] = evaluator_fields["model_compatibility"]

        # ---- K. Discovery metadata (from evaluator phase) ----
        package["tier"] = evaluator_fields["tier"]
        package["is_flagship"] = evaluator_fields["is_flagship"]
        package["parent_flagship_slug"] = evaluator_fields["parent_flagship_slug"]
        package["presets"] = evaluator_fields.get("presets", None)

        # ---- L. SEO/GEO fields: keywords from evaluator, og stat computed here (Fix #3b) ----
        package["core_keywords"] = evaluator_fields["core_keywords"]
        package["meta_title_suffix"] = evaluator_fields.get("meta_title_suffix", None)

        # og_image_fields: merge LLM-provided headline with Assembler-computed stat fields
        _og_from_llm = evaluator_fields.get("og_image_fields", {}) or {}
        _constraint_list = package.get("constraints", [])
        _constraint_count = len(_constraint_list)
        _fatal_count = sum(1 for c in _constraint_list if c.get("severity") == "fatal")
        _source_file_count = len(
            {
                c.get("evidence_locator", "").split(":")[0]
                for c in _constraint_list
                if c.get("evidence_locator")
            }
        )
        package["og_image_fields"] = {
            "headline": _og_from_llm.get("headline", ""),
            "headline_en": _og_from_llm.get("headline_en", ""),
            "stat_primary": f"{_constraint_count} 条防坑规则",
            "stat_primary_en": f"{_constraint_count} pitfall rules",
            "stat_secondary": f"{_fatal_count} 条 FATAL · {_source_file_count} 处源码",
            "stat_secondary_en": f"{_fatal_count} FATAL · {_source_file_count} source locations",
        }
        logger.info(
            "Assembler: og_image_fields computed: "
            "constraint_count=%d, fatal_count=%d, source_files=%d",
            _constraint_count,
            _fatal_count,
            _source_file_count,
        )

        logger.info(
            "Assembler: package assembled for slug='%s', constraints=%d, faqs=%d, core_keywords=%d",
            package["slug"],
            len(package["constraints"]),
            len(package["faqs"]),
            len(package["core_keywords"]),
        )

        return package

    def validate_structure(self, package: dict[str, Any]) -> list[str]:
        """Quick structural validation — returns list of issues (empty = ok).

        This is a lightweight pre-check before calling preflight.
        Does NOT duplicate preflight logic — just checks field presence and types.
        """
        issues: list[str] = []

        top_level_required = [
            "slug",
            "name",
            "name_en",
            "definition",
            "definition_en",
            "description",
            "description_en",
            "category_slug",
            "tags",
            "version",
            "blueprint_id",
            "blueprint_source",
            "blueprint_commit",
            "seed_content",
            "constraints",
            "faqs",
            "changelog",
            "changelog_en",
            "contributors",
            "sample_output",
            "applicable_scenarios",
            "inapplicable_scenarios",
            "host_adapters",
            "required_inputs",
            "creator_proof",
            "model_compatibility",
            "tier",
            "is_flagship",
            "parent_flagship_slug",
            "core_keywords",
            "og_image_fields",
        ]

        for field in top_level_required:
            if field not in package:
                issues.append(f"Missing required field: {field}")
            elif package[field] is None and field not in {
                "parent_flagship_slug",
                "meta_title_suffix",
                "presets",
            }:
                issues.append(f"Field '{field}' is null but must be non-null")

        return issues
