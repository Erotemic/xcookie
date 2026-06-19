import datetime as _datetime
import json
import tempfile

import toml
import ubelt as ub

from xcookie.util.util_metadata import coerce_author_entries


def _resolve_uv_exclude_newer(self, pyproj_config):
    """Decide the ``[tool.uv] exclude-newer`` value to write.

    The supply-chain guard pins ``uv lock`` to ignore packages published
    after a given date. Behavior:

    * ``False``/``None`` → disable (do not emit the setting).
    * ``'auto'`` → preserve any existing value on disk; otherwise stamp
      today's UTC date.
    * any other string → use verbatim.
    """
    configured = self.config.get('uv_exclude_newer', 'auto')
    if configured in (False, None, 'false', 'False', 'off'):
        return None

    existing = (
        pyproj_config.get('tool', {})
        .get('uv', {})
        .get('exclude-newer')
    )
    if configured == 'auto':
        if existing:
            return existing
        return _datetime.date.today().isoformat()
    return str(configured)


def _autodictify(value):
    if isinstance(value, dict) and not isinstance(value, ub.AutoDict):
        return ub.AutoDict({k: _autodictify(v) for k, v in value.items()})
    if isinstance(value, list):
        return [_autodictify(v) for v in value]
    return value


# Common free-text license names mapped to SPDX identifiers.  PEP 639 (and
# setuptools >= 77) require the ``project.license`` field to be a string
# containing a valid SPDX expression rather than the older ``{text = ...}``
# table form.
_SPDX_LICENSE_ALIASES = {
    'Apache 2': 'Apache-2.0',
    'Apache 2.0': 'Apache-2.0',
    'Apache2': 'Apache-2.0',
    'BSD-3': 'BSD-3-Clause',
    'BSD3': 'BSD-3-Clause',
    'MIT': 'MIT',
    'GPL3': 'GPL-3.0-only',
}


def _coerce_spdx_license(value: str) -> str:
    """Coerce a configured license value into a valid SPDX expression."""
    return _SPDX_LICENSE_ALIASES.get(value, value)


def _build_xcookie_tool_config(self, pyproj_config):
    """Build the ``[tool.xcookie]`` block without leaking inferred defaults.

    ``XCookieConfig`` is resolved before builders run, so values such as
    ``version='0.0.1'``, ``pkg_name=mod_name``, and ``os=['linux', 'osx',
    'win']`` may be present even when the user never wrote them in
    ``pyproject.toml``.  Persisting those values creates noisy diffs and, in
    the case of ``version``, can produce stale metadata next to a dynamic
    PEP 621 version declaration.
    """
    existing_tool = pyproj_config.get('tool', {}).get('xcookie', {}) or {}
    existing_keys = set(existing_tool.keys())

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
        'use_pyproject_requirements',
    ]
    raw_config = ub.udict(ub.dict_subset(self.config, options_to_save))

    # Start with the explicit on-disk settings so nested user config such as
    # entry_points, package_data, and ci_blocklist survives regeneration.
    config_to_save = ub.udict(existing_tool)

    always_save = {
        'tags',
        'mod_name',
        'repo_name',
        'min_python',
        'url',
        'author',
        'author_email',
        'description',
        'typed',
        'use_setup_py',
        'use_pyproject_requirements',
    }

    default_os = {'linux', 'osx', 'win'}

    for key, value in raw_config.items():
        if value is None:
            continue

        should_save = key in always_save or key in existing_keys

        if key == 'pkg_name':
            # ``pkg_name`` is derived from ``mod_name`` unless explicitly
            # customized.  Avoid rewriting redundant defaults.
            should_save = should_save or value != self.config['mod_name']
        elif key == 'rel_mod_parent_dpath':
            should_save = should_save or value not in {'.', ''}
        elif key == 'os':
            os_values = set(value) if not isinstance(value, str) else {value}
            should_save = should_save or os_values != default_os
        elif key == 'version':
            # Do not introduce the resolver's placeholder version.  If a
            # project already has a real or dynamic PEP 621 version, that is
            # the authoritative source.  Preserve explicit tool.xcookie
            # versions for backwards compatibility.
            should_save = key in existing_keys and value != '0.0.1'
        elif key == 'license':
            should_save = should_save or value not in {
                'Apache 2',
                'Apache 2.0',
                'Apache-2.0',
            }
        elif key == 'dev_status':
            should_save = should_save or value != 'planning'
        elif key in {'remote_host', 'remote_group'}:
            # These are usually inferred from the URL and need not be persisted
            # unless the user explicitly had them on disk already.
            should_save = key in existing_keys

        if should_save:
            config_to_save[key] = value
        elif key in config_to_save:
            # If a previously explicit value has become the default, leave it
            # alone rather than deleting user-authored config.
            pass

    return dict(config_to_save)


