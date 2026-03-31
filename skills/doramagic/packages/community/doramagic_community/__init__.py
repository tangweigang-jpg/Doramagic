"""doramagic_community — GitHub search, download, and community signals."""

from doramagic_community.community_signals import (
    collect_changelog_signals,
    collect_community_signals,
    compute_dsd_metrics,
    fetch_github_issues,
    process_issues_to_signals,
)
from doramagic_community.github_search import download_repo, search_github

__all__ = [
    "collect_changelog_signals",
    "collect_community_signals",
    "compute_dsd_metrics",
    "download_repo",
    "fetch_github_issues",
    "process_issues_to_signals",
    "search_github",
]
