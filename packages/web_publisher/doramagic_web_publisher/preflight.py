"""Local preflight gate runner.

Implements the subset of the 36 quality gates (SOP §2.4) that can be
evaluated locally before the HTTP POST. Running these locally saves
round-trips and gives faster feedback to the operator.

Implemented gates (5 real, as per CEO delivery requirement):
  1. SEO-SLUG          — slug format validation
  2. SEO-TITLE-LENGTH  — derived meta title ≤ 60 chars
  3. GEO-FAQ-COUNT     — faqs count ∈ [5, 8]
  4. I18N-COMPLETE     — all _en fields non-empty
  5. DATA-VERSION      — version matches semver pattern

All other gates (31 total) run server-side on the Publish API.

Usage:
    runner = PreflightRunner()
    results = runner.run(package)
    fatal_failures = [r for r in results if r["level"] == "fatal" and not r["passed"]]
"""

from __future__ import annotations

import logging
import re
from typing import Any

from doramagic_web_publisher.errors import PreflightError

logger = logging.getLogger(__name__)

# Semver pattern matching SOP §2.3
_SEMVER_RE = re.compile(r"^v\d+\.\d+\.\d+$")

# Slug pattern matching SOP §2.3
_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{2,59}$")

# Internal ID pattern forbidden in slug (SOP §2.4 SEO-SLUG rule)
_SLUG_BP_RE = re.compile(r"bp-\d+")

# Pattern for pure numeric segments in slug
_SLUG_PURE_NUMERIC_SEG_RE = re.compile(r"(^|-)\d+($|-)")

# _en field suffixes to check for I18N-COMPLETE
_EN_FIELDS_TOP_LEVEL = [
    "name_en",
    "definition_en",
    "description_en",
    "changelog_en",
]


def _derive_meta_title(package: dict[str, Any]) -> str:
    """Derive metaTitle (Chinese) as the Publish API would (SOP §2.5).

    Template: `{name} | {core_keywords_zh[0]} | {meta_title_suffix or "Doramagic"}`
    Truncation: if total > 60 chars, keyword segment is truncated to fit.
    """
    name = package.get("name", "")
    keywords = package.get("core_keywords", [])
    # Find first Chinese keyword (contains a CJK character)
    zh_keywords = [k for k in keywords if any("\u4e00" <= c <= "\u9fff" for c in k)]
    keyword_seg = zh_keywords[0] if zh_keywords else ""
    suffix = package.get("meta_title_suffix") or "Doramagic"

    candidate = f"{name} | {keyword_seg} | {suffix}"
    if len(candidate) <= 60:
        return candidate

    # Truncate keyword segment
    max_keyword_len = 60 - len(name) - len(suffix) - 6  # " | " × 2 = 6
    if max_keyword_len > 0:
        keyword_seg = keyword_seg[:max_keyword_len]
        return f"{name} | {keyword_seg} | {suffix}"
    return f"{name} | {suffix}"


def _derive_meta_title_en(package: dict[str, Any]) -> str:
    """Derive metaTitleEn (English) as the Publish API would (SOP §2.5).

    Template: `{name_en} | {core_keywords_en[0]} | Doramagic`
    Uses first English (non-CJK) keyword from core_keywords.
    Truncation: if total > 60 chars, keyword segment is truncated to fit.
    """
    name_en = package.get("name_en", "")
    keywords = package.get("core_keywords", [])
    # Find first English keyword (no CJK characters)
    en_keywords = [k for k in keywords if not any("\u4e00" <= c <= "\u9fff" for c in k)]
    keyword_seg = en_keywords[0] if en_keywords else ""
    suffix = "Doramagic"

    candidate = f"{name_en} | {keyword_seg} | {suffix}"
    if len(candidate) <= 60:
        return candidate

    # Truncate keyword segment
    max_keyword_len = 60 - len(name_en) - len(suffix) - 6  # " | " × 2 = 6
    if max_keyword_len > 0:
        keyword_seg = keyword_seg[:max_keyword_len]
        return f"{name_en} | {keyword_seg} | {suffix}"
    return f"{name_en} | {suffix}"


