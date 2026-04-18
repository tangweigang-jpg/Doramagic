"""Prompts package — Markdown prompt templates for each phase.

Templates are loaded as plain text strings.
Each phase's build_prompt() method should:
  1. Load the template from this package (e.g., load_template('content'))
  2. Interpolate ctx values into the template
  3. Return the rendered string as the user message for the LLM
"""

from __future__ import annotations

from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent


def load_template(phase_name: str) -> str:
    """Load a prompt template by phase name.

    Args:
        phase_name: One of 'content', 'constraints', 'faq', 'evaluator'

    Returns:
        Template string (Markdown).

    Raises:
        FileNotFoundError: If template file does not exist.
    """
    path = _PROMPTS_DIR / f"{phase_name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: {path}")
    return path.read_text(encoding="utf-8")
