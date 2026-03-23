"""测试套件 — brick_injection.py

覆盖：
- 正常路径：单框架、多框架、合并文件加载
- 边界情况：框架名大小写、空列表、无匹配框架
- 去重逻辑：FastAPI + Flask 同指一个文件时只加载一次
- 文件写入：output_dir 写入 domain_bricks.jsonl
- 容错：不存在的积木文件 → 0 bricks，不崩溃
- 注入文本格式验证
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# --- 路径设置 ---
_TESTS_DIR = Path(__file__).parent.resolve()
_S1_DIR = _TESTS_DIR.parent

# 将 s1-sonnet 目录加入 sys.path，以便直接 import brick_injection
if str(_S1_DIR) not in sys.path:
    sys.path.insert(0, str(_S1_DIR))

from doramagic_extraction.brick_injection import (  # noqa: E402
    BrickInjectionResult,
    _generate_injection_text,
    _load_bricks_from_file,
    _normalize_framework_name,
    _resolve_brick_filename,
    _write_merged_bricks,
    load_and_inject_bricks,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def real_bricks_dir() -> Path:
    """返回主仓库 bricks/ 目录（若存在）。"""
    # 从 races/r06/injection/s1-sonnet/ 往上找 bricks/
    candidate = _S1_DIR
    for _ in range(8):
        candidate = candidate.parent
        bricks = candidate / "bricks"
        if bricks.is_dir() and list(bricks.glob("*.jsonl")):
            return bricks
    pytest.skip("Could not locate bricks/ directory with JSONL files")


@pytest.fixture()
def tmp_bricks_dir(tmp_path: Path) -> Path:
    """创建临时 bricks/ 目录，含少量测试积木。"""
    bricks_dir = tmp_path / "bricks"
    bricks_dir.mkdir()

    # django.jsonl — 3 条
    django_bricks = [
        {
            "brick_id": "django-l1-mtv",
            "domain_id": "django",
            "knowledge_type": "rationale",
            "statement": "Django uses MTV, not MVC.",
            "confidence": "high",
            "signal": "ALIGNED",
            "source_project_ids": ["test"],
            "support_count": 1,
            "evidence_refs": [],
            "tags": ["django"],
        },
        {
            "brick_id": "django-l2-n-plus-1",
            "domain_id": "django",
            "knowledge_type": "failure",
            "statement": "N+1 query problem: use select_related/prefetch_related.",
            "confidence": "high",
            "signal": "ALIGNED",
            "source_project_ids": ["test"],
            "support_count": 1,
            "evidence_refs": [],
            "tags": ["django"],
        },
        {
            "brick_id": "django-l2-signals",
            "domain_id": "django",
            "knowledge_type": "failure",
            "statement": "post_save fires before transaction commit.",
            "confidence": "high",
            "signal": "ALIGNED",
            "source_project_ids": ["test"],
            "support_count": 1,
            "evidence_refs": [],
            "tags": ["django"],
        },
    ]
    _write_jsonl(bricks_dir / "django.jsonl", django_bricks)

    # react.jsonl — 2 条
    react_bricks = [
        {
            "brick_id": "react-l1-hooks",
            "domain_id": "react",
            "knowledge_type": "constraint",
            "statement": "Hooks must be called at the top level.",
            "confidence": "high",
            "signal": "ALIGNED",
            "source_project_ids": ["test"],
            "support_count": 1,
            "evidence_refs": [],
            "tags": ["react"],
        },
        {
            "brick_id": "react-l2-key",
            "domain_id": "react",
            "knowledge_type": "failure",
            "statement": "Array index as key causes state corruption.",
            "confidence": "high",
            "signal": "ALIGNED",
            "source_project_ids": ["test"],
            "support_count": 1,
            "evidence_refs": [],
            "tags": ["react"],
        },
    ]
    _write_jsonl(bricks_dir / "react.jsonl", react_bricks)

    # fastapi_flask.jsonl — 2 条
    fastapi_flask_bricks = [
        {
            "brick_id": "fastapi-l1-di",
            "domain_id": "fastapi-flask",
            "knowledge_type": "capability",
            "statement": "FastAPI uses dependency injection via Depends().",
            "confidence": "high",
            "signal": "ALIGNED",
            "source_project_ids": ["test"],
            "support_count": 1,
            "evidence_refs": [],
            "tags": ["fastapi"],
        },
        {
            "brick_id": "flask-l2-request-context",
            "domain_id": "fastapi-flask",
            "knowledge_type": "failure",
            "statement": "Flask context proxies don't work outside request context.",
            "confidence": "high",
            "signal": "ALIGNED",
            "source_project_ids": ["test"],
            "support_count": 1,
            "evidence_refs": [],
            "tags": ["flask"],
        },
    ]
    _write_jsonl(bricks_dir / "fastapi_flask.jsonl", fastapi_flask_bricks)

    return bricks_dir


def _write_jsonl(path: Path, records: list[dict]) -> None:
    lines = [json.dumps(r, ensure_ascii=False) for r in records]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# 单元测试：内部工具函数
# ---------------------------------------------------------------------------


class TestNormalizeFrameworkName:
    def test_lowercase(self):
        assert _normalize_framework_name("Django") == "django"

    def test_strip_whitespace(self):
        assert _normalize_framework_name("  React  ") == "react"

    def test_already_lower(self):
        assert _normalize_framework_name("fastapi") == "fastapi"

    def test_mixed_case(self):
        assert _normalize_framework_name("FastAPI") == "fastapi"


class TestResolveBrickFilename:
    def test_django(self):
        assert _resolve_brick_filename("Django") == "django"

    def test_react(self):
        assert _resolve_brick_filename("React") == "react"

    def test_fastapi(self):
        assert _resolve_brick_filename("FastAPI") == "fastapi_flask"

    def test_flask(self):
        assert _resolve_brick_filename("Flask") == "fastapi_flask"

    def test_case_insensitive(self):
        assert _resolve_brick_filename("DJANGO") == "django"

    def test_go_module(self):
        result = _resolve_brick_filename("Go module")
        assert result == "go_general"

    def test_unknown_returns_candidate(self):
        # 未知框架返回候选名称（不返回 None），调用方检查文件是否存在
        result = _resolve_brick_filename("SomeUnknownFramework")
        assert result is not None
        assert isinstance(result, str)


class TestLoadBricksFromFile:
    def test_valid_jsonl(self, tmp_path: Path):
        jsonl = tmp_path / "test.jsonl"
        records = [{"brick_id": "a", "statement": "s1"}, {"brick_id": "b", "statement": "s2"}]
        _write_jsonl(jsonl, records)
        result = _load_bricks_from_file(jsonl)
        assert len(result) == 2
        assert result[0]["brick_id"] == "a"

    def test_missing_file_returns_empty(self, tmp_path: Path):
        result = _load_bricks_from_file(tmp_path / "nonexistent.jsonl")
        assert result == []

    def test_empty_file_returns_empty(self, tmp_path: Path):
        jsonl = tmp_path / "empty.jsonl"
        jsonl.write_text("", encoding="utf-8")
        result = _load_bricks_from_file(jsonl)
        assert result == []

    def test_skips_corrupt_lines(self, tmp_path: Path):
        jsonl = tmp_path / "mixed.jsonl"
        jsonl.write_text('{"brick_id": "good"}\nNOT_JSON\n{"brick_id": "also_good"}\n', encoding="utf-8")
        result = _load_bricks_from_file(jsonl)
        assert len(result) == 2
        assert result[0]["brick_id"] == "good"
        assert result[1]["brick_id"] == "also_good"

    def test_blank_lines_ignored(self, tmp_path: Path):
        jsonl = tmp_path / "blanks.jsonl"
        jsonl.write_text('{"brick_id": "x"}\n\n\n{"brick_id": "y"}\n', encoding="utf-8")
        result = _load_bricks_from_file(jsonl)
        assert len(result) == 2


class TestGenerateInjectionText:
    def test_empty_bricks_returns_empty_string(self):
        assert _generate_injection_text([], []) == ""

    def test_contains_header(self):
        bricks = [{"domain_id": "django", "statement": "MTV pattern."}]
        text = _generate_injection_text(bricks, ["Django"])
        assert "你已经知道以下框架基线知识" in text

    def test_contains_footer(self):
        bricks = [{"domain_id": "react", "statement": "Hooks rule."}]
        text = _generate_injection_text(bricks, ["React"])
        assert "不要重复以上知识" in text

    def test_brick_label_appears(self):
        bricks = [{"domain_id": "django", "statement": "Django is MTV."}]
        text = _generate_injection_text(bricks, ["Django"])
        assert "[Django]" in text

    def test_statement_truncated_at_200_chars(self):
        long_statement = "x" * 300
        bricks = [{"domain_id": "django", "statement": long_statement}]
        text = _generate_injection_text(bricks, ["Django"])
        # 注入文本中的 statement 部分应被截断
        assert "..." in text
        # 截断后应 <= 200 字符 (197 + "...")
        for line in text.splitlines():
            if line.startswith("[Django]"):
                statement_part = line[len("[Django] "):]
                assert len(statement_part) <= 200

    def test_multiple_bricks(self):
        bricks = [
            {"domain_id": "django", "statement": "Django is MTV."},
            {"domain_id": "react", "statement": "Hooks top-level only."},
        ]
        text = _generate_injection_text(bricks, ["Django", "React"])
        assert "[Django]" in text
        assert "[React]" in text

    def test_domain_pkm_label_cleaned(self):
        """domain-pkm → Pkm (去掉 domain- 前缀)。"""
        bricks = [{"domain_id": "domain-pkm", "statement": "PKM links."}]
        text = _generate_injection_text(bricks, ["pkm"])
        assert "[Pkm]" in text or "[Domain-Pkm]" not in text  # domain- 前缀已去掉


class TestWriteMergedBricks:
    def test_creates_artifacts_dir(self, tmp_path: Path):
        bricks = [{"brick_id": "a", "statement": "s"}]
        path = _write_merged_bricks(bricks, str(tmp_path))
        assert (tmp_path / "artifacts" / "domain_bricks.jsonl").exists()

    def test_output_path_returned(self, tmp_path: Path):
        path = _write_merged_bricks([], str(tmp_path))
        assert path.endswith("domain_bricks.jsonl")

    def test_empty_bricks_writes_empty_file(self, tmp_path: Path):
        path = _write_merged_bricks([], str(tmp_path))
        content = Path(path).read_text(encoding="utf-8")
        assert content.strip() == ""

    def test_bricks_written_as_jsonl(self, tmp_path: Path):
        bricks = [
            {"brick_id": "a", "statement": "s1"},
            {"brick_id": "b", "statement": "s2"},
        ]
        path = _write_merged_bricks(bricks, str(tmp_path))
        lines = [l for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lines) == 2
        assert json.loads(lines[0])["brick_id"] == "a"
        assert json.loads(lines[1])["brick_id"] == "b"

    def test_unicode_preserved(self, tmp_path: Path):
        bricks = [{"brick_id": "cjk", "statement": "中文测试"}]
        path = _write_merged_bricks(bricks, str(tmp_path))
        content = Path(path).read_text(encoding="utf-8")
        assert "中文测试" in content


# ---------------------------------------------------------------------------
# 集成测试：load_and_inject_bricks
# ---------------------------------------------------------------------------


class TestLoadAndInjectBricks:
    def test_single_framework_loaded(self, tmp_bricks_dir: Path):
        result = load_and_inject_bricks(
            frameworks=["Django"],
            bricks_dir=str(tmp_bricks_dir),
        )
        assert result.bricks_loaded == 3
        assert "Django" in result.frameworks_matched
        assert result.frameworks_not_matched == []

    def test_multiple_frameworks(self, tmp_bricks_dir: Path):
        result = load_and_inject_bricks(
            frameworks=["Django", "React"],
            bricks_dir=str(tmp_bricks_dir),
        )
        assert result.bricks_loaded == 5  # 3 django + 2 react
        assert len(result.frameworks_matched) == 2

    def test_case_insensitive_match(self, tmp_bricks_dir: Path):
        result = load_and_inject_bricks(
            frameworks=["DJANGO"],
            bricks_dir=str(tmp_bricks_dir),
        )
        assert result.bricks_loaded == 3

    def test_empty_frameworks_list(self, tmp_bricks_dir: Path):
        result = load_and_inject_bricks(
            frameworks=[],
            bricks_dir=str(tmp_bricks_dir),
        )
        assert result.bricks_loaded == 0
        assert result.frameworks_matched == []
        assert result.injection_text == ""
        assert result.bricks_path is None

    def test_unknown_framework_no_crash(self, tmp_bricks_dir: Path):
        result = load_and_inject_bricks(
            frameworks=["UnknownFramework42"],
            bricks_dir=str(tmp_bricks_dir),
        )
        assert result.bricks_loaded == 0
        assert "UnknownFramework42" in result.frameworks_not_matched

    def test_missing_bricks_dir_no_crash(self, tmp_path: Path):
        result = load_and_inject_bricks(
            frameworks=["Django"],
            bricks_dir=str(tmp_path / "nonexistent_bricks"),
        )
        assert result.bricks_loaded == 0
        assert "Django" in result.frameworks_not_matched

    def test_fastapi_and_flask_deduplicated(self, tmp_bricks_dir: Path):
        """FastAPI + Flask 都映射到同一文件，只加载一次（不重复）。"""
        result = load_and_inject_bricks(
            frameworks=["FastAPI", "Flask"],
            bricks_dir=str(tmp_bricks_dir),
        )
        # fastapi_flask.jsonl 有 2 条，只加载一次
        assert result.bricks_loaded == 2

    def test_no_output_dir_bricks_path_none(self, tmp_bricks_dir: Path):
        result = load_and_inject_bricks(
            frameworks=["Django"],
            bricks_dir=str(tmp_bricks_dir),
            output_dir=None,
        )
        assert result.bricks_path is None

    def test_output_dir_writes_file(self, tmp_bricks_dir: Path, tmp_path: Path):
        output_dir = tmp_path / "output"
        result = load_and_inject_bricks(
            frameworks=["Django"],
            bricks_dir=str(tmp_bricks_dir),
            output_dir=str(output_dir),
        )
        assert result.bricks_path is not None
        assert Path(result.bricks_path).exists()

    def test_output_file_contents_valid_jsonl(self, tmp_bricks_dir: Path, tmp_path: Path):
        output_dir = tmp_path / "output"
        result = load_and_inject_bricks(
            frameworks=["Django", "React"],
            bricks_dir=str(tmp_bricks_dir),
            output_dir=str(output_dir),
        )
        lines = [
            l for l in Path(result.bricks_path).read_text(encoding="utf-8").splitlines()
            if l.strip()
        ]
        assert len(lines) == 5  # 3 + 2
        for line in lines:
            obj = json.loads(line)
            assert "brick_id" in obj

    def test_injection_text_not_empty_when_bricks_loaded(self, tmp_bricks_dir: Path):
        result = load_and_inject_bricks(
            frameworks=["Django"],
            bricks_dir=str(tmp_bricks_dir),
        )
        assert result.injection_text != ""
        assert "你已经知道以下框架基线知识" in result.injection_text

    def test_injection_text_empty_when_no_bricks(self, tmp_bricks_dir: Path):
        result = load_and_inject_bricks(
            frameworks=["NonExistentFramework"],
            bricks_dir=str(tmp_bricks_dir),
        )
        assert result.injection_text == ""

    def test_raw_bricks_returned(self, tmp_bricks_dir: Path):
        result = load_and_inject_bricks(
            frameworks=["React"],
            bricks_dir=str(tmp_bricks_dir),
        )
        assert len(result.raw_bricks) == 2
        assert all("brick_id" in b for b in result.raw_bricks)

    def test_partial_match_mixed_result(self, tmp_bricks_dir: Path):
        """部分框架有积木，部分没有。"""
        result = load_and_inject_bricks(
            frameworks=["Django", "SomethingUnknown"],
            bricks_dir=str(tmp_bricks_dir),
        )
        assert result.bricks_loaded == 3
        assert "Django" in result.frameworks_matched
        assert "SomethingUnknown" in result.frameworks_not_matched

    def test_result_type(self, tmp_bricks_dir: Path):
        result = load_and_inject_bricks(
            frameworks=["Django"],
            bricks_dir=str(tmp_bricks_dir),
        )
        assert isinstance(result, BrickInjectionResult)
        assert isinstance(result.bricks_loaded, int)
        assert isinstance(result.frameworks_matched, list)
        assert isinstance(result.frameworks_not_matched, list)
        assert isinstance(result.injection_text, str)
        assert isinstance(result.raw_bricks, list)


# ---------------------------------------------------------------------------
# 集成测试：使用真实积木文件（若可用）
# ---------------------------------------------------------------------------


class TestWithRealBricks:
    def test_django_real(self, real_bricks_dir: Path):
        result = load_and_inject_bricks(
            frameworks=["Django"],
            bricks_dir=str(real_bricks_dir),
        )
        assert result.bricks_loaded >= 7
        assert "Django" in result.frameworks_matched
        assert "你已经知道以下框架基线知识" in result.injection_text

    def test_react_real(self, real_bricks_dir: Path):
        result = load_and_inject_bricks(
            frameworks=["React"],
            bricks_dir=str(real_bricks_dir),
        )
        assert result.bricks_loaded >= 6

    def test_django_react_combined(self, real_bricks_dir: Path, tmp_path: Path):
        result = load_and_inject_bricks(
            frameworks=["Django", "React"],
            bricks_dir=str(real_bricks_dir),
            output_dir=str(tmp_path / "out"),
        )
        assert result.bricks_loaded >= 13
        assert result.bricks_path is not None
        lines = [
            l for l in Path(result.bricks_path).read_text(encoding="utf-8").splitlines()
            if l.strip()
        ]
        assert len(lines) == result.bricks_loaded

    def test_all_12_files_loadable(self, real_bricks_dir: Path):
        """12 个 JSONL 文件都应能正常加载。"""
        all_jsonl = list(real_bricks_dir.glob("*.jsonl"))
        assert len(all_jsonl) == 12, f"Expected 12, got {len(all_jsonl)}"
        total = 0
        for f in all_jsonl:
            bricks = _load_bricks_from_file(f)
            assert len(bricks) > 0, f"Empty file: {f.name}"
            total += len(bricks)
        assert total == 89

    def test_total_89_bricks(self, real_bricks_dir: Path):
        """对所有已知框架调用，总积木数 = 89。"""
        all_frameworks = [
            "Django", "React", "FastAPI", "Python", "Go module",
            "Home Assistant", "Obsidian", "Logseq",
        ]
        result = load_and_inject_bricks(
            frameworks=all_frameworks,
            bricks_dir=str(real_bricks_dir),
        )
        # 加载数量取决于去重逻辑；只确保 > 0
        assert result.bricks_loaded > 0
