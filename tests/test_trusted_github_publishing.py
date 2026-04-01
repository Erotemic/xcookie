import sys
import types

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


class _FakeQueue:
    created = []

    def __init__(self):
        self.commands = []
        self.ran = False
        self.run_kwargs = None

    @classmethod
    def create(cls, **kwargs):
        inst = cls()
        setattr(inst, 'create_kwargs', kwargs)
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


def test_template_registry_contains_tests_and_release_workflows(tmp_path):
    self = _make_applier(tmp_path, trusted=True, enable_gpg=True)
    self._build_template_registry()
    fnames = {str(info['fname']) for info in self.template_infos}
    assert '.github/workflows/tests.yml' in fnames
    assert '.github/workflows/release.yml' in fnames


def test_build_github_actions_wrapper_points_to_tests_workflow(tmp_path):
    self = _make_applier(tmp_path, trusted=True, enable_gpg=True)
    assert self.build_github_actions() == self.build_github_actions_tests()


def test_tests_workflow_has_no_release_jobs(tmp_path):
    text = _make_applier(
        tmp_path, trusted=True, enable_gpg=True
    ).build_github_actions_tests()

    assert 'test_deploy:' not in text
    assert 'live_deploy:' not in text
    assert 'release:' not in text
    assert 'pypa/gh-action-pypi-publish@release/v1' not in text
    assert 'lint_job:' in text
    assert 'pull_request:' in text


def test_release_workflow_has_release_jobs_and_no_test_matrix_purepy(tmp_path):
    text = _make_applier(
        tmp_path, trusted=True, enable_gpg=True
    ).build_github_actions_release()

    assert 'test_deploy:' in text
    assert 'live_deploy:' in text
    assert 'release:' in text
    assert 'pypa/gh-action-pypi-publish@release/v1' in text
    assert 'packages-dir: publish_wheelhouse' in text
    assert 'id-token: write' in text
    assert 'environment: testpypi' in text
    assert 'environment: pypi' in text
    assert 'workflow_dispatch:' in text
    assert 'pull_request:' not in text
    assert 'test_purepy_wheels:' not in text
    assert 'build_sdist:' in text
    assert 'build_purepy_wheels:' in text


def test_release_workflow_binpy_uses_cibuildwheel(tmp_path):
    text = _make_applier(
        tmp_path,
        trusted=True,
        enable_gpg=True,
        tags=['github', 'erotemic', 'binpy'],
        min_python='3.9',
    ).build_github_actions_release()

    assert 'build_binpy_wheels:' in text
    assert 'pypa/cibuildwheel@v3.3.1' in text
    assert 'test_binpy_wheels:' not in text
    assert 'pypa/gh-action-pypi-publish@release/v1' in text


def test_release_workflow_trusted_footer_drops_twine_act_secrets(tmp_path):
    text = _make_applier(
        tmp_path, trusted=True, enable_gpg=True
    ).build_github_actions_release()

    assert 'Trusted publishing cannot be fully emulated with local act secrets.' in text
    assert 'EROTEMIC_TWINE_PASSWORD' not in text
    assert 'EROTEMIC_TEST_TWINE_PASSWORD' not in text
    assert 'EROTEMIC_CI_SECRET' in text


def test_release_workflow_legacy_footer_keeps_twine_act_secrets(tmp_path):
    text = _make_applier(
        tmp_path, trusted=False, enable_gpg=True
    ).build_github_actions_release()

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
