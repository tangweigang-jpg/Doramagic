"""测试 JSONL 读写和索引。"""

import sys
import tempfile
from pathlib import Path

from doramagic_judgment_schema.serializer import JudgmentStore
from doramagic_judgment_schema.types import (
    Consequence,
    ConsequenceKind,
    JudgmentCore,
    Layer,
    Modality,
    Relation,
    RelationType,
)

sys.path.insert(0, str(Path(__file__).parent))
from helpers import make_valid_judgment


class TestJudgmentStore:
    def test_store_and_retrieve(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JudgmentStore(tmpdir)
            j = make_valid_judgment()
            store.store(j)
            assert store.count() == 1
            assert store.get("finance-K-001") is not None

    def test_list_by_domain(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JudgmentStore(tmpdir)
            store.store(make_valid_judgment(id="finance-K-001"))
            store.store(
                make_valid_judgment(
                    id="finance-K-002",
                    core=JudgmentCore(
                        when="进行回测时的不同条件",
                        modality=Modality.SHOULD,
                        action="使用 Decimal 类型处理所有金额",
                        consequence=Consequence(
                            kind=ConsequenceKind.BUG,
                            description="避免精度累积偏差导致回测结果不可复现",
                        ),
                    ),
                )
            )
            results = store.list_by_domain("finance")
            assert len(results) == 2

    def test_persistence_across_instances(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store1 = JudgmentStore(tmpdir)
            store1.store(make_valid_judgment())
            del store1

            store2 = JudgmentStore(tmpdir)
            assert store2.count() == 1

    def test_graph_expansion(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JudgmentStore(tmpdir)

            j1 = make_valid_judgment(
                id="finance-K-001",
                relations=[
                    Relation(
                        type=RelationType.GENERATES,
                        target_id="finance-R-001",
                        description="精度约束导致必须选择支持 Decimal 的数据管道",
                    )
                ],
            )
            j2 = make_valid_judgment(
                id="finance-R-001",
                layer=Layer.RESOURCE,
                core=JudgmentCore(
                    when="选择数据管道组件时需要评估",
                    modality=Modality.MUST,
                    action="确保管道支持 Decimal 类型传递",
                    consequence=Consequence(
                        kind=ConsequenceKind.DATA_CORRUPTION,
                        description="管道内部精度丢失导致下游计算全部偏差",
                    ),
                ),
            )
            store.store(j1)
            store.store(j2)

            related = store.get_relations("finance-K-001", max_hops=1)
            assert len(related) == 1
            assert related[0].id == "finance-R-001"
