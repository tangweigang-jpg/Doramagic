"""Context window management — track usage, trigger summarization."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Chars-per-token heuristic for mixed CJK/English content.
# Pure English is ~4 chars/token; CJK is ~1.5 chars/token.
# 3.5 is a practical midpoint that errs on the conservative side.
_CHARS_PER_TOKEN: float = 3.5


def _count_chars(obj: Any) -> int:
    """Recursively count all string characters in a nested structure."""
    if isinstance(obj, str):
        return len(obj)
    if isinstance(obj, dict):
        return sum(_count_chars(v) for v in obj.values()) + sum(_count_chars(k) for k in obj.keys())
    if isinstance(obj, (list, tuple)):
        return sum(_count_chars(item) for item in obj)
    return 0


class ContextManager:
    """Tracks context window usage and triggers summarization when needed.

    Token counting is purely heuristic (char-based) — no tokenizer dependency.
    This keeps the extraction agent lightweight and avoids the overhead of
    loading a full tokenizer just for threshold checks.

    Typical usage in the agent loop::

        ctx_mgr = ContextManager()
        if ctx_mgr.should_summarize(messages):
            messages, summary_text = ctx_mgr.summarize_messages(messages)
            checkpoint.archive_conversation(phase, messages, sequence=seq)
    """

    def __init__(
        self,
        max_context_tokens: int = 150_000,  # conservative: leave 54K headroom for system prompt + tools + response
        summarize_threshold: float = 0.65,  # trigger earlier to avoid overflow
    ) -> None:
        if not (0.0 < summarize_threshold <= 1.0):
            raise ValueError(f"summarize_threshold must be in (0, 1], got {summarize_threshold}")
        self._max = max_context_tokens
        self._threshold = summarize_threshold

    # ------------------------------------------------------------------ #
    # Token estimation                                                     #
    # ------------------------------------------------------------------ #

    def estimate_tokens(self, messages: list[dict]) -> int:
        """Estimate the token count for a message list.

        Heuristic: ~3.5 chars per token for mixed CJK/English.
        All string content in the message dicts is counted recursively,
        including nested tool_use / tool_result content blocks.

        This is intentionally fast — O(n) single pass, no regex.
        """
        total_chars = _count_chars(messages)
        return int(total_chars / _CHARS_PER_TOKEN)

    def should_summarize(self, messages: list[dict]) -> bool:
        """Return True if estimated token count exceeds the summarization threshold."""
        estimated = self.estimate_tokens(messages)
        threshold_tokens = int(self._max * self._threshold)
        if estimated > threshold_tokens:
            logger.debug(
                "Context summarization triggered: %d estimated tokens > %d threshold",
                estimated,
                threshold_tokens,
            )
            return True
        return False

    # ------------------------------------------------------------------ #
    # Summarization (local, no LLM call)                                  #
    # ------------------------------------------------------------------ #

    def summarize_messages(
        self,
        messages: list[dict],
        keep_last_n: int = 4,
    ) -> tuple[list[dict], str]:
        """Produce a summarized message list without calling an LLM.

        Strategy:
        1. Keep the final ``keep_last_n`` messages verbatim so the model
           retains immediate context.
        2. Summarize all earlier messages into a single structured text block
           (file paths read, claims made, artifacts written, progress notes).
        3. Inject the summary as a synthetic ``system``-role message at position 0.

        NOTE: This is a LOCAL, deterministic summary.  For higher-quality
        condensation the agent_loop should call the LLM with the summary text
        as a prompt — that is explicitly out of scope for this method.

        Args:
            messages: The full conversation history to condense.
            keep_last_n: How many tail messages to preserve verbatim.

        Returns:
            A tuple of (new_messages, summary_text).
            - ``new_messages`` is ready to pass back to the LLM.
            - ``summary_text`` is suitable for archival or for feeding into an
              LLM-powered summarization call.
        """
        if len(messages) <= keep_last_n:
            # Nothing to compress
            summary_text = self._extract_summary_from_messages(messages)
            return list(messages), summary_text

        to_summarize = messages[:-keep_last_n]
        tail = messages[-keep_last_n:]

        summary_text = self._extract_summary_from_messages(to_summarize)

        summary_message: dict = {
            "role": "user",
            "content": (
                "[CONTEXT SUMMARY — earlier messages have been condensed]\n\n"
                + summary_text
                + "\n\n[END OF SUMMARY — continuing from most recent messages below]"
            ),
        }

        new_messages = [summary_message] + list(tail)

        logger.info(
            "Context compressed: %d → %d messages (kept last %d verbatim)",
            len(messages),
            len(new_messages),
            keep_last_n,
        )
        return new_messages, summary_text

    # ------------------------------------------------------------------ #
    # Internal extraction                                                  #
    # ------------------------------------------------------------------ #

    def _extract_summary_from_messages(self, messages: list[dict]) -> str:
        """Extract a structured summary from a slice of message history.

        Scans each message for:
        - File paths referenced in tool_use / tool_result blocks
        - Tool calls made (name + truncated input)
        - Artifact writes (detected by tool name or content heuristics)
        - Key text snippets from assistant messages

        Returns a plain-text structured summary.
        """
        file_paths: list[str] = []
        tool_calls: list[str] = []
        artifact_writes: list[str] = []
        assistant_snippets: list[str] = []

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")

            # Content can be a plain string or a list of typed blocks
            blocks: list[Any] = []
            if isinstance(content, str):
                if role == "assistant" and content.strip():
                    snippet = content.strip()[:300]
                    if snippet:
                        assistant_snippets.append(snippet)
            elif isinstance(content, list):
                blocks = content

            for block in blocks:
                if not isinstance(block, dict):
                    continue

                block_type = block.get("type", "")

                # ---- tool_use block (assistant calling a tool) ---- #
                if block_type == "tool_use":
                    tool_name = block.get("name", "unknown_tool")
                    tool_input = block.get("input", {})

                    # Collect file paths from common input keys
                    for key in ("file_path", "path", "filename", "output_path"):
                        val = tool_input.get(key)
                        if isinstance(val, str) and val:
                            file_paths.append(val)

                    # Detect artifact writes
                    if tool_name in ("write_file", "Write", "write") or any(
                        k in tool_input for k in ("file_path", "output_path")
                    ):
                        dest = (
                            tool_input.get("file_path")
                            or tool_input.get("output_path")
                            or tool_input.get("path")
                            or ""
                        )
                        if dest:
                            artifact_writes.append(dest)

                    # Summarise the call itself (truncate large inputs)
                    input_repr = _truncate_repr(tool_input, max_chars=120)
                    tool_calls.append(f"{tool_name}({input_repr})")

                # ---- tool_result block (environment response) ---- #
                elif block_type == "tool_result":
                    result_content = block.get("content", "")
                    # Extract file paths from result text using a simple heuristic
                    result_text = (
                        result_content
                        if isinstance(result_content, str)
                        else _flatten_text(result_content)
                    )
                    for token in result_text.split():
                        if token.startswith("/") and ("." in token or "/" in token):
                            # Looks like an absolute path
                            file_paths.append(token.strip("`,;\"'"))

                # ---- plain text block (assistant) ---- #
                elif block_type == "text":
                    text = block.get("text", "")
                    if role == "assistant" and text.strip():
                        snippet = text.strip()[:300]
                        assistant_snippets.append(snippet)

        # De-duplicate while preserving first-seen order
        file_paths = _dedup(file_paths)
        tool_calls_unique = _dedup(tool_calls)
        artifact_writes = _dedup(artifact_writes)

        lines: list[str] = ["=== CONTEXT SUMMARY ==="]

        if file_paths:
            lines.append("\n## Files Read / Referenced")
            for p in file_paths:
                lines.append(f"  - {p}")

        if artifact_writes:
            lines.append("\n## Artifacts Written")
            for a in artifact_writes:
                lines.append(f"  - {a}")

        if tool_calls_unique:
            lines.append("\n## Tool Calls Made")
            for tc in tool_calls_unique[:40]:  # cap for readability
                lines.append(f"  - {tc}")
            if len(tool_calls_unique) > 40:
                lines.append(f"  ... ({len(tool_calls_unique) - 40} more)")

        if assistant_snippets:
            lines.append("\n## Key Assistant Outputs (truncated)")
            for i, snippet in enumerate(assistant_snippets[:10], 1):
                lines.append(f"\n  [{i}] {snippet}")
            if len(assistant_snippets) > 10:
                lines.append(f"\n  ... ({len(assistant_snippets) - 10} more snippets)")

        lines.append("\n=== END SUMMARY ===")
        return "\n".join(lines)


# ------------------------------------------------------------------ #
# Private helpers                                                     #
# ------------------------------------------------------------------ #


def _dedup(items: list[str]) -> list[str]:
    """Remove duplicates while preserving insertion order."""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _truncate_repr(obj: Any, max_chars: int = 120) -> str:
    """Return a repr of obj, truncated to max_chars."""
    r = repr(obj)
    if len(r) <= max_chars:
        return r
    return r[:max_chars] + "…"


def _flatten_text(content: Any) -> str:
    """Flatten nested content (list of blocks or plain str) to a single string."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(item.get("text", ""))
        return " ".join(parts)
    return str(content)