def _collect_en_fields(package: dict[str, Any]) -> list[tuple[str, Any]]:
    """Collect all _en sub-fields that must be non-empty."""
    fields: list[tuple[str, Any]] = []

    # Top-level _en fields
    for f in _EN_FIELDS_TOP_LEVEL:
        fields.append((f, package.get(f)))

    # known_gaps _en fields
    for i, gap in enumerate(package.get("known_gaps", [])):
        fields.append((f"known_gaps[{i}].description_en", gap.get("description_en")))
        fields.append((f"known_gaps[{i}].impact_en", gap.get("impact_en")))

    # constraints _en fields
    for i, c in enumerate(package.get("constraints", [])):
        fields.append((f"constraints[{i}].summary_en", c.get("summary_en")))

    # faqs _en fields
    for i, faq in enumerate(package.get("faqs", [])):
        fields.append((f"faqs[{i}].question_en", faq.get("question_en")))
        fields.append((f"faqs[{i}].answer_en", faq.get("answer_en")))

    # sample_output _en
    so = package.get("sample_output", {})
    fields.append(("sample_output.caption_en", so.get("caption_en")))

    # applicable_scenarios _en
    for i, s in enumerate(package.get("applicable_scenarios", [])):
        fields.append((f"applicable_scenarios[{i}].text_en", s.get("text_en")))

    # inapplicable_scenarios _en
    for i, s in enumerate(package.get("inapplicable_scenarios", [])):
        fields.append((f"inapplicable_scenarios[{i}].text_en", s.get("text_en")))

    # required_inputs _en
    for i, inp in enumerate(package.get("required_inputs", [])):
        fields.append((f"required_inputs[{i}].hint_en", inp.get("hint_en")))

    # creator_proof _en
    for i, cp in enumerate(package.get("creator_proof", [])):
        fields.append((f"creator_proof[{i}].summary_en", cp.get("summary_en")))

    # model_compatibility _en (only for partial/not_recommended)
    for i, mc in enumerate(package.get("model_compatibility", [])):
        if mc.get("status") in {"partial", "not_recommended"}:
            fields.append((f"model_compatibility[{i}].note_en", mc.get("note_en")))

    # og_image_fields _en
    ogf = package.get("og_image_fields", {})
    fields.append(("og_image_fields.headline_en", ogf.get("headline_en")))
    fields.append(("og_image_fields.stat_primary_en", ogf.get("stat_primary_en")))
    fields.append(("og_image_fields.stat_secondary_en", ogf.get("stat_secondary_en")))

    # presets _en fields (SOP §1.2 Group K) — presets may be None when is_flagship=False
    for i, preset in enumerate(package.get("presets") or []):
        fields.append((f"presets[{i}].name_en", preset.get("name_en")))
        fields.append((f"presets[{i}].description_en", preset.get("description_en")))

    return fields


class GateResult:
    """Result of a single preflight gate check."""

    def __init__(
        self,
        gate_id: str,
        level: str,
        passed: bool,
        message: str = "",
    ) -> None:
        self.gate_id = gate_id
        self.level = level  # "fatal" | "warn"
        self.passed = passed
        self.message = message

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate": self.gate_id,
            "level": self.level,
            "passed": self.passed,
            "message": self.message,
        }


