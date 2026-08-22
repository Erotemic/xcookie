"""Top-level command line interface for xcookie."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import kwconf

from xcookie import __version__
from xcookie.main import TemplateApplier, XCookieConfig


class GenerateConfig(XCookieConfig):
    """Generate or update project boilerplate."""

    __epilog__ = """
    Usage
    -----
    # Create a new python repo
    xcookie generate --repo_name=cookiecutter_purepy --repodir="$HOME"/code/cookiecutter_purepy --tags="github,purepy"

    # Create a new binary repo
    xcookie generate --repo_name=cookiecutter_binpy --repodir="$HOME"/code/cookiecutter_binpy --tags="github,binpy,gdal"
    """

    def __post_init__(self) -> None:
        """Keep parser construction free of repository resolution."""

    @classmethod
    def main(
        cls,
        argv: int | bool | str | Sequence[str] | None = False,
        strict: bool = True,
        autocomplete: bool | str = 'auto',
        **kwargs: Any,
    ) -> TemplateApplier:
        """Run generation with the normal repository-aware config."""
        return XCookieConfig.main(
            argv=argv,
            strict=strict,
            autocomplete=autocomplete,
            **kwargs,
        )


class XCookieCLI(kwconf.ModalCLI):
    """Generate and maintain Python project infrastructure."""

    __prog__ = 'xcookie'
    __version__ = __version__

    generate = GenerateConfig


def main(argv: Sequence[str] | None = None) -> Any:
    """Run the top-level xcookie command line interface."""
    return XCookieCLI.main(argv=argv, strict=True, autocomplete='auto')
