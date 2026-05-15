from __future__ import annotations

from xcookie.template_registry import TemplateContext


def apply_template_context(text: str, context: TemplateContext) -> str:
    """Apply simple token substitutions without regex replacement semantics."""
    for old, new in context.replacements().items():
        text = text.replace(old, new)
    return text
