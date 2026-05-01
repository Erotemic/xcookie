import sys
from pathlib import Path

from xcookie.main import TemplateApplier, XCookieConfig


def _make_applier(tmp_path, *, trusted, enable_gpg, tags=None, min_python=None):
    if tags is None:
        tags = ['github', 'erotemic', 'purepy']
    kwargs = dict(
        repodir=tmp_path,
        repo_name='demo_pkg',
        tags=tags,
        interactive=False,
        rotate_secrets=False,
        refresh_docs=False,
    )
    if min_python is not None:
        kwargs['min_python'] = min_python
    cfg = XCookieConfig(**kwargs)
    cfg['ci_pypi_trusted_publishing'] = trusted
    cfg['enable_gpg'] = enable_gpg
    self = TemplateApplier(cfg)
    self._presetup()
    return self


def test_generated_workflows_set_top_level_read_permissions(tmp_path):
    text = _make_applier(
        tmp_path, trusted=True, enable_gpg=True
    ).build_github_actions_tests()

    assert 'permissions:' in text
    assert 'contents: read' in text
    assert 'jobs:' in text
    assert text.index('permissions:') < text.index('jobs:')


def test_checkout_persist_credentials_disabled_by_default(tmp_path):
    text = _make_applier(
        tmp_path, trusted=True, enable_gpg=True
    ).build_github_actions_tests()

    assert 'uses: actions/checkout@v6.0.2' in text
    assert 'persist-credentials: false' in text


def test_release_workflow_push_trigger_is_scoped(tmp_path):
    text = _make_applier(
        tmp_path, trusted=True, enable_gpg=True
    ).build_github_actions_release()

    assert 'push:' in text
    assert 'branches: [ main, release ]' in text
    assert "tags: [ 'v*' ]" in text
    assert 'workflow_dispatch:' in text
    assert 'pull_request:' not in text


def test_release_jobs_keep_required_elevated_permissions(tmp_path):
    text = _make_applier(
        tmp_path, trusted=True, enable_gpg=True
    ).build_github_actions_release()

    assert 'id-token: write' in text
    assert 'contents: write' in text
    assert 'environment: testpypi' in text
    assert 'environment: pypi' in text


def test_hardening_tests_are_self_contained():
    root = Path(__file__).resolve().parents[1]
    test_text = (root / 'tests' / 'test_github_actions_hardening.py').read_text()
    assert 'from tests.' not in test_text
    assert 'import tests.' not in test_text
    assert str(root) not in sys.path[:1]
