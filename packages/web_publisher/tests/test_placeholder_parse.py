"""Tests for seed.md Placeholder parser — SOP §2.4.1.

Covers: stripping, escaping, de-dup, case validation, invalid detection,
empty file, frontmatter, inline code, fenced code, HTML comments.
"""

from __future__ import annotations

from doramagic_web_publisher.runtime.placeholder import ParsedPlaceholders, parse_seed_placeholders

# ---- Helper ----


def _parse(seed: str) -> ParsedPlaceholders:
    return parse_seed_placeholders(seed)


# ---- Test cases ----


class TestBasicExtraction:
    def test_single_valid_placeholder(self):
        result = _parse("Hello {{ticker}}, how are you?")
        assert result.valid == {"ticker"}
        assert result.invalid == set()

    def test_multiple_valid_placeholders(self):
        result = _parse("{{start_date}} to {{end_date}} for {{ticker}}")
        assert result.valid == {"start_date", "end_date", "ticker"}
        assert result.invalid == set()

    def test_empty_content(self):
        result = _parse("")
        assert result.valid == set()
        assert result.invalid == set()

    def test_no_placeholders(self):
        result = _parse("This seed has no placeholders at all.")
        assert result.valid == set()
        assert result.invalid == set()

    def test_whitespace_inside_braces(self):
        """SOP §2.4.1: regex allows whitespace inside {{ }}."""
        result = _parse("{{  ticker  }} and {{ start_date }}")
        assert "ticker" in result.valid
        assert "start_date" in result.valid

    def test_deduplication(self):
        """Same placeholder appearing multiple times → counted once."""
        result = _parse("{{ticker}} ... {{ticker}} ... {{ticker}}")
        assert result.valid == {"ticker"}


class TestStripping:
    def test_fenced_code_block_excluded(self):
        """Placeholders inside ``` ... ``` are NOT extracted (SOP §2.4.1 step 2)."""
        seed = """
Normal text with {{real_input}}.

```python
x = {{not_a_placeholder}}
```

End.
"""
        result = _parse(seed)
        assert "real_input" in result.valid
        assert "not_a_placeholder" not in result.valid
        assert "not_a_placeholder" not in result.invalid

    def test_inline_code_excluded(self):
        """Placeholders inside `...` single backtick are NOT extracted (step 3)."""
        seed = "Use `{{example_var}}` in your code, but {{real_input}} is injected."
        result = _parse(seed)
        assert "real_input" in result.valid
        assert "example_var" not in result.valid

    def test_html_comment_excluded(self):
        """Placeholders inside <!-- ... --> are NOT extracted (step 4)."""
        seed = "<!-- {{comment_var}} is hidden --> But {{visible_var}} is real."
        result = _parse(seed)
        assert "visible_var" in result.valid
        assert "comment_var" not in result.valid
        assert "comment_var" not in result.invalid

    def test_yaml_frontmatter_excluded(self):
        """Placeholders inside YAML frontmatter (--- ... ---) are NOT extracted."""
        seed = """---
input: {{not_counted}}
---

Body text with {{real_input}}.
"""
        result = _parse(seed)
        assert "real_input" in result.valid
        assert "not_counted" not in result.valid
        assert "not_counted" not in result.invalid


class TestInvalidPlaceholders:
    def test_uppercase_is_invalid(self):
        """{{FOO}} has invalid name → goes to invalid set."""
        result = _parse("Use {{FOO}} here.")
        assert "FOO" not in result.valid
        assert "{{FOO}}" in result.invalid or any("FOO" in s for s in result.invalid)

    def test_camelcase_is_invalid(self):
        """{{userName}} uses camelCase → invalid."""
        result = _parse("Set {{userName}} for login.")
        assert "userName" not in result.valid
        # Should appear in invalid
        assert len(result.invalid) >= 1

    def test_hyphen_is_invalid(self):
        """{{user-name}} uses hyphen → invalid (snake_case required)."""
        result = _parse("Value: {{user-name}}")
        assert "user-name" not in result.valid
        assert len(result.invalid) >= 1

    def test_empty_braces_is_invalid(self):
        """{{ }} (empty) → invalid."""
        result = _parse("Value: {{  }}")
        assert len(result.invalid) >= 1

    def test_too_long_name_is_invalid(self):
        """Name longer than 32 chars (a + 32 chars) → invalid."""
        long_name = "a" + "b" * 32  # 33 chars total
        result = _parse(f"Value: {{{{{long_name}}}}}")
        assert long_name not in result.valid


class TestEscaping:
    def test_backslash_escaped_not_counted(self):
        r"""Escaped placeholder \{{x}} should NOT be counted as a placeholder."""
        # Note: in Python string, \{{ is a backslash then {{
        seed = r"Show example \{{ticker}} but inject {{real_var}}."
        result = _parse(seed)
        assert "real_var" in result.valid
        # ticker should NOT be in valid because it was escaped
        assert "ticker" not in result.valid


class TestRealWorldSeed:
    def test_seed_md_with_no_placeholders(self):
        """bp-009 seed.md has no {{}} placeholders — S_seed should be empty."""
        # Simulated real seed.md with Python f-string style only (no {{ }} placeholders)
        seed = """# A股 MACD 日线金叉策略回测

> Crystal IR: finance-bp-009

## Setup

```python
START_DATE = "{start}"
END_DATE = "{end}"
TICKER = "{ticker}"
```

## After Task Completion

Task completed.
Feedback: https://doramagic.ai/r/macd-backtest-a-shares
"""
        result = _parse(seed)
        # Python f-string style {var} is NOT a placeholder (needs double braces)
        assert result.valid == set()
        assert result.invalid == set()
