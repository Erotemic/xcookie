"""
Common subroutines for consitency between gitlab-ci / github actions / etc...
"""


def make_build_wheel_parts(self, wheelhouse_dpath='wheelhouse'):
    commands = [
        # 'python -m pip install pip -U',
        'python -m pip install setuptools>=0.8 wheel build',
        f'python -m build --wheel --outdir {wheelhouse_dpath}',
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
                                      test_command='auto',
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

    get_wheel_fpath_python = Yaml.CodeBlock(f"import pathlib; print(str(sorted(pathlib.Path('{wheelhouse_dpath}').glob('{self.mod_name}*.whl'))[-1]).replace(chr(92), chr(47)))")
    # get_wheel_fpath_python = f"import pathlib; print(str(sorted(pathlib.Path('{wheelhouse_dpath}').glob('{self.mod_name}*.whl'))[-1]).replace(r'\\', '/'))"
    get_wheel_fpath_bash = f'python -c "{get_wheel_fpath_python}"'

    get_mod_version_python = "from pkginfo import Wheel; print(Wheel('$WHEEL_FPATH').version)"
    get_mod_version_bash = f'python -c "{get_mod_version_python}"'

    # get_modpath_python = "import ubelt; print(ubelt.modname_to_modpath(f'{self.mod_name}'))"
    get_modpath_python = f"import {self.mod_name}, os; print(os.path.dirname({self.mod_name}.__file__))"
    get_modpath_bash = f'python -c "{get_modpath_python}"'

    if test_command == 'auto':
        test_command = [
            Yaml.CodeBlock(f'python -m pytest --verbose -p pytester -p no:doctest --xdoctest --cov-config ../pyproject.toml --cov-report term --cov="{self.mod_name}" "$MOD_DPATH" ../tests'),
            'echo "pytest command finished, moving the coverage file to the repo root"',
        ]

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
