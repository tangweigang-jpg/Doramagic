"""Artifact read/write tools for the extraction agent.

Provides two tools that let the agent persist and retrieve extraction outputs:

- ``write_artifact`` — write content to a named file under the artifacts
                       directory.  The name is validated to prevent path
                       traversal and must end with a recognised extension.
- ``get_artifact``   — read a previously written artifact by name.

Both tools are bound to a specific ``artifacts_dir`` at construction time.
"""

from __future__ import annotations

from pathlib import Path

from doramagic_extraction_agent.core.tool_registry import ToolDef

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VALID_EXTENSIONS = {".md", ".yaml", ".json", ".jsonl", ".txt"}

_ARTIFACT_TYPE_EXTENSIONS: dict[str, str] = {
    "report_md": ".md",
    "blueprint_yaml": ".yaml",
    "constraints_json": ".json",
    "notes": ".txt",
}


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_name(name: str) -> str | None:
    """Check that *name* is a safe, relative filename.

    Returns an error string if validation fails, or ``None`` on success.
    """
    if not name or not name.strip():
        return "ERROR: artifact name must not be empty"

    if ".." in name:
        return f"ERROR: artifact name {name!r} must not contain '..'"

    p = Path(name)
    if p.is_absolute():
        return f"ERROR: artifact name {name!r} must be a relative path, not absolute"

    if p.suffix not in _VALID_EXTENSIONS:
        return (
            f"ERROR: artifact name {name!r} must end with one of "
            f"{sorted(_VALID_EXTENSIONS)}"
        )

    return None


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_artifact_tools(artifacts_dir: Path) -> list[ToolDef]:
    """Create artifact tools bound to *artifacts_dir*.

    Args:
        artifacts_dir: Directory where artifacts are stored.  Will be created
            if it does not yet exist when a tool is first invoked.

    Returns:
        A list of two :class:`ToolDef` instances ready for registration with
        a :class:`~doramagic_extraction_agent.core.tool_registry.ToolRegistry`.
    """

    base_dir = artifacts_dir.resolve()

    # -----------------------------------------------------------------------
    # Tool 1: write_artifact
    # -----------------------------------------------------------------------

    async def _write_artifact(
        name: str,
        content: str,
        artifact_type: str | None = None,
    ) -> str:
        """Write *content* to ``artifacts_dir / name``."""
        err = _validate_name(name)
        if err:
            return err

        # Optionally validate artifact_type if provided
        if artifact_type is not None and artifact_type not in _ARTIFACT_TYPE_EXTENSIONS:
            valid = list(_ARTIFACT_TYPE_EXTENSIONS)
            return (
                f"ERROR: unknown artifact_type {artifact_type!r}. "
                f"Must be one of: {valid}"
            )

        dest = base_dir / name
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
        except OSError as exc:
            return f"ERROR: could not write artifact {name!r}: {exc}"

        byte_count = len(content.encode("utf-8"))
        return f"Written {byte_count:,} bytes to {dest}"

    write_artifact_tool = ToolDef(
        name="write_artifact",
        description=(
            "Write content to a named artifact file under the artifacts directory. "
            "The name must be a relative path (no '..', no absolute paths) and must "
            "end with one of: .md, .yaml, .json, .jsonl, .txt. "
            "Parent directories are created automatically."
        ),
        parameters={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": (
                        "Relative filename for the artifact, e.g. 'report.md' or "
                        "'finance/constraints.json'. Must not contain '..' and must "
                        "end with .md, .yaml, .json, .jsonl, or .txt."
                    ),
                },
                "content": {
                    "type": "string",
                    "description": "Text content to write to the artifact file.",
                },
                "artifact_type": {
                    "type": "string",
                    "enum": list(_ARTIFACT_TYPE_EXTENSIONS),
                    "description": (
                        "Optional semantic type of the artifact. "
                        "One of: 'report_md', 'blueprint_yaml', 'constraints_json', 'notes'."
                    ),
                },
            },
            "required": ["name", "content"],
        },
        handler=_write_artifact,
    )

    # -----------------------------------------------------------------------
    # Tool 2: get_artifact
    # -----------------------------------------------------------------------

    async def _get_artifact(name: str) -> str:
        """Read a previously written artifact."""
        err = _validate_name(name)
        if err:
            return err

        dest = base_dir / name
        if not dest.exists():
            return f"ERROR: artifact not found: {name!r}"
        if not dest.is_file():
            return f"ERROR: {name!r} is not a file"

        try:
            return dest.read_text(encoding="utf-8")
        except OSError as exc:
            return f"ERROR: could not read artifact {name!r}: {exc}"

    get_artifact_tool = ToolDef(
        name="get_artifact",
        description=(
            "Read a previously written artifact by name. "
            "Returns the full text content of the artifact file, "
            "or an error message if it does not exist."
        ),
        parameters={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": (
                        "Relative filename of the artifact to read, "
                        "e.g. 'report.md' or 'finance/constraints.json'."
                    ),
                },
            },
            "required": ["name"],
        },
        handler=_get_artifact,
    )

    return [write_artifact_tool, get_artifact_tool]
