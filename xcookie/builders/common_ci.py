from __future__ import annotations

"""
Common subroutines for consistency between gitlab-ci / github actions / etc...
"""

import shlex

import ubelt as ub

from xcookie.builders import ci_plan


def get_pyproject_optional_dependency_keys(self):
    """
    Return optional-dependency keys declared in ``pyproject.toml``.

    Compatibility wrapper around :mod:`xcookie.builders.ci_plan`.
    """
    return ci_plan.get_pyproject_optional_dependency_keys(self)


def filter_pyproject_extras(self, desired_extras):
    """
    Return ``desired_extras`` filtered down to extras declared by pyproject.

    Compatibility wrapper around :mod:`xcookie.builders.ci_plan`.
    """
    return list(ci_plan.filter_pyproject_extras(self, desired_extras))


def format_pyproject_install_target(extras, target='.', editable=False):
    """
    Build a pip install target, omitting brackets when extras are empty.

    Compatibility wrapper around :mod:`xcookie.builders.ci_plan`.
    """
    return ci_plan.format_pyproject_install_target(
        extras, target=target, editable=editable
    )


def make_ci_plan(self):
    """Return the shared provider-neutral CI plan for this applier."""
    return ci_plan.make_ci_plan(self)


def make_typecheck_parts(self, plan: ci_plan.CIPlan | None = None):
    """
    Return a list of shell commands to run type checkers.

    By default this will run both `mypy` and `ty` (in that order). The
    returned value is a list of command strings so callers can adapt it to
    either GitHub Actions (`run` string) or GitLab CI (`script` list).
    """

    # TODO: more control over which type checkers to use.
    # right now we always enable ty unless notypes is on.
    # but we should have more sane defaults.
    checkers = None
    if checkers is None:
        checkers = ['ty']

    if 'mypy' in self.tags:
        checkers += ['mypy']

    # Where to install runtime/type requirements from
    type_requirement_files = [
        # TODO: get this location from the config
        'requirements/runtime.txt'
    ]
    req_files_text = ' '.join(type_requirement_files)

    if self.config['use_pyproject_requirements']:
        if plan is None:
            plan = make_ci_plan(self)
        target = format_pyproject_install_target(
            plan.typecheck_extras, editable=True
        )
        pip_install_reqs = f'pip install --prefer-binary {target}'
    else:
        pip_install_reqs = f'pip install -r {req_files_text}'

    commands = []

    if 'mypy' in checkers:
        commands += [
            'python -m pip install mypy',
            pip_install_reqs,
            # TODO; this likely needs to be replaced with some explicit
            # registration of what typing requirements are for the library
            # f'mypy --install-types --non-interactive ./{self.rel_mod_dpath}',
            f'mypy ./{self.rel_mod_dpath}',
        ]

    if 'ty' in checkers:
        # Generic support for "ty". Install and run; users can customize
        # behavior by changing `checkers` or adding config-specific steps.
        commands += [
            'python -m pip install ty',
            pip_install_reqs,
            f'ty check ./{self.rel_mod_dpath}',
        ]

    return commands


def make_build_sdist_parts(self, wheelhouse_dpath='wheelhouse'):
    commands = [
        # 'python -m pip install pip -U',
        f'{self.UPDATE_PIP}',
        f'{self.PIP_INSTALL} setuptools>=0.8 wheel build twine',
        f'python -m build --sdist --outdir {wheelhouse_dpath}',
        f'python -m twine check ./{wheelhouse_dpath}/{self.pkg_fname_prefix}*.tar.gz',
    ]

    build_parts = {
        'commands': commands,
        'artifact': f'./{wheelhouse_dpath}/{self.pkg_fname_prefix}*.tar.gz',
    }
    return build_parts


def make_build_wheel_parts(self, wheelhouse_dpath='wheelhouse'):
    commands = [
        # 'python -m pip install pip -U',
        f'{self.UPDATE_PIP}',
        f'{self.PIP_INSTALL} setuptools>=0.8 wheel build twine',
        f'python -m build --wheel --outdir {wheelhouse_dpath}',
        f'python -m twine check ./{wheelhouse_dpath}/{self.pkg_fname_prefix}*.whl',
    ]

    build_wheel_parts = {
        'commands': commands,
        'artifact': f'./{wheelhouse_dpath}/{self.pkg_fname_prefix}*.whl',
    }
    return build_wheel_parts


