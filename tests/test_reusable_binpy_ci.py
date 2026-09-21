import toml

from xcookie.builders import ci_model, common_ci
from xcookie.main import TemplateApplier, XCookieConfig
from xcookie.util_yaml import Yaml


def _make_applier(tmp_path, *, tags):
    cfg = XCookieConfig(
        repodir=tmp_path,
        repo_name='demo_pkg',
        mod_name='demo_pkg',
        tags=tags,
        min_python='3.10',
        max_python='3.12',
        interactive=False,
        use_vcs=False,
        use_setup_py=True,
        test_variants=['minimal-strict', 'full-loose'],
    )
    cfg['enable_gpg'] = False
    cfg['deploy'] = False
    cfg['linter'] = False
    cfg['ci_cpython_versions'] = ['3.10', '3.11', '3.12']
    self = TemplateApplier(cfg)
    self._presetup()
    return self


def _configure_reusable_ci(self):
    self.config['ci_reusable_wheels'] = True
    self.config['ci_wheel_build_post_commands'] = [
        'python dev/check_wheel_artifact.py wheelhouse/demo_pkg*.whl'
    ]
    self.config['test_env'] = {'DEMO_FORCE_RUNTIME': '1'}
    self.config['ci_source_checks'] = {
        'backend-parity': {
            'name': 'Backend parity',
            'python_version': '3.12',
            'setup_commands': [
                'export DEMO_TOOLCHAIN=/tmp/demo-toolchain',
                'python -m pip install -r requirements/tests.txt',
            ],
            'commands': [
                'test "$DEMO_TOOLCHAIN" = /tmp/demo-toolchain',
                './dev/check_backend_parity.sh',
            ],
            'env': {'DEMO_FORCE_BACKEND': '1'},
            'allow_failure': True,
        }
    }
    # Rebuild the shared plan after mutating test configuration.
    return TemplateApplier(self.config)


def test_reusable_wheel_contract_drives_github_ci(tmp_path):
    self = _make_applier(tmp_path, tags=['github', 'binpy'])
    self = _configure_reusable_ci(self)
    self._presetup()

    tests_text = self.build_github_actions_tests()
    checks_text = self.build_github_actions_checks()
    release_text = self.build_github_actions_release()

    # Reusable wheels are selected by pyproject.toml instead of a per-python
    # matrix override. This covers py3-none and stable ABI wheels such as abi3.
    assert 'cibw_skip:' not in tests_text
    assert 'CIBW_SKIP' not in tests_text
    assert 'stable-ABI wheels' in tests_text

    # Binary test jobs should download only the artifact from their platform,
    # rather than merging Linux/macOS/Windows wheelhouses together.
    assert 'Download wheel for this platform' in tests_text
    assert 'name: wheels-${{ matrix.os }}-${{ matrix.arch }}' in tests_text
    assert 'merge-multiple: true' not in tests_text
    assert "DEMO_FORCE_RUNTIME: '1'" in tests_text

    # Project-owned wheel validation runs for both ordinary and release builds.
    for text in [tests_text, release_text]:
        assert 'Validate built wheel artifacts' in text
        assert (
            'python dev/check_wheel_artifact.py wheelhouse/demo_pkg*.whl'
            in text
        )

    # Source parity is normal CI evidence, but it has its own workflow rather
    # than being embedded in the expensive test matrix or release pipeline.
    assert 'check_backend_parity:' not in tests_text
    assert 'check_backend_parity:' in checks_text
    assert 'Backend parity' in checks_text
    assert 'export DEMO_TOOLCHAIN=/tmp/demo-toolchain' in checks_text
    assert 'test "$DEMO_TOOLCHAIN" = /tmp/demo-toolchain' in checks_text
    assert './dev/check_backend_parity.sh' in checks_text
    assert 'DEMO_FORCE_BACKEND: \'1\'' in checks_text
    assert 'continue-on-error: true' in checks_text
    assert 'pull_request:' in checks_text
    assert 'check_backend_parity:' not in release_text


