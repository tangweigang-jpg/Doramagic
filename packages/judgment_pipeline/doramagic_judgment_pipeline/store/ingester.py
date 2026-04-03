"""入库主逻辑：校验 → 存储。"""

from __future__ import annotations

from doramagic_judgment_schema.serializer import JudgmentStore
from doramagic_judgment_schema.types import Judgment
from doramagic_judgment_schema.validators import validate_judgment


async def ingest_judgments(
    judgments: list[Judgment],
    store: JudgmentStore,
) -> dict:
    """批量入库。返回统计信息。"""
    stats: dict = {"stored": 0, "rejected": 0, "errors": []}

    for j in judgments:
        validation = validate_judgment(j)
        if not validation.valid:
            stats["rejected"] += 1
            stats["errors"].append({"id": j.id, "errors": validation.errors})
            continue

        store.store(j)
        stats["stored"] += 1

    return stats
