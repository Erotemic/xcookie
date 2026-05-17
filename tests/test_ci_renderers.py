from xcookie.main import TemplateApplier, XCookieConfig


def _make_applier(tmp_path, *, tags, use_pyproject_requirements=False):
    cfg = XCookieConfig(
        repodir=tmp_path,
        repo_name='demo_pkg',
        mod_name='demo_pkg',
        tags=tags,
        interactive=False,
        rotate_secrets=False,
        refresh_docs=False,
        test_variants=['minimal-strict', 'full-loose'],
    )
    cfg['enable_gpg'] = False
    cfg['deploy'] = False
    cfg['linter'] = False
    cfg['ci_cpython_versions'] = cfg['ci_cpython_versions'][-2:]
    cfg['use_pyproject_requirements'] = use_pyproject_requirements
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
    assert 'refs/heads/release' in text


def test_gitlab_purepy_render_uses_artifact_test_cases(tmp_path):
    self = _make_applier(tmp_path, tags=['gitlab', 'purepy'])
    text = self.build_gitlab_ci()
    assert 'build/sdist:' in text
    assert 'build/cp' in text
    assert 'test/full-loose/cp' in text
    assert 'test/minimal-strict/cp' in text
    assert 'export INSTALL_EXTRAS="tests,optional"' in text
    assert 'export INSTALL_EXTRAS="tests-strict,runtime-strict"' in text


def test_gitlab_purepy_gdal_cases_select_strict_and_loose_requirement_files(tmp_path):
    self = _make_applier(tmp_path, tags=['gitlab', 'purepy', 'gdal'])
    text = self.build_gitlab_ci()
    assert 'requirements/gdal.txt' in text
    assert 'requirements/gdal-strict.txt' in text
    assert "sed 's/>=/==/'" in text
