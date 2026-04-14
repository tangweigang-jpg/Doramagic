"""Tool registration and dispatch for the extraction agent.

Tools are registered once at startup and then looked up by name during the
agent loop.  Each tool has an async handler so IO-bound tools (file reads,
HTTP calls) do not block the event loop.

Typical usage::

    registry = ToolRegistry()

    registry.register(ToolDef(
        name="read_file",
        description="Read the content of a file.",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
        handler=read_file_handler,
    ))

    # Pass tool definitions to the model
    api_tools = registry.get_api_tools()

    # After the model replies with tool_use blocks
    result = await registry.execute("read_file", {"path": "/tmp/foo.txt"})

    # Phase-scoped subset
    phase_registry = registry.filter(["read_file", "search_code"])
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from doramagic_extraction_agent.core.message import ToolResult

logger = logging.getLogger(__name__)


@dataclass
class ToolDef:
    """Definition of a single tool available to the agent.

    Attributes:
        name: Unique tool identifier.  Must match the name the model uses
            in ``tool_use`` blocks.
        description: Human-readable description sent to the model so it
            knows when and how to invoke the tool.
        parameters: JSON Schema for the tool's input arguments.  Passed
            verbatim as ``input_schema`` in the Anthropic API format.
        handler: Async callable that executes the tool.  Receives the
            tool's arguments as keyword arguments and must return a ``str``
            (the result to feed back to the model).
        concurrent_safe: Whether this tool can safely run concurrently
            with other tools.  Used by orchestration layers that wish to
            parallelise independent tool calls.
    """

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema
    handler: Callable[..., Any]  # async (**kwargs) -> str
    concurrent_safe: bool = True


class ToolRegistry:
    """Registry of tools available to the extraction agent.

    Maintains an ordered mapping of tool name → ``ToolDef`` and provides
    helpers for API serialisation and async dispatch.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDef] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, tool: ToolDef) -> None:
        """Register a tool definition.

        If a tool with the same name has already been registered it is
        silently replaced.  Log a warning so accidental double-registration
        is visible during development.
        """
        if tool.name in self._tools:
            logger.warning("ToolRegistry: replacing already-registered tool %r", tool.name)
        self._tools[tool.name] = tool

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def get_names(self) -> list[str]:
        """Return the names of all registered tools in registration order."""
        return list(self._tools)

    def get_api_tools(self) -> list[dict[str, Any]]:
        """Return tool definitions in Anthropic Messages API format.

        Each entry has the shape::

            {
                "name": "...",
                "description": "...",
                "input_schema": { ...JSON Schema... },
            }
        """
        return [
            {
                "name": td.name,
                "description": td.description,
                "input_schema": td.parameters,
            }
            for td in self._tools.values()
        ]

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    async def execute(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        """Execute a registered tool by name with the given arguments.

        Returns a ``ToolResult``.  Any exception raised by the handler is
        caught and surfaced as an error result so the agent loop can feed
        the error message back to the model rather than crashing.

        Args:
            name: Tool name as it appears in the model's ``tool_use`` block.
            arguments: Parsed argument dict from the ``tool_use`` block's
                ``input`` field.

        Returns:
            ``ToolResult`` with ``is_error=False`` on success or
            ``is_error=True`` and a descriptive message on failure.
        """
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(
                tool_use_id="",  # caller must set the real id
                content=f"Unknown tool: {name!r}. Available tools: {self.get_names()}",
                is_error=True,
            )

        try:
            result = await tool.handler(**arguments)
            return ToolResult(
                tool_use_id="",  # caller must set the real id from the tool_use block
                content=str(result),
                is_error=False,
            )
        except Exception as exc:
            logger.exception("Tool %r raised an exception: %s", name, exc)
            return ToolResult(
                tool_use_id="",
                content=str(exc),
                is_error=True,
            )

    # ------------------------------------------------------------------
    # Subset / filtering
    # ------------------------------------------------------------------

    def filter(self, names: list[str]) -> ToolRegistry:
        """Return a new registry containing only the named tools.

        Tools whose names are not present in this registry are silently
        skipped (a warning is logged).  Useful for phase-specific tool
        whitelists where the active tool set changes between phases of the
        agent loop.

        Args:
            names: Tool names to include in the returned registry.

        Returns:
            A fresh ``ToolRegistry`` with only the requested tools,
            preserving the order given in ``names``.
        """
        subset = ToolRegistry()
        for name in names:
            tool = self._tools.get(name)
            if tool is None:
                logger.warning("ToolRegistry.filter: tool %r not found, skipping", name)
                continue
            subset._tools[name] = tool
        return subset

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: object) -> bool:
        return name in self._tools

    def __repr__(self) -> str:
        return f"ToolRegistry(tools={self.get_names()})"
