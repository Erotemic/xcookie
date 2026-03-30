#!/usr/bin/env python3
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "libcst",
# ]
# ///

"""
Add `-> None` to Python functions that:
1) have no return type annotation, and
2) contain no `return` statement.

Uses LibCST so formatting/comments are preserved as much as possible.

Examples:
    python add_none_returns.py path/to/file.py
    python add_none_returns.py src/ tests/
    python add_none_returns.py src/ --check
    python add_none_returns.py src/ --diff

    uv run --script ~/code/xcookie/dev/poc/add_none_returns.py tests --diff
"""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path
from typing import Iterable

import libcst as cst

PYTHON_SUFFIXES = {'.py'}


class ReturnFinder(cst.CSTVisitor):
    """
    Detect whether a function body contains any `return` statement,
    excluding nested functions/classes/lambdas.
    """

    def __init__(self) -> None:
        self.has_return = False
        self._nested_scope_depth = 0

    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:
        # Do not descend into nested functions.
        if self._nested_scope_depth > 0:
            return False
        self._nested_scope_depth += 1
        return True

    def leave_FunctionDef(self, original_node: cst.FunctionDef) -> None:
        self._nested_scope_depth -= 1

    def visit_Lambda(self, node: cst.Lambda) -> bool:
        return False

    def visit_ClassDef(self, node: cst.ClassDef) -> bool:
        return False

    def visit_Return(self, node: cst.Return) -> None:
        if self._nested_scope_depth == 1:
            self.has_return = True


def function_has_return_statement(func: cst.FunctionDef) -> bool:
    finder = ReturnFinder()
    func.visit(finder)
    return finder.has_return


class AddNoneReturnTransformer(cst.CSTTransformer):
    """
    Add `-> None` to eligible functions.
    """

    def leave_FunctionDef(
        self,
        original_node: cst.FunctionDef,
        updated_node: cst.FunctionDef,
    ) -> cst.FunctionDef:
        if original_node.returns is not None:
            return updated_node

        if function_has_return_statement(original_node):
            return updated_node

        return updated_node.with_changes(
            returns=cst.Annotation(annotation=cst.Name('None'))
        )


def transform_code(source: str) -> str:
    module = cst.parse_module(source)
    updated = module.visit(AddNoneReturnTransformer())
    return updated.code


def iter_python_files(paths: Iterable[Path], recursive: bool) -> Iterable[Path]:
    for path in paths:
        if path.is_file():
            if path.suffix in PYTHON_SUFFIXES:
                yield path
            continue

        if path.is_dir():
            walker = path.rglob('*') if recursive else path.glob('*')
            for child in walker:
                if child.is_file() and child.suffix in PYTHON_SUFFIXES:
                    yield child


def unified_diff(old: str, new: str, filename: str) -> str:
    return ''.join(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f'{filename} (original)',
            tofile=f'{filename} (updated)',
        )
    )


def process_file(path: Path, check: bool, show_diff: bool, write: bool) -> bool:
    original = path.read_text(encoding='utf-8')
    updated = transform_code(original)

    changed = updated != original

    if show_diff and changed:
        sys.stdout.write(unified_diff(original, updated, str(path)))

    if write and changed:
        path.write_text(updated, encoding='utf-8')

    if check and changed:
        print(str(path))

    return changed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            'Add `-> None` to functions that have no return annotation '
            'and no return statement.'
        )
    )
    parser.add_argument(
        'paths',
        nargs='+',
        type=Path,
        help='Python files or directories to process.',
    )
    parser.add_argument(
        '--check',
        action='store_true',
        help='Do not modify files; print files that would change and exit nonzero if any would change.',
    )
    parser.add_argument(
        '--diff',
        action='store_true',
        help='Print a unified diff for files that would change.',
    )
    parser.add_argument(
        '--no-recursive',
        action='store_true',
        help='Do not recurse into directories.',
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    recursive = not args.no_recursive
    files = list(iter_python_files(args.paths, recursive=recursive))

    if not files:
        print('No Python files found.', file=sys.stderr)
        return 2

    changed_any = False
    write = not args.check

    for path in files:
        try:
            changed = process_file(
                path=path,
                check=args.check,
                show_diff=args.diff,
                write=write,
            )
            changed_any = changed_any or changed
        except Exception as exc:
            print(f'Error processing {path}: {exc}', file=sys.stderr)
            return 2

    if args.check and changed_any:
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