def test_reusable_release_matrix_covers_required_native_architectures(tmp_path):
    self = _make_applier(tmp_path, tags=['github', 'binpy'])
    self = _configure_reusable_ci(self)
    self._presetup()

    release = Yaml.loads(self.build_github_actions_release())
    matrix = release['jobs']['build_binpy_wheels']['strategy']['matrix']
    assert matrix['include'] == [
        {'os': 'ubuntu-latest', 'arch': 'auto'},
        {'os': 'ubuntu-24.04-arm', 'arch': 'auto'},
        {'os': 'macos-15', 'arch': 'auto'},
        {'os': 'macos-15-intel', 'arch': 'auto'},
        {'os': 'windows-latest', 'arch': 'auto'},
    ]

    # The deployment jobs are intentionally downstream of the whole matrix;
    # no platform is optional just to make publication proceed.
    assert matrix.get('exclude') is None
    assert release['jobs']['build_binpy_wheels']['strategy']['fail-fast'] is False
    build_step = next(
        step
        for step in release['jobs']['build_binpy_wheels']['steps']
        if step.get('name') == 'Build binary wheels'
    )
    assert build_step['env']['CIBW_ARCHS_WINDOWS'] == 'auto64'
    assert build_step['env']['CIBW_ARCHS_MACOS'] == 'auto64'


def test_reusable_wheel_contract_drives_gitlab_ci(tmp_path):
    self = _make_applier(tmp_path, tags=['gitlab', 'binpy'])
    self = _configure_reusable_ci(self)
    self._presetup()

    manifest_text = self.build_gitlab_ci()
    manifest = Yaml.loads(manifest_text)
    main_text = self.build_gitlab_ci_main()
    body = Yaml.loads(main_text)
    checks_text = self.build_gitlab_ci_checks()
    checks = Yaml.loads(checks_text)

    assert manifest['include'] == [
        {'local': '.gitlab/ci/main.yml'},
        {'local': '.gitlab/ci/checks.yml'},
    ]

    reusable_builds = [key for key in body if key.startswith('build/reusable-')]
    assert reusable_builds == ['build/reusable-linux-x86_64']
    build_name = reusable_builds[0]
    assert 'variables' not in body[build_name]

    binary_test_jobs = {
        key: job
        for key, job in body.items()
        if key.startswith('test/') and not key.startswith('test/sdist/')
    }
    assert binary_test_jobs
    assert all(job['needs'] == [build_name] for job in binary_test_jobs.values())
    inherited_test_env = body['.common_test_template'].get('variables', {})
    assert inherited_test_env['DEMO_FORCE_RUNTIME'] == '1'
    for job in binary_test_jobs.values():
        variables = job.get('variables', inherited_test_env)
        assert variables['DEMO_FORCE_RUNTIME'] == '1'

    # The selector stays in pyproject.toml; GitLab must not override it once
    # per test interpreter.
    assert 'CIBW_BUILD:' not in main_text

    assert (
        'python dev/check_wheel_artifact.py wheelhouse/demo_pkg*.whl'
        in body['.cibuildwheel_template']['script']
    )
    assert 'check/backend-parity' not in body
    parity = checks['check/backend-parity']
    assert parity['stage'] == 'test'
    assert parity['image'] == 'python:3.12'
    assert 'python -m pip install -r requirements/tests.txt' in parity['script']
    assert './dev/check_backend_parity.sh' in parity['script']
    assert parity['variables']['DEMO_FORCE_BACKEND'] == '1'
    assert parity['except']['refs'] == ['release']
    assert parity['allow_failure'] is True

    release_plan = ci_model.make_release_plan(self, provider='gitlab')
    assert release_plan.build_job_keys == ('build/reusable-linux-x86_64',)


def test_historical_versionless_flag_is_still_reusable(tmp_path):
    self = _make_applier(tmp_path, tags=['github', 'binpy'])
    assert not common_ci.uses_reusable_binary_wheels(self)
    self.config['ci_versionless_wheels'] = True
    assert common_ci.uses_reusable_binary_wheels(self)


