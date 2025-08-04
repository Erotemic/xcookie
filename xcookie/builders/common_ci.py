"""
Common subroutines for consistency between gitlab-ci / github actions / etc...
"""


def make_mypy_check_parts(self):
    import ubelt as ub

    type_requirement_files = [
        # TODO: get this location from the config
        'requirements/runtime.txt'
    ]
    req_files_text = ' '.join(type_requirement_files)
    commands = ub.codeblock(
        f'''
        python -m pip install mypy
        pip install -r {req_files_text}
        mypy --install-types --non-interactive ./{self.rel_mod_dpath}
        mypy ./{self.rel_mod_dpath}
        ''')
    return commands


def make_build_sdist_parts(self, wheelhouse_dpath='wheelhouse'):
    commands = [
        # 'python -m pip install pip -U',
        f'{self.UPDATE_PIP}',
        f'{self.PIP_INSTALL} setuptools>=0.8 wheel build twine',
        f'python -m build --sdist --outdir {wheelhouse_dpath}',
        f'python -m twine check ./{wheelhouse_dpath}/{self.mod_name}*.tar.gz',
    ]

    build_parts = {
        'commands': commands,
        'artifact': f"./{wheelhouse_dpath}/{self.mod_name}*.tar.gz"
    }
    return build_parts


def make_build_wheel_parts(self, wheelhouse_dpath='wheelhouse'):
    commands = [
        # 'python -m pip install pip -U',
        f'{self.UPDATE_PIP}',
        f'{self.PIP_INSTALL} setuptools>=0.8 wheel build twine',
        f'python -m build --wheel --outdir {wheelhouse_dpath}',
        f'python -m twine check ./{wheelhouse_dpath}/{self.mod_name}*.whl',
    ]

    build_wheel_parts = {
        'commands': commands,
        'artifact': f"./{wheelhouse_dpath}/{self.mod_name}*.whl"
    }
    return build_wheel_parts


