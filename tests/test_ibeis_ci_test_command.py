from xcookie.main import TemplateApplier, XCookieConfig


def test_ibeis_auto_ci_runs_pytest_suite(tmp_path):
    cfg = XCookieConfig(
        repodir=tmp_path,
        repo_name='ibeis',
        mod_name='ibeis',
        tags=['github', 'purepy'],
        interactive=False,
        test_variants=['minimal-strict'],
    )
    cfg['enable_gpg'] = False
    cfg['deploy'] = False
    cfg['linter'] = False
    cfg['ci_cpython_versions'] = cfg['ci_cpython_versions'][-1:]
    self = TemplateApplier(cfg)
    self._presetup()

    text = self.build_github_actions_tests()

    assert 'python -m pytest --verbose' in text
    assert '"$MOD_DPATH" ../tests' in text
    assert 'python -m xdoctest $MOD_DPATH --style=google all' not in text
