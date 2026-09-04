from xcookie.builders import ci_model
from xcookie.builders.action_versions import ACTION_VERSIONS
from xcookie.main import TemplateApplier, XCookieConfig


def _make_applier(
    tmp_path,
    *,
    tags,
    use_pyproject_requirements=False,
    min_python=None,
    max_python=None,
    use_setup_py=False,
    ci_allow_failure=None,
    ci_prerelease_python_policy=None,
    typecheck_extra_paths=None,
):
    kwargs = dict(
        repodir=tmp_path,
        repo_name='demo_pkg',
        mod_name='demo_pkg',
        tags=tags,
        interactive=False,
        test_variants=['minimal-strict', 'full-loose'],
    )
    if min_python is not None:
        kwargs['min_python'] = min_python
    if max_python is not None:
        kwargs['max_python'] = max_python
    cfg = XCookieConfig(**kwargs)
    cfg['enable_gpg'] = False
    cfg['deploy'] = False
    cfg['linter'] = False
    cfg['ci_cpython_versions'] = cfg['ci_cpython_versions'][-2:]
    cfg['use_pyproject_requirements'] = use_pyproject_requirements
    cfg['use_setup_py'] = use_setup_py
    if ci_allow_failure is not None:
        cfg['ci_allow_failure'] = ci_allow_failure
    if ci_prerelease_python_policy is not None:
        cfg['ci_prerelease_python_policy'] = ci_prerelease_python_policy
    if typecheck_extra_paths is not None:
        cfg['typecheck_extra_paths'] = typecheck_extra_paths
    self = TemplateApplier(cfg)
    self._presetup()
    return self


def test_github_purepy_uses_shared_workflow_plan_and_test_cases(tmp_path):
    self = _make_applier(tmp_path, tags=['github', 'purepy'])
    text = self.build_github_actions_tests()
    assert 'build_purepy_wheels:' in text
    assert 'test_purepy_wheels:' in text
    assert 'build_and_test_sdist:' in text
    assert 'matrix:' in text
    assert 'install-extras:' in text
    assert (
        'minimal-strict' not in text
    )  # GitHub matrix stores extras, not variant keys
    # The tests workflow no longer runs on deploy-bearing refs at all;
    # release.yml owns them, so no job needs a release-ref guard.
    assert 'refs/heads/release' not in text
    assert 'concurrency:' in text
    assert 'cancel-in-progress: true' in text
    assert '3.15' in text
    assert 'allow-prereleases:' in text
    assert 'check-latest:' in text
    assert 'Prioritized MSVC linker directory:' in text
    assert 'command -v cl.exe' in text
    assert 'VSCMD_ARG_HOST_ARCH' not in text
    assert 'VSCMD_ARG_TGT_ARCH' not in text
    assert text.index('Prioritized MSVC linker directory:') < text.index(
        'Installing helpers: update pip'
    )


def test_github_binpy_uses_shared_workflow_plan_and_test_cases(tmp_path):
    self = _make_applier(tmp_path, tags=['github', 'binpy'], min_python='3.10')
    text = self.build_github_actions_tests()
    assert 'build_binpy_wheels:' in text
    assert 'test_binpy_wheels:' in text
    assert 'build_and_test_sdist:' in text
    assert 'pypa/cibuildwheel' in text
    assert 'matrix:' in text
    assert 'install-extras:' in text
    # The tests workflow no longer runs on deploy-bearing refs at all;
    # release.yml owns them, so no job needs a release-ref guard.
    assert 'refs/heads/release' not in text
    assert 'concurrency:' in text
    assert 'cancel-in-progress: true' in text
    assert 'CIBW_ENABLE: cpython-prerelease' in text
    cibw_version = ACTION_VERSIONS['pypa/cibuildwheel']
    assert f'pypa/cibuildwheel@{cibw_version}' in text


def _assert_all_setup_python_steps_allow_prereleases(text):
    lines = text.splitlines()
    setup_blocks = []
    for index, line in enumerate(lines):
        if 'uses: actions/setup-python@' not in line:
            continue
        uses_indent = len(line) - len(line.lstrip())
        block = [line]
        for candidate in lines[index + 1 :]:
            stripped = candidate.strip()
            indent = len(candidate) - len(candidate.lstrip())
            if stripped and indent < uses_indent:
                break
            block.append(candidate)
        setup_blocks.append('\n'.join(block))

    assert setup_blocks
    for block in setup_blocks:
        assert 'allow-prereleases:' in block
        assert 'check-latest:' in block
        assert 'allow-prereleases: false' not in block
        assert 'check-latest: false' not in block