def build_pyproject(self):
    """
    Returns:
        str: templated code
    """
    # Start from the existing pyproject.toml when available so unrelated
    # sections survive a regen.
    pyproj_config = _autodictify(self.config._load_pyproject_config() or {})
    use_setup_py = self.config.get('use_setup_py', True)
    pyproject_settings = self.config._load_xcookie_pyproject_settings()
    if pyproject_settings is None:
        pyproject_settings = {}
    # {'tool': {}}
    if 'binpy' in self.config['tags']:
        build_system_requires = list(
            pyproj_config['build-system'].get('requires') or []
        )
        build_system_requires.extend(
            [
                'setuptools>=77',
                # setuptools_scm[toml]
                # "wheel",
                'scikit-build>=0.11.1',
                'numpy',
                'ninja>=1.10.2',
                'cmake>=3.21.2',
                'cython>=0.29.24',
            ]
        )
        pyproj_config['build-system']['requires'] = list(
            ub.oset(build_system_requires)
        )

        supported_cp_version = []
        for pyver in self.config['supported_python_versions']:
            supported_cp_version.append('cp' + pyver.replace('.', ''))

        wheel_build_patterns = []
        for cpver in supported_cp_version:
            wheel_build_patterns.append(cpver + '-*')

        test_extras = ['tests-strict', 'runtime-strict']
        if 'cv2' in self.config['tags']:
            test_extras += ['headless-strict']

        skip_tokens = ['pp*', '*-musllinux_*']
        if 'win' in self.config['os']:
            for pyver in self.config['supported_python_versions']:
                pyver_parts = tuple(int(p) for p in str(pyver).split('.')[:2])
                if pyver_parts < (3, 11):
                    skip_tokens.append(
                        'cp' + str(pyver).replace('.', '') + '-win_arm64'
                    )

        pyproj_config['tool']['cibuildwheel'].update(
            {
                'build': ' '.join(wheel_build_patterns),
                'build-frontend': 'build',
                # 'skip': "pp* cp27-* cp34-* cp35-* cp36-* *-musllinux_*",
                'skip': ' '.join(ub.oset(skip_tokens)),
                'build-verbosity': 1,
                # 'test-requires': ["-r requirements/tests.txt"],
                'test-extras': test_extras,
                'test-command': 'python {project}/run_tests.py',
            }
        )

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
                ],
            }
            for plat in req_commands.keys():
                cmd = ' && '.join(req_commands[plat])
                cibw[plat]['before-all'] = cmd
    else:
        build_system_requires = list(
            pyproj_config['build-system'].get('requires') or []
        )
        build_system_requires.extend(
            [
                'setuptools>=77',
                # setuptools_scm[toml]
                # "wheel>=0.37.1",
            ]
        )
        pyproj_config['build-system']['requires'] = list(
            ub.oset(build_system_requires)
        )
        pyproj_config['build-system'].setdefault(
            'build-backend', 'setuptools.build_meta'
        )

    if self.config.get('use_uv'):
        exclude_newer = _resolve_uv_exclude_newer(self, pyproj_config)
        if exclude_newer:
            tool_uv = pyproj_config['tool'].get('uv') or {}
            tool_uv['exclude-newer'] = exclude_newer
            pyproj_config['tool']['uv'] = tool_uv

    WITH_PYTEST_INI = 1
    if WITH_PYTEST_INI:
        xdoctest_style = self.config['xdoctest_style']
        pytest_ini_opts = pyproj_config['tool']['pytest']['ini_options']
        pytest_ini_opts['addopts'] = (
            f'-p no:doctest --xdoctest --xdoctest-style={xdoctest_style} --ignore-glob=setup.py --ignore-glob=dev --ignore-glob=docs'
        )
        pytest_ini_opts['norecursedirs'] = (
            '.git ignore build __pycache__ dev _skbuild docs'
        )
        pytest_ini_opts['filterwarnings'] = [
            'default',
            'ignore:.*No cfgstr given in Cacher constructor or call.*:Warning',
            'ignore:.*Define the __nice__ method for.*:Warning',
            'ignore:.*private pytest class or function.*:Warning',
        ]

    WITH_COVERAGE = 1
    if WITH_COVERAGE:
        pyproj_config['tool']['coverage'].update(
            toml.loads(
                ub.codeblock(
                    """
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
            """
                ).format(REPO_NAME=self.repo_name)
            )
        )

    pyproj_config['tool']['mypy']['ignore_missing_imports'] = True

    WITH_XCOOKIE = 1
    if WITH_XCOOKIE:
        pyproj_config['tool']['xcookie'] = _build_xcookie_tool_config(
            self, pyproj_config
        )

    use_pyproject_requirements = self.config.get('use_pyproject_requirements')

    if not use_setup_py:
        project_block = pyproj_config['project']
        project_block['name'] = self.config['pkg_name']
        project_block['description'] = self.config['description']
        project_block['requires-python'] = f'>={self.config["min_python"]}'
        dynamic_entries = list(project_block.get('dynamic', []))
        dynamic_entries.append('version')
        if not use_pyproject_requirements:
            dynamic_entries.extend(['dependencies', 'optional-dependencies'])
        project_block['dynamic'] = list(ub.oset(dynamic_entries))
        project_block.pop('version', None)
        if not use_pyproject_requirements:
            for key in ['dependencies', 'optional-dependencies']:
                project_block.pop(key, None)

        author_entries = coerce_author_entries(
            self.config['author'], self.config['author_email']
        )
        if author_entries:
            project_block['authors'] = author_entries

        project_block['classifiers'] = self._project_classifiers()
        if self.config['license']:
            # PEP 639: ``license`` is a string SPDX expression; license files
            # are listed separately under ``license-files``.
            project_block['license'] = _coerce_spdx_license(
                self.config['license']
            )
            project_block['license-files'] = ['LICENSE']
        if self.config['url']:
            urls = project_block.get('urls', {})
            urls['Homepage'] = str(self.config['url'])
            project_block['urls'] = urls

        setuptools_block = pyproj_config['tool']['setuptools']
        setuptools_block['include-package-data'] = True
        if isinstance(setuptools_block.get('packages'), list):
            setuptools_block['packages'] = ub.AutoDict()
        setuptools_block['packages']['find']['where'] = [
            self.config['rel_mod_parent_dpath']
        ]
        setuptools_block['packages']['find']['include'] = [
            f'{self.config["mod_name"]}*'
        ]

        if self.config['rel_mod_parent_dpath'] != '.':
            setuptools_block['package-dir'] = {
                '': self.config['rel_mod_parent_dpath']
            }

        package_data = setuptools_block['package-data']
        package_data['*'] = ['requirements/*.txt']
        if self.config['typed']:
            package_data[self.mod_name] = ['py.typed', '*.pyi']
        for key, value in pyproject_settings.get('package_data', {}).items():
            normalized_key = '*' if key == '' else key
            package_data[normalized_key] = value

        setuptools_dynamic = setuptools_block['dynamic']
        setuptools_dynamic['version'] = {
            'attr': f'{self.config["mod_name"]}.__version__'
        }
        readme_fpath = self._readme_fpath()
        setuptools_dynamic['readme'] = {
            'file': [readme_fpath.name],
            'content-type': self._readme_content_type(),
        }
        if not use_pyproject_requirements:
            setuptools_dynamic['dependencies'] = {
                'file': ['requirements/runtime.txt']
            }

            extras = ['tests', 'optional', 'docs']
            if 'cv2' in self.tags:
                extras.extend(['headless', 'graphics'])
            if 'postgresql' in self.tags:
                extras.append('postgresql')

            # Auto-discover any additional requirements/<name>.txt files so
            # they become optional extras. Mirrors the legacy setup.py
            # builder which exposed one extra per requirements file.
            requirements_dpath = self.repodir / 'requirements'
            if requirements_dpath.exists():
                discovered = sorted(
                    f.stem for f in requirements_dpath.glob('*.txt')
                )
                # ``runtime`` is the install_requires source, not an extra.
                extras = list(ub.oset(extras + [
                    name for name in discovered if name != 'runtime'
                ]))

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

        extra_entry_points = {
            k: v for k, v in entry_points.items() if k != 'console_scripts'
        }
        if extra_entry_points:
            ep_table = {}
            for group, entries in extra_entry_points.items():
                group_entries = {}
                for item in entries:
                    name, _, target = item.partition('=')
                    group_entries[name.strip()] = target.strip()
                ep_table[group] = group_entries
            project_block['entry-points'] = ep_table

        pyproj_config['build-system'].setdefault(
            'build-backend', 'setuptools.build_meta'
        )

    try:
        # fix GitURL issue
        pyproj_config['tool']['xcookie']['url'] = str(
            pyproj_config['tool']['xcookie']['url']
        )
    except KeyError:
        ...

    text = toml.dumps(pyproj_config)
    try:
        from pyproject_fmt import run as pyproject_fmt_run
    except Exception:
        return text

    with tempfile.TemporaryDirectory() as temp_dpath:
        temp_fpath = ub.Path(temp_dpath) / 'pyproject.toml'
        temp_fpath.write_text(text)
        pyproject_fmt_run(
            [
                '--no-generate-python-version-classifiers',
                '--keep-full-version',
                '--no-print-diff',
                str(temp_fpath),
            ]
        )
        text = temp_fpath.read_text()

    project_name = pyproj_config.get('project', {}).get('name')
    if project_name:
        section_name = None
        fixed_lines = []
        for line in text.splitlines():
            if line.startswith('[') and line.endswith(']'):
                section_name = line.strip()[1:-1]
                fixed_lines.append(line)
                continue
            if section_name == 'project' and line.lstrip().startswith('name = '):
                indent = line[: len(line) - len(line.lstrip())]
                line = f'{indent}name = {json.dumps(project_name)}'
            fixed_lines.append(line)
        text = '\n'.join(fixed_lines)
    return text
