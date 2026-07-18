from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_uv_lock_is_checked_in_and_sanitized() -> None:
    lock_fpath = REPO_ROOT / 'uv.lock'
    if not lock_fpath.exists():
        pytest.skip(f'uv.lock not present at {lock_fpath} (non-source test run)')
    text = lock_fpath.read_text()
    assert 'name = "xcookie"' in text
    assert 'https://pypi.org/simple' in text
    assert 'files.pythonhosted.org' in text
    assert 'applied-caas' not in text
    assert 'internal.api.openai.org' not in text
    assert 'reader:' not in text


def test_checked_lock_requirement_exports_are_present_and_sanitized() -> None:
    lock_dpath = REPO_ROOT / 'requirements/locks'
    if not lock_dpath.exists():
        pytest.skip(f'{lock_dpath} not present (non-source test run)')
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


def test_refresh_locks_sh_emits_one_export_per_strict_variant(tmp_path) -> None:
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
        use_pyproject_requirements=True,
        min_python='3.11',
        test_variants=['minimal-strict', 'full-strict', 'full-loose'],
    )
    cfg['enable_gpg'] = False
    cfg['deploy'] = False
    self = TemplateApplier(cfg)
    self._presetup()
    text = self.build_refresh_locks_sh()

    assert text.startswith('#!/usr/bin/env bash\n')
    assert 'set -euo pipefail' in text
    assert 'uv lock' in text
    # The two strict variants for a vanilla purepy project are tests and
    # tests,optional; each should emit its own export line.
    assert '-o requirements/locks/tests.txt' in text
    assert '-o requirements/locks/tests-optional.txt' in text
    assert text.count('uv export --frozen --no-emit-project') == 2
    # Generator must wire the script into the template registry only when uv
    # lockfile CI is in use.
    self._build_template_registry()
    infos = [
        info
        for info in self.template_infos
        if str(info.get('fname', '')) == 'dev/refresh_locks.sh'
    ]
    assert len(infos) == 1
    assert infos[0].enabled is True
    assert 'x' in infos[0].perms


def test_refresh_locks_sh_disabled_for_legacy_setup_py_repos(tmp_path) -> None:
    from xcookie.main import TemplateApplier, XCookieConfig

    cfg = XCookieConfig(
        repodir=tmp_path,
        repo_name='legacy_pkg',
        mod_name='legacy_pkg',
        tags=['github', 'purepy'],
        interactive=False,
        rotate_secrets=False,
        refresh_docs=False,
        use_setup_py=True,
        use_pyproject_requirements=False,
        min_python='3.11',
    )
    cfg['enable_gpg'] = False
    cfg['deploy'] = False
    self = TemplateApplier(cfg)
    self._presetup()
    self._build_template_registry()
    # Legacy setup.py + non-pyproject-requirements projects use generated
    # ``*-strict`` extras instead of a checked-in lockfile, so the refresh
    # script has nothing to do; it should be present but disabled.
    infos = [
        info
        for info in self.template_infos
        if str(info.get('fname', '')) == 'dev/refresh_locks.sh'
    ]
    assert len(infos) == 1
    assert infos[0].enabled is False
