"""Shared JSON recovery helpers for MiniMax L3 raw text.

Low-level, pure-text → JSON-structure utilities used by both the derive
and synthesis recovery paths.  No business logic, no schema imports.
"""

from __future__ import annotations

import contextlib
import json
import re


def strip_markdown_fences(text: str) -> str:
    """Remove all ```json / ``` markdown fences from *text*.

    Opening fences (``\\`\\`\\`json`` or ``\\`\\`\\```) together with any
    trailing newline are removed first; closing fences (``\\`\\`\\```) together
    with any leading newline are removed second.
    """
    cleaned = re.sub(r"```(?:json)?\s*\n?", "", text)
    cleaned = re.sub(r"\n?```", "", cleaned)
    return cleaned


def extract_json_object(text: str) -> str | None:
    """Extract the first top-level JSON object from *text* (greedy match).

    Matches from the first ``{`` to the last ``}`` in *text*.  Returns the
    matched substring, or ``None`` if no ``{...}`` span is found.
    """
    m = re.search(r"\{[\s\S]*\}", text)
    return m.group(0) if m else None


def extract_json_array(text: str) -> str | None:
    """Extract the first top-level JSON array from *text* (greedy match).

    Matches from the first ``[`` to the last ``]`` in *text*.  Returns the
    matched substring, or ``None`` if no ``[...]`` span is found.
    """
    m = re.search(r"\[[\s\S]*\]", text)
    return m.group(0) if m else None


def extract_fenced_json_blocks(text: str) -> list[str]:
    """Return all fenced JSON code block bodies from *text* (non-greedy).

    Extracts the inner content of every ``\\`\\`\\`json {...} \\`\\`\\``` or
    ``\\`\\`\\` {...} \\`\\`\\``` block.  Each returned string is the raw block
    body (not yet parsed).
    """
    return re.findall(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)


def try_parse_json_with_fallbacks(text: str) -> object | None:
    """Best-effort JSON recovery from raw LLM output.

    Tries in order:

    1. **Fenced blocks** — if ≥ 2 ``\\`\\`\\`json {...}\\`\\`\\``` blocks are
       found, parse each individually and aggregate into a list.
    2. **Strip fences + greedy object** — strip all fences then match the
       widest ``{...}`` span and attempt ``json.loads``.
    3. **Strip fences + greedy array** — same but for the widest ``[...]``
       span.

    Returns the parsed ``dict`` / ``list`` on first success, or ``None`` if
    every strategy fails.
    """
    # Strategy 1: multiple fenced blocks → aggregate list
    blocks = extract_fenced_json_blocks(text)
    if len(blocks) >= 2:
        aggregated: list[object] = []
        for block in blocks:
            with contextlib.suppress(json.JSONDecodeError, ValueError):
                aggregated.append(json.loads(block))
        if aggregated:
            return aggregated

    # Strategy 2: strip fences + greedy object
    cleaned = strip_markdown_fences(text)
    obj_str = extract_json_object(cleaned)
    if obj_str is not None:
        with contextlib.suppress(json.JSONDecodeError, ValueError):
            return json.loads(obj_str)

    # Strategy 3: strip fences + greedy array
    arr_str = extract_json_array(cleaned)
    if arr_str is not None:
        with contextlib.suppress(json.JSONDecodeError, ValueError):
            return json.loads(arr_str)

    return None