def test_github_only_prerelease_python_uses_it_as_main(tmp_path):
    self = _make_applier(
        tmp_path,
        tags=['github', 'purepy'],
        min_python='3.15',
        max_python='3.15',
    )
    tests_text = self.build_github_actions_tests()
    assert 'Set up Python max' not in tests_text
    assert '3.15' in tests_text
    _assert_all_setup_python_steps_allow_prereleases(tests_text)

    release_text = self.build_github_actions_release()
    _assert_all_setup_python_steps_allow_prereleases(release_text)


def test_gitlab_315_uses_prerelease_docker_image(tmp_path):
    self = _make_applier(
        tmp_path,
        tags=['gitlab', 'purepy'],
        min_python='3.15',
        max_python='3.15',
    )
    text = self.build_gitlab_ci()
    assert 'python:3.15-rc' in text


def test_gitlab_purepy_render_uses_artifact_test_cases(tmp_path):
    self = _make_applier(tmp_path, tags=['gitlab', 'purepy'], min_python='3.10')
    text = self.build_gitlab_ci()
    assert 'build/sdist:' in text
    assert 'build/wheel:' in text
    assert 'build/cp' not in text
    assert 'test/full-loose/cp' in text
    assert 'test/minimal-strict/cp' in text
    assert 'export INSTALL_EXTRAS="tests,optional"' in text
    assert 'export INSTALL_EXTRAS="tests"' in text
    assert 'export USE_UV_LOCK="true"' in text
    assert 'export LOCK_REQUIREMENTS="requirements/locks/tests.txt"' in text
    assert 'tests-strict' not in text
    assert 'runtime-strict' not in text
    assert 'setuptools>=77' in text


def test_gitlab_purepy_tests_share_one_wheel_build(tmp_path):
    from xcookie.util_yaml import Yaml

    self = _make_applier(tmp_path, tags=['gitlab', 'purepy'], min_python='3.10')
    text = self.build_gitlab_ci()
    body = Yaml.loads(text)

    wheel_build_jobs = [
        key
        for key in body
        if key.startswith('build/') and key != 'build/sdist'
    ]
    assert wheel_build_jobs == ['build/wheel']

    wheel_test_jobs = {
        key: job
        for key, job in body.items()
        if key.startswith('test/') and not key.startswith('test/sdist/')
    }
    artifact_test_cases = ci_model.make_artifact_test_cases(
        self, provider='gitlab'
    )
    assert len(wheel_test_jobs) == len(artifact_test_cases)
    assert all(
        job['needs'] == ['build/wheel'] for job in wheel_test_jobs.values()
    )


def test_gitlab_binpy_render_uses_artifact_test_cases(tmp_path):
    self = _make_applier(tmp_path, tags=['gitlab', 'binpy'], min_python='3.9')
    text = self.build_gitlab_ci()
    assert 'build/cp' in text
    assert 'test/full-loose/cp' in text
    assert 'test/minimal-strict/cp' in text
    assert 'export INSTALL_EXTRAS="tests,optional"' in text
    assert 'export INSTALL_EXTRAS="tests"' in text
    assert 'export USE_UV_LOCK="true"' in text
    assert 'export LOCK_REQUIREMENTS="requirements/locks/tests.txt"' in text
    assert 'tests-strict' not in text
    assert 'runtime-strict' not in text
    assert 'CIBW_BUILD:' in text


def test_gitlab_legacy_setup_py_render_keeps_synthetic_strict_extras(tmp_path):
    self = _make_applier(
        tmp_path,
        tags=['gitlab', 'purepy'],
        use_setup_py=True,
        use_pyproject_requirements=False,
    )
    text = self.build_gitlab_ci()
    assert 'export INSTALL_EXTRAS="tests-strict,runtime-strict"' in text


