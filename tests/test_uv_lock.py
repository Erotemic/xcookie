from pathlib import Path


def test_uv_lock_is_checked_in_and_sanitized() -> None:
    lock_fpath = Path('uv.lock')
    assert lock_fpath.exists()
    text = lock_fpath.read_text()
    assert 'name = "xcookie"' in text
    assert 'https://pypi.org/simple' in text
    assert 'files.pythonhosted.org' in text
    assert 'applied-caas' not in text
    assert 'internal.api.openai.org' not in text
    assert 'reader:' not in text


def test_checked_lock_requirement_exports_are_present_and_sanitized() -> None:
    lock_dpath = Path('requirements/locks')
    expected = {
        'runtime.txt',
        'tests.txt',
        'optional.txt',
        'docs.txt',
        'tests-optional.txt',
    }
    assert expected <= {p.name for p in lock_dpath.glob('*.txt')}
    for fpath in lock_dpath.glob('*.txt'):
        text = fpath.read_text()
        assert '==' in text
        assert 'applied-caas' not in text
        assert 'internal.api.openai.org' not in text
        assert 'reader:' not in text


def test_generated_github_ci_uses_checked_lock_requirement_cases(tmp_path) -> None:
    from xcookie.main import TemplateApplier, XCookieConfig

    cfg = XCookieConfig(
        repodir=tmp_path,
        repo_name='demo_pkg',
        mod_name='demo_pkg',
        tags=['github', 'purepy'],
        interactive=False,
        rotate_secrets=False,
        refresh_docs=False,
        use_setup_py=False,
        use_pyproject_requirements=False,
        min_python='3.10',
        test_variants=['minimal-strict', 'full-loose'],
    )
    cfg['enable_gpg'] = False
    cfg['deploy'] = False
    self = TemplateApplier(cfg)
    self._presetup()
    text = self.build_github_actions_tests()
    assert 'use-lockfile:' in text
    assert 'lock-requirements:' in text
    assert 'LOCK_REQUIREMENTS: ${{ matrix.lock-requirements }}' in text
    assert 'requirements/locks/tests.txt' in text
    assert 'Using checked-in lock requirements' in text
    assert 'python -m uv export --frozen --no-emit-project' not in text
    assert 'python -m uv pip compile' not in text
