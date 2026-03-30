"""知识积木直缝引擎测试。

覆盖：BrickMatcher 回退匹配、BrickSelector 质量排序、完整直缝流程。
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# sys.path: allow running from any working directory
# ---------------------------------------------------------------------------
_THIS_DIR = Path(__file__).resolve().parent
_PACKAGES_DIR = _THIS_DIR.parent.parent

_BRICK_STITCHER_PATH = _PACKAGES_DIR / "executors" / "doramagic_executors" / "brick_stitcher.py"
_spec = importlib.util.spec_from_file_location("test_brick_stitcher_module", _BRICK_STITCHER_PATH)
assert _spec is not None and _spec.loader is not None
_module = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _module
_spec.loader.exec_module(_module)

BRICK_CATALOG = _module.BRICK_CATALOG
BrickMatch = _module.BrickMatch
_fallback_match = _module._fallback_match
select_bricks = _module.select_bricks

# ---------------------------------------------------------------------------
# BrickMatcher 回退匹配
# ---------------------------------------------------------------------------


class TestFallbackMatch:
    def test_always_includes_skill_architecture(self):
        """任何意图都应该包含 skill_architecture。"""
        matches = _fallback_match("something random", "")
        domain_ids = [m.domain_id for m in matches]
        assert "skill_architecture" in domain_ids

    def test_matches_telegram_keywords(self):
        """包含 messaging 关键词时匹配 messaging_integration。"""
        matches = _fallback_match("build a Telegram bot for alerts", "messaging")
        domain_ids = [m.domain_id for m in matches]
        assert "messaging_integration" in domain_ids

    def test_matches_financial_keywords(self):
        """包含 financial 关键词时匹配 financial_trading。"""
        matches = _fallback_match("monitor crypto prices", "financial trading")
        domain_ids = [m.domain_id for m in matches]
        assert "financial_trading" in domain_ids

    def test_max_5_matches(self):
        """回退匹配最多返回 5 个。"""
        matches = _fallback_match(
            "python django react typescript langchain web security api data email",
            "everything",
        )
        assert len(matches) <= 5


# ---------------------------------------------------------------------------
# BrickSelector 质量排序
# ---------------------------------------------------------------------------


class TestBrickSelector:
    def test_failure_bricks_rank_higher(self, tmp_path: Path):
        """failure 类型的积木应该排名高于 capability。"""
        bricks_file = tmp_path / "test_domain.jsonl"
        bricks = [
            {
                "brick_id": "test-l2-001",
                "domain_id": "test_domain",
                "knowledge_type": "capability",
                "statement": "A basic capability",
                "confidence": "high",
            },
            {
                "brick_id": "test-l2-002",
                "domain_id": "test_domain",
                "knowledge_type": "failure",
                "statement": "A critical failure pattern",
                "confidence": "high",
            },
        ]
        bricks_file.write_text("\n".join(json.dumps(b) for b in bricks), encoding="utf-8")

        matches = [BrickMatch("test_domain", 8, "test")]
        selected = select_bricks(matches, tmp_path, max_bricks=10)

        assert len(selected) == 2
        assert selected[0].brick["knowledge_type"] == "failure"

    def test_l1_bricks_get_bonus(self, tmp_path: Path):
        """L1 积木应该比同类型 L2 积木排名更高。"""
        bricks_file = tmp_path / "test_domain.jsonl"
        bricks = [
            {
                "brick_id": "test-l2-001",
                "domain_id": "test_domain",
                "knowledge_type": "rationale",
                "statement": "L2 rationale",
                "confidence": "high",
            },
            {
                "brick_id": "test-l1-001",
                "domain_id": "test_domain",
                "knowledge_type": "rationale",
                "statement": "L1 rationale",
                "confidence": "high",
            },
        ]
        bricks_file.write_text("\n".join(json.dumps(b) for b in bricks), encoding="utf-8")

        matches = [BrickMatch("test_domain", 8, "test")]
        selected = select_bricks(matches, tmp_path, max_bricks=10)

        assert selected[0].brick["brick_id"] == "test-l1-001"

    def test_higher_relevance_ranks_higher(self, tmp_path: Path):
        """高相关度类别的积木排名高于低相关度类别。"""
        # 高相关度类别
        high_file = tmp_path / "high_rel.jsonl"
        high_file.write_text(
            json.dumps(
                {
                    "brick_id": "high-l2-001",
                    "domain_id": "high_rel",
                    "knowledge_type": "rationale",
                    "statement": "High relevance brick",
                    "confidence": "high",
                }
            ),
            encoding="utf-8",
        )
        # 低相关度类别
        low_file = tmp_path / "low_rel.jsonl"
        low_file.write_text(
            json.dumps(
                {
                    "brick_id": "low-l2-001",
                    "domain_id": "low_rel",
                    "knowledge_type": "rationale",
                    "statement": "Low relevance brick",
                    "confidence": "high",
                }
            ),
            encoding="utf-8",
        )

        matches = [
            BrickMatch("high_rel", 9, "high"),
            BrickMatch("low_rel", 5, "low"),
        ]
        selected = select_bricks(matches, tmp_path, max_bricks=10)
        assert selected[0].domain_id == "high_rel"

    def test_max_bricks_limit(self, tmp_path: Path):
        """不超过 max_bricks 限制。"""
        bricks_file = tmp_path / "big.jsonl"
        lines = []
        for i in range(100):
            lines.append(
                json.dumps(
                    {
                        "brick_id": f"big-l2-{i:03d}",
                        "domain_id": "big",
                        "knowledge_type": "rationale",
                        "statement": f"Brick {i}",
                        "confidence": "high",
                    }
                )
            )
        bricks_file.write_text("\n".join(lines), encoding="utf-8")

        matches = [BrickMatch("big", 8, "big")]
        selected = select_bricks(matches, tmp_path, max_bricks=20)
        assert len(selected) == 20


# ---------------------------------------------------------------------------
# BrickSelector on real bricks
# ---------------------------------------------------------------------------


class TestBrickSelectorReal:
    def test_loads_real_bricks(self):
        """能从真实积木目录加载积木。"""
        bricks_dir = Path(__file__).resolve().parents[3] / "bricks"
        if not bricks_dir.exists():
            return  # 跳过（CI 环境可能没有 bricks）
        matches = [BrickMatch("skill_architecture", 9, "test")]
        selected = select_bricks(matches, bricks_dir, max_bricks=10)
        assert len(selected) > 0
        assert all(s.domain_id == "skill_architecture" for s in selected)


# ---------------------------------------------------------------------------
# BRICK_CATALOG 完整性
# ---------------------------------------------------------------------------


class TestCatalog:
    def test_catalog_covers_all_brick_files(self):
        """BRICK_CATALOG 应覆盖所有积木文件。"""
        bricks_dir = Path(__file__).resolve().parents[3] / "bricks"
        if not bricks_dir.exists():
            return
        for jsonl in bricks_dir.glob("*.jsonl"):
            domain = jsonl.stem
            assert domain in BRICK_CATALOG, f"Missing catalog entry for {domain}"