def test_gitlab_purepy_gdal_cases_select_strict_and_loose_requirement_files(
    tmp_path,
):
    self = _make_applier(tmp_path, tags=['gitlab', 'purepy', 'gdal'])
    text = self.build_gitlab_ci()
    assert 'requirements/gdal.txt' in text
    assert 'requirements/gdal-strict.txt' in text
    assert "sed 's/>=/==/'" in text
    assert '--find-links https://girder.github.io/large_image_wheels' in text


def test_github_binpy_versionless_wheels_and_vcpkg(tmp_path):
    """
    A binpy repo with python-version-independent wheels (e.g. pure ctypes
    bindings tagged py3-none) builds ONE wheel per platform: no per-python
    cibuildwheel fanout, no msvc-dev-cmd setup, and no coverage combining in
    the build job (the wheel test jobs own coverage). The vcpkg tag composes
    with it and must appear in BOTH the tests and release workflows.
    """
    self = _make_applier(
        tmp_path, tags=['github', 'binpy', 'vcpkg'], min_python='3.11'
    )
    self.config['ci_versionless_wheels'] = True
    tests_text = self.build_github_actions_tests()
    release_text = self.build_github_actions_release()

    for text in (tests_text, release_text):
        # Single build per platform: the skip matrix dimension and the
        # msvc/matrix related cibuildwheel env vars disappear; build/skip
        # selection lives in [tool.cibuildwheel] in pyproject.toml.
        assert 'cibw_skip:' not in text
        assert 'CIBW_SKIP' not in text
        assert 'VSCMD_ARG_TGT_ARCH' not in text
        assert 'python-version independent' in text
        # vcpkg support pieces (shared between tests and release builds).
        assert 'Restore vcpkg caches (Windows)' in text
        assert 'Save vcpkg caches (Windows, even on failure)' in text
        assert (
            'CMAKE_ARGS=-DCMAKE_TOOLCHAIN_FILE='
            'C:/vcpkg/scripts/buildsystems/vcpkg.cmake'
        ) in text
        assert 'PYTHONUTF8=1' in text

    # The versionless build job runs only a smoke test inside cibuildwheel,
    # so it must not try to combine or upload coverage (the test job still
    # does, hence the split-scope assertion).
    build_job_section = tests_text.split('test_binpy_wheels:')[0]
    assert 'Codecov' not in build_job_section
    assert 'combine coverage' not in build_job_section


def test_github_binpy_default_keeps_per_python_builds(tmp_path):
    """
    Without ci_versionless_wheels, nothing changes: repos that link against
    the CPython C API keep the per-python-version cibuildwheel builds.
    """
    self = _make_applier(tmp_path, tags=['github', 'binpy'], min_python='3.11')
    text = self.build_github_actions_tests()
    assert 'cibw_skip:' in text
    assert 'CIBW_SKIP' in text
    assert 'msvc-dev-cmd' in text


def test_github_release_resolves_version_tag_before_tagging(tmp_path):
    """The release action must target the generated version tag, not the branch."""
    from xcookie.builders.github_actions import build_github_release

    self = _make_applier(tmp_path, tags=['github', 'binpy'], min_python='3.11')
    job = build_github_release(self)
    meta_steps = [
        step
        for step in job['steps']
        if step.get('name') == 'Resolve Release Tag'
    ]
    tag_steps = [
        step
        for step in job['steps']
        if step.get('name') == 'Tag Release Commit'
    ]
    release_steps = [
        step for step in job['steps'] if step.get('name') == 'Create Release'
    ]
    assert len(meta_steps) == len(tag_steps) == len(release_steps) == 1

    meta = meta_steps[0]
    assert meta['id'] == 'release_meta'
    assert 'test -n "$VERSION"' in meta['run']
    assert 'TAG="v$VERSION"' in meta['run']
    assert 'echo "tag=$TAG" >> "$GITHUB_OUTPUT"' in meta['run']

    tag_run = tag_steps[0]['run']
    assert 'git ls-remote --refs origin "refs/tags/$TAG"' in tag_run
    assert 'test "$REMOTE_SHA" = "$GITHUB_SHA"' in tag_run
    assert 'git tag "$TAG" "$GITHUB_SHA"' in tag_run
    assert 'git push origin "refs/tags/$TAG"' in tag_run

    release = release_steps[0]
    assert release['uses'].startswith('softprops/action-gh-release@')
    assert (
        release['with']['tag_name'] == '${{ steps.release_meta.outputs.tag }}'
    )
    assert (
        release['with']['name']
        == 'Release ${{ steps.release_meta.outputs.tag }}'
    )
    assert release['with']['target_commitish'] == '${{ github.sha }}'
    assert '${{ github.ref }}' not in str(release['with'])


