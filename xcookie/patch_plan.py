"""Structured patch planning for staged template outputs.

This module contains the side-effect-light data model used to describe what
xcookie intends to do after it has rendered files into the temporary staging
area.  Keeping this model separate from rendering and prompting makes the
planner easier to unit test and gives future callers a stable object to inspect
before applying filesystem changes.
"""

from __future__ import annotations

import fnmatch
import os
import re
import shutil
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CopyTask:
    """Copy one staged file into the repository."""

    src: Path
    dst: Path

    def as_tuple(self) -> tuple[Path, Path]:
        """Return the legacy tuple representation."""
        return (self.src, self.dst)


@dataclass(frozen=True)
class PermTask:
    """Set a file mode on an existing repository path."""

    path: Path
    mode: int

    def as_tuple(self) -> tuple[Path, int]:
        """Return the legacy tuple representation."""
        return (self.path, self.mode)


@dataclass(frozen=True)
class MkdirTask:
    """Create a repository directory."""

    path: Path


@dataclass(frozen=True)
class SearchPattern:
    """Small compatibility wrapper for xcookie path matching options.

    Historically options such as ``regen='pyproject'`` and
    ``only_generate='README'`` were search-style matches against generated
    relative paths.  The third-party pattern helpers xcookie uses do not all
    expose the same ``search`` API, so this wrapper centralizes the compatibility
    behavior and keeps :meth:`TemplateApplier.gather_tasks` focused on staging
    decisions.
    """

    spec: Any

    @classmethod
    def coerce(cls, spec: Any) -> SearchPattern | None:
        """Return a matcher for ``spec`` or ``None`` when no filter is active."""
        if spec is None:
            return None
        return cls(spec)

    def matches(self, text: os.PathLike[str] | str) -> bool:
        """Return True when ``text`` matches this pattern specification."""
        text = os.fspath(text)
        if self._matches_multipattern(text):
            return True
        return any(
            self._matches_string_pattern(pattern, text)
            for pattern in self._string_patterns()
        )

    def _matches_multipattern(self, text: str) -> bool:
        try:
            import kwutil
        except Exception:
            return False
        try:
            matcher = kwutil.MultiPattern.coerce(self.spec)
            return bool(matcher.match(text))
        except (AttributeError, TypeError, ValueError, NotImplementedError):
            return False

    def _string_patterns(self) -> list[str]:
        spec = self.spec
        if isinstance(spec, str):
            return [spec]
        if isinstance(spec, Mapping):
            return []
        try:
            items = list(spec)
        except TypeError:
            return []
        return [item for item in items if isinstance(item, str)]

    @staticmethod
    def _matches_string_pattern(pattern: str, text: str) -> bool:
        if pattern in text:
            return True
        if fnmatch.fnmatch(text, pattern):
            return True
        try:
            return bool(re.search(pattern, text))
        except re.error:
            return False