class PreflightRunner:
    """Runs the locally-implementable subset of quality gates."""

    def run(self, package: dict[str, Any]) -> list[GateResult]:
        """Run all implemented gates and return results.

        Args:
            package: Crystal Package dict from Assembler.

        Returns:
            List of GateResult (one per implemented gate).
        """
        results: list[GateResult] = [
            self._check_seo_slug(package),
            self._check_seo_title_length(package),
            self._check_geo_faq_count(package),
            self._check_i18n_complete(package),
            self._check_data_version(package),
        ]
        return results

    def run_and_raise_on_fatal(self, package: dict[str, Any]) -> list[GateResult]:
        """Run gates and raise PreflightError if any fatal gate fails.

        Args:
            package: Crystal Package dict.

        Returns:
            List of all GateResult objects.

        Raises:
            PreflightError: If any FATAL gate fails.
        """
        results = self.run(package)
        failures = [r.to_dict() for r in results if not r.passed and r.level == "fatal"]
        if failures:
            raise PreflightError(failures)

        # Log warnings
        warns = [r for r in results if not r.passed and r.level == "warn"]
        if warns:
            for w in warns:
                logger.warning("Preflight WARN [%s]: %s", w.gate_id, w.message)

        return results

    # ------------------------------------------------------------------
    # Gate implementations
    # ------------------------------------------------------------------

    def _check_seo_slug(self, package: dict[str, Any]) -> GateResult:
        """SEO-SLUG: slug must be URL-safe, semantic, not contain internal IDs."""
        gate = "SEO-SLUG"
        slug = package.get("slug", "")

        if not slug:
            return GateResult(gate, "fatal", False, "slug is empty")

        if not _SLUG_RE.match(slug):
            return GateResult(
                gate, "fatal", False, f"slug '{slug}' does not match /^[a-z][a-z0-9-]{{2,59}}$/"
            )

        if _SLUG_BP_RE.search(slug):
            return GateResult(
                gate, "fatal", False, f"slug '{slug}' contains internal ID pattern 'bp-\\d+'"
            )

        if _SLUG_PURE_NUMERIC_SEG_RE.search(slug):
            return GateResult(
                gate, "fatal", False, f"slug '{slug}' contains a pure numeric segment"
            )

        return GateResult(gate, "fatal", True, f"slug '{slug}' is valid")

    def _check_seo_title_length(self, package: dict[str, Any]) -> GateResult:
        """SEO-TITLE-LENGTH: derived metaTitle (ZH) and metaTitleEn (EN) must both be ≤ 60 chars."""
        gate = "SEO-TITLE-LENGTH"

        meta_title = _derive_meta_title(package)
        zh_length = len(meta_title)

        meta_title_en = _derive_meta_title_en(package)
        en_length = len(meta_title_en)

        failures = []
        if zh_length > 60:
            failures.append(f"metaTitle (ZH) is {zh_length} chars > 60: '{meta_title}'")
        if en_length > 60:
            failures.append(f"metaTitleEn (EN) is {en_length} chars > 60: '{meta_title_en}'")

        if failures:
            return GateResult(gate, "fatal", False, "; ".join(failures))
        return GateResult(
            gate,
            "fatal",
            True,
            f"metaTitle {zh_length} chars ≤ 60; metaTitleEn {en_length} chars ≤ 60",
        )

    def _check_geo_faq_count(self, package: dict[str, Any]) -> GateResult:
        """GEO-FAQ-COUNT: faqs must have 5-8 entries (v2.2 lower bound raised from 3 to 5)."""
        gate = "GEO-FAQ-COUNT"

        faqs = package.get("faqs", [])
        count = len(faqs)

        if count < 5:
            return GateResult(
                gate, "fatal", False, f"faqs has {count} entries < minimum 5 (SOP v2.2)"
            )
        if count > 8:
            return GateResult(gate, "fatal", False, f"faqs has {count} entries > maximum 8")
        return GateResult(gate, "fatal", True, f"faqs count {count} ∈ [5, 8]")

    def _check_i18n_complete(self, package: dict[str, Any]) -> GateResult:
        """I18N-COMPLETE: all _en fields must be non-empty."""
        gate = "I18N-COMPLETE"

        en_fields = _collect_en_fields(package)
        empty = [
            field_path
            for field_path, value in en_fields
            if not value or (isinstance(value, str) and not value.strip())
        ]

        if empty:
            return GateResult(
                gate,
                "fatal",
                False,
                f"Empty _en fields: {', '.join(empty[:10])}" + (" ..." if len(empty) > 10 else ""),
            )
        return GateResult(gate, "fatal", True, f"All {len(en_fields)} _en fields are non-empty")

    def _check_data_version(self, package: dict[str, Any]) -> GateResult:
        """DATA-VERSION: version must match vMAJOR.MINOR.PATCH format.

        Note: The server-side gate also checks version > existing version.
        The local check only validates the format.
        """
        gate = "DATA-VERSION"

        version = package.get("version", "")
        if not version:
            return GateResult(gate, "fatal", False, "version field is empty")

        if not _SEMVER_RE.match(version):
            return GateResult(
                gate, "fatal", False, f"version '{version}' does not match /^v\\d+\\.\\d+\\.\\d+$/"
            )
        return GateResult(gate, "fatal", True, f"version '{version}' is valid semver")