def make_install_and_test_wheel_parts(
    self,
    wheelhouse_dpath,
    special_install_lines,
    workspace_dname,
    custom_before_test_lines=[],
    custom_after_test_commands=[],
):
    """
    Builds the YAML common between github actions and gitlab CI to install and
    tests python packages.

    References:
        https://stackoverflow.com/questions/42019184/python-how-can-i-get-the-version-number-from-a-whl-file
    """
    from xcookie.util_yaml import Yaml

    # get_modname_python = "import tomli; print(tomli.load(open('pyproject.toml', 'rb'))['tool']['xcookie']['mod_name'])"
    # get_modname_bash = f'python -c "{get_modname_python}"'
    # get_wheel_fpath_python = f"import pathlib; print(str(sorted(pathlib.Path('{wheelhouse_dpath}').glob('{self.mod_name}*.whl'))[-1]).replace(r'\\', '/'))"

    # get_wheel_fpath_python = Yaml.CodeBlock(f"import pathlib; print(str(sorted(pathlib.Path('{wheelhouse_dpath}').glob('{self.mod_name}*.whl'))[-1]).replace(chr(92), chr(47)))")
    # get_wheel_fpath_bash = f'python -c "{get_wheel_fpath_python}"'
    # get_mod_version_python = "from pkginfo import Wheel; print(Wheel('$WHEEL_FPATH').version)"
    # get_mod_version_bash = f'python -c "{get_mod_version_python}"'

    get_wheel_fpath_bash = ub.codeblock(
        f"""
        python -c "if 1:
            import pathlib
            from packaging import tags
            from packaging.utils import parse_wheel_filename
            dist_dpath = pathlib.Path('{wheelhouse_dpath}')
            wheels = sorted(dist_dpath.glob('{self.pkg_fname_prefix}*.whl'))
            if wheels:
                sys_tags = set(tags.sys_tags())
                matching = []
                for w in wheels:
                    try:
                        _, _, _, wheel_tags = parse_wheel_filename(w.name)
                    except Exception:
                        continue
                    if any(t in sys_tags for t in wheel_tags):
                        matching.append(w)
                fpath = sorted(matching or wheels)[-1]
            else:
                sdists = sorted(dist_dpath.glob('{self.pkg_fname_prefix}*.tar.gz'))
                if not sdists:
                    raise SystemExit('No wheel artifacts found in wheelhouse')
                fpath = sdists[-1]
            print(str(fpath).replace(chr(92), chr(47)))
        "
        """
    )

    # if tuple(map(int, self.config.min_python.split('.'))) >= (3, 8):
    #     # Not sure why this fails on 3.6 / 3.7?
    #     # Use less ugly version when we can
    #     get_mod_version_bash = ub.codeblock(
    #         """
    #         python -c "if 1:
    #             from pkginfo import Wheel, SDist
    #             import pathlib
    #             fpath = '$WHEEL_FPATH'
    #             cls = Wheel if fpath.endswith('.whl') else SDist
    #             item = cls(fpath)
    #             print(item.version)
    #         "
    #         """
    #     )
    # else:
    #     get_mod_version_bash = ub.codeblock(
    #         """
    #         python -c "if 1:
    #             from pkginfo import Wheel, SDist
    #             import pathlib
    #             fpath = '$WHEEL_FPATH'
    #             cls = Wheel if fpath.endswith('.whl') else SDist
    #             item = cls(fpath)
    #             if item.version is None:
    #                 import re
    #                 # This is very fragile
    #                 fname = pathlib.Path(fpath).name
    #                 match = re.match(r'^([^-]+)-([^-]+)(.whl|.tar.gz)$', fname)
    #                 bs = chr(92)
    #                 pat = '([0-9]+' + bs + '.[0-9]+' + bs + '.[0-9]+)'
    #                 import re
    #                 # Not sure why version is None in 3.6 and 3.7
    #                 match = re.search(pat, fname)
    #                 assert match is not None
    #                 version = match.groups()[0]
    #                 print(version)
    #             else:
    #                 print(item.version)
    #         "
    #         """
    #     )

    # get_modpath_python = "import ubelt; print(ubelt.modname_to_modpath(f'{self.mod_name}'))"
    get_modpath_python = f'import {self.mod_name}, os; print(os.path.dirname({self.mod_name}.__file__))'
    get_modpath_bash = f'python -c "{get_modpath_python}"'

    test_command = self.config['test_command']

    if test_command == 'auto':
        if 'ibeis' == self.mod_name:
            test_command = [
                'python -m xdoctest $MOD_DPATH --style=google all',
                'echo "xdoctest command finished"',
            ]
        else:
            test_command = [
                Yaml.CodeBlock(
                    'python -m pytest --verbose -p pytester -p no:doctest --xdoctest --cov-config ../pyproject.toml --cov-report term --durations=100 --cov="$MOD_NAME" "$MOD_DPATH" ../tests'
                ),
                'echo "pytest command finished, moving the coverage file to the repo root"',
            ]
    else:
        if isinstance(test_command, str):
            test_command = [Yaml.CodeBlock(test_command)]

    # export UV_EXTRA_INDEX_URL="https://download.pytorch.org/whl/nightly/cpu https://download.pytorch.org/whl/nightly/cu126"

    if self.config['use_pyproject_requirements']:
        install_helpers = [
            'echo "Installing helpers: setuptools"',
            f'{self.PIP_INSTALL} --resolution=highest setuptools>=0.8 setuptools_scm wheel build -U',  # is this necessary?
            'echo "Installing helpers: tomli and pkginfo"',
            f'{self.PIP_INSTALL} --resolution=highest tomli pkginfo packaging',
        ]
    else:
        install_helpers = [
            'echo "Installing helpers: setuptools"',
            f'{self.PIP_INSTALL} setuptools>=0.8 setuptools_scm wheel build -U',  # is this necessary?
            'echo "Installing helpers: tomli and pkginfo"',
            f'{self.PIP_INSTALL} tomli pkginfo packaging',
        ]

    # Note: export does not expose the environment variable to subsequent jobs.
    install_wheel_commands = (
        [
            'echo "Finding the path to the wheel"',
            f'ls {wheelhouse_dpath} || echo "{wheelhouse_dpath} does not exist"',
            'echo "Installing helpers: update pip"',
            f'{self.UPDATE_PIP}',
            *install_helpers,
            f'export WHEEL_FPATH=$({get_wheel_fpath_bash})',
            # f'export MOD_VERSION=$({get_mod_version_bash})',
        ]
        + special_install_lines
        + [
            'echo "WHEEL_FPATH=$WHEEL_FPATH"',
            'echo "INSTALL_EXTRAS=$INSTALL_EXTRAS"',
            'echo "UV_RESOLUTION=$UV_RESOLUTION"',
            # 'echo "MOD_VERSION=$MOD_VERSION"',
            # This helps but doesn't solve the problem.
            # https://github.com/Erotemic/xdoctest/pull/158#discussion_r1697092781
            # 'echo "Downloading dependencies from pypi"',
            # f'pip download "{self.mod_name}[$INSTALL_EXTRAS]==$MOD_VERSION" --dest wheeldownload',
            # f'echo "Overwriting pypi {self.mod_name} wheel"',
            # 'cp wheelhouse/* wheeldownload/',
            # f'pip install --prefer-binary "{self.mod_name}[$INSTALL_EXTRAS]==$MOD_VERSION" -f wheeldownload --no-index',
            # TODO: flag to allow prerelease?
            # f'{self.PIP_INSTALL_PREFER_BINARY} --prerelease=allow "{self.pkg_name}[$INSTALL_EXTRAS]==$MOD_VERSION" -f {wheelhouse_dpath}',
            'if [[ -n "${INSTALL_EXTRAS:-}" ]]; then',
            '    INSTALL_TARGET="${WHEEL_FPATH}[${INSTALL_EXTRAS}]"',
            'else',
            '    INSTALL_TARGET="${WHEEL_FPATH}"',
            'fi',
            'echo "INSTALL_TARGET=$INSTALL_TARGET"',
            f'{self.PIP_INSTALL_PREFER_BINARY} "${{INSTALL_TARGET}}"',
            'echo "Install finished."',
        ]
    )

    test_wheel_commands = (
        [
            'echo "Creating test sandbox directory"',
            f'export WORKSPACE_DNAME="{workspace_dname}"',
            'echo "WORKSPACE_DNAME=$WORKSPACE_DNAME"',
            'mkdir -p $WORKSPACE_DNAME',
            'echo "cd-ing into the workspace"',
            'cd $WORKSPACE_DNAME',
            'pwd',
            'ls -altr',
            # 'pip freeze',
            '# Get the path to the installed package and run the tests',
            f'export MOD_DPATH=$({get_modpath_bash})',
            f'export MOD_NAME={self.mod_name}',
            Yaml.CodeBlock(
                """
            echo "
            ---
            MOD_DPATH = $MOD_DPATH
            ---
            running the pytest command inside the workspace
            ---
            "
            """
            ),
        ]
        + custom_before_test_lines
        + test_command
        + custom_after_test_commands
    )

    install_and_test_wheel_parts = {
        'install_wheel_commands': install_wheel_commands,
        'test_wheel_commands': test_wheel_commands,
    }
    return install_and_test_wheel_parts


