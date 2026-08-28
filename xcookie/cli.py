"""Top-level command line interface for xcookie."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import kwconf

from xcookie import __version__
from xcookie.docs import DocsRefresher
from xcookie.main import TemplateApplier, XCookieConfig
from xcookie.secrets import SecretRotator
from xcookie.versioning import VersionBumper


def _normalize_cli_argv(
    argv: int | bool | str | Sequence[str] | None,
) -> bool | str | Sequence[str] | None:
    """Normalize the legacy integer argv sentinel for kwconf."""
    if isinstance(argv, int) and not isinstance(argv, bool):
        if argv != 0:
            raise ValueError('integer argv values must be 0')
        normalized: bool | str | Sequence[str] | None = False
    else:
        normalized = argv
    return normalized


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


class RefreshDocsConfig(kwconf.Config):
    """Regenerate Sphinx API documentation for an existing repository."""

    __command__ = 'refresh-docs'
    __default__ = {
        'repodir': kwconf.Value(
            '.', position=1, help='path to the existing repository'
        ),
    }

    @classmethod
    def main(
        cls,
        argv: int | bool | str | Sequence[str] | None = False,
        strict: bool = True,
        autocomplete: bool | str = 'auto',
        **kwargs: Any,
    ) -> DocsRefresher:
        """Load project settings and regenerate its API documentation."""
        command_config = cls.cli(
            argv=_normalize_cli_argv(argv),
            data=kwargs,
            strict=strict,
            autocomplete=autocomplete,
        )
        project_config = XCookieConfig.load_from_cli_and_pyproject(
            argv=False, repodir=command_config['repodir']
        )
        refresher = DocsRefresher(project_config)
        refresher.refresh_docs()
        return refresher


class RotateSecretsConfig(kwconf.Config):
    """Rotate CI secrets for an existing repository."""

    __command__ = 'rotate-secrets'
    __default__ = {
        'repodir': kwconf.Value(
            '.', position=1, help='path to the existing repository'
        ),
        'interactive': kwconf.Value(
            True, isflag=True, help='prompt before executing the rotation plan'
        ),
        'yes': kwconf.Value(
            False, isflag=True, help='accept the rotation confirmation'
        ),
    }

    @classmethod
    def main(
        cls,
        argv: int | bool | str | Sequence[str] | None = False,
        strict: bool = True,
        autocomplete: bool | str = 'auto',
        **kwargs: Any,
    ) -> SecretRotator:
        """Load project settings and rotate its configured CI secrets."""
        command_config = cls.cli(
            argv=_normalize_cli_argv(argv),
            data=kwargs,
            strict=strict,
            autocomplete=autocomplete,
        )
        project_config = XCookieConfig.load_from_cli_and_pyproject(
            argv=False,
            repodir=command_config['repodir'],
            interactive=command_config['interactive'],
            yes=command_config['yes'],
        )
        rotator = SecretRotator(project_config)
        rotator.rotate_secrets()
        return rotator


class BumpConfig(kwconf.Config):
    """Bump the package version and start the next changelog section."""

    __command__ = 'bump'
    __default__ = {
        'target': kwconf.Value(
            'patch',
            position=1,
            help='patch, minor, major, micro, or an explicit target version',
        ),
        'repodir': kwconf.Value(
            '.', position=2, help='path to the existing repository'
        ),
        'branch': kwconf.Value(
            False,
            isflag=True,
            help=(
                'create and switch to dev/<new-version> before applying '
                'the bump'
            ),
        ),
    }

    @classmethod
    def main(
        cls,
        argv: int | bool | str | Sequence[str] | None = False,
        strict: bool = True,
        autocomplete: bool | str = 'auto',
        **kwargs: Any,
    ) -> VersionBumper:
        """Bump the authoritative version source and roll the changelog."""
        command_config = cls.cli(
            argv=_normalize_cli_argv(argv),
            data=kwargs,
            strict=strict,
            autocomplete=autocomplete,
        )
        bumper = VersionBumper(command_config['repodir'])
        bumper.bump(
            command_config['target'],
            branch=command_config['branch'],
        )
        return bumper


class XCookieCLI(kwconf.ModalCLI):
    """Generate and maintain Python project infrastructure."""

    __prog__ = 'xcookie'
    __version__ = __version__

    generate = kwconf.ModalValue(GenerateConfig, alias=['g'])
    bump = kwconf.ModalValue(BumpConfig, alias=['b'])
    refresh_docs = kwconf.ModalValue(RefreshDocsConfig, alias=['docs'])
    rotate_secrets = kwconf.ModalValue(
        RotateSecretsConfig, alias=['secrets']
    )


def main(argv: Sequence[str] | None = None) -> Any:
    """Run the top-level xcookie command line interface."""
    return XCookieCLI.main(argv=argv, strict=True, autocomplete='auto')
