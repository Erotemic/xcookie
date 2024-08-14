"""
Common subroutines for consitency between gitlab-ci / github actions / etc...
"""


def make_mypy_check_parts(self):
    import ubelt as ub

    type_requirement_files = [
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
        'python -m pip install setuptools>=0.8 wheel build twine',
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
        'python -m pip install setuptools>=0.8 wheel build twine',
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
    get_mod_version_bash = ub.codeblock(
        '''
        python -c "if 1:
            from pkginfo import Wheel, SDist
            fpath = '$WHEEL_FPATH'
            cls = Wheel if fpath.endswith('.whl') else SDist
            print(cls(fpath).version)
        "
        ''')

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

    # Note: export does not expose the enviornment variable to subsequent jobs.
    install_wheel_commands = [
        'echo "Finding the path to the wheel"',
        f'ls {wheelhouse_dpath} || echo "{wheelhouse_dpath} does not exist"',
        'echo "Installing helpers"',
        # 'pip install pip setuptools>=0.8 setuptools_scm wheel build -U',  # is this necessary?
        'pip install setuptools>=0.8 setuptools_scm wheel build -U',  # is this necessary?
        'pip install tomli pkginfo',
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

        f'pip install --prefer-binary "{self.mod_name}[$INSTALL_EXTRAS]==$MOD_VERSION" -f {wheelhouse_dpath}',
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