def test_reusable_legacy_binpy_defaults_to_minimum_build_selector(tmp_path):
    self = _make_applier(tmp_path, tags=['github', 'binpy'])
    self.config['ci_reusable_wheels'] = True
    text = self.build_pyproject()
    data = toml.loads(text)
    assert data['tool']['cibuildwheel']['build'] == 'cp310-*'
    assert data['tool']['cibuildwheel']['archs'] == ['auto64']


def test_reusable_local_wheel_helper_honors_pyproject_selector(tmp_path):
    self = _make_applier(tmp_path, tags=['github', 'binpy'])
    self = _configure_reusable_ci(self)
    self._presetup()

    text = common_ci.build_wheels_script(self)
    assert 'LOCAL_CP_VERSION=' not in text
    assert 'CIBW_BUILD = <from pyproject.toml>' in text
    assert 'rm -rf wheelhouse' in text
    assert 'cibuildwheel --config-file pyproject.toml' in text
    assert (
        'python dev/check_wheel_artifact.py wheelhouse/demo_pkg*.whl' in text
    )


def test_nonreusable_local_wheel_helper_keeps_current_python_shortcut(tmp_path):
    self = _make_applier(tmp_path, tags=['github', 'binpy'])
    self._presetup()
    text = common_ci.build_wheels_script(self)
    assert 'LOCAL_CP_VERSION=' in text
    assert 'CIBW_BUILD="${CIBW_BUILD:-${LOCAL_CP_VERSION}-*}"' in text
    assert 'rm -rf wheelhouse' in text


def test_source_check_split_also_works_for_purepy(tmp_path):
    self = _make_applier(tmp_path, tags=['github', 'gitlab', 'purepy'])
    self.config['ci_source_checks'] = {
        'compile': {
            'setup_commands': ['python -V'],
            'commands': ['python -m compileall demo_pkg'],
        }
    }
    self = TemplateApplier(self.config)
    self._presetup()

    github_tests = self.build_github_actions_tests()
    github_checks = self.build_github_actions_checks()
    assert 'check_compile:' not in github_tests
    assert 'check_compile:' in github_checks
    assert 'python -m compileall demo_pkg' in github_checks

    gitlab_root = Yaml.loads(self.build_gitlab_ci())
    assert gitlab_root['include'] == [
        {'local': '.gitlab/ci/main.yml'},
        {'local': '.gitlab/ci/checks.yml'},
    ]
    gitlab_main = Yaml.loads(self.build_gitlab_ci_main())
    gitlab_checks = Yaml.loads(self.build_gitlab_ci_checks())
    assert 'check/compile' not in gitlab_main
    assert 'check/compile' in gitlab_checks
    assert 'python -m compileall demo_pkg' in gitlab_checks['check/compile']['script']