def get_supported_platform_info(self):
    """
    CommandLine:
        xdoctest -m /home/joncrall/code/xcookie/xcookie/builders/common_ci.py get_supported_platform_info
        xdoctest -m xcookie.builders.common_ci get_supported_platform_info

    Example:
        >>> from xcookie.builders.github_actions import *  # NOQA
        >>> from xcookie.builders.common_ci import *  # NOQA
        >>> from xcookie.main import XCookieConfig
        >>> from xcookie.main import TemplateApplier
        >>> config = XCookieConfig(tags=['purepy'], remote_group='Org', repo_name='Repo')
        >>> self = TemplateApplier(config)
        >>> supported_platform_info = get_supported_platform_info(self)
        >>> import ubelt as ub
        >>> print(f'supported_platform_info = {ub.urepr(supported_platform_info, nl=2)}')
    """
    os_list = []

    # TODO: maybe allow pinning, or list out what the options are
    # https://docs.github.com/en/actions/using-github-hosted-runners/about-github-hosted-runners/about-github-hosted-runners#standard-github-hosted-runners-for-public-repositories
    # I think this only matters for github?
    if 'linux' in self.config['os']:
        os_list.append('ubuntu-latest')
    if 'osx' in self.config['os']:
        os_list.append('macOS-latest')
    if 'win' in self.config['os']:
        os_list.append('windows-latest')
        # os_list.append('windows-11-arm')

    if 'binpy-ubuntu-arm' in self.config['tags']:
        # From TTsangSC:
        # Overhead of building ARM wheels on Intel Linux nodes is unreasonably high
        # (20s build time per wheel vs 3m); it's better to just spin another runner
        # up to build them natively
        os_list.append('ubuntu-24.04-arm')

    cpython_versions = self.config['ci_cpython_versions']
    pypy_versions = [f'pypy-{v}' for v in self.config['ci_pypy_versions']]
    # 3.4 is broken on github actions it seems
    cpython_versions_non34 = [v for v in cpython_versions if v != '3.4']
    supported_py_versions = self.config['supported_python_versions']
    if len(supported_py_versions) == 0:
        raise Exception('no supported python versions?')

    from xcookie import constants

    INFO_LUT = {
        row['version']: row for row in constants.KNOWN_PYTHON_VERSION_INFO
    }

    def _parse_pyver_tuple(pyver):
        parts = [p for p in str(pyver).split('.') if p.isdigit()]
        return tuple(int(p) for p in parts[:2])

    if 'binpy' in self.config['tags']:
        min_py = _parse_pyver_tuple(self.config['min_python'])
        if min_py < (3, 9):
            raise ValueError(
                'xcookie does not support generating binpy workflows for Python < 3.9. '
                'Bump min_python to >= 3.9 or disable binpy.'
            )
        for ver in supported_py_versions:
            if _parse_pyver_tuple(ver) < (3, 9):
                raise ValueError(
                    f'binpy requested with python-version={ver}, but xcookie requires >=3.9 for binpy'
                )
        for ver in cpython_versions:
            if _parse_pyver_tuple(ver) < (3, 9):
                raise ValueError(
                    f'binpy requested with python-version={ver}, but xcookie requires >=3.9 for binpy'
                )

    # Choose which Python version will be the "main" one we use for version
    # agnostic jobs.
    main_python_version = self.config['main_python']
    if main_python_version == 'max':
        # import kwutil
        for pyver in supported_py_versions[::-1]:
            info = INFO_LUT[pyver]
            if info.get('is_prerelease'):
                continue
            main_python_version = pyver
            break
    elif main_python_version == 'min':
        main_python_version = supported_py_versions[0]
    else:
        main_python_version = str(main_python_version)

    # main_python_version = '3.13'

    # TODO: find a nicer way to codify the idea that the supported python
    # version needs to map to something github actions knows about, which could
    # be a prerelease version.
    cpython_versions_non34_ = []
    cpython_versions_non34_non_prerelease_ = []
    for pyver in cpython_versions_non34:
        info = INFO_LUT[pyver]
        if 'github_action_version' in info:
            pyver = info['github_action_version']
        cpython_versions_non34_.append(pyver)
        if not info.get('is_prerelease'):
            cpython_versions_non34_non_prerelease_.append(pyver)
    cpython_versions_non34 = cpython_versions_non34_

    extras_versions_templates = {
        'full-loose': self.config['ci_versions_full_loose'],
        'full-strict': self.config['ci_versions_full_strict'],
        'minimal-loose': self.config['ci_versions_minimal_loose'],
        'minimal-strict': self.config['ci_versions_minimal_strict'],
    }
    extras_versions = {}
    for k, v in extras_versions_templates.items():
        if v == '' or v is None:
            v = []
        elif v == 'min':
            v = [cpython_versions_non34_[0]]
        elif v == 'max':
            v = [cpython_versions_non34_non_prerelease_[-1]]
            # v = [cpython_versions_non34_[-1]]
        elif v == 'main':
            v = [main_python_version]
        elif v == '*':
            v = cpython_versions_non34 + pypy_versions
        else:
            raise KeyError(v)
        extras_versions[k] = v

    # NOTE, the os-list that we build on may be different than the one we ant
    # to test on.

    supported_platform_info = {
        'os_list': os_list,
        'cpython_versions': cpython_versions_non34,
        'pypy_versions': pypy_versions,
        # 'min_python_version': supported_py_versions[0],
        # 'max_python_version': supported_py_versions[-1],
        'main_python_version': main_python_version,
        'install_extra_versions': extras_versions,
    }

    print(
        f'supported_platform_info = {ub.urepr(supported_platform_info, nl=1)}'
    )
    return supported_platform_info


