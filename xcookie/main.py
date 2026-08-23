#!/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK
"""
This is a Python script to apply the xcookie template to either create a new repo
or update an existing one with the latest standards.

TODO:
    Port logic from ~/misc/make_new_python_package_repo.sh

CommandLine:
    ~/code/xcookie/xcookie/main.py

    python -m xcookie.main

ExampleUsage:
    # Update my repos
    python -m xcookie.main --repodir=$HOME/code/pyflann_ibeis --tags="erotemic,github,binpy"

    python -m xcookie.main --repodir=$HOME/code/whodat --tags="kitware,gitlab,purepy,cv2,gdal"
    python -m xcookie.main --repodir=$HOME/code/whatdat --tags="kitware,gitlab,purepy,cv2,gdal"
    python -m xcookie.main --repodir=$HOME/code/whendat --tags="kitware,gitlab,purepy,cv2,gdal"
    python -m xcookie.main --repodir=$HOME/code/whydat --tags="kitware,gitlab,purepy,cv2,gdal"
    python -m xcookie.main --repodir=$HOME/code/howdat --tags="kitware,gitlab,purepy,cv2,gdal"

    python -m xcookie.main --repodir=$HOME/code/kwconf --tags="kitware,gitlab,erotemic,github,purepy"

    # Create this repo
    python -m xcookie.main --repo_name=xcookie --repodir=$HOME/code/xcookie --tags="erotemic,github,purepy"

    # Create a new python repo
    python -m xcookie.main --repo_name=cookiecutter_purepy --repodir=$HOME/code/cookiecutter_purepy --tags="github,purepy"

    # Create a new binary repo
    python -m xcookie.main --repo_name=cookiecutter_binpy --repodir=$HOME/code/cookiecutter_binpy --tags="github,binpy,gdal"

    # Create a new binary gitlab kitware repo
    python -m xcookie.main --repo_name=kwimage_ext --repodir=$HOME/code/kwimage_ext --tags="kitware,gitlab,binpy"
    python -m xcookie.main --repo_name=balanced_sampler --repodir=$HOME/code/balanced_sampler --tags="kitware,gitlab,binpy"

    python -m xcookie.main --repo_name=kwcoco_dataloader --repodir=$HOME/code/kwcoco_dataloader --tags="kitware,gitlab,purepy,gdal,cv2"

    # Create a new binary github repo
    python -m xcookie.main --repodir=$HOME/code/networkx_algo_common_subtree --tags="github,erotemic,binpy"

    # Create a new purepy github repo
    python -m xcookie.main --repodir=$HOME/code/googledoc --tags="github,erotemic,purepy"

    python -m xcookie.main --repodir=$HOME/code/networkx_algo_common_subtree_cython --tags="github,erotemic,binpy"

    python -m xcookie.main --repo_name=delayed_image --repodir=$HOME/code/delayed_image --tags="kitware,gitlab,purepy,cv2,gdal"


    HOST=https://gitlab.kitware.com
    export PRIVATE_GITLAB_TOKEN=$(git_token_for "$HOST")
    python -m xcookie.main --repo_name=kwutil --repodir=$HOME/code/kwutil --tags="kitware,gitlab,purepy"

    python -m xcookie.main --repo_name=geowatch --repodir=$HOME/code/geowatch --tags="kitware,gitlab,purepy,cv2,gdal"

    python -m xcookie.main --repo_name=stdx --repodir=$HOME/code/stdx --tags="github,purepy,erotemic"

    python -m xcookie.main --repo_name=ustd --repodir=$HOME/code/ustd --tags="github,purepy,erotemic"

    load_secrets
    export PRIVATE_GITLAB_TOKEN=$(git_token_for "https://gitlab.kitware.com")
    python -m xcookie.main --repo_name=simple_dvc --repodir=$HOME/code/simple_dvc --tags="gitlab,kitware,purepy,erotemic"

    python -m xcookie.main \
        --repo_name=audio_restore --repodir=$HOME/code/audio_restore --tags="github,erotemic,purepy" \
        --use_pyproject_requirements=True --use_setup_py=False
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import warnings
import weakref
from collections.abc import Sequence
from typing import Any, cast

import kwconf
import toml
import ubelt as ub
from packaging.version import parse as Version

from xcookie._vendor.xdev import difftext
from xcookie.patch_plan import PatchPlan, SearchPattern, render_patch_plan
from xcookie.resolved_config import resolve_xcookie_config
from xcookie.staging import apply_template_context
from xcookie.template_registry import (
    TemplateContext,
    TemplateInfo,
)
from xcookie.util.util_metadata import metadata_text
from xcookie.vcs.url import GitURL


class SkipFile(Exception):
    pass


# TODO: split up into a configuration that is saved to pyproject.toml and one
# that is on only used when executing
class XCookieConfig(kwconf.Config):
    """
    The XCookie CLI
    """

    __epilog__ = """
    Usage
    -----
    # Create a new python repo
    xcookie --repo_name=cookiecutter_purepy --repodir="$HOME"/code/cookiecutter_purepy --tags="github,purepy"

    # Create a new binary repo
    xcookie --repo_name=cookiecutter_binpy --repodir="$HOME"/code/cookiecutter_binpy --tags="github,binpy,gdal"
    """
    __default__ = {
        'repodir': kwconf.Value(
            '.', help='path to the new or existing repo', position=1
        ),
        'repo_name': kwconf.Value(None, help='defaults to ``repodir.name``'),
        'mod_name': kwconf.Value(
            None,
            help='The name of the importable Python module. defaults to ``repo_name``',
        ),
        'pkg_name': kwconf.Value(
            None,
            help='The distribution project name of the installable Python package (i.e. what you pass to ``pip install``). defaults to ``mod_name``',
        ),
        'rel_mod_parent_dpath': kwconf.Value(
            '.',
            help=ub.paragraph(
                """
            The location of the module directory relative to the repository
            root.  This defaults to simply placing the module in ".", but
            another common pattern is to specify this as "./src".
            """
            ),
        ),
        'deploy': kwconf.Value(
            True, help='If False, disable all deployment', isflag=True
        ),
        'deploy_pypi': kwconf.Value(
            True, help='If False, disable pypi deployment', isflag=True
        ),
        'deploy_tags': kwconf.Value(
            True, help='If False, disable tags deployment', isflag=True
        ),
        'deploy_artifacts': kwconf.Value(
            True, help='If False, disable github/gitlab deployment', isflag=True
        ),
        'os': kwconf.Value('all', help='all or any of win,osx,linux'),
        'is_new': kwconf.Value(
            'auto',
            help=ub.paragraph(
                """
            If the repo is detected or specified as being new, then steps to
            create a project for the repo on github/gitlab and other
            initialization procedures will be executed. Otherwise we assume
            that we are updating an existing repo.
            """
            ),
        ),
        'init_new_remotes': kwconf.Value(
            True,
            help=ub.paragraph(
                """
            If True, try to initialize a new repo on the remote if the repo is
            new.
            """
            ),
        ),
        'min_python': kwconf.Value(
            '3.7', type=str, help='used to infer supported_python_versions'
        ),
        'max_python': kwconf.Value(
            None, type=str, help='used to infer supported_python_versions'
        ),
        'main_python': kwconf.Value(
            'max',
            help='The main version of Python to use for version agnostic jobs. A value of max uses the maximum version',
        ),
        'typed': kwconf.Value(
            None, help='Should be None, False, True, partial or full'
        ),
        'supported_python_versions': kwconf.Value(
            'auto',
            help=ub.paragraph(
                """
            can specify as a list of explicit major.minor versions. Auto will
            use everything above the min_python version
            """
            ),
        ),
        'ci_cpython_versions': kwconf.Value(
            'auto',
            help=ub.paragraph(
                """
            Specify the major.minor CPython versions to use on the CI.
            Will default to the supported_python_versions. E.g. ["3.7", "3.10"]
            """
            ),
        ),
        'ci_pypy_versions': kwconf.Value(
            'auto',
            help=ub.paragraph(
                """
            Specify the major.minor PyPy versions to use on the CI as a list,
            e.g. ["3.10", "3.11"]. With "auto", purepy repos test on the most
            recent released PyPy whose CPython level is within the supported
            python range (and no PyPy job if none is compatible); binpy repos
            default to no PyPy.
            """
            ),
        ),
        'ci_prerelease_python_policy': kwconf.Value(
            'allow-failure',
            help=ub.paragraph(
                """
            Policy for unreleased CPython versions in test CI.
            "allow-failure" runs prerelease interpreter jobs but makes their
            failures non-blocking. "strict" makes them normal blocking jobs.
            "skip" omits prerelease interpreter-specific jobs.
            """
            ),
        ),
        'ci_blocklist': kwconf.Value(
            [],
            help=ub.paragraph(
                """
            List[Dict] of filters that will remove generated includes. Keys can
            be os or python-version and values are glob strings.
            """
            ),
        ),
        'ci_allow_failure': kwconf.Value(
            [],
            help=ub.paragraph(
                """
            List[Dict] of filters that mark generated GitHub Actions matrix
            jobs as experimental. Keys can be os, python-version, or any other
            generated matrix field, and values are glob strings. Matching jobs
            still run, but compatibility failures are reported as warnings and
            do not fail the job or workflow.
            """
            ),
        ),
        'typecheck_extra_paths': kwconf.Value(
            [],
            help=ub.paragraph(
                """
            Additional repository-relative files or directories to pass to each
            configured type checker after the main importable module. This is
            useful for consumer-facing assert_type contracts that should be
            checked without type-checking the entire test suite.
            """
            ),
        ),
        'ci_versions_minimal_strict': kwconf.Value('min', help='todo: sus out'),
        'ci_versions_full_strict': kwconf.Value('main'),
        'ci_versions_minimal_loose': kwconf.Value('main'),
        'ci_versions_full_loose': kwconf.Value('*'),
        'remote_host': kwconf.Value(
            None, help='if unspecified, attempt to infer from tags'
        ),
        'remote_group': kwconf.Value(
            None, help='if unspecified, attempt to infer from tags'
        ),
        'autostage': kwconf.Value(
            False, help='if true, automatically add changes to version control'
        ),
        'visibility': kwconf.Value(
            'public', help='or private. Does limit what we can do'
        ),
        'test_env': kwconf.Value(
            None,
            help='A YAML coercible dictionary of environment variables to use in test stages. (TOTO',
        ),
        'version': kwconf.Value(
            None, help='repo metadata: url for the project'
        ),
        'url': kwconf.Value(
            None, type=str, help='repo metadata: url for the project'
        ),
        # Note: these may be a string or a list of strings. kwconf only
        # applies the parser to CLI/env strings, so list-valued TOML
        # metadata passes through unmangled (scriptconfig's type=str cast
        # used to stringify lists into their repr).
        'author': kwconf.Value(
            None,
            type=str,
            help='repo metadata: author for the project. '
            'A string or a list of strings.',
        ),
        'author_email': kwconf.Value(
            None,
            type=str,
            help='repo metadata. A string or a list of strings.',
        ),
        'description': kwconf.Value(None, type=str, help='repo metadata'),
        'license': kwconf.Value(None, help='repo metadata'),
        'dev_status': kwconf.Value('planning'),
        'enable_gpg': kwconf.Value(True),
        'ci_gpg_secret_transport': kwconf.Value(
            'direct_ci',
            help=ub.paragraph(
                """
                Controls how GPG signing key material is transported to CI.
                "direct_ci" (default): key material is uploaded directly to
                the CI provider as environment-scoped secrets. No encrypted
                files are committed to the repo. CI imports the key material
                from provider secrets and verifies the identity against
                dev/public_gpg_key.
                "encrypted_repo" (legacy): key material is encrypted with
                CI_SECRET and committed to the repository as .enc files; CI
                decrypts at runtime using the CI_SECRET variable.
                """
            ),
        ),
        'defaultbranch': kwconf.Value('main'),
        'xdoctest_style': kwconf.Value('google', help='type of xdoctest style'),
        'test_command': kwconf.Value(
            'auto', help='The pytest command to run in the CL'
        ),
        'ci_pypi_live_password_varname': kwconf.Value(
            'TWINE_PASSWORD',
            help='variable of the live twine password in your secrets',
        ),
        'ci_pypi_test_password_varname': kwconf.Value(
            'TEST_TWINE_PASSWORD',
            help='variable of the test twine password in your secrets',
        ),
        'ci_pypi_trusted_publishing': kwconf.Value(
            True,
            help='if True, github deploy jobs use PyPI trusted publishing instead of twine password secrets',
        ),
        'regen': kwconf.Value(
            None,
            help=ub.paragraph(
                """
            if specified, any modified template file that matches this pattern
            will be considered for re-write. This does not limit generation to
            matching files; combine with --only-generate to scope the run.
            """
            ),
        ),
        'only_generate': kwconf.Value(
            None,
            alias=['only_gen'],
            help=ub.paragraph(
                """
            if specified, only generate files matching this multipattern.
            """
            ),
        ),
        'tags': kwconf.Value(
            'auto',
            nargs='*',
            help=ub.paragraph(
                """
            Tags modify what parts of the template are used.
            Valid tags are:
                "binpy" - do we build binpy wheels?
                "erotemic" - this is an erotemic repo
                "kitware" - this is an kitware repo
                "pyutils" - this is an pyutils repo
                "purepy" - this is a pure python repo
                "gdal" - add in our gdal hack # TODO
                "postgresql" - add in postgresql dependencies
                "cv2" - enable the headless hack
                "vcpkg" - enable Windows vcpkg bootstrap/caching
                "opencv_link" - enable build-time OpenCV link on Windows
                "win_smoke" / "windows_smoke" - enable Windows smoke test
                "ci_debug_windows_env" - debug print Windows cibuildwheel env
                "notypes" - disable type checking in lint checks
            """
            ),
        ),
        'linter': kwconf.Value(
            True, help=ub.paragraph('if true enables lint checks in CI')
        ),
        'skip_autogen': kwconf.Value(
            None,
            help=ub.paragraph(
                'list of targets to not auto-generate by default'
            ),
        ),
        'render_doc_images': kwconf.Value(
            False,
            help=ub.paragraph(
                """
            if true, adds kwplot as a dependency to build docs and enable rendering images from doctests.
            """
            ),
        ),
        # TODO: Better mechanism for controlling which of the loose / strict /
        # minimal / full variants will be run.
        'test_variants': kwconf.Value(
            ['full-loose', 'full-strict', 'minimal-loose', 'minimal-strict'],
            help='A list of which CI loose / strict / minimal / full variants to use',
        ),
        'ci_versionless_wheels': kwconf.Value(
            False,
            isflag=True,
            help=ub.paragraph(
                """
                If True, the project's binary wheels are python-version
                independent (e.g. py3-none tags from pure ctypes bindings),
                so CI builds a single wheel per platform instead of one per
                CPython version. The interpreter that performs the build is
                pinned in the [tool.cibuildwheel] section of pyproject.toml.
                The default (False) keeps per-python-version builds, which
                repos that link against the CPython C API require.
                """
            ),
        ),
        'ci_extras': kwconf.Value(
            None,
            help=ub.paragraph(
                """
            A YAML dictionary specifying extra CI test dependencies.
            Supports keys: 'loose', 'strict', 'minimal-loose', 'full-loose',
            'minimal-strict', 'full-strict'. Values are lists of extra package names
            to add to the corresponding test variant.
            Example: "loose: [tests-binary]" or "full-loose: [tests-binary]"
            """
            ),
        ),
        'use_vcs': kwconf.Value(
            'auto',
            help=ub.paragraph(
                """
            Set to False to disable VCS. Will default to True if config has enough information to infer a VCS
            """
            ),
        ),
        'use_uv': kwconf.Value(
            'auto',
            help=ub.paragraph(
                'if False use plain pip, otherwise use uv instead'
            ),
        ),
        'use_pyproject_requirements': kwconf.Value(
            False,
            help=ub.paragraph(
                """
            If False, keep requirements/*.txt as the dependency source of
            truth. In PEP 621 mode xcookie references those files via
            setuptools dynamic dependency metadata. If True, write dependency
            declarations directly into pyproject.toml instead.
            """
            ),
        ),
        'requirements_package': kwconf.Value(
            'auto',
            help=ub.paragraph(
                """
            Import package that owns the requirements resource tree. With
            "auto", xcookie recognizes a repository-level requirements
            symlink that points into an importable package (for example,
            requirements -> kwcoco/rc/requirements). When enabled, both the
            regular requirement files and requirements/locks/*.txt are shipped
            as package data. Set to False to disable packaged requirements.
            """
            ),
        ),
        'use_setup_py': kwconf.Value(
            'auto',
            help=ub.paragraph(
                """
            If False, do not generate setup.py and instead emit a fully-specified
            PEP621-compatible pyproject.toml. When True, the legacy setup.py
            will be generated alongside a minimal pyproject.toml. The default
            "auto" preserves setup.py metadata in existing legacy repositories
            but uses PEP621 for new repositories and repositories that already
            define a [project] table.
            """
            ),
        ),
        # ---
        'interactive': kwconf.Value(True),
        'yes': kwconf.Value(False, help=ub.paragraph('Say yes to everything')),
    }

    @property
    def _description(self):
        """Argparse description, separate from project metadata."""
        description = getattr(self, '__description__', None)
        if description is None:
            description = self.__class__.__doc__
        if description is not None:
            description = ub.codeblock(description)
        return description

    def __post_init__(self):
        object.__setattr__(self, 'resolved', resolve_xcookie_config(self))

    def _load_pyproject_config(self):
        pyproject_fpath = self['repodir'] / 'pyproject.toml'
        if pyproject_fpath.exists():
            try:
                disk_config = toml.loads(pyproject_fpath.read_text())
            except Exception:
                raise
            return disk_config
        return {}

    def _load_xcookie_pyproject_settings(self):
        disk_config = self._load_pyproject_config()
        # print(f'disk_config = {ub.urepr(disk_config, nl=1)}')
        if disk_config is not None:
            settings = disk_config.get('tool', {}).get('xcookie', {})

            config = self._infer_xcookie_settings_from_pyproject(disk_config)

            config = ub.udict(config)
            settings = ub.udict(settings)

            # Only add things not explicitly set
            settings.update(config - settings)

            # If an xcookie section isn't available, we can infer a lot of what
            # we need from other more standard pyproject settings.
            return settings

    def _infer_project_authors(self, disk_config):
        project_block = disk_config.get('project', {})
        authors = project_block.get('authors', [])
        if not isinstance(authors, (list, tuple)):
            return {}

        author_names = []
        author_emails = []
        for entry in authors:
            if not isinstance(entry, dict):
                continue
            name = entry.get('name')
            email = entry.get('email')
            if name:
                author_names.append(name)
            if email:
                author_emails.append(email)

        config = {}
        if author_names:
            config['author'] = (
                author_names[0] if len(author_names) == 1 else author_names
            )
        if author_emails:
            config['author_email'] = (
                author_emails[0] if len(author_emails) == 1 else author_emails
            )
        return config

    def _infer_xcookie_settings_from_pyproject(self, disk_config):
        """
        Helper to populate the xcookie main settings from more standard
        pyproject schemas.
        """
        config = {}
        project_block = disk_config.get('project', {})
        config['pkg_name'] = project_block.get('name')
        config['description'] = project_block.get('description')
        config.update(self._infer_project_authors(disk_config))
        from xcookie.versioning import find_version_source

        version_source = find_version_source(
            self.repodir, data=disk_config, required=False
        )
        if version_source is not None:
            config['version'] = version_source.version

        setuptools_config = disk_config.get('tool', {}).get('setuptools', {})
        setuptools_packages = setuptools_config.get('packages', [])
        if (
            isinstance(setuptools_packages, list)
            and len(setuptools_packages) == 1
        ):
            config['mod_name'] = setuptools_packages[0]
            config['rel_mod_parent_dpath'] = '.'

        if isinstance(setuptools_packages, dict):
            setuptools_find_config = setuptools_packages.get('find', {})
            setuptools_include = setuptools_find_config.get('include')
            if len(setuptools_include) == 1:
                import glob

                results = list(glob.glob(setuptools_include[0]))
                results = [
                    r for r in results if '.egg-info' not in r and '-' not in r
                ]
                if len(results) == 1:
                    config['mod_name'] = results[0]
                    config['rel_mod_parent_dpath'] = '.'

        repo_url = project_block.get('urls', {}).get('Repository')
        if repo_url is not None:
            if 'github' in repo_url:
                config['url'] = repo_url
                config['tags'] = ['github', 'purepy']

        req_py_block = project_block.get('requires-python')
        if req_py_block:
            from xcookie.version_helpers import parse_minimum_python_version

            config['min_python'] = parse_minimum_python_version(req_py_block)

        return config

    def confirm(self, msg: str, default: bool = True) -> bool:
        """
        Args:
            msg (str): display to the user
            default (bool): default value if non-interactive

        Returns:
            bool:
        """
        if self.get('yes', False):
            flag = default
        elif self['interactive']:
            from rich import prompt

            flag = prompt.Confirm.ask(msg)
        else:
            flag = default
        return flag

    def prompt(
        self,
        msg: str,
        choices: list[str],
        default: str | bool = True,
    ) -> str | bool:
        """
        Args:
            msg (str): display to the user
            default (bool): default value if non-interactive

        Returns:
            bool:
        """
        if self.get('yes', False):
            answer = default
        elif self['interactive']:
            from xcookie.rich_ext import FuzzyPrompt

            answer = FuzzyPrompt.ask(msg, choices=choices)
        else:
            answer = default
        return answer

    @classmethod
    def load_from_cli_and_pyproject(
        cls,
        argv: int | bool | str | Sequence[str] | None = False,
        strict: bool = True,
        autocomplete: bool | str = 'auto',
        **kwargs: Any,
    ) -> XCookieConfig:
        # We load the config multiple times to get the right defaults.
        # ideally we should fix this up
        if isinstance(argv, int) and not isinstance(argv, bool):
            if argv != 0:
                raise ValueError('integer argv values must be 0')
            cli_argv: bool | str | Sequence[str] | None = False
        else:
            cli_argv = argv
        config = cast(
            XCookieConfig,
            cls.cli(
                argv=cli_argv,
                data=kwargs,
                strict=strict,
                autocomplete=autocomplete,
            ),
        )
        # config.__post_init__()
        settings = config._load_xcookie_pyproject_settings()
        if settings:
            print(f'settings={settings}')
            config = cast(
                XCookieConfig,
                cls.cli(
                    argv=cli_argv,
                    data=kwargs,
                    default=ub.dict_isect(settings, config),
                    strict=strict,
                    autocomplete=autocomplete,
                ),
            )
        return config

    @classmethod
    def main(
        cls,
        argv: int | bool | str | Sequence[str] | None = False,
        strict: bool = True,
        autocomplete: bool | str = 'auto',
        **kwargs: Any,
    ) -> TemplateApplier:
        """
        Main entry point

        Ignore:
            repodir = ub.Path('~/code/pyflann_ibeis').expand()
            kwargs = {
                'repodir': repodir,
                'tags': ['binpy', 'erotemic', 'github'],
            }
            argv = 0

        Example:
            repodir = ub.Path.appdir('pypkg/demo/my_new_repo')
            import sys, ubelt
            sys.path.append(ubelt.expandpath('~/code/xcookie'))
            from xcookie.main import *  # NOQA
            kwargs = {
                'repodir': repodir,
            }
            argv = 0
        """
        # We load the config multiple times to get the right defaults.
        config = XCookieConfig.load_from_cli_and_pyproject(
            argv=argv,
            strict=strict,
            autocomplete=autocomplete,
            **kwargs,
        )
        # # config.__post_init__()
        # settings = config._load_xcookie_pyproject_settings()
        # if settings:
        #     print(f'settings={settings}')
        #     config = XCookieConfig.cli(argv=argv, data=kwargs, default=ub.dict_isect(settings, config))
        # config.__post_init__()

        # import xdev
        # xdev.embed()

        import rich

        rich.print('config = {}'.format(ub.urepr(config, nl=1)))
        # repodir = ub.Path(config['repodir']).absolute()
        # repodir.ensuredir()

        self = TemplateApplier(config)
        self.setup()
        self.apply()
        return self


class TemplateApplier:
    """
    The primary xcookie autogeneration class.

    Note:
        this does not write any files unless you call setup (which just writes
        to a temporary directory) or apply (which can destructively clobber
        things).
    """

    def __init__(self, config: XCookieConfig | dict[str, Any]) -> None:
        if isinstance(config, dict):
            config = XCookieConfig(**config)

        self.config = config
        self.resolved = resolve_xcookie_config(self.config)
        self.repodir = self.resolved.repodir
        self.repo_name = self.resolved.repo_name
        self._tmpdir = tempfile.TemporaryDirectory(prefix=self.repo_name)
        # TemporaryDirectory emits a ResourceWarning when its own finalizer has
        # to clean up implicitly. Tie cleanup to the TemplateApplier lifetime
        # so temporary staging directories are removed without warning even
        # when callers do not use the explicit close/context-manager API.
        self._tmpdir_cleanup = weakref.finalize(self, self._tmpdir.cleanup)

        self.template_infos: list[TemplateInfo] = []
        try:
            xcookie_dpath = ub.Path(__file__).parent.parent
        except NameError:
            xcookie_dpath = ub.Path('~/misc/templates/xcookie').expand()
        self.template_dpath = xcookie_dpath
        self.staging_dpath = ub.Path(self._tmpdir.name)
        self.remote_info = {'type': 'unknown'}
        self._setup_pip_commands()  # Is this sufficient here?

    def close(self) -> None:
        """Remove the temporary staging directory owned by this applier."""
        self._tmpdir_cleanup()

    def __enter__(self) -> TemplateApplier:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def apply(self):
        """
        Does the actual modification of the target repo.

        Has special logic to handle building new respos versus updating repos.
        """
        if self.config['use_vcs']:
            self.vcs_checks()
        self.copy_staged_files()
        if self.config['use_vcs']:
            if self.config['autostage']:
                self.autostage()

    def autostage(self):
        import git

        repo = git.Repo(self.repodir)

        # Find untracked files
        untracked = []
        for info in self.staging_infos:
            fpath = info['repo_fpath']
            if not repo.git.ls_files(fpath):
                untracked.append(fpath)

        repo.git.add(untracked)

    @property
    def rel_mod_dpath(self) -> ub.Path:
        return self.resolved.rel_mod_dpath

    @property
    def mod_dpath(self) -> ub.Path:
        return self.resolved.mod_dpath

    @property
    def mod_name(self) -> str:
        return self.resolved.mod_name

    @property
    def pkg_name(self) -> str:
        return self.resolved.pkg_name

    @property
    def pkg_fname_prefix(self) -> str:
        # the files have underscores replaced in the prefix
        return self.config['pkg_name'].replace('-', '_')

    def _readme_fpath(self) -> ub.Path:
        """
        Prefer an existing README.md over README.rst, otherwise default to
        README.rst for newly generated repos.
        """
        for rel in ['README.md', 'README.rst']:
            fpath = self.repodir / rel
            if fpath.exists():
                return fpath
        return self.repodir / 'README.rst'

    def _readme_content_type(self) -> str:
        readme_fpath = self._readme_fpath()
        if readme_fpath.suffix.lower() == '.md':
            return 'text/markdown'
        return 'text/x-rst'

    def _build_template_registry(self):
        """Build the active template inventory."""
        from xcookie.template_registry import build_template_registry

        self.template_infos = build_template_registry(self)
        return self.template_infos

    @property
    def tags(self):
        return set(self.config['tags'])

    def _project_classifiers(self):
        version_classifiers = [
            f'Programming Language :: Python :: {ver}'
            for ver in self.config['supported_python_versions']
        ]

        dev_status = self.config['dev_status'].lower()
        if dev_status == 'planning':
            dev_status = 'Development Status :: 1 - Planning'
        elif dev_status == 'pre-alpha':
            dev_status = 'Development Status :: 2 - Pre-Alpha'
        elif dev_status == 'alpha':
            dev_status = 'Development Status :: 3 - Alpha'
        elif dev_status == 'beta':
            dev_status = 'Development Status :: 4 - Beta'
        elif dev_status in {'stable', 'production'}:
            dev_status = 'Development Status :: 5 - Production/Stable'
        elif dev_status == 'mature':
            dev_status = 'Development Status :: 6 - Mature'
        elif dev_status == 'inactive':
            dev_status = 'Development Status :: 7 - Inactive'

        other_classifiers = [
            # https://pypi.python.org/pypi?%3Aaction=list_classifiers
            'Intended Audience :: Developers',
            'Topic :: Software Development :: Libraries :: Python Modules',
            'Topic :: Utilities',
            # This should be interpreted as Apache License v2.0
            # 'License :: OSI Approved :: Apache Software License',
        ]

        disk_config = self.config._load_pyproject_config()
        if disk_config is None:
            disk_config = {}
        other_classifiers += disk_config.get('project', {}).get(
            'classifiers', []
        )

        pyproject_settings = self.config._load_xcookie_pyproject_settings()
        if (
            pyproject_settings is not None
            and 'classifiers' in pyproject_settings
        ):
            other_classifiers += pyproject_settings['classifiers']

        classifiers = [dev_status] + other_classifiers + version_classifiers
        classifiers = list(ub.oset(classifiers))
        return classifiers

    def _presetup(self):
        """Resolve repository hosting metadata before staging templates."""
        from xcookie.vcs.remote_info import resolve_remote_info

        self.remote_info = resolve_remote_info(self.config, self.repodir)

    def setup(self):
        """
        Finalizes a few variables and writes the "clean" template to the
        staging directory.
        """
        self._presetup()

        tags = set(self.config['tags'])

        use_vcs = self.config['use_vcs']
        warn_on_vcs_fallback = use_vcs == 'auto'

        if self.remote_info['type'] == 'unknown':
            if use_vcs == 'auto':
                use_vcs = False
            msg = 'Tags does not include github or gitlab. Cannot use VCS system without that'
            if use_vcs:
                raise Exception(msg)
            if warn_on_vcs_fallback:
                print(f'tags={tags}')
                print(
                    'self.remote_info = {}'.format(
                        ub.urepr(self.remote_info, nl=1)
                    )
                )
                warnings.warn(msg)

        if 'group' not in self.remote_info:
            if use_vcs == 'auto':
                use_vcs = False
            msg = 'Unknown user / group, specify a tag for a known user. Or a URL in the pyproject.toml [tool.xcookie]'
            if use_vcs:
                raise Exception(msg)
            if warn_on_vcs_fallback:
                print(f'tags={tags}')
                print(
                    'self.remote_info = {}'.format(
                        ub.urepr(self.remote_info, nl=1)
                    )
                )
                warnings.warn(msg)

        if use_vcs == 'auto':
            use_vcs = True
        self.config['use_vcs'] = use_vcs

        self._build_template_registry()
        self.stage_files()
        return self

    def copy_staged_files(self):
        plan = self.gather_tasks()
        self.render_patch_plan(plan)
        task_summary = plan.task_summary
        if any(task_summary.values()):
            print('task_summary = {}'.format(ub.urepr(task_summary, nl=1)))
            answer = self.config.prompt(
                'What parts of the patch to apply?',
                ['yes', 'all', 'some', 'none'],
                default='yes',
            )
            if answer in {'all', 'yes'}:
                plan.apply_all()
            elif answer == 'some':
                selected = []
                for task in plan.copy:
                    if self.config.confirm(f'Apply {task.dst}?'):
                        selected.append(task.dst)
                plan.apply_some(selected)

    def vcs_checks(self):
        """Initialize Git and hosting state for a newly generated repository."""
        from xcookie.repository import RepositoryInitializer

        initializer = RepositoryInitializer(
            self.config, self.repodir, self.remote_info
        )
        initializer.initialize()

    @property
    def template_context(self) -> TemplateContext:
        return TemplateContext.from_config(self.config)

    def _stage_file(self, info):
        """
        Write a single file to the staging directory based on its template
        info.

        Args:
            info (TemplateInfo | dict):
                a template record that defines how to construct a file

        Returns:
            TemplateInfo: enriched information.  A side effect of this function
            is writing the data to temporary storage.

        Example:
            >>> from xcookie.main import *  # NOQA
            >>> dpath = ub.Path.appdir('xcookie/tests/test-stage').delete().ensuredir()
            >>> kwargs = {
            >>>     'repodir': dpath / 'testrepo',
            >>>     'tags': ['gitlab', 'kitware', 'purepy', 'cv2'],
            >>>     'is_new': False,
            >>>     'interactive': False,
            >>> }
            >>> config = XCookieConfig.cli(argv=0, data=kwargs)
            >>> print('config = {}'.format(ub.urepr(dict(config), nl=1)))
            >>> self = TemplateApplier(config)
            >>> self._build_template_registry()
            >>> info = [d for d in self.template_infos if d['fname'] == '.gitlab-ci.yml'][0]
            >>> self._stage_file(info)
        """
        info = TemplateInfo.coerce(info)
        if not info.tag_requirements_met(self.tags):
            raise SkipFile

        path_name = info.fname
        path_type = info.path_type

        stage_fpath = self.staging_dpath / path_name
        info.stage_fpath = stage_fpath
        info.repo_fpath = self.repodir / path_name
        info.path_type = path_type
        if path_type == 'dir':
            stage_fpath.ensuredir()
        else:
            stage_fpath.parent.ensuredir()
            if info.builder is not None:
                text = info.builder(self, info)
            elif info.dynamic:
                text = getattr(self, info.dynamic)()
            else:
                text = None

            if info.builder is not None or info.dynamic:
                if text is None:
                    raise SkipFile('file was disabled')
                try:
                    stage_fpath.write_text(text)
                    if 'x' in info.perms:
                        stage_fpath.chmod('+x')
                except Exception:
                    print(f'text={text}')
                    raise
            else:
                in_fname = info.input_fname or path_name
                raw_fpath = self.template_dpath / in_fname
                if not raw_fpath.exists():
                    raise IOError(
                        f'Template file: raw_fpath={raw_fpath} does not exist'
                    )
                shutil.copy2(raw_fpath, stage_fpath)

                self._apply_xcookie_directives(stage_fpath)

                if info.template:
                    text = stage_fpath.read_text()
                    text = apply_template_context(text, self.template_context)
                    stage_fpath.write_text(text)

        # Probably inefficient.
        if stage_fpath.name.endswith('.py'):
            new_text = self.format_code(
                stage_fpath.read_text(), filename=stage_fpath.name
            )
            stage_fpath.write_text(new_text)
        return info

    def _apply_xcookie_directives(self, stage_fpath):
        text = stage_fpath.read_text()
        from xcookie.directive import DirectiveExtractor

        namespace = 'xcookie'
        commands = ['UNCOMMENT_IF', 'COMMENT_IF']
        extractor = DirectiveExtractor(namespace, commands)

        import re

        def comment_line(line):
            """

            line = '       #- pip install .[tests-strict,headless-strict]  # testrepo: +UNCOMMENT_IF(cv2)'
            uncomment_line(line)

            cases = [
                '   foobar',
                'foobar',
                '   def fds(): # hello',
            ]
            for line in cases:
                cline = comment_line(line)
                uline = uncomment_line(cline)
                print(f'line={line}')
                print(f'cline={cline}')
                print(f'uline={uline}')
                assert uline == line
            cases = [
                '#   foobar',
                '   #  foobar',
                '   #foobar',
                '#foobar',
                '#  foobar',
                '# foobar',
                '#   def fds(): # hello',
                '   #def fds(): # hello',
            ]
            for line in cases:
                uline = uncomment_line(cline)
                cline = comment_line(line)
                print(f'line={line}')
                print(f'cline={cline}')
                print(f'uline={uline}')
            """
            return re.sub(r'^(\s*)([^\s])', r'\g<1># \g<2>', line)

        def uncomment_line(line):
            return re.sub(r'^(\s*)#\s*', r'\g<1>', line, count=1)

        def tags_satisfied(directive, tags):
            value = tags.issuperset(set(directive.args))
            return value

        tags = set(self.config['tags'])
        new_lines = []
        did_work = 0
        for line in text.split('\n'):
            extracted = list(extractor.extract(line))
            # if 'COMMENT' in line:
            #     print(f'line={line}')
            #     print(f'extracted={extracted}')
            if extracted:
                for directive in extracted:
                    action = None
                    if directive.name == 'COMMENT_IF':
                        value = tags_satisfied(directive, tags)
                        if value:
                            action = comment_line
                            # print(f'action={action}')
                            did_work = 1
                    if directive.name == 'UNCOMMENT_IF':
                        value = tags_satisfied(directive, tags)
                        if value:
                            action = uncomment_line
                            # print(f'action={action}')
                            did_work = 1
                    if action is not None:
                        # print(f'directive.name={directive.name}')
                        # print(f'action={action}')
                        # print(f'old line={line}')
                        line = action(line)
                        # print(f'new line={line}')
            new_lines.append(line)

        if did_work:
            stage_fpath.write_text('\n'.join(new_lines))

    def stage_files(self):
        self.staging_infos = []
        for info in ub.ProgIter(self.template_infos, desc='staging'):
            if not info.get('enabled', True):
                continue
            try:
                info = self._stage_file(info)
            except SkipFile:
                continue
            else:
                self.staging_infos.append(info)

        if self.config.get('verbose', 0) > 2:
            print(
                'self.staging_infos = {}'.format(
                    ub.urepr(
                        [info.to_dict() for info in self.staging_infos],
                        nl=1,
                    )
                )
            )

    def gather_tasks(self) -> PatchPlan:
        plan = PatchPlan()

        regen_pat = SearchPattern.coerce(self.config.get('regen'))
        onlygen_pat = SearchPattern.coerce(self.config.get('only_generate'))

        for info in self.staging_infos:
            stage_fpath = info['stage_fpath']
            repo_fpath = info['repo_fpath']
            if info.get('skip', False):
                continue
            if onlygen_pat is not None:
                if not onlygen_pat.matches(info['fname']):
                    continue
            if not repo_fpath.exists():
                if stage_fpath.is_dir():
                    plan.add_mkdir(repo_fpath)
                    plan.missing_dir.append(repo_fpath)
                else:
                    plan.missing.append(repo_fpath)
                    plan.add_copy(stage_fpath, repo_fpath)
                    stage_text = stage_fpath.read_text()
                    diff_text = difftext(
                        '',
                        stage_text[:1000],
                        colored=True,
                        context_lines=2,
                    )
                    diff_text += '...and more'
                    plan.diff_texts[repo_fpath] = diff_text
            else:
                assert stage_fpath.exists()
                if stage_fpath.is_dir():
                    continue
                repo_text = repo_fpath.read_text()
                stage_text = stage_fpath.read_text()
                if stage_text.strip() == repo_text.strip():
                    diff_text = None
                else:
                    diff_text = difftext(
                        repo_text,
                        stage_text,
                        colored=True,
                        context_lines=1,
                    )
                if diff_text:
                    want_rewrite = info['overwrite']
                    if not want_rewrite:
                        if regen_pat is not None:
                            if regen_pat.matches(info['fname']):
                                want_rewrite = True

                    if want_rewrite:
                        plan.add_copy(stage_fpath, repo_fpath)
                        plan.dirty.append(repo_fpath)
                        plan.diff_texts[repo_fpath] = diff_text
                    else:
                        plan.modified.append(repo_fpath)
                else:
                    plan.clean.append(repo_fpath)

            if 'x' in info.get('perms', ''):
                import stat

                if info['repo_fpath'].exists():
                    st = ub.Path(info['repo_fpath']).stat()
                    mode_want = st.st_mode | stat.S_IEXEC
                    if mode_want != st.st_mode:
                        plan.add_perm(info['repo_fpath'], mode_want)
                # else:
                #     plan.add_perm(info['repo_fpath'], mode_want)

        return plan

    def render_patch_plan(self, plan: PatchPlan) -> None:
        render_patch_plan(plan)

    def build_requirements_txt(self):
        if self.config['use_pyproject_requirements']:
            return None
        # existing = (self.repodir / 'requirements').ls()
        candidate_all_requirements = [
            'requirements/runtime.txt',
            'requirements/tests.txt',
            'requirements/optional.txt',
            'requirements/build.txt',
            'requirements/postgresql.txt',
        ]
        requirement_lines = []
        for fpath_rel in candidate_all_requirements:
            fpath_rel = ub.Path(fpath_rel)
            fpath = self.repodir / fpath_rel
            if fpath.exists():
                requirement_lines.append('-r ' + os.fspath(fpath_rel))

        text = '\n'.join(requirement_lines)
        return text

    def build_readthedocs(self):
        """
        Returns:
            str: templated code
        """
        from xcookie.builders import readthedocs

        return readthedocs.build_readthedocs(self)

    def build_setup(self):
        """
        Returns:
            str: templated code
        """
        from xcookie.builders import setup

        return setup.build_setup(self)

    def build_pyproject(self):
        """
        Returns:
            str: templated code
        """
        from xcookie.builders import pyproject

        return pyproject.build_pyproject(self)

    def format_code(self, text, filename='snippet.py'):
        """
        Format Python code using the project's pyproject.toml ruff settings.

        Reads ruff configuration from [tool.ruff] and [tool.ruff.format] sections
        of the project's pyproject.toml and uses those as defaults for formatting.

        Args:
            text (str): Python code to format
            filename (str): Virtual filename for the formatter (default: 'snippet.py')

        Returns:
            str: Formatted code
        """
        from xcookie.util.util_code_format import (
            RuffFormatConfig,
            make_backend,
        )
        from xcookie.util.util_code_format import (
            format_code as util_format_code,
        )

        # Read the project's ruff configuration if available
        disk_config = self.config._load_pyproject_config()
        ruff_config_dict = disk_config.get('tool', {}).get('ruff', {})
        ruff_format_dict = ruff_config_dict.get('format', {})

        # Build RuffFormatConfig from the pyproject settings
        ruff_config_kwargs = {}

        # Map pyproject settings to RuffFormatConfig parameters
        if 'quote-style' in ruff_format_dict:
            ruff_config_kwargs['quote_style'] = ruff_format_dict['quote-style']
        if 'indent-style' in ruff_format_dict:
            ruff_config_kwargs['indent_style'] = ruff_format_dict[
                'indent-style'
            ]
        if 'skip-magic-trailing-comma' in ruff_format_dict:
            ruff_config_kwargs['skip_magic_trailing_comma'] = ruff_format_dict[
                'skip-magic-trailing-comma'
            ]
        if 'preview' in ruff_format_dict:
            ruff_config_kwargs['preview'] = ruff_format_dict['preview']
        if 'docstring-code-format' in ruff_format_dict:
            ruff_config_kwargs['docstring_code_format'] = ruff_format_dict[
                'docstring-code-format'
            ]
        if 'docstring-code-line-length' in ruff_format_dict:
            ruff_config_kwargs['docstring_code_line_length'] = ruff_format_dict[
                'docstring-code-line-length'
            ]
        if 'line-length' in ruff_config_dict:
            ruff_config_kwargs['line_length'] = ruff_config_dict['line-length']

        # Create the config and backend
        ruff_config = RuffFormatConfig(**ruff_config_kwargs)
        backend = make_backend('ruff', ruff_config=ruff_config)

        # Format and return the code
        return util_format_code(text, backend=backend, filename=filename)

    def _setup_pip_commands(self):
        # Hack for uv migration, to get some common variables.  need to clean
        # up how we control what is used as the package installer later.
        if self.config.use_uv:
            # Does UV always prefer binary?
            self.PIP_INSTALL = 'python -m uv pip install'
            # self.PIP_INSTALL_PREFER_BINARY = 'python -m uv pip install'
            self.PIP_INSTALL_PREFER_BINARY = (
                'python -m pip install --prefer-binary'
            )
            self.UPDATE_PIP = 'python -m pip install pip uv -U'
            # The system uv seems to have an issue on CI
            self.SYSTEM_PIP_INSTALL = 'python -m pip install'
            # self.SYSTEM_PIP_INSTALL = 'python -m uv pip install --system --break-system-packages'
        else:
            self.PIP_INSTALL = 'python -m pip install'
            self.PIP_INSTALL_PREFER_BINARY = (
                'python -m pip install --prefer-binary'
            )
            self.UPDATE_PIP = 'python -m pip install pip -U'
            self.SYSTEM_PIP_INSTALL = 'python -m pip install'

    def build_github_actions(self):
        # Backwards-compatible wrapper. Keep this pointing at tests.yml for
        # older call sites.
        return self.build_github_actions_tests()

    def build_github_actions_tests(self):
        from xcookie.builders import github_actions

        self._setup_pip_commands()
        return github_actions.build_github_actions_tests(self)

    def build_github_actions_release(self):
        from xcookie.builders import github_actions

        self._setup_pip_commands()
        return github_actions.build_github_actions_release(self)

    def build_gitlab_ci(self):
        from xcookie.builders import gitlab_ci

        self._setup_pip_commands()  # Do we need this here?
        return gitlab_ci.build_gitlab_ci(self)


    def build_refresh_locks_sh(self):
        """Build ``dev/refresh_locks.sh``.

        The script regenerates ``uv.lock`` from ``pyproject.toml`` and re-exports
        the ``requirements/locks/<extras>.txt`` files referenced by the strict
        CI variants in the active CI plan.  Generated content is deterministic:
        one ``uv export`` invocation per unique extras combo.
        """
        from xcookie.builders import common_ci, ci_plan
        from xcookie.requirements_layout import RequirementsLayout

        layout = RequirementsLayout.from_config(self.config)
        plan = common_ci.make_ci_plan(self)
        strict_variants = list(
            plan.iter_active_variants(['minimal-strict', 'full-strict'])
        )

        # Deduplicate by ordered extras so the same combo isn't re-exported
        # twice when minimal-strict and full-strict happen to collapse.
        seen_extras: set[tuple[str, ...]] = set()
        combos: list[tuple[str, ...]] = []
        for variant in strict_variants:
            key = tuple(variant.extras)
            if key in seen_extras:
                continue
            seen_extras.add(key)
            combos.append(key)

        export_blocks: list[str] = []
        for extras in combos:
            out_path = ci_plan.lock_requirements_path(extras)
            label = ', '.join(extras) if extras else 'runtime'
            # Build the export command line-by-line so indentation is exact
            # regardless of how the surrounding script is dedented.
            lines = [
                f'# Strict CI variant extras: {label}',
                'uv export --frozen --no-emit-project --format requirements.txt --no-hashes \\',
            ]
            for extra in extras:
                lines.append(f'    --extra {extra} \\')
            lines.append(f'    -o {out_path}')
            export_blocks.append('\n'.join(lines))

        if not export_blocks:
            # Defensive: should not happen because the registry entry is gated
            # on uses_lockfile_ci, but emit something safe if it does.
            export_blocks.append('# No strict CI variants are active.')

        package_note = ''
        if layout.package is not None:
            package_note = (
                '# The requirements tree is also shipped as package resources '
                f'under {layout.package}.\n'
            )
        header = ub.codeblock(
            f"""
            #!/usr/bin/env bash
            # Regenerate uv.lock and the pinned lock files in requirements/locks/.
            #
            # Run this whenever a dependency in pyproject.toml changes so the
            # strict CI variants install the same versions you tested locally.
            {package_note}#
            # This script is generated by xcookie; see
            # xcookie/main.py:build_refresh_locks_sh.  Manual edits will be
            # overwritten on the next regeneration.
            set -euo pipefail

            cd "$(dirname "$0")/.."

            mkdir -p {layout.lock_relpath.as_posix()}
            uv lock
            """
        )
        body = '\n\n'.join(export_blocks)
        return header + '\n\n' + body + '\n'

    def build_run_linter(self):
        text = ub.codeblock(
            f"""
            #!/usr/bin/env bash
            flake8 --count --select=E9,F63,F7,F82 --show-source --statistics {self.rel_mod_dpath}
            flake8 --count --select=E9,F63,F7,F82 --show-source --statistics ./tests
            """
        )
        return text


    def build_readme(self):
        from xcookie.builders import readme

        if not self.config['use_vcs']:
            return None
        return readme.build_readme(self)

    def build_docs_index(self):
        from xcookie.builders import docs

        return docs.build_docs_index(self)

    def build_docs_conf(self):
        from xcookie.builders import docs

        return docs.build_docs_conf(self)

    def build_docs_requirements(self):
        from xcookie.builders import docs

        return docs.build_docs_requirements(self)

    # TODO: generate better stub requirements based on common packages
    def build_optional_requirements(self):
        if self.config['use_pyproject_requirements']:
            return None
        text = ub.codeblock(
            """
            """
        )
        return text

    def build_runtime_requirements(self):
        if self.config['use_pyproject_requirements']:
            return None
        text = ub.codeblock(
            """
            """
        )
        return text

    def build_tests_requirements(self):
        if self.config['use_pyproject_requirements']:
            return None
        text = ub.codeblock(
            """
            xdoctest >= 1.1.5
            # Pin maximum pytest versions for older python versions
            # TODO: determine what the actual minimum and maximum acceptable versions of
            # pytest (that are also compatible with xdoctest) are for each legacy python
            # major.minor version.
            # See xdev availpkg
            pytest>=6.2.5            ;                               python_version >= '3.10.0'  # Python 3.10+
            pytest>=4.6.0            ; python_version < '3.10.0' and python_version >= '3.7.0'   # Python 3.7-3.9
            pytest>=4.6.0            ; python_version < '3.7.0'  and python_version >= '3.6.0'   # Python 3.6
            pytest>=4.6.0, <= 6.1.2  ; python_version < '3.6.0'  and python_version >= '3.5.0'   # Python 3.5
            pytest>=4.6.0, <= 4.6.11 ; python_version < '3.5.0'  and python_version >= '3.4.0'   # Python 3.4
            pytest>=4.6.0, <= 4.6.11 ; python_version < '2.8.0'  and python_version >= '2.7.0'   # Python 2.7

            pytest-cov>=3.0.0           ;                               python_version >= '3.6.0'   # Python 3.6+
            pytest-cov>=2.9.0           ; python_version < '3.6.0'  and python_version >= '3.5.0'   # Python 3.5
            pytest-cov>=2.8.1           ; python_version < '3.5.0'  and python_version >= '3.4.0'   # Python 3.4
            pytest-cov>=2.8.1           ; python_version < '2.8.0'  and python_version >= '2.7.0'   # Python 2.7

            # xdev availpkg pytest-timeout
            pytest-timeout>=1.4.2

            # xdev availpkg xdoctest
            # xdev availpkg coverage
            coverage>=6.1.1     ;                            python_version >= '3.10'    # Python 3.10+
            coverage>=5.3.1     ; python_version < '3.10' and python_version >= '3.9'    # Python 3.9
            coverage>=6.1.1     ; python_version < '3.9' and python_version >= '3.8'    # Python 3.8
            coverage>=6.1.1     ; python_version < '3.8' and python_version >= '3.7'    # Python 3.7
            coverage>=6.1.1     ; python_version < '3.7' and python_version >= '3.6'    # Python 3.6
            coverage>=5.3.1     ; python_version < '3.6' and python_version >= '3.5'    # Python 3.5
            coverage>=4.3.4     ; python_version < '3.5' and python_version >= '3.4'    # Python 3.4
            coverage>=5.3.1     ; python_version < '3.4' and python_version >= '2.7'    # Python 2.7
            coverage>=4.5       ; python_version < '2.7' and python_version >= '2.6'    # Python 2.6
            """
        )
        return text

    def _build_special_requirements(
        self, variant, version_defaults, header_lines
    ):
        """
        Example:
            >>> from xcookie.main import *  # NOQA
            >>> dpath = ub.Path.appdir('xcookie/tests/test-stage').delete().ensuredir()
            >>> kwargs = {
            >>>     'repodir': dpath / 'testrepo',
            >>>     'tags': ['gitlab', 'kitware', 'purepy', 'cv2'],
            >>>     'is_new': False,
            >>>     'min_python': '3.9',
            >>>     'max_python': '3.12',
            >>>     'interactive': False,
            >>> }
            >>> config = XCookieConfig.cli(argv=0, data=kwargs)
            >>> print('config = {}'.format(ub.urepr(dict(config), nl=1)))
            >>> self = TemplateApplier(config)
            >>> print(chr(10) + 'headless.txt')
            >>> print(self.build_cv2_headless_requirements_txt())
            >>> print(chr(10) + 'gdal.txt')
            >>> print(self.build_gdal_requirements_txt())
        """
        req_lines = [
            '# Generated dynamically via: ~/code/xcookie/xcookie/main.py::TemplateApplier._build_special_requirements'
        ]
        req_lines.extend(header_lines)
        max_pyver = Version(self.config['max_python'] or '4.0')
        min_pyver = Version(self.config['min_python'])

        for row in version_defaults:
            lt = row['pyver_lt']
            # lt = min(row['pyver_lt'], max_pyver) # FIXME, exclusive vs inclusive
            ge = max(row['pyver_ge'], min_pyver)
            skip = row['pyver_ge'] > max_pyver
            skip |= row['pyver_lt'] <= min_pyver
            skip |= ge >= lt
            if not skip:
                req_lines.append(
                    f"{variant}{row['version']} ; python_version < '{lt}' and python_version >= '{ge}'"
                )
        req_text = '\n'.join(req_lines)
        return req_text

    def _build_cv2_requirements(self, variant):
        header_lines = [
            f'# xdev availpkg {variant}',
            '# --prefer-binary',
        ]
        version_defaults = [
            {
                'version': '>=4.10.0.84',
                'pyver_ge': Version('3.13'),
                'pyver_lt': Version('4.0'),
            },  # minimal for numpy 2.x
            {
                'version': '>=4.5.5.64',
                'pyver_ge': Version('3.11'),
                'pyver_lt': Version('3.13'),
            },
            {
                'version': '>=4.5.4.58',
                'pyver_ge': Version('3.10'),
                'pyver_lt': Version('3.11'),
            },
            {
                'version': '>=3.4.15.55',
                'pyver_ge': Version('3.7'),
                'pyver_lt': Version('3.10'),
            },
            {
                'version': '>=3.4.13.47',
                'pyver_ge': Version('3.6'),
                'pyver_lt': Version('3.7'),
            },
            {
                'version': '>=3.4.2.16',
                'pyver_ge': Version('2.7'),
                'pyver_lt': Version('3.5'),
            },
        ]
        return self._build_special_requirements(
            variant, version_defaults, header_lines
        )

    def build_cv2_headless_requirements_txt(self):
        variant = 'opencv-python-headless'
        return self._build_cv2_requirements(variant)

    def build_cv2_graphics_requirements_txt(self):
        variant = 'opencv-python'
        return self._build_cv2_requirements(variant)

    def _gdal_requirement_parts(self):
        # TODO: make more dynamic
        variant = 'GDAL'
        version_defaults = [
            {
                'version': '>=3.11.3.1',
                'pyver_ge': Version('3.14'),
                'pyver_lt': Version('4.0'),
            },
            {
                # GDAL 3.9+ builds its NumPy bindings against NumPy 2 on
                # Python 3.9+, producing bindings that are compatible with
                # both NumPy 1 and 2.  The large-image wheelhouse provides
                # GDAL 3.10.0 wheels for Python 3.9 through 3.13.
                'version': '>=3.10.0',
                'pyver_ge': Version('3.9'),
                'pyver_lt': Version('3.14'),
            },
            {
                'version': '>=3.4.1,<=3.11.0',
                'pyver_ge': Version('3.6'),
                'pyver_lt': Version('3.9'),
            },
        ]
        return variant, version_defaults

    def build_gdal_requirements_txt(self):
        variant, version_defaults = self._gdal_requirement_parts()
        return self._build_special_requirements(
            variant, version_defaults, header_lines=[]
        )

    def build_run_doctests(self):
        return ub.codeblock(
            f"""
            #!/usr/bin/env bash
            xdoctest {self.rel_mod_dpath} --style={self.config['xdoctest_style']} all "$@"
            """
        )




def _parse_remote_url(url):
    """Legacy remote URL parser retained for import compatibility."""
    info = {}
    if url.startswith('https://'):
        parts = url.split('https://')[1].split('/')
        info['host'] = 'https://' + parts[0]
        info['group'] = parts[1]
        info['repo_name'] = parts[2]
    elif url.startswith('git@'):
        parts = url.split('git@')[1].split(':')
        info['host'] = 'https://' + parts[0]
        info['group'] = parts[1].split('/')[0]
        info['repo_name'] = parts[1].split('/')[1]
    else:
        raise ValueError(url)
    return info


def find_git_root(dpath):
    """Find the nearest ancestor containing ``.git``."""
    cwd = ub.Path(dpath).resolve()
    parts = cwd.parts
    found = None
    for i in reversed(range(0, len(parts) + 1)):
        subparts = parts[0:i]
        if len(subparts) == 0:
            break
        p = ub.Path(*subparts)
        cand = p / '.git'
        if cand.exists():
            found = p
            break
    if found is None:
        raise Exception('cannot find git root')
    return found

def main():
    XCookieConfig.main(argv=True, strict=True, autocomplete=True)



if __name__ == '__main__':
    main()
