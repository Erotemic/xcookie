"""Small serial shell-command queue used by xcookie.

This intentionally implements only the narrow subset of :mod:`cmd_queue` that
xcookie needs.  Keeping it local avoids pulling NumPy and pandas into xcookie's
runtime dependency graph for two serial administrative command sequences.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


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
        return subprocess.run(
            ['bash', '-c', self.finalize_text()],
            cwd=None if self.cwd is None else str(self.cwd),
            check=check,
            text=True,
        )


def make_command_queue(**kwargs: Any):
    """Use cmd_queue when present, otherwise use the lightweight local queue."""
    try:
        import cmd_queue
    except ModuleNotFoundError as ex:
        if ex.name != 'cmd_queue':
            raise
        return SerialCommandQueue.create(**kwargs)
    else:
        return cmd_queue.Queue.create(**kwargs)
