import ubelt as ub
import toml


def build_pyproject(self):
    """
    Returns:
        str: templated code
    """
    # data = toml.loads((self.template_dpath / 'pyproject.toml').read_text())
    # print('data = {}'.format(ub.urepr(data, nl=5)))
    pyproj_config = ub.AutoDict()
    use_setup_py = self.config.get('use_setup_py', True)
    pyproject_settings = self.config._load_xcookie_pyproject_settings()
    if pyproject_settings is None:
        pyproject_settings = {}
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

        test_extras = ["tests-strict", "runtime-strict"]
        if 'cv2' in self.config['tags']:
            test_extras += ["headless-strict"]

        pyproj_config['tool']['cibuildwheel'].update({
            'build': " ".join(wheel_build_patterns),
            'build-frontend': "build",
            # 'skip': "pp* cp27-* cp34-* cp35-* cp36-* *-musllinux_*",
            'skip': "pp* *-musllinux_*",
            'build-verbosity': 1,
            # 'test-requires': ["-r requirements/tests.txt"],
            'test-extras': test_extras,
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
            'use_setup_py',
        ]
        config_to_save = ub.dict_subset(self.config, options_to_save)
        pyproj_config['tool']['xcookie'].update(config_to_save)

    if not use_setup_py:
        project_block = pyproj_config['project']
        project_block['name'] = self.config['pkg_name']
        project_block['description'] = self.config['description']
        project_block['requires-python'] = f">={self.config['min_python']}"
        project_block['dynamic'] = [
            'version',
            'dependencies',
            'optional-dependencies',
        ]

        authors = self.config['author']
        author_emails = self.config['author_email']
        author_entries = []
        if authors:
            if not isinstance(authors, (list, tuple)):
                authors = [authors]
            if not isinstance(author_emails, (list, tuple)):
                author_emails = [author_emails] if author_emails else []
            for idx, name in enumerate(authors):
                entry = {'name': name}
                if idx < len(author_emails) and author_emails[idx]:
                    entry['email'] = author_emails[idx]
                elif isinstance(author_emails, str) and idx == 0:
                    entry['email'] = author_emails
                author_entries.append(entry)
        if author_entries:
            project_block['authors'] = author_entries

        project_block['classifiers'] = self._project_classifiers()
        if self.config['license']:
            project_block['license'] = {'text': self.config['license']}
        if self.config['url']:
            project_block['urls'] = {'Homepage': self.config['url']}
        if self.config['tags']:
            project_block['keywords'] = sorted({tag for tag in self.config['tags'] if tag})

        setuptools_block = pyproj_config['tool']['setuptools']
        setuptools_block['include-package-data'] = True
        setuptools_block['packages']['find']['where'] = [self.config['rel_mod_parent_dpath']]
        setuptools_block['packages']['find']['include'] = [f"{self.config['mod_name']}*"]

        if self.config['rel_mod_parent_dpath'] != '.':
            setuptools_block['package-dir'] = {'': self.config['rel_mod_parent_dpath']}

        package_data = setuptools_block['package-data']
        package_data['*'] = ["requirements/*.txt"]
        if self.config['typed']:
            package_data[self.mod_name] = ['py.typed', '*.pyi']
        for key, value in pyproject_settings.get('package_data', {}).items():
            normalized_key = '*' if key == '' else key
            package_data[normalized_key] = value

        setuptools_dynamic = setuptools_block['dynamic']
        setuptools_dynamic['version'] = {'attr': f"{self.config['mod_name']}.__version__"}
        setuptools_dynamic['readme'] = {'file': ['README.rst'], 'content-type': 'text/x-rst'}
        setuptools_dynamic['dependencies'] = {'file': ['requirements/runtime.txt']}

        extras = ['tests', 'optional', 'docs']
        if 'cv2' in self.tags:
            extras.extend(['headless', 'graphics'])
        if 'postgresql' in self.tags:
            extras.append('postgresql')

        optional_dynamic = {}
        for name in extras:
            optional_dynamic[name] = {'file': [f'requirements/{name}.txt']}
        setuptools_dynamic['optional-dependencies'] = optional_dynamic

        entry_points = pyproject_settings.get('entry_points', {})
        console_scripts = entry_points.get('console_scripts', [])
        if console_scripts:
            scripts = {}
            for item in console_scripts:
                name, _, target = item.partition('=')
                scripts[name.strip()] = target.strip()
            project_block['scripts'] = scripts

        extra_entry_points = {k: v for k, v in entry_points.items() if k != 'console_scripts'}
        if extra_entry_points:
            ep_table = {}
            for group, entries in extra_entry_points.items():
                group_entries = {}
                for item in entries:
                    name, _, target = item.partition('=')
                    group_entries[name.strip()] = target.strip()
                ep_table[group] = group_entries
            project_block['entry-points'] = ep_table

        pyproj_config['build-system'].setdefault('build-backend', 'setuptools.build_meta')

    text = toml.dumps(pyproj_config)
    return text
