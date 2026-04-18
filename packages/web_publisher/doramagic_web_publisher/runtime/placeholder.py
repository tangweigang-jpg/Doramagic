"""seed.md Placeholder Parser — SOP §2.4.1 implementation.

Extracts the set of valid {{placeholder}} names from seed.md content,
stripping code blocks, inline code, HTML comments, and YAML frontmatter
before applying the regex.

The result is used by EvaluatorPhase to:
1. Feed the required_inputs set into the prompt as a hard constraint.
2. Validate that required_inputs[].name exactly matches the parsed set.

Algorithm (from SOP §2.4.1):
  1. Strip YAML frontmatter (--- ... ---)
  2. Strip fenced code blocks (``` ... ```)
  3. Strip inline code (` ... `)
  4. Strip HTML comments (<!-- ... -->)
  5. Detect escaped \\{{x\\}} — not counted
  6. Regex: /\\{\\{\\s*([a-z][a-z0-9_]{0,31})\\s*\\}\\}/g
  7. De-duplicate; collect invalid placeholders separately
  8. Return ParsedPlaceholders(valid: set, invalid: set)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Regex for valid placeholder names: lowercase snake_case, 1-32 chars
_VALID_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")

# Regex matching any {{ ... }} pattern (including invalid ones)
_ANY_PLACEHOLDER_RE = re.compile(r"\{\{\s*([^}]*?)\s*\}\}")

# Regex for valid placeholders — the canonical extractor
_VALID_PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-z][a-z0-9_]{0,31})\s*\}\}")

# Regex for YAML frontmatter at start of file
_FRONTMATTER_RE = re.compile(r"^\s*---\s*\n.*?\n---\s*\n", re.DOTALL)

# Regex for fenced code blocks (``` or ~~~)
_FENCED_CODE_RE = re.compile(r"```[^\n]*\n.*?```", re.DOTALL)
_FENCED_CODE_TILDE_RE = re.compile(r"~~~[^\n]*\n.*?~~~", re.DOTALL)

# Regex for inline code (single backtick, non-greedy)
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")

# Regex for HTML comments
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)

# Regex for escaped placeholders: \{{ or \\{{ style (not counted)
# We detect literal backslash before {{ in the stripped text
_ESCAPED_RE = re.compile(r"\\+\{\{")


@dataclass
class ParsedPlaceholders:
    """Result of parsing seed.md for placeholders."""

    valid: set[str] = field(default_factory=set)
    """Set of valid lowercase snake_case placeholder names."""

    invalid: set[str] = field(default_factory=set)
    """Set of invalid placeholder literals (e.g. '{{FOO}}', '{{user-name}}')."""


def parse_seed_placeholders(seed_content: str) -> ParsedPlaceholders:
    """Parse seed.md content to extract {{placeholder}} names.

    Steps (SOP §2.4.1):
      1. Strip YAML frontmatter
      2. Strip fenced code blocks (``` and ~~~)
      3. Strip inline code (single backtick pairs)
      4. Strip HTML comments
      5. Mark and skip escaped placeholders (\\{{ ... }})
      6. Extract valid placeholders with regex
      7. Collect invalid patterns

    Args:
        seed_content: Full text of seed.md.

    Returns:
        ParsedPlaceholders with valid and invalid sets.
    """
    text = seed_content

    # Step 1: Strip YAML frontmatter (only at very start of file)
    text = _FRONTMATTER_RE.sub("", text)

    # Step 2: Strip fenced code blocks (replace with empty lines to preserve line structure)
    text = _FENCED_CODE_RE.sub("", text)
    text = _FENCED_CODE_TILDE_RE.sub("", text)

    # Step 3: Strip inline code
    text = _INLINE_CODE_RE.sub("", text)

    # Step 4: Strip HTML comments
    text = _HTML_COMMENT_RE.sub("", text)

    # Step 5: Remove escaped placeholder markers so they aren't counted.
    # Escaped form: \{{x}} — replace with a sentinel that won't match later.
    text = _ESCAPED_RE.sub("__ESCAPED__", text)

    # Step 6 + 7: Scan for all {{ }} patterns
    valid: set[str] = set()
    invalid: set[str] = set()

    for match in _ANY_PLACEHOLDER_RE.finditer(text):
        inner = match.group(1).strip()
        literal = match.group(0)  # e.g. "{{FOO}}"

        if _VALID_NAME_RE.match(inner):
            valid.add(inner)
        elif inner:  # non-empty but invalid name
            invalid.add(literal)
        else:
            # Empty: {{ }} — treat as invalid
            invalid.add(literal)

    return ParsedPlaceholders(valid=valid, invalid=invalid)
