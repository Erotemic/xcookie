import ubelt as ub
import toml


def build_pyproject(self):
    """
    Returns:
        str: templated code
    """
    # data = toml.loads((self.template_dpath / 'pyproject.toml').read_text())
    # print('data = {}'.format(ub.repr2(data, nl=5)))
    pyproj_config = ub.AutoDict()
    # {'tool': {}}
    if 'binpy' in self.config['tags']:
        pyproj_config['build-system']['requires'] = [
            "setuptools>=41.0.1",
            # setuptools_scm[toml]
            "wheel",
            "scikit-build>=0.9.0",
            "numpy",
            "ninja"
            "cmake"
        ]
        pyproj_config['tool']['cibuildwheel'].update({
            'build': "cp37-* cp38-* cp39-* cp310-*",
            'build-frontend': "build",
            'skip': "pp* cp27-* cp34-* cp35-* cp36-* *-musllinux_*",
            'build-verbosity': 1,
            'test-requires': ["-r requirements/tests.txt"],
            'test-command': "python {project}/run_tests.py"
        })

        if True:
            cibw = pyproj_config['tool']['cibuildwheel']
            req_commands = {
                'linux': [
                    'yum install epel-release lz4 lz4-devel -y',
                ],
                'windows': [
                    'choco install lz4 -y',
                ],
                'macos': [
                    'brew install lz4',
                ]
            }
            for plat in req_commands.keys():
                cmd = ' && '.join(req_commands[plat])
                cibw[plat]['before-all'] = cmd
    else:
        pyproj_config['build-system']['requires'] = [
            "setuptools>=41.0.1",
            # setuptools_scm[toml]
            "wheel>=0.37.1",
        ]

    WITH_PYTEST_INI = 1
    if WITH_PYTEST_INI:
        pytest_ini_opts = pyproj_config['tool']['pytest']['ini_options']
        pytest_ini_opts['addopts'] = "-p no:doctest --xdoctest --xdoctest-style=google --ignore-glob=setup.py"
        pytest_ini_opts['norecursedirs'] = ".git ignore build __pycache__ dev _skbuild"
        pytest_ini_opts['filterwarnings'] = [
            "default",
            "ignore:.*No cfgstr given in Cacher constructor or call.*:Warning",
            "ignore:.*Define the __nice__ method for.*:Warning",
            "ignore:.*private pytest class or function.*:Warning",
        ]

    WITH_COVERAGE = 1
    if WITH_COVERAGE:
        pyproj_config['tool']['coverage'].update(toml.loads(ub.codeblock(
            '''
            [run]
            branch = true

            [report]
            exclude_lines =[
                "pragma: no cover",
                ".*  # pragma: no cover",
                ".*  # nocover",
                "def __repr__",
                "raise AssertionError",
                "raise NotImplementedError",
                "if 0:",
                "if trace is not None",
                "verbose = .*",
                "^ *raise",
                "^ *pass *$",
                "if _debug:",
                "if __name__ == .__main__.:",
                ".*if six.PY2:"
            ]

            omit=[
                "{REPO_NAME}/__main__.py",
                "*/setup.py"
            ]
            ''').format(REPO_NAME=self.repo_name)))

    pyproj_config['tool']['mypy']['ignore_missing_imports'] = True

    WITH_XCOOKIE = 1
    if WITH_XCOOKIE:
        pyproj_config['tool']['xcookie'].update(toml.loads(ub.codeblock(
            f'''
            tags = {self.config['tags']}
            mod_name = "{self.config['mod_name']}"
            repo_name = "{self.config['repo_name']}"
            ''')))

    text = toml.dumps(pyproj_config)
    return text
