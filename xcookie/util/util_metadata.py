"""
Helpers for normalizing project metadata in generated templates.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def _is_nonstring_iterable(value: Any) -> bool:
    return isinstance(value, Iterable) and not isinstance(value, (str, bytes))


def _split_comma_text(value: str) -> list[str]:
    """Split comma-delimited metadata text while trimming empty parts."""
    return [part.strip() for part in value.split(',') if part.strip()]


def metadata_list(value: Any, *, split_commas: bool = False) -> list[str]:
    """
    Coerce scalar / sequence metadata into a list of strings.

    Args:
        value: Scalar text or an iterable of metadata items.
        split_commas: If True, comma-delimited strings are split into multiple
            items. This is useful for legacy ``tool.xcookie`` author metadata
            that predated explicit PEP 621 author tables.
    """
    if value is None:
        return []
    if isinstance(value, bytes):
        value = value.decode()
    if isinstance(value, str):
        if split_commas:
            return _split_comma_text(value)
        return [value]
    if _is_nonstring_iterable(value):
        items: list[str] = []
        for item in value:
            if item is None:
                continue
            text = str(item).strip()
            if not text:
                continue
            if split_commas:
                items.extend(_split_comma_text(text))
            else:
                items.append(text)
        return items
    text = str(value).strip()
    return [text] if text else []


def metadata_text(value: Any) -> str:
    """Coerce scalar / sequence metadata into display text."""
    return ', '.join(metadata_list(value))


def coerce_author_entries(authors: Any, author_emails: Any) -> list[dict[str, str]]:
    """
    Normalize xcookie author metadata into PEP 621 author entries.

    Historically, xcookie projects commonly used comma-delimited
    ``tool.xcookie.author`` and ``tool.xcookie.author_email`` strings. Treat
    those strings as paired lists when there is more than one email so that
    generated ``[project].authors`` entries remain valid PEP 621 metadata.
    """
    emails = metadata_list(author_emails, split_commas=True)
    split_author_commas = isinstance(authors, str) and len(emails) > 1
    names = metadata_list(authors, split_commas=split_author_commas)

    num_entries = max(len(names), len(emails))
    entries: list[dict[str, str]] = []
    for idx in range(num_entries):
        entry: dict[str, str] = {}
        if idx < len(names) and names[idx]:
            entry['name'] = names[idx]
        if idx < len(emails) and emails[idx]:
            entry['email'] = emails[idx]
        if entry:
            entries.append(entry)
    return entries
