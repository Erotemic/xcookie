import sys
import types

import pytest

from xcookie.main import TemplateApplier, XCookieConfig


def _make_applier(tmp_path, *, trusted, enable_gpg):
    cfg = XCookieConfig(
        repodir=tmp_path,
        repo_name='demo_pkg',
        tags=['github', 'erotemic', 'purepy'],
        interactive=False,
        rotate_secrets=False,
        refresh_docs=False,
    )
    cfg['ci_pypi_trusted_publishing'] = trusted
    cfg['enable_gpg'] = enable_gpg
    self = TemplateApplier(cfg)
    self._presetup()
    return self


class _FakeQueue:
    created = []

    def __init__(self):
        self.commands = []
        self.ran = False
        self.run_kwargs = None

    @classmethod
    def create(cls, **kwargs):
        inst = cls()
        inst.create_kwargs = kwargs
        cls.created.append(inst)
        return inst

    def submit(self, cmd, log=False):
        self.commands.append(cmd)
        return self

    def sync(self):
        return self

    def rprint(self):
        return None

    def run(self, **kwargs):
        self.ran = True
        self.run_kwargs = kwargs
        return None


def test_render_github_actions_trusted_publishing(tmp_path):
    text = _make_applier(
        tmp_path, trusted=True, enable_gpg=True
    ).build_github_actions()

    assert 'pypa/gh-action-pypi-publish@release/v1' in text
    assert 'packages-dir: publish_wheelhouse' in text
    assert 'id-token: write' in text
    assert 'twine upload --username __token__' not in text
    assert 'Sign distributions' in text
    assert 'Prepare publish directory' in text
    assert 'Publish test artifacts to TestPyPI' in text
    assert 'Publish live artifacts to PyPI' in text


def test_render_github_actions_legacy_publishing(tmp_path):
    text = _make_applier(
        tmp_path, trusted=False, enable_gpg=True
    ).build_github_actions()

    assert 'pypa/gh-action-pypi-publish@release/v1' not in text
    assert 'id-token: write' not in text
    assert 'twine upload --username __token__' in text
    assert 'Sign and Publish' in text


def test_render_github_actions_trusted_footer_drops_twine_act_secrets(tmp_path):
    text = _make_applier(
        tmp_path, trusted=True, enable_gpg=True
    ).build_github_actions()

    assert 'Trusted publishing cannot be fully emulated with local act secrets.' in text
    assert 'EROTEMIC_TWINE_PASSWORD' not in text
    assert 'EROTEMIC_TEST_TWINE_PASSWORD' not in text
    assert 'EROTEMIC_CI_SECRET' in text


def test_render_github_actions_legacy_footer_keeps_twine_act_secrets(tmp_path):
    text = _make_applier(
        tmp_path, trusted=False, enable_gpg=True
    ).build_github_actions()

    assert 'EROTEMIC_TWINE_PASSWORD' in text
    assert 'EROTEMIC_TEST_TWINE_PASSWORD' in text


def test_rotate_secrets_trusted_without_gpg_skips_secret_upload(monkeypatch, tmp_path):
    _FakeQueue.created.clear()
    fake_cmd_queue = types.SimpleNamespace(Queue=_FakeQueue)
    monkeypatch.setitem(sys.modules, 'cmd_queue', fake_cmd_queue)

    self = _make_applier(tmp_path, trusted=True, enable_gpg=False)
    self.rotate_secrets()

    queue = _FakeQueue.created[-1]
    joined = '\n'.join(queue.commands)

    assert 'source ' in queue.commands[0]
    assert 'setup_package_environs_github_erotemic' in joined
    assert 'source $(secret_loader.sh)' in joined
    assert 'export_encrypted_code_signing_keys' not in joined
    assert 'upload_github_secrets' not in joined
    assert 'no CI secrets need to be uploaded' in joined
    assert queue.ran


def test_rotate_secrets_trusted_with_gpg_keeps_gpg_export_and_secret_upload(monkeypatch, tmp_path):
    _FakeQueue.created.clear()
    fake_cmd_queue = types.SimpleNamespace(Queue=_FakeQueue)
    monkeypatch.setitem(sys.modules, 'cmd_queue', fake_cmd_queue)

    self = _make_applier(tmp_path, trusted=True, enable_gpg=True)
    self.rotate_secrets()

    queue = _FakeQueue.created[-1]
    joined = '\n'.join(queue.commands)

    assert 'export_encrypted_code_signing_keys' in joined
    assert 'upload_github_secrets' in joined
    assert queue.ran
