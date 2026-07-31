"""Small serial shell-command queue used by xcookie.

This intentionally implements only the narrow subset of :mod:`cmd_queue` that
xcookie needs.  Keeping it local avoids pulling NumPy and pandas into xcookie's
runtime dependency graph for two serial administrative command sequences.
"""

from __future__ import annotations

import os
from pathlib import Path, PureWindowsPath
import shutil
import subprocess
import sys
from typing import Any


def _windows_git_bash_candidates(
    git_executable: str | None,
) -> list[str]:
    """Return likely Git Bash executables for a resolved ``git.exe``."""
    if git_executable is None:
        return []

    git_fpath = PureWindowsPath(git_executable)
    parent = git_fpath.parent
    if parent.name.lower() in {'cmd', 'bin'}:
        git_root = parent.parent
    else:
        git_root = parent
    return [
        str(git_root / 'bin' / 'bash.exe'),
        str(git_root / 'usr' / 'bin' / 'bash.exe'),
    ]


def _is_windows_wsl_bash_launcher(executable: str) -> bool:
    """Check for the legacy Windows ``bash.exe`` WSL launcher."""
    normalized = str(PureWindowsPath(executable)).lower()
    return normalized.endswith(r'\windows\system32\bash.exe')


def find_bash_executable() -> str | None:
    """Find a usable Bash executable without mistaking WSL for Git Bash.

    On Windows, ``shutil.which('bash')`` can resolve to the legacy WSL
    launcher even when no WSL distribution is installed.  Prefer the Bash
    bundled with the resolved Git installation, then consider other PATH
    matches only after rejecting that launcher.
    """
    if not sys.platform.startswith('win'):
        return shutil.which('bash')

    candidates = _windows_git_bash_candidates(shutil.which('git'))
    for envvar in ('ProgramFiles', 'ProgramFiles(x86)', 'LocalAppData'):
        root = os.environ.get(envvar)
        if root is None:
            continue
        root_fpath = PureWindowsPath(root)
        if envvar == 'LocalAppData':
            git_root = root_fpath / 'Programs' / 'Git'
        else:
            git_root = root_fpath / 'Git'
        candidates.extend(
            [
                str(git_root / 'bin' / 'bash.exe'),
                str(git_root / 'usr' / 'bin' / 'bash.exe'),
            ]
        )

    path_bash = shutil.which('bash')
    if path_bash is not None and not _is_windows_wsl_bash_launcher(path_bash):
        candidates.append(path_bash)

    seen: set[str] = set()
    for candidate in candidates:
        normalized = os.path.normcase(os.path.normpath(candidate))
        if normalized in seen:
            continue
        seen.add(normalized)
        if os.path.isfile(candidate):
            return candidate
    return None


class SerialCommandQueue:
    """Accumulate commands that must execute in one persistent Bash process."""

    def __init__(self, *, cwd: str | Path | None = None, log: bool = True):
        self.cwd = None if cwd is None else Path(cwd)
        self.log = log
        self.jobs: list[str] = []

    @classmethod
    def create(cls, **kwargs: Any) -> 'SerialCommandQueue':
        """Compatibility constructor for the subset of ``cmd_queue`` we used."""
        backend = kwargs.pop('backend', 'serial')
        if backend != 'serial':
            raise ValueError(
                f'Only the serial backend is supported, got {backend!r}'
            )
        return cls(**kwargs)

    def submit(
        self, command: str, log: bool | None = None
    ) -> 'SerialCommandQueue':
        """Append a command and return ``self`` for fluent call sites."""
        del log
        self.jobs.append(command)
        return self

    def sync(self) -> 'SerialCommandQueue':
        """Commands are already serial, so synchronization is a no-op."""
        return self

    def finalize_text(self, **kwargs: Any) -> str:
        """Render all commands as one Bash script.

        ``with_gaurds`` is accepted for compatibility with cmd_queue's historic
        misspelled keyword.  xcookie deliberately manages tracing itself, so the
        local implementation never inserts xtrace guards.
        """
        kwargs.pop('with_gaurds', None)
        kwargs.pop('with_guards', None)
        if kwargs:
            unknown = ', '.join(sorted(kwargs))
            raise TypeError(f'Unexpected finalize_text arguments: {unknown}')
        commands = ['set -e']
        commands.extend(self.jobs)
        return '\n'.join(commands) + '\n'

    def rprint(self) -> None:
        """Print the script that would be executed."""
        print(self.finalize_text(), end='')

    def run(self, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        """Execute the accumulated commands in one Bash process."""
        check = kwargs.pop('check', True)
        if kwargs:
            unknown = ', '.join(sorted(kwargs))
            raise TypeError(f'Unexpected run arguments: {unknown}')
        bash_executable = find_bash_executable()
        if bash_executable is None:
            raise RuntimeError(
                'A usable Bash executable is required. On Windows, install '
                'Git for Windows so xcookie can use Git Bash.'
            )
        return subprocess.run(
            [bash_executable, '-c', self.finalize_text()],
            cwd=None if self.cwd is None else str(self.cwd),
            check=check,
            text=True,
        )


def make_command_queue(**kwargs: Any) -> SerialCommandQueue:
    """Construct xcookie's deliberately small local serial queue."""
    return SerialCommandQueue.create(**kwargs)