def make_install_and_test_wheel_parts(self,
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

    import ubelt as ub
    get_wheel_fpath_bash = ub.codeblock(
        f'''
        python -c "if 1:
            import pathlib
            dist_dpath = pathlib.Path('{wheelhouse_dpath}')
            candidates = list(dist_dpath.glob('{self.mod_name}*.whl'))
            candidates += list(dist_dpath.glob('{self.mod_name}*.tar.gz'))
            fpath = sorted(candidates)[-1]
            print(str(fpath).replace(chr(92), chr(47)))
        "
        ''')

    if tuple(map(int, self.config.min_python.split('.'))) >= (3, 8):
        # Not sure why this fails on 3.6 / 3.7?
        # Use less ugly version when we can
        get_mod_version_bash = ub.codeblock(
            '''
            python -c "if 1:
                from pkginfo import Wheel, SDist
                import pathlib
                fpath = '$WHEEL_FPATH'
                cls = Wheel if fpath.endswith('.whl') else SDist
                item = cls(fpath)
                print(item.version)
            "
            ''')
    else:
        get_mod_version_bash = ub.codeblock(
            '''
            python -c "if 1:
                from pkginfo import Wheel, SDist
                import pathlib
                fpath = '$WHEEL_FPATH'
                cls = Wheel if fpath.endswith('.whl') else SDist
                item = cls(fpath)
                if item.version is None:
                    import re
                    # This is very fragile
                    fname = pathlib.Path(fpath).name
                    match = re.match(r'^([^-]+)-([^-]+)(.whl|.tar.gz)$', fname)
                    bs = chr(92)
                    pat = '([0-9]+' + bs + '.[0-9]+' + bs + '.[0-9]+)'
                    import re
                    # Not sure why version is None in 3.6 and 3.7
                    match = re.search(pat, fname)
                    assert match is not None
                    version = match.groups()[0]
                    print(version)
                else:
                    print(item.version)
            "
            ''')
    # get_mod_version_bash = ub.codeblock(
    #     r'''
    #     export MOD_VERSION=$(printf "$WHEEL_FPATH" | sed -E 's#.*/[^/]+-([0-9]+\.[0-9]+\.[0-9]+)[-.].*#\1#')
    #     '''
    # )
    # # Will this help?
    # get_mod_version_bash = ub.codeblock(
    #     '''
    #     python -c "if 1:
    #         from pkginfo import Wheel, SDist
    #         import sys
    #         f=sys.argv[1]
    #         cls=Wheel if f.endswith('.whl') else SDist
    #         print(cls(f).version)
    #     " "$WHEEL_FPATH"
    #     '''
    # )

    # get_modpath_python = "import ubelt; print(ubelt.modname_to_modpath(f'{self.mod_name}'))"
    get_modpath_python = f"import {self.mod_name}, os; print(os.path.dirname({self.mod_name}.__file__))"
    get_modpath_bash = f'python -c "{get_modpath_python}"'

    test_command = self.config['test_command']

    if test_command == 'auto':
        if 'ibeis' == self.mod_name:
            test_command = [
                'python -m xdoctest $MOD_DPATH --style=google all',
                'echo "xdoctest command finished"'
            ]
        else:
            test_command = [
                Yaml.CodeBlock('python -m pytest --verbose -p pytester -p no:doctest --xdoctest --cov-config ../pyproject.toml --cov-report term --durations=100 --cov="$MOD_NAME" "$MOD_DPATH" ../tests'),
                'echo "pytest command finished, moving the coverage file to the repo root"',
            ]
    else:
        if isinstance(test_command, str):
            test_command = [Yaml.CodeBlock(test_command)]

    # Note: export does not expose the environment variable to subsequent jobs.
    install_wheel_commands = [
        'echo "Finding the path to the wheel"',
        f'ls {wheelhouse_dpath} || echo "{wheelhouse_dpath} does not exist"',
        'echo "Installing helpers"',
        f'{self.UPDATE_PIP}',
        # 'pip install pip setuptools>=0.8 setuptools_scm wheel build -U',  # is this necessary?
        f'{self.PIP_INSTALL} setuptools>=0.8 setuptools_scm wheel build -U',  # is this necessary?
        f'{self.PIP_INSTALL} tomli pkginfo',
        # 'pip install delorean',
        f'export WHEEL_FPATH=$({get_wheel_fpath_bash})',
        # 'echo "WHEEL_FPATH=$WHEEL_FPATH"',
        f'export MOD_VERSION=$({get_mod_version_bash})',
        # 'echo "MOD_VERSION=$MOD_VERSION"',
    ] + special_install_lines + [
        'echo "WHEEL_FPATH=$WHEEL_FPATH"',
        'echo "INSTALL_EXTRAS=$INSTALL_EXTRAS"',
        'echo "MOD_VERSION=$MOD_VERSION"',

        # This helps but doesn't solve the problem.
        # https://github.com/Erotemic/xdoctest/pull/158#discussion_r1697092781
        # 'echo "Downloading dependencies from pypi"',
        # f'pip download "{self.mod_name}[$INSTALL_EXTRAS]==$MOD_VERSION" --dest wheeldownload',
        # f'echo "Overwriting pypi {self.mod_name} wheel"',
        # 'cp wheelhouse/* wheeldownload/',
        # f'pip install --prefer-binary "{self.mod_name}[$INSTALL_EXTRAS]==$MOD_VERSION" -f wheeldownload --no-index',

        f'{self.PIP_INSTALL_PREFER_BINARY} "{self.mod_name}[$INSTALL_EXTRAS]==$MOD_VERSION" -f {wheelhouse_dpath}',
        'echo "Install finished."',
    ]

    test_wheel_commands = [
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
            '''
            echo "
            ---
            MOD_DPATH = $MOD_DPATH
            ---
            running the pytest command inside the workspace
            ---
            "
            '''),
    ] + custom_before_test_lines + test_command + custom_after_test_commands

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
    if 'linux' in self.config['os']:
        os_list.append('ubuntu-latest')
    if 'osx' in self.config['os']:
        os_list.append('macOS-latest')
    if 'win' in self.config['os']:
        os_list.append('windows-latest')

    cpython_versions = self.config['ci_cpython_versions']
    pypy_versions = [
        f'pypy-{v}'
        for v in self.config['ci_pypy_versions']
    ]
    # 3.4 is broken on github actions it seems
    cpython_versions_non34 = [v for v in cpython_versions if v != '3.4']
    supported_py_versions = self.config['supported_python_versions']
    if len(supported_py_versions) == 0:
        raise Exception('no supported python versions?')

    # Choose which Python version will be the "main" one we use for version
    # agnostic jobs.
    main_python_version = supported_py_versions[-1]
    from xcookie import constants
    # import kwutil
    INFO_LUT = {row['version']: row for row in constants.KNOWN_PYTHON_VERSION_INFO}
    for pyver in supported_py_versions[::-1]:
        info = INFO_LUT[pyver]
        if info.get('is_prerelease'):
            continue
        main_python_version = pyver
        break

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
    print(f'cpython_versions_non34_={cpython_versions_non34_}')
    print(f'cpython_versions_non34_non_prerelease_={cpython_versions_non34_non_prerelease_}')

    extras_versions_templates = {
        'full-loose': self.config['ci_versions_full_loose'],
        'full-strict': self.config['ci_versions_full_strict'],
        'minimal-loose': self.config['ci_versions_minimal_loose'],
        'minimal-strict': self.config['ci_versions_minimal_strict'],
    }
    extras_versions = {}
    for k, v in extras_versions_templates.items():
        if v == '':
            v = []
        elif v == 'min':
            v = [cpython_versions_non34_[0]]
        elif v == 'max':
            v = [cpython_versions_non34_non_prerelease_[-1]]
            # v = [cpython_versions_non34_[-1]]
        elif v == '*':
            v = cpython_versions_non34 + pypy_versions
        else:
            raise KeyError(v)
        extras_versions[k] = v

    supported_platform_info = {
        'os_list': os_list,
        'cpython_versions': cpython_versions_non34,
        'pypy_versions': pypy_versions,
        'min_python_version': supported_py_versions[0],
        'max_python_version': supported_py_versions[-1],
        'main_python_version': main_python_version,
        'install_extra_versions': extras_versions,
    }
    return supported_platform_info
