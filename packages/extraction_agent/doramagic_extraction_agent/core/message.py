"""Multi-block message types for agentic conversations.

The Anthropic Messages API requires ``content`` to be ``list[dict]`` when
a message contains tool_use or tool_result blocks.  The shared ``LLMMessage``
type only holds ``content: str`` and must not be modified.  This module
provides ``AgentMessage`` / ``ContentBlock`` / ``ToolResult`` for use inside
the extraction agent's conversation loop.

Typical usage::

    # Start a conversation
    msg = AgentMessage.from_text("user", "Find all A-share listed companies.")

    # After the model replies with tool calls
    assistant_msg = AgentMessage.from_llm_response(response)

    # After executing tools
    result_msg = AgentMessage.tool_results([
        ToolResult(tool_use_id="tu_abc", content='["AAPL", "GOOG"]'),
    ])

    # Feed into next API call
    history = [msg.to_api_dict(), assistant_msg.to_api_dict(), result_msg.to_api_dict()]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from doramagic_shared_utils.llm_adapter import LLMResponse


@dataclass
class ContentBlock:
    """A single block in a multi-block message.

    The Anthropic API supports several block types in a single message:
    - ``text`` — plain assistant text
    - ``tool_use`` — the model requesting a tool call
    - ``tool_result`` — the result returned to the model
    - ``thinking`` — extended-thinking output (returned by some providers
      such as MiniMax); preserved verbatim so the history stays coherent
    """

    type: str  # "text", "tool_use", "tool_result", "thinking"
    text: str | None = None
    tool_use_id: str | None = None
    tool_name: str | None = None
    tool_input: dict | None = None
    content: str | None = None  # for tool_result blocks
    is_error: bool = False
    # Extended-thinking: the Anthropic API returns a ``signature`` alongside
    # the ``thinking`` text and requires it to be echoed back verbatim.
    thinking_signature: str | None = None

    def to_api_dict(self) -> dict[str, Any]:
        """Serialise this block to the Anthropic API wire format."""
        if self.type == "text":
            return {"type": "text", "text": self.text or ""}

        if self.type == "tool_use":
            return {
                "type": "tool_use",
                "id": self.tool_use_id or "",
                "name": self.tool_name or "",
                "input": self.tool_input or {},
            }

        if self.type == "tool_result":
            block: dict[str, Any] = {
                "type": "tool_result",
                "tool_use_id": self.tool_use_id or "",
                "content": self.content or "",
            }
            if self.is_error:
                block["is_error"] = True
            return block

        if self.type == "thinking":
            # The Anthropic API requires thinking blocks to be echoed back with
            # both the ``thinking`` text AND the original ``signature`` field.
            # Omitting the signature causes an API validation error.
            thinking_dict: dict[str, Any] = {"type": "thinking", "thinking": self.text or ""}
            if self.thinking_signature is not None:
                thinking_dict["signature"] = self.thinking_signature
            return thinking_dict

        # Unknown block type — pass through best-effort
        return {"type": self.type, "text": self.text or ""}


@dataclass
class ToolResult:
    """The outcome of executing a single tool call.

    Created by tool handlers and collected into a ``AgentMessage`` via
    ``AgentMessage.tool_results()``.
    """

    tool_use_id: str
    content: str
    is_error: bool = False


@dataclass
class AgentMessage:
    """Multi-block message for agentic conversations.

    Wraps a sequence of ``ContentBlock`` items and serialises them to the
    format expected by the Anthropic Messages API::

        {"role": "assistant", "content": [...blocks...]}
    """

    role: str  # "user" or "assistant"
    blocks: list[ContentBlock] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_api_dict(self) -> dict[str, Any]:
        """Convert to Anthropic Messages API format.

        Returns a dict with ``role`` and ``content`` (list of block dicts).
        """
        return {
            "role": self.role,
            "content": [b.to_api_dict() for b in self.blocks],
        }

    # ------------------------------------------------------------------
    # Constructors
    # ------------------------------------------------------------------

    @classmethod
    def from_text(cls, role: str, text: str) -> "AgentMessage":
        """Build a single-text-block message.

        Convenience constructor for the common case where a message
        contains only a plain text block.
        """
        return cls(role=role, blocks=[ContentBlock(type="text", text=text)])

    @classmethod
    def from_llm_response(cls, response: "LLMResponse") -> "AgentMessage":
        """Build an assistant message from an ``LLMResponse``.

        Handles three kinds of content that ``LLMResponse`` may carry:

        * ``response.content`` — plain text (may be empty when the model
          issued only tool calls)
        * ``response.tool_calls`` — list of ``{"id": ..., "name": ...,
          "arguments": {...}}`` dicts produced by the LLM adapter
        * Thinking blocks are **not** present in ``LLMResponse`` today but
          the adapter may evolve; the structure is ready for them.

        The Anthropic API requires that text blocks appear *before*
        tool_use blocks in assistant messages, which this method enforces.
        """
        blocks: list[ContentBlock] = []

        # Text block first (skip if empty)
        if response.content:
            blocks.append(ContentBlock(type="text", text=response.content))

        # Tool use blocks
        for tc in response.tool_calls:
            blocks.append(
                ContentBlock(
                    type="tool_use",
                    tool_use_id=tc.get("id", ""),
                    tool_name=tc.get("name", ""),
                    tool_input=tc.get("arguments", {}),
                )
            )

        return cls(role="assistant", blocks=blocks)

    @classmethod
    def from_raw_api_response(cls, resp: Any) -> "AgentMessage":
        """Build an assistant message directly from a raw Anthropic API response.

        Preserves ALL content blocks returned by the API — including ``thinking``
        blocks produced by extended-thinking models such as MiniMax — so that
        the full response can be echoed back verbatim in the next conversation
        turn.  This is required for models that enforce thinking-block continuity
        (i.e. the API errors if thinking blocks present in the assistant turn are
        not echoed back in the next call).

        The raw Anthropic response object exposes ``resp.content`` as a list of
        typed block objects.  Each block has a ``.type`` attribute and
        type-specific attributes (``text``, ``id``/``name``/``input`` for
        tool_use, ``thinking`` for thinking blocks).

        Args:
            resp: Raw Anthropic ``Message`` object returned by
                ``client.messages.create()``.

        Returns:
            ``AgentMessage`` with role ``"assistant"`` and one ``ContentBlock``
            per content block in the response, in the original order.
        """
        blocks: list[ContentBlock] = []
        for raw_block in resp.content:
            block_type = getattr(raw_block, "type", None)
            if block_type == "text":
                blocks.append(ContentBlock(type="text", text=raw_block.text))
            elif block_type == "tool_use":
                blocks.append(
                    ContentBlock(
                        type="tool_use",
                        tool_use_id=raw_block.id,
                        tool_name=raw_block.name,
                        tool_input=raw_block.input,
                    )
                )
            elif block_type == "thinking":
                # Echo thinking content and signature back unchanged.
                # The Anthropic API enforces that both fields are present.
                thinking_text = getattr(raw_block, "thinking", "") or ""
                thinking_sig = getattr(raw_block, "signature", None)
                blocks.append(
                    ContentBlock(
                        type="thinking",
                        text=thinking_text,
                        thinking_signature=thinking_sig,
                    )
                )
            else:
                # Unknown block type — best-effort pass-through using text field.
                text_val = getattr(raw_block, "text", None) or ""
                blocks.append(ContentBlock(type=block_type or "unknown", text=text_val))
        return cls(role="assistant", blocks=blocks)

    @classmethod
    def tool_results(cls, results: list[ToolResult]) -> "AgentMessage":
        """Build a user message containing tool_result blocks.

        This is the message sent back to the model after executing the
        tools it requested.  The Anthropic API requires that *all*
        tool_result blocks be in a single user turn.
        """
        blocks = [
            ContentBlock(
                type="tool_result",
                tool_use_id=r.tool_use_id,
                content=r.content,
                is_error=r.is_error,
            )
            for r in results
        ]
        return cls(role="user", blocks=blocks)
