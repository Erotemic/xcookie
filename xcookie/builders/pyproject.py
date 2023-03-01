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
            # "wheel",
            "scikit-build>=0.11.1",
            "numpy",
            "ninja>=1.10.2",
            "cmake>=3.21.2",
            "cython>=0.29.24",
        ]

        supported_cp_version = []
        for pyver in self.config['supported_python_versions']:
            supported_cp_version.append('cp' + pyver.replace('.', ''))

        wheel_build_patterns = []
        for cpver in supported_cp_version:
            wheel_build_patterns.append(cpver + '-*')

        pyproj_config['tool']['cibuildwheel'].update({
            'build': " ".join(wheel_build_patterns),
            'build-frontend': "build",
            # 'skip': "pp* cp27-* cp34-* cp35-* cp36-* *-musllinux_*",
            'skip': "pp* *-musllinux_*",
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
            # "wheel>=0.37.1",
        ]
        pyproj_config['build-system']['build-backend'] = 'setuptools.build_meta'

    WITH_PYTEST_INI = 1
    if WITH_PYTEST_INI:
        xdoctest_style = self.config['xdoctest_style']
        pytest_ini_opts = pyproj_config['tool']['pytest']['ini_options']
        pytest_ini_opts['addopts'] = f"-p no:doctest --xdoctest --xdoctest-style={xdoctest_style} --ignore-glob=setup.py --ignore-glob=dev --ignore-glob=docs"
        pytest_ini_opts['norecursedirs'] = ".git ignore build __pycache__ dev _skbuild docs"
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
        options_to_save = [
            'tags',
            'mod_name',
            'repo_name',
            'pkg_name',
            'rel_mod_parent_dpath',
            'os',
            'min_python',
            'version',
            'url',
            'author',
            'author_email',
            'description',
            'license',
            'dev_status',
            'typed',
            'remote_host',
            'remote_group',
        ]
        config_to_save = ub.dict_subset(self.config, options_to_save)
        pyproj_config['tool']['xcookie'].update(config_to_save)

    text = toml.dumps(pyproj_config)
    return text
