import json
import tempfile

import toml
import ubelt as ub

from xcookie.requirements_layout import RequirementsLayout
from xcookie.util.util_metadata import coerce_author_entries




_METADATA_IGNORED_PIP_OPTIONS = (
    '--extra-index-url',
    '--find-links',
    '--index-url',
    '--pre',
    '--prefer-binary',
    '--trusted-host',
    '-f',
    '-i',
)


def _parse_requirement_file_for_metadata(fpath):
    """Separate package requirements from pip-only composition/policy."""
    fpath = ub.Path(fpath)
    direct_lines = []
    include_fpaths = []
    ignored_lines = []
    if not fpath.exists():
        return direct_lines, include_fpaths, ignored_lines

    for lineno, line in enumerate(fpath.read_text().splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue

        include_target = None
        if stripped.startswith('-r '):
            include_target = stripped[3:].strip()
        elif stripped.startswith('--requirement '):
            include_target = stripped[len('--requirement '):].strip()
        if include_target is not None:
            include_fpaths.append(fpath.parent / include_target)
            continue

        if stripped.startswith(_METADATA_IGNORED_PIP_OPTIONS):
            ignored_lines.append(stripped)
            continue
        if stripped.startswith('-'):
            raise ValueError(
                'cannot represent pip requirement directive in package '
                f'metadata: {fpath}: line {lineno}: {stripped!r}'
            )

        # The legacy setup.py parser tolerated an inline find-links suffix.
        # Keep that pip-facing syntax out of package metadata.
        if ' --find-links ' in stripped:
            stripped = stripped.split(' --find-links ', 1)[0].rstrip()
            ignored_lines.append(line.strip())
        direct_lines.append(stripped)

    return direct_lines, include_fpaths, ignored_lines


def _requirement_file_needs_metadata_copy(fpath):
    """Whether a requirements file needs a companion for its local entries."""
    direct_lines, include_fpaths, ignored_lines = (
        _parse_requirement_file_for_metadata(fpath)
    )
    return bool(direct_lines and (include_fpaths or ignored_lines))


def _build_setuptools_requirement_metadata_text(fpath):
    """Build metadata for only the direct requirements in one pip file.

    Recursive ``-r`` composition is represented by multiple paths in
    ``tool.setuptools.dynamic`` instead of duplicating transitive requirements
    into this companion file. Installer-only options are omitted.
    """
    direct_lines, _, _ = _parse_requirement_file_for_metadata(fpath)
    return '\n'.join(direct_lines) + ('\n' if direct_lines else '')



def _dynamic_requirement_relpaths(self, name):
    """Resolve one pip requirements file into setuptools metadata sources."""
    root_fpath = self.repodir / 'requirements' / f'{name}.txt'
    if not root_fpath.exists():
        # New projects may not have requirement files on disk until staging.
        # Standard generated requirement files are metadata-safe.
        return [f'requirements/{name}.txt']

    result = []
    stack = []

    def _visit(fpath):
        fpath = ub.Path(fpath)
        if fpath in stack:
            chain = ' -> '.join(map(str, stack + [fpath]))
            raise ValueError(f'cyclic requirement include: {chain}')
        if not fpath.exists():
            raise ValueError(f'requirement include does not exist: {fpath}')

        stack.append(fpath)
        try:
            direct_lines, include_fpaths, ignored_lines = (
                _parse_requirement_file_for_metadata(fpath)
            )
            relpath = fpath.relative_to(self.repodir).as_posix()
            if direct_lines:
                if include_fpaths or ignored_lines:
                    metadata_relpath = fpath.with_name(
                        fpath.stem + '-metadata.txt'
                    ).relative_to(self.repodir).as_posix()
                    result.append(metadata_relpath)
                else:
                    result.append(relpath)
            for include_fpath in include_fpaths:
                _visit(include_fpath)
        finally:
            stack.pop()

    _visit(root_fpath)
    return list(ub.oset(result))



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
        'typecheck_extra_paths',
        'ci_prerelease_python_policy',
        'remote_host',
        'remote_group',
        'use_setup_py',
        'use_pyproject_requirements',
        'requirements_package',
    ]
    raw_config = ub.udict(ub.dict_subset(self.config, options_to_save))

    # Start with the explicit on-disk settings so nested user config such as
    # entry_points, package_data, ci_blocklist, ci_allow_failure, and other
    # explicit CI customization
    # survive regeneration.
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
        'requirements_package',
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
        elif key == 'typecheck_extra_paths':
            should_save = should_save or bool(value)
        elif key == 'ci_prerelease_python_policy':
            should_save = should_save or value != 'allow-failure'
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
        has_static_readme = 'readme' in project_block
        if not has_static_readme:
            dynamic_entries.append('readme')
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

        def _merge_package_data(key, values):
            existing = package_data.get(key, []) or []
            if isinstance(existing, str):
                existing = [existing]
            if isinstance(values, str):
                values = [values]
            package_data[key] = list(ub.oset([*existing, *values]))

        _merge_package_data('*', ['requirements/*.txt'])
        requirements_layout = RequirementsLayout.from_config(self.config)
        if requirements_layout.package is not None:
            _merge_package_data(
                requirements_layout.package,
                requirements_layout.package_data_patterns,
            )
        if self.config['typed']:
            _merge_package_data(self.mod_name, ['py.typed'])
        for key, value in pyproject_settings.get('package_data', {}).items():
            normalized_key = '*' if key == '' else key
            _merge_package_data(normalized_key, value)

        setuptools_dynamic = setuptools_block['dynamic']
        setuptools_dynamic['version'] = {
            'attr': f'{self.config["mod_name"]}.__version__'
        }
        if has_static_readme:
            setuptools_dynamic.pop('readme', None)
        else:
            readme_fpath = self._readme_fpath()
            setuptools_dynamic['readme'] = {
                'file': [readme_fpath.name],
                'content-type': self._readme_content_type(),
            }
        if not use_pyproject_requirements:
            runtime_req_relpaths = _dynamic_requirement_relpaths(
                self, 'runtime'
            )
            setuptools_dynamic['dependencies'] = {
                'file': runtime_req_relpaths
            }

            previous_optional_dynamic = dict(
                setuptools_dynamic.get('optional-dependencies', {}) or {}
            )
            extras = ['tests', 'optional', 'docs']
            extras.extend(
                name for name in previous_optional_dynamic if name != 'all'
            )
            if 'cv2' in self.tags:
                extras.extend(['headless', 'graphics'])
            if 'postgresql' in self.tags:
                extras.append('postgresql')
            if 'gdal' in self.tags:
                extras.append('gdal')

            # Auto-discover additional standalone requirements files. Files
            # used only as ``-r`` composition fragments are implementation
            # details, not public install extras, unless the project already
            # exposed them explicitly above.
            requirements_dpath = self.repodir / 'requirements'
            if requirements_dpath.exists():
                discovered_fpaths = sorted(requirements_dpath.glob('*.txt'))
                included_names = set()
                for req_fpath in discovered_fpaths:
                    if req_fpath.stem.endswith('-metadata'):
                        continue
                    _, include_fpaths, _ = _parse_requirement_file_for_metadata(
                        req_fpath
                    )
                    for include_fpath in include_fpaths:
                        if include_fpath.parent == requirements_dpath:
                            included_names.add(include_fpath.stem)
                discovered = [
                    f.stem
                    for f in discovered_fpaths
                    if not f.stem.endswith('-metadata')
                    and f.stem != 'runtime'
                    and f.stem not in included_names
                ]
                extras = list(ub.oset(extras + discovered))

            optional_dynamic = {}
            for name in extras:
                req_relpaths = _dynamic_requirement_relpaths(self, name)
                optional_dynamic[name] = {'file': req_relpaths}

            # Recreate the legacy ``all`` convenience extra so users can run
            # ``pip install pkg[all]``. setuptools concatenates a list of
            # requirement files for a single dynamic extra, so no aggregate
            # file needs to be generated. Development-only extras are excluded
            # because ``all`` is meant for end users pulling in optional runtime
            # features. The loose/strict distinction is handled by lock-file
            # constraints in CI, so there is intentionally no ``all-strict``.
            DEV_EXTRAS = {'tests', 'docs', 'linting'}
            all_extra_names = [
                name
                for name in extras
                if name not in DEV_EXTRAS and name != 'all'
            ]
            if all_extra_names:
                optional_dynamic['all'] = {
                    'file': list(
                        ub.oset(
                            relpath
                            for name in all_extra_names
                            for relpath in _dynamic_requirement_relpaths(
                                self, name
                            )
                        )
                    )
                }

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

    # Normalize the package name after serialization.
    project_name = pyproj_config.get('project', {}).get('name')
    section_name = None
    fixed_lines = []
    for line in text.splitlines():
        if line.startswith('[') and line.endswith(']'):
            section_name = line.strip()[1:-1]
        if (
            project_name
            and section_name == 'project'
            and line.lstrip().startswith('name = ')
        ):
            indent = line[: len(line) - len(line.lstrip())]
            line = f'{indent}name = {json.dumps(project_name)}'
        fixed_lines.append(line)
    # ``splitlines`` drops the trailing newline; restore it so the rewritten
    # file keeps a POSIX-friendly final newline.
    text = '\n'.join(fixed_lines) + '\n'
    return text
