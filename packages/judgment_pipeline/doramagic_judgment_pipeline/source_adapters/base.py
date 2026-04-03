"""所有来源适配器的统一输出格式。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class RawExperienceRecord:
    """所有来源适配器的统一输出格式。"""

    # 来源标识
    source_type: str  # "github_issue" | "reddit_post" | "discord_message" | ...
    source_id: str  # 来源内唯一 ID
    source_url: str  # 原始 URL
    source_platform: str  # "github" | "reddit" | "discord" | ...
    project_or_community: str  # "freqtrade" | "r/algotrading" | ...

    # 内容
    title: str
    body: str
    replies: list[str] = field(default_factory=list)
    code_blocks: list[str] = field(default_factory=list)

    # 质量信号（各来源适配器负责映射为标准信号）
    signals: dict = field(default_factory=dict)

    # 时间
    created_at: str = ""
    resolved_at: str | None = None

    # 分类
    pre_category: str | None = None


class BaseAdapter(ABC):
    """来源适配器基类。"""

    @abstractmethod
    async def fetch(self, target: dict) -> list[RawExperienceRecord]:
        """根据 target 配置拉取数据。"""
        ...
