"""CodeSearchAdapter 单元测试。"""

from doramagic_judgment_pipeline.source_adapters.code_search import CodeSearchAdapter


class TestCodeSnippetExtraction:
    """测试代码片段提取逻辑（纯本地，不依赖 GitHub API）。"""

    def test_extract_assert_snippets(self):
        content = """import pandas as pd

def validate_data(df):
    # 确保没有空值
    assert not df.isnull().any().any(), "DataFrame contains null values"

    # 确保价格为正
    assert (df['price'] > 0).all(), "Prices must be positive"

    return df

def process():
    pass
"""
        snippets = CodeSearchAdapter._extract_relevant_snippets(content, "assert", context_lines=3)
        assert len(snippets) >= 1
        assert any("assert" in s for s in snippets)

    def test_extract_raise_snippets(self):
        content = """from decimal import Decimal

def set_price(value):
    if not isinstance(value, Decimal):
        raise TypeError("Price must be Decimal, got {type(value)}")
    if value < 0:
        raise ValueError("Price cannot be negative")
    return value
"""
        snippets = CodeSearchAdapter._extract_relevant_snippets(
            content, "raise ValueError", context_lines=5
        )
        assert len(snippets) >= 1
        assert any("raise ValueError" in s for s in snippets)

    def test_no_match_returns_empty(self):
        content = "def hello():\n    print('world')\n"
        snippets = CodeSearchAdapter._extract_relevant_snippets(content, "assert", context_lines=3)
        assert snippets == []

    def test_overlapping_ranges_merged(self):
        content = "\n".join([f"line {i}" for i in range(50)])
        lines = content.split("\n")
        lines[10] = "assert x > 0"
        lines[12] = "assert y > 0"
        content = "\n".join(lines)

        snippets = CodeSearchAdapter._extract_relevant_snippets(content, "assert", context_lines=5)
        assert len(snippets) == 1

    def test_max_snippets_capped(self):
        lines = [f"assert condition_{i}" for i in range(20)]
        content = "\n\n\n\n\n\n\n\n\n\n\n".join(lines)

        snippets = CodeSearchAdapter._extract_relevant_snippets(content, "assert", context_lines=2)
        assert len(snippets) <= 5

    def test_line_numbers_in_snippets(self):
        content = "line1\nline2\nassert something\nline4\n"
        snippets = CodeSearchAdapter._extract_relevant_snippets(content, "assert", context_lines=1)
        assert len(snippets) == 1
        assert "L3:" in snippets[0]
