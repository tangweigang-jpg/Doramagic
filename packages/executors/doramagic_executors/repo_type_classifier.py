"""Repo type classifier -- deterministic classification, no LLM.

Classifies repos into:
  TOOL      -- utility/application (deep extraction)
  FRAMEWORK -- library/framework (deep extraction)
  CATALOG   -- awesome-list/resource collection (shallow extraction)

WHY deterministic: repo type affects extraction path cost significantly.
CATALOG repos skip deep code analysis (saves ~60s per repo).
LLM classification would add latency and non-determinism for no benefit.
"""

from __future__ import annotations

import re
from typing import Literal

RepoType = Literal["TOOL", "FRAMEWORK", "CATALOG"]


def classify_repo_type(facts: dict, repo_name: str = "") -> RepoType:
    """Classify a repo based on deterministic signals from repo_facts.

    Priority:
    1. CATALOG: awesome-list signals dominate
    2. FRAMEWORK: large API surface, docs, package manifests
    3. TOOL: default (application/utility)
    """
    name_lower = repo_name.lower()

    # --- CATALOG detection ---
    # Strong signal: name contains "awesome"
    if "awesome" in name_lower:
        return "CATALOG"

    # README-heavy with many links = catalog
    readme_lines = facts.get("readme_lines", 0)
    link_density = facts.get("link_density", 0.0)
    if readme_lines > 200 and link_density > 0.3:
        return "CATALOG"

    # High doc-to-code ratio with many outbound links
    code_files = facts.get("code_file_count", facts.get("file_count", 0))
    doc_files = facts.get("doc_file_count", 0)
    if code_files > 0 and doc_files > 0:
        ratio = doc_files / max(code_files, 1)
        if ratio > 2.0:
            return "CATALOG"

    # Name patterns for catalogs
    catalog_patterns = [
        r"^awesome-",
        r"-awesome$",
        r"^curated-",
        r"^list-of-",
        r"^resources-",
        r"-resources$",
        r"^collection-",
    ]
    for pattern in catalog_patterns:
        if re.search(pattern, name_lower):
            return "CATALOG"

    # --- FRAMEWORK detection ---
    # Has package.json/setup.py/Cargo.toml + src/ + docs/
    has_package_manifest = facts.get("has_package_manifest", False)
    has_src = facts.get("has_src", False)
    has_docs = facts.get("has_docs", False)
    has_examples = facts.get("has_examples", False)

    # Check for common package manifests
    if not has_package_manifest:
        for indicator in [
            "package.json",
            "setup.py",
            "pyproject.toml",
            "Cargo.toml",
            "go.mod",
            "pom.xml",
            "build.gradle",
        ]:
            if indicator in facts.get("root_files", []):
                has_package_manifest = True
                break

    # Framework: has all three of package manifest + source + docs/examples
    if has_package_manifest and has_src and (has_docs or has_examples):
        # Additional check: if it has a large API surface
        api_surface = facts.get("api_surface_size", 0)
        if api_surface > 10 or facts.get("export_count", 0) > 10:
            return "FRAMEWORK"

    # Framework name patterns
    framework_patterns = [
        r"-framework$",
        r"^lib",
        r"-lib$",
        r"-sdk$",
        r"^sdk-",
        r"-engine$",
        r"-core$",
    ]
    for pattern in framework_patterns:
        if re.search(pattern, name_lower):
            if has_package_manifest and has_src:
                return "FRAMEWORK"

    # Default: TOOL
    return "TOOL"