def test_maturin_binpy_backend_is_not_polluted_by_legacy_build_stack(tmp_path):
    pyproject = {
        'build-system': {
            'requires': ['maturin>=1.7,<2.0'],
            'build-backend': 'maturin',
        },
        'project': {
            'name': 'demo-pkg',
            'version': '1.2.3',
            'description': 'demo',
            'requires-python': '>=3.10',
            'dependencies': ['ubelt'],
        },
        'tool': {
            'xcookie': {
                'tags': ['github', 'binpy'],
                'mod_name': 'demo_pkg',
                'repo_name': 'demo_pkg',
                'min_python': '3.10',
                'ci_reusable_wheels': True,
                'test_env': {'DEMO_FORCE_RUNTIME': '1'},
                'ci_wheel_build_post_commands': [
                    'python dev/check_wheel_artifact.py wheelhouse/demo_pkg*.whl'
                ],
                'ci_source_checks': {
                    'backend-parity': {
                        'python_version': '3.12',
                        'setup_commands': ['export RUSTUP_HOME=/tmp/rustup'],
                        'commands': ['./dev/check_backend_parity.sh'],
                    },
                },
            },
            'maturin': {
                'manifest-path': 'rust/Cargo.toml',
                'module-name': 'demo_pkg._rust',
            },
            'cibuildwheel': {
                'build': 'cp310-*',
                'skip': 'pp* *-musllinux_*',
                'linux': {
                    'before-all': 'install-project-rust-toolchain',
                    'environment': {'PATH': '$HOME/.cargo/bin:$PATH'},
                },
            },
        },
    }
    (tmp_path / 'pyproject.toml').write_text(toml.dumps(pyproject))

    cfg = XCookieConfig.load_from_cli_and_pyproject(
        argv=0,
        repodir=tmp_path,
        interactive=False,
        init_new_remotes=False,
        use_vcs=False,
        use_setup_py=False,
    )
    self = TemplateApplier(cfg)
    self._presetup()
    rendered = toml.loads(self.build_pyproject())

    assert rendered['build-system'] == pyproject['build-system']
    assert rendered['project']['version'] == '1.2.3'
    assert rendered['project']['dependencies'] == ['ubelt']
    assert rendered['tool']['maturin'] == pyproject['tool']['maturin']
    assert 'setuptools' not in rendered['tool']
    assert rendered['tool']['cibuildwheel']['build'] == 'cp310-*'
    assert rendered['tool']['cibuildwheel']['archs'] == ['auto64']
    assert 'build-frontend' not in rendered['tool']['cibuildwheel']
    assert 'test-command' not in rendered['tool']['cibuildwheel']
    assert (
        rendered['tool']['cibuildwheel']['linux']['before-all']
        == 'install-project-rust-toolchain'
    )
    requirements = rendered['build-system']['requires']
    assert not any('scikit-build' in item for item in requirements)
    assert not any('cython' in item.lower() for item in requirements)
    assert not any('cmake' in item.lower() for item in requirements)
    assert not any('ninja' in item.lower() for item in requirements)

    xcookie_config = rendered['tool']['xcookie']
    assert xcookie_config['ci_reusable_wheels'] is True
    assert xcookie_config['test_env'] == {'DEMO_FORCE_RUNTIME': '1'}
    assert xcookie_config['ci_wheel_build_post_commands'] == [
        'python dev/check_wheel_artifact.py wheelhouse/demo_pkg*.whl'
    ]
    assert xcookie_config['ci_source_checks']['backend-parity'] == {
        'python_version': '3.12',
        'setup_commands': ['export RUSTUP_HOME=/tmp/rustup'],
        'commands': ['./dev/check_backend_parity.sh'],
    }


def test_reusable_binpy_preserves_explicit_arch_policy(tmp_path):
    pyproject = {
        'build-system': {
            'requires': ['maturin>=1.7,<2.0'],
            'build-backend': 'maturin',
        },
        'project': {
            'name': 'demo-pkg',
            'version': '1.2.3',
            'requires-python': '>=3.10',
        },
        'tool': {
            'xcookie': {
                'tags': ['github', 'binpy'],
                'mod_name': 'demo_pkg',
                'repo_name': 'demo_pkg',
                'min_python': '3.10',
                'ci_reusable_wheels': True,
            },
            'maturin': {
                'manifest-path': 'rust/Cargo.toml',
                'module-name': 'demo_pkg._rust',
            },
            'cibuildwheel': {
                'build': 'cp310-*',
                'archs': ['AMD64', 'x86'],
            },
        },
    }
    (tmp_path / 'pyproject.toml').write_text(toml.dumps(pyproject))

    cfg = XCookieConfig.load_from_cli_and_pyproject(
        argv=0,
        repodir=tmp_path,
        interactive=False,
        init_new_remotes=False,
        use_vcs=False,
        use_setup_py=False,
    )
    self = TemplateApplier(cfg)
    self._presetup()
    rendered = toml.loads(self.build_pyproject())

    assert rendered['tool']['cibuildwheel']['archs'] == ['AMD64', 'x86']
