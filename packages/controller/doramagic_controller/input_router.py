"""Deterministic input routing for Doramagic v12.1.1."""

from __future__ import annotations

import re

from doramagic_contracts.base import NeedProfile, RoutingDecision


class InputRouter:
    """Route user intent without using an LLM."""

    URL_PATTERN = re.compile(r"https?://(?:github|gitlab|gitee)\.com/[\w.-]+/[\w.-]+/?")
    REPO_SLUG_PATTERN = re.compile(r"\b([\w.-]+/[\w.-]+)\b")
    PROJECT_NAME_PATTERN = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")
    FALSE_POSITIVE_SLUGS = {
        "iOS/Android",
        "HTTP/2",
        "TCP/IP",
        "CI/CD",
        "input/output",
        "read/write",
        "on/off",
    }

    def route(self, profile: NeedProfile) -> RoutingDecision:
        raw_input = profile.raw_input[:200]

        urls = self.URL_PATTERN.findall(raw_input)
        if urls:
            return RoutingDecision(
                route="DIRECT_URL",
                skip_discovery=True,
                max_repos=max(1, min(len(urls), 3)),
                repo_urls=urls[:3],
                project_names=[],
                confidence=1.0,
                reasoning=f"found explicit repo URL(s): {len(urls)}",
            )

        slugs = [
            slug
            for slug in self.REPO_SLUG_PATTERN.findall(raw_input)
            if slug not in self.FALSE_POSITIVE_SLUGS
        ]
        if slugs:
            return RoutingDecision(
                route="NAMED_PROJECT",
                skip_discovery=False,
                max_repos=max(1, min(len(slugs) + 1, 3)),
                repo_urls=[],
                project_names=slugs[:3],
                confidence=0.9,
                reasoning=f"found repo slug(s): {slugs[:3]}",
            )

        if profile.confidence < 0.7:
            return RoutingDecision(
                route="LOW_CONFIDENCE",
                skip_discovery=False,
                max_repos=max(1, min(profile.max_projects, 3)),
                repo_urls=[],
                project_names=[],
                confidence=profile.confidence,
                reasoning=f"low confidence={profile.confidence:.2f}",
            )

        project_names = [
            keyword[:200]
            for keyword in profile.keywords
            if self.PROJECT_NAME_PATTERN.match(keyword[:200]) and len(keyword) >= 3
        ]
        if project_names:
            return RoutingDecision(
                route="NAMED_PROJECT",
                skip_discovery=False,
                max_repos=max(1, min(len(project_names) + 1, 3)),
                repo_urls=[],
                project_names=project_names[:3],
                confidence=max(profile.confidence, 0.8),
                reasoning=f"project-like keyword(s): {project_names[:3]}",
            )

        return RoutingDecision(
            route="DOMAIN_EXPLORE",
            skip_discovery=False,
            max_repos=max(1, min(profile.max_projects, 3)),
            repo_urls=[],
            project_names=[],
            confidence=profile.confidence,
            reasoning="default domain exploration route",
        )
