"""RepoDocAdapter 单元测试。"""

from doramagic_judgment_pipeline.source_adapters.repo_doc import RepoDocAdapter


class TestMarkdownSplitting:
    """测试 markdown 拆分逻辑（纯本地，不依赖 GitHub API）。"""

    def setup_method(self):
        self.adapter = RepoDocAdapter.__new__(RepoDocAdapter)

    def test_split_with_headers(self):
        content = """# Title

Some preamble text that is long enough to be kept as a section for the overview.

## Installation

Run pip install to set up the project. This section has enough content to pass the threshold.

## Architecture

The system uses event-driven design. Data flows through ingestion, normalization, and computation layers.

### Known Limitations

Rate limiting applies after 100 requests per minute. The API does not support real-time streaming.
"""
        sections = self.adapter._split_markdown(content)
        assert len(sections) >= 3
        assert sections[0]["heading"] == "Overview"
        headings = [s["heading"] for s in sections]
        assert "Installation" in headings or "Architecture" in headings

    def test_split_no_headers(self):
        content = "A" * 100
        sections = self.adapter._split_markdown(content)
        assert len(sections) == 1
        assert sections[0]["heading"] == "Overview"

    def test_skip_short_sections(self):
        content = """## Short

Hi.

## Long Enough Section

This section has plenty of content to make it past the minimum threshold of fifty characters.
"""
        sections = self.adapter._split_markdown(content)
        headings = [s["heading"] for s in sections]
        assert "Short" not in headings

    def test_extract_code_blocks(self):
        text = "Some text\n```python\nprint('hello')\n```\nMore text\n```\nraw block\n```"
        blocks = RepoDocAdapter._extract_code_blocks(text)
        assert len(blocks) == 2
        assert "print('hello')" in blocks[0]

    def test_make_record_signals(self):
        record = self.adapter._make_record(
            source_type="github_readme",
            source_id="readme:overview",
            source_url="https://github.com/test/repo#readme",
            project="test/repo",
            title="Overview",
            body="This tool has a limitation: rate limits apply. You must always use caching.",
        )
        assert record.signals["is_documentation"] is True
        assert record.signals["has_api_boundaries"] is True
        assert record.signals["has_domain_rules"] is True
