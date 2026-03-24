"""doramagic_community — GitHub search, download, and community signals."""

from doramagic_community.github_search import download_repo, search_github
from doramagic_community.community_signals import (
    collect_community_signals,
    fetch_github_issues,
    collect_changelog_signals,
    compute_dsd_metrics,
    process_issues_to_signals,
)

__all__ = [
    "search_github",
    "download_repo",
    "collect_community_signals",
    "fetch_github_issues",
    "collect_changelog_signals",
    "compute_dsd_metrics",
    "process_issues_to_signals",
]