@dataclass
class PatchPlan:
    """A side-effect-light description of staged changes to apply."""

    copy: list[CopyTask] = field(default_factory=list)
    perms: list[PermTask] = field(default_factory=list)
    mkdir: list[MkdirTask] = field(default_factory=list)
    missing: list[Path] = field(default_factory=list)
    modified: list[Path] = field(default_factory=list)
    dirty: list[Path] = field(default_factory=list)
    clean: list[Path] = field(default_factory=list)
    missing_dir: list[Path] = field(default_factory=list)
    diff_texts: dict[Path, str] = field(default_factory=dict)

    def add_copy(self, src: os.PathLike[str], dst: os.PathLike[str]) -> CopyTask:
        """Register a file-copy task and return it."""
        task = CopyTask(Path(src), Path(dst))
        self.copy.append(task)
        return task

    def add_perm(self, path: os.PathLike[str], mode: int) -> PermTask:
        """Register a permission update task and return it."""
        task = PermTask(Path(path), mode)
        self.perms.append(task)
        return task

    def add_mkdir(self, path: os.PathLike[str]) -> MkdirTask:
        """Register a directory creation task and return it."""
        task = MkdirTask(Path(path))
        self.mkdir.append(task)
        return task

    @property
    def stats(self) -> dict[str, list[Path]]:
        """Return a legacy dict-shaped summary of path classifications."""
        return {
            'missing': self.missing,
            'modified': self.modified,
            'dirty': self.dirty,
            'clean': self.clean,
            'missing_dir': self.missing_dir,
        }

    @property
    def tasks(self) -> dict[str, list[Any]]:
        """Return a legacy dict-shaped summary of planned tasks."""
        return {
            'copy': [task.as_tuple() for task in self.copy],
            'perms': [task.as_tuple() for task in self.perms],
            'mkdir': [task.path for task in self.mkdir],
        }

    @property
    def task_summary(self) -> dict[str, int]:
        """Return counts for each task type."""
        return {
            'copy': len(self.copy),
            'perms': len(self.perms),
            'mkdir': len(self.mkdir),
        }

    def has_tasks(self) -> bool:
        """Return True if applying this plan would modify the repository."""
        return any(self.task_summary.values())

    def apply_all(self) -> None:
        """Apply all planned tasks without prompting."""
        for dpath in sorted(self.parent_directories()):
            Path(dpath).mkdir(parents=True, exist_ok=True)
        for mkdir_task in self.mkdir:
            mkdir_task.path.mkdir(parents=True, exist_ok=True)
        for copy_task in self.copy:
            shutil.copy2(copy_task.src, copy_task.dst)
        for perm_task in self.perms:
            os.chmod(perm_task.path, perm_task.mode)

    def apply_some(self, include: Iterable[os.PathLike[str]]) -> None:
        """Apply copy tasks whose destinations are present in ``include``.

        Permission and directory tasks are intentionally applied wholesale.
        This matches the historical ``some`` behavior where the prompt only
        filtered copy operations.
        """
        include_paths = {Path(path) for path in include}
        copy_tasks = [task for task in self.copy if task.dst in include_paths]
        for dpath in sorted({task.dst.parent for task in copy_tasks}):
            dpath.mkdir(parents=True, exist_ok=True)
        for mkdir_task in self.mkdir:
            mkdir_task.path.mkdir(parents=True, exist_ok=True)
        for copy_task in copy_tasks:
            shutil.copy2(copy_task.src, copy_task.dst)
        for perm_task in self.perms:
            os.chmod(perm_task.path, perm_task.mode)

    def parent_directories(self) -> set[Path]:
        """Return parent directories required by all copy tasks."""
        return {task.dst.parent for task in self.copy}


def render_patch_plan(plan: PatchPlan) -> None:
    """Print the human-readable patch summary for a staging plan."""
    import pprint

    for fpath in plan.missing:
        difftext = plan.diff_texts.get(fpath)
        if difftext:
            print(f'<NEW FPATH={fpath}>')
            print(difftext)
            print(f'<END FPATH={fpath}>')
    for fpath in plan.dirty:
        difftext = plan.diff_texts.get(fpath)
        if difftext:
            print(f'<DIFF FOR repo_fpath={fpath}>')
            print(difftext)
            print(f'<END DIFF repo_fpath={fpath}>')
    print('stats = {}'.format(pprint.pformat(plan.stats)))


def coerce_legacy_patch_plan(
    stats: Mapping[str, Iterable[os.PathLike[str]]],
    tasks: Mapping[str, Iterable[Any]],
) -> PatchPlan:
    """Build a :class:`PatchPlan` from the previous ``(stats, tasks)`` shape.

    This helper is mainly for tests and temporary downstream compatibility
    during the refactor.
    """
    plan = PatchPlan()
    for key in ['missing', 'modified', 'dirty', 'clean', 'missing_dir']:
        getattr(plan, key).extend(Path(path) for path in stats.get(key, []))
    for src, dst in tasks.get('copy', []):
        plan.add_copy(src, dst)
    for path, mode in tasks.get('perms', []):
        plan.add_perm(path, mode)
    for path in tasks.get('mkdir', []):
        plan.add_mkdir(path)
    return plan
