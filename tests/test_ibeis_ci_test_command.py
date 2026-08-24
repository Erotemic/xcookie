from xcookie.main import TemplateApplier, XCookieConfig


def test_ibeis_auto_ci_runs_one_pytest_collection(tmp_path):
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

    # Run normal pytest collection once. Xdoctest participates in that same
    # collection; pytest's own plugin controls belong in pytest configuration
    # rather than process argv, where applications may define their own -p.
    assert 'python -m pytest --verbose --xdoctest' in text
    assert '"$MOD_DPATH" ../tests' in text
    assert '-p pytester' not in text
    assert '-p no:doctest' not in text
    assert 'pytest.main([' not in text
    assert 'python -m xdoctest ibeis.' not in text
    assert 'python -m xdoctest $MOD_DPATH' not in text