def test_github_auto_setup_py_preserves_legacy_test_extras(tmp_path):
    (tmp_path / '.git').mkdir()
    (tmp_path / 'setup.py').write_text('from setuptools import setup\n')
    (tmp_path / 'pyproject.toml').write_text(
        '[build-system]\nrequires = ["setuptools"]\n'
    )
    self = _make_applier(
        tmp_path,
        tags=['github', 'purepy'],
        use_setup_py='auto',
        use_pyproject_requirements=False,
    )
    text = self.build_github_actions_tests()
    assert self.config['use_setup_py'] is True
    assert "install-extras: tests" in text
    assert "install-extras: tests-strict,runtime-strict" in text
    assert 'requirements/locks/runtime.txt' not in text
    assert 'requirements/locks/tests.txt' not in text


def test_github_allow_failure_rules_normalize_experimental_steps(tmp_path):
    self = _make_applier(
        tmp_path,
        tags=['github', 'purepy'],
        ci_allow_failure=[{'python-version': '3.15'}],
        ci_prerelease_python_policy='strict',
    )
    text = self.build_github_actions_tests()
    continue_expr = 'continue-on-error: ${{ matrix.experimental || false }}'
    assert text.count(continue_expr) == 3
    assert 'id: setup_python' in text
    assert 'id: install_wheel' in text
    assert 'id: test_wheel' in text
    assert 'Report experimental failure' in text
    assert 'Experimental CI failure' in text
    assert "python-version: '3.15'" in text
    assert 'experimental: true' in text

    stable_self = _make_applier(
        tmp_path,
        tags=['github', 'purepy'],
        ci_prerelease_python_policy='strict',
    )
    stable_text = stable_self.build_github_actions_tests()
    assert continue_expr not in stable_text
    assert 'Report experimental failure' not in stable_text


def test_github_typecheck_extra_paths_are_rendered(tmp_path):
    self = _make_applier(
        tmp_path,
        tags=['github', 'purepy', 'mypy'],
        typecheck_extra_paths=['tests/typecheck_consumer.py'],
    )
    self.config['linter'] = True
    text = self.build_github_actions_tests()
    expected_targets = './demo_pkg ./tests/typecheck_consumer.py'
    assert f'mypy {expected_targets}' in text
    assert f'ty check {expected_targets}' in text


def test_gitlab_prerelease_python_policy_defaults_to_allow_failure(tmp_path):
    from xcookie.util_yaml import Yaml

    self = _make_applier(tmp_path, tags=['gitlab', 'purepy'], min_python='3.10')
    body = Yaml.loads(self.build_gitlab_ci())
    prerelease_jobs = {
        key: job
        for key, job in body.items()
        if key.startswith('test/') and '/cp315-' in key
    }
    stable_jobs = {
        key: job
        for key, job in body.items()
        if key.startswith('test/')
        and '/cp315-' not in key
        and not key.startswith('test/sdist/')
    }
    assert prerelease_jobs
    assert stable_jobs
    assert all(
        job.get('allow_failure') is True
        for job in prerelease_jobs.values()
    )
    assert all('allow_failure' not in job for job in stable_jobs.values())


def test_gitlab_prerelease_python_policy_strict(tmp_path):
    from xcookie.util_yaml import Yaml

    self = _make_applier(
        tmp_path,
        tags=['gitlab', 'purepy'],
        min_python='3.10',
        ci_prerelease_python_policy='strict',
    )
    body = Yaml.loads(self.build_gitlab_ci())
    prerelease_jobs = {
        key: job
        for key, job in body.items()
        if key.startswith('test/') and '/cp315-' in key
    }
    assert prerelease_jobs
    assert all('allow_failure' not in job for job in prerelease_jobs.values())