def _py_shell_command(code: str) -> str:
    """Return a shell-safe ``python -c`` command."""
    return 'python -c ' + shlex.quote(code)


def make_project_version_getter(self) -> str:
    """Return a shell command that prints the project version.

    Historically generated deploy jobs imported ``setup.VERSION``.  That is
    invalid for pyproject-only repositories.  When ``setup.py`` is disabled,
    statically parse ``__version__`` from the package ``__init__`` module
    instead of importing the project package or its runtime dependencies.
    """
    if self.config['use_setup_py']:
        return 'python -c "import setup; print(setup.VERSION)"'

    rel_init = (self.rel_mod_dpath / '__init__.py').as_posix()
    py_code = (
        'import ast, pathlib; '
        f'tree = ast.parse(pathlib.Path({rel_init!r}).read_text()); '
        'print(next(ast.literal_eval(n.value) for n in tree.body '
        'if isinstance(n, ast.Assign) '
        'and any(getattr(t, "id", None) == "__version__" '
        'for t in n.targets)))'
    )
    return _py_shell_command(py_code)


def make_project_version_assignment(
    self, variable: str = 'VERSION', export: bool = False
) -> str:
    """Return a shell assignment for the current project version."""
    prefix = 'export ' if export else ''
    return f'{prefix}{variable}=$({make_project_version_getter(self)})'
