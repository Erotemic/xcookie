from xcookie.main import TemplateApplier, XCookieConfig


def _make_applier(
    tmp_path, *, tags, use_pyproject_requirements=False, min_python=None, use_setup_py=False
):
    kwargs = dict(
        repodir=tmp_path,
        repo_name='demo_pkg',
        mod_name='demo_pkg',
        tags=tags,
        interactive=False,
        rotate_secrets=False,
        refresh_docs=False,
        test_variants=['minimal-strict', 'full-loose'],
    )
    if min_python is not None:
        kwargs['min_python'] = min_python
    cfg = XCookieConfig(**kwargs)
    cfg['enable_gpg'] = False
    cfg['deploy'] = False
    cfg['linter'] = False
    cfg['ci_cpython_versions'] = cfg['ci_cpython_versions'][-2:]
    cfg['use_pyproject_requirements'] = use_pyproject_requirements
    cfg['use_setup_py'] = use_setup_py
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
    assert 'minimal-strict' not in text  # GitHub matrix stores extras, not variant keys
    # The tests workflow no longer runs on deploy-bearing refs at all;
    # release.yml owns them, so no job needs a release-ref guard.
    assert 'refs/heads/release' not in text
    assert 'concurrency:' in text
    assert 'cancel-in-progress: true' in text


def test_github_binpy_uses_shared_workflow_plan_and_test_cases(tmp_path):
    self = _make_applier(
        tmp_path, tags=['github', 'binpy'], min_python='3.10'
    )
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


def test_gitlab_purepy_render_uses_artifact_test_cases(tmp_path):
    self = _make_applier(tmp_path, tags=['gitlab', 'purepy'], min_python='3.10')
    text = self.build_gitlab_ci()
    assert 'build/sdist:' in text
    assert 'build/cp' in text
    assert 'test/full-loose/cp' in text
    assert 'test/minimal-strict/cp' in text
    assert 'export INSTALL_EXTRAS="tests,optional"' in text
    assert 'export INSTALL_EXTRAS="tests"' in text
    assert 'export USE_UV_LOCK="true"' in text
    assert 'export LOCK_REQUIREMENTS="requirements/locks/tests.txt"' in text
    assert 'tests-strict' not in text
    assert 'runtime-strict' not in text


def test_gitlab_binpy_render_uses_artifact_test_cases(tmp_path):
    self = _make_applier(
        tmp_path, tags=['gitlab', 'binpy'], min_python='3.9'
    )
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

def test_gitlab_purepy_gdal_cases_select_strict_and_loose_requirement_files(tmp_path):
    self = _make_applier(tmp_path, tags=['gitlab', 'purepy', 'gdal'])
    text = self.build_gitlab_ci()
    assert 'requirements/gdal.txt' in text
    assert 'requirements/gdal-strict.txt' in text
    assert "sed 's/>=/==/'" in text


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


def test_github_release_tag_step_guards_empty_version(tmp_path):
    """
    The tag-on-success step must refuse to create a bogus "v" tag when the
    version fails to parse.
    """
    from xcookie.builders.github_actions import build_github_release

    self = _make_applier(tmp_path, tags=['github', 'binpy'], min_python='3.11')
    job = build_github_release(self)
    tag_steps = [
        step
        for step in job['steps']
        if step.get('name') == 'Tag Release Commit'
    ]
    assert len(tag_steps) == 1
    run_text = tag_steps[0]['run']
    assert 'test -n "$VERSION"' in run_text
    assert run_text.index('test -n "$VERSION"') < run_text.index('git tag')
