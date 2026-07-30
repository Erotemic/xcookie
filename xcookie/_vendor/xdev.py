"""Minimal vendored subset of :mod:`xdev` used by xcookie.

This module vendors ``xdev.misc.difftext`` from xdev 1.5.4, the version that
xcookie previously resolved in ``uv.lock``.  The implementation is kept local
so xcookie does not inherit xdev's broad dependency graph.

The original implementation is Apache-2.0 licensed and came from:
https://github.com/Erotemic/xdev/blob/v1.5.4/xdev/misc.py

Only the behavior xcookie uses is retained.  The original Pygments-backed
highlighting call is replaced by a tiny ANSI diff highlighter so colored
staging output does not require another package.
"""

from __future__ import annotations

import difflib

_ANSI_RESET = '\x1b[0m'
_ANSI_DIFF_COLORS = {
    '+': '\x1b[32m',
    '-': '\x1b[31m',
    '?': '\x1b[36m',
}


def _colorize_diff(text: str) -> str:
    """Color ndiff marker lines while leaving context lines unchanged."""
    colored_lines: list[str] = []
    for line in text.splitlines():
        color = _ANSI_DIFF_COLORS.get(line[:1])
        if color is None:
            colored_lines.append(line)
        else:
            colored_lines.append(f'{color}{line}{_ANSI_RESET}')
    return '\n'.join(colored_lines)


def difftext(
    text1: str,
    text2: str,
    context_lines: int | None = 0,
    ignore_whitespace: bool = False,
    colored: bool = False,
) -> str:
    """Return an optionally colored, context-filtered ``ndiff``.

    This preserves the subset of ``xdev.difftext`` behavior that xcookie used
    before xdev was removed as a runtime dependency.

    Args:
        text1: Original text.
        text2: Updated text.
        context_lines: Number of unchanged lines retained around differences.
            ``None`` retains all context.
        ignore_whitespace: Ignore trailing whitespace differences.
        colored: Add ANSI colors to inserted, deleted, and hint lines.

    Returns:
        The rendered diff text.
    """
    text1_lines = text1.splitlines()
    text2_lines = text2.splitlines()

    if ignore_whitespace:
        text1_lines = [line.rstrip() for line in text1_lines]
        text2_lines = [line.rstrip() for line in text2_lines]
        all_diff_lines = list(
            difflib.ndiff(
                text1_lines,
                text2_lines,
                linejunk=difflib.IS_LINE_JUNK,
                charjunk=difflib.IS_CHARACTER_JUNK,
            )
        )
    else:
        all_diff_lines = list(difflib.ndiff(text1_lines, text2_lines))

    if context_lines is None:
        diff_lines = all_diff_lines
    else:
        context_lines = int(context_lines)
        if context_lines < 0:
            raise ValueError('context_lines must be nonnegative or None')

        marked = [
            bool(line) and line[0] in '+-?' for line in all_diff_lines
        ]
        retained = marked[:]
        for offset in range(1, context_lines + 1):
            retained[:-offset] = map(
                any, zip(retained[:-offset], marked[offset:])
            )
            retained[offset:] = map(
                any, zip(retained[offset:], marked[:-offset])
            )
        diff_lines = [
            line for line, keep in zip(all_diff_lines, retained) if keep
        ]

    text = '\n'.join(diff_lines)
    if colored:
        text = _colorize_diff(text)
    return text
