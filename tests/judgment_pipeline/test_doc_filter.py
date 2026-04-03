"""文档过滤器单元测试。"""

import re

from doramagic_judgment_pipeline.extract.doc_filter import (
    DocFilterTrack,
    filter_doc_records,
)
from doramagic_judgment_pipeline.source_adapters.base import RawExperienceRecord


def _make_doc_record(
    title: str, body: str, source_type: str = "github_readme"
) -> RawExperienceRecord:
    return RawExperienceRecord(
        source_type=source_type,
        source_id=f"test:{title}",
        source_url="https://github.com/test/repo",
        source_platform="github",
        project_or_community="test/repo",
        title=title,
        body=body,
        signals={
            "is_documentation": True,
            "source_type": source_type,
            "body_length": len(body),
            "has_code_blocks": "```" in body,
            "has_warnings": bool(re.search(r"(?i)(warning|limitation)", body)),
            "has_api_boundaries": bool(re.search(r"(?i)(limit|not.?support)", body)),
            "has_domain_rules": bool(re.search(r"(?i)(must|never|always)", body)),
        },
    )


class TestDocFilter:
    def test_blacklist_excludes_contributing(self):
        record = _make_doc_record("Contributing Guide", "How to contribute to this project..." * 10)
        results = filter_doc_records([record])
        assert len(results) == 1
        assert results[0].track == DocFilterTrack.BLACKLIST_EXCLUDED
        assert not results[0].passed

    def test_blacklist_excludes_license(self):
        record = _make_doc_record("License", "MIT License..." * 10)
        results = filter_doc_records([record])
        assert results[0].track == DocFilterTrack.BLACKLIST_EXCLUDED

    def test_whitelist_passes_limitations(self):
        record = _make_doc_record("Known Limitations", "Rate limiting applies..." * 10)
        results = filter_doc_records([record])
        assert results[0].track == DocFilterTrack.WHITELIST_PASSED
        assert results[0].passed

    def test_whitelist_passes_architecture(self):
        record = _make_doc_record("Architecture Overview", "The system design..." * 10)
        results = filter_doc_records([record])
        assert results[0].track == DocFilterTrack.WHITELIST_PASSED

    def test_signal_scoring_high_value(self):
        body = "Warning: You must never use float for financial calculations. " * 5
        record = _make_doc_record("Data Processing", body)
        results = filter_doc_records([record])
        assert results[0].passed

    def test_signal_scoring_low_value(self):
        body = "x" * 60
        record = _make_doc_record("Some Section", body)
        results = filter_doc_records([record])
        assert not results[0].passed

    def test_deps_always_pass(self):
        record = _make_doc_record(
            "Dependencies: pyproject.toml", "pandas>=2.0", source_type="github_deps"
        )
        results = filter_doc_records([record])
        assert results[0].passed