def test_gitlab_prerelease_python_policy_skip(tmp_path):
    self = _make_applier(
        tmp_path,
        tags=['gitlab', 'purepy'],
        min_python='3.10',
        ci_prerelease_python_policy='skip',
    )
    text = self.build_gitlab_ci()
    assert '/cp315-' not in text
    assert 'python:3.15-rc' not in text


def _write_workspace_demo(tmp_path):
    (tmp_path / 'demo_pkg').mkdir(exist_ok=True)
    (tmp_path / 'demo_pkg' / '__init__.py').write_text(
        "__version__ = '1.2.3'\n"
    )
    (tmp_path / 'pyproject.toml').write_text(
        '''
[project]
name = "demo-pkg"
dynamic = ["version"]
dependencies = ["demo-theory==1.2.3"]

[project.optional-dependencies]
tests = []
helm = []

[tool.setuptools.dynamic]
version = {attr = "demo_pkg.__version__"}

[tool.setuptools.packages.find]
where = ["."]
include = ["demo_pkg*"]

[tool.xcookie]
workspace_members = ["packages/demo-theory"]
workspace_sync_versions = true
typecheck_install_extras = ["tests", "helm"]
'''.lstrip()
    )
    member = tmp_path / 'packages' / 'demo-theory'
    (member / 'src' / 'demo_theory').mkdir(parents=True)
    (member / 'tests').mkdir()
    (member / 'src' / 'demo_theory' / '__init__.py').write_text(
        "__version__ = '1.2.3'\n"
    )
    (member / 'tests' / 'test_smoke.py').write_text(
        'import demo_theory\n\ndef test_import():\n    assert demo_theory\n'
    )
    (member / 'pyproject.toml').write_text(
        '''
[build-system]
requires = ["setuptools>=77"]
build-backend = "setuptools.build_meta"

[project]
name = "demo-theory"
dynamic = ["version"]
dependencies = []

[tool.setuptools.dynamic]
version = {attr = "demo_theory.__version__"}

[tool.setuptools.packages.find]
where = ["src"]
include = ["demo_theory*"]

[tool.xcookie]
mod_name = "demo_theory"
rel_mod_parent_dpath = "src"
typed = true
'''.lstrip()
    )


def test_github_workspace_ci_installs_and_tests_member(tmp_path):
    _write_workspace_demo(tmp_path)
    self = _make_applier(
        tmp_path,
        tags=['github', 'purepy'],
        use_pyproject_requirements=True,
    )
    self.config['workspace_members'] = ['packages/demo-theory']
    self.config['typecheck_install_extras'] = ['tests', 'helm']
    self.config['linter'] = True
    text = self.build_github_actions_tests()
    assert 'workspace_demo_theory:' in text
    assert 'Build demo-theory' in text
    assert 'Test demo-theory in isolation' in text
    assert '-e "./packages/demo-theory"' in text
    assert '-e ".[tests,helm]"' in text
    assert 'expected dependency-free wheel' in text


def test_github_workspace_release_builds_and_publishes_member(tmp_path):
    _write_workspace_demo(tmp_path)
    self = _make_applier(
        tmp_path,
        tags=['github', 'purepy'],
        use_pyproject_requirements=True,
    )
    self.config['workspace_members'] = ['packages/demo-theory']
    self.config['deploy'] = True
    self.config['deploy_pypi'] = True
    self.config['ci_pypi_trusted_publishing'] = True
    text = self.build_github_actions_release()
    assert 'workspace_demo_theory:' in text
    assert 'workspace-demo-theory-release' in text
    assert 'Publish demo-theory to PyPI' in text
    assert 'packages-dir: workspace_release/demo_theory' in text
    assert 'deploy_workspace_artifacts' in text
    assert 'workspace_release/**/*' in text


def test_github_workspace_publish_requires_trusted_publishing(tmp_path):
    _write_workspace_demo(tmp_path)
    self = _make_applier(
        tmp_path,
        tags=['github', 'purepy'],
        use_pyproject_requirements=True,
    )
    self.config['workspace_members'] = ['packages/demo-theory']
    self.config['deploy'] = True
    self.config['deploy_pypi'] = True
    self.config['ci_pypi_trusted_publishing'] = False
    import pytest

    with pytest.raises(ValueError, match='trusted publishing'):
        self.build_github_actions_release()
