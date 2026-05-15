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

    def finalize_text(self, **kwargs):
        # TemplateApplier.rotate_secrets now bypasses Queue.run() so it can
        # call cmd_queue's finalize_text(with_gaurds=False) and run the
        # resulting bash with xtrace guards disabled.  Keep this test double
        # side-effect-free while preserving the old "ran" signal and the
        # submitted commands for orchestration assertions below.
        self.ran = True
        self.run_kwargs = kwargs
        return 'true\n'


def _patch_rotate_secret_shell(monkeypatch):
    """Avoid invoking platform bash from rotate_secrets unit tests.

    These tests verify the cmd_queue orchestration decisions.  The actual
    subprocess execution is covered by production code and should not depend on
    whether the test platform has a usable bash executable, especially on
    Windows where GitHub-hosted runners may resolve ``bash`` to WSL.
    """
    calls = []

    def fake_run(cmd, cwd=None, **kwargs):
        calls.append({'cmd': cmd, 'cwd': cwd, 'kwargs': kwargs})
        return types.SimpleNamespace(returncode=0)

    import subprocess

    monkeypatch.setattr(subprocess, 'run', fake_run)
    return calls


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

    assert 'Trusted publishing setup checklist' in text
    assert '.github/workflows/release.yml' in text
    assert 'https://github.com/Erotemic/demo_pkg/settings/environments' in text
    assert (
        'https://github.com/Erotemic/demo_pkg/actions/workflows/release.yml'
        in text
    )
    assert (
        'https://pypi.org/manage/project/demo-pkg/settings/publishing/' in text
    )
    assert (
        'https://test.pypi.org/manage/project/demo-pkg/settings/publishing/'
        in text
    )
    assert 'https://pypi.org/manage/account/publishing/' in text
    assert 'https://test.pypi.org/manage/account/publishing/' in text
    assert (
        'Trusted publishing cannot be fully emulated with local act secrets.'
        in text
    )
    assert 'EROTEMIC_TWINE_PASSWORD' not in text
    assert 'EROTEMIC_TEST_TWINE_PASSWORD' not in text


def test_release_workflow_legacy_footer_keeps_twine_act_secrets(tmp_path):
    text = _make_applier(
        tmp_path, trusted=False, enable_gpg=True
    ).build_github_actions_release()

    assert 'EROTEMIC_TWINE_PASSWORD' in text
    assert 'EROTEMIC_TEST_TWINE_PASSWORD' in text


def test_rotate_secrets_trusted_without_gpg_skips_secret_upload(
    monkeypatch, tmp_path
):
    _FakeQueue.created.clear()
    fake_cmd_queue = types.SimpleNamespace(Queue=_FakeQueue)
    monkeypatch.setitem(sys.modules, 'cmd_queue', fake_cmd_queue)

    self = _make_applier(tmp_path, trusted=True, enable_gpg=False)
    _patch_rotate_secret_shell(monkeypatch)
    self.rotate_secrets()

    queue = _FakeQueue.created[-1]
    joined = '\n'.join(queue.commands)

    joined_posix = joined.replace('\\', '/')

    assert 'setup_package_environs_github_erotemic' in joined
    assert 'dev/setup_secrets.sh' in joined_posix
    assert 'source $(secret_loader.sh)' not in joined
    assert 'export_encrypted_code_signing_keys' not in joined
    assert 'upload_github_secrets' not in joined
    assert 'no additional CI secrets' in joined
    assert queue.ran


def test_rotate_secrets_trusted_with_gpg_keeps_gpg_export_and_secret_upload(
    monkeypatch, tmp_path
):
    """
    With the legacy ``encrypted_repo`` transport, rotate_secrets must still
    export the encrypted code-signing keys and upload the CI_SECRET-bearing
    repo secrets, even when trusted publishing is enabled.
    """
    _FakeQueue.created.clear()
    fake_cmd_queue = types.SimpleNamespace(Queue=_FakeQueue)
    monkeypatch.setitem(sys.modules, 'cmd_queue', fake_cmd_queue)

    self = _make_applier(tmp_path, trusted=True, enable_gpg=True)
    self.config['ci_gpg_secret_transport'] = 'encrypted_repo'
    _patch_rotate_secret_shell(monkeypatch)
    self.rotate_secrets()

    queue = _FakeQueue.created[-1]
    joined = '\n'.join(queue.commands)

    assert 'export_encrypted_code_signing_keys' in joined
    assert 'upload_github_secrets' in joined
    assert queue.ran


# ---------------------------------------------------------------------------
# Helpers for direct_ci transport mode tests
# ---------------------------------------------------------------------------


def _make_direct_gpg_applier(tmp_path, *, trusted, enable_gpg=True, tags=None):
    """Build a TemplateApplier with ci_gpg_secret_transport='direct_ci'."""
    self = _make_applier(
        tmp_path, trusted=trusted, enable_gpg=enable_gpg, tags=tags
    )
    self.config['ci_gpg_secret_transport'] = 'direct_ci'
    return self


# ---------------------------------------------------------------------------
# Template generation — GitHub Actions
# ---------------------------------------------------------------------------


def test_direct_gpg_github_env_has_gpg_secrets_not_ci_secret(tmp_path):
    text = _make_direct_gpg_applier(
        tmp_path, trusted=False
    ).build_github_actions_release()
    assert 'GPG_SECRET_SIGNING_SUBKEY_B64' in text
    assert 'GPG_PUBLIC_KEY_B64' in text
    assert 'GPG_OWNER_TRUST_B64' in text
    assert 'CI_SECRET' not in text


def test_direct_gpg_github_has_no_openssl_decrypt(tmp_path):
    text = _make_direct_gpg_applier(
        tmp_path, trusted=False
    ).build_github_actions_release()
    assert 'openssl enc' not in text
    assert '.pgp.enc' not in text
    assert 'Decrypting Keys' not in text


def test_direct_gpg_github_reads_anchor_from_repo_and_verifies(tmp_path):
    text = _make_direct_gpg_applier(
        tmp_path, trusted=False
    ).build_github_actions_release()
    assert 'cat dev/public_gpg_key' in text
    assert 'base64 -d' in text
    assert 'IMPORTED_FPR' in text
    assert 'fingerprint' in text.lower()


def test_direct_gpg_github_uses_printf_not_echo_for_decode(tmp_path):
    text = _make_direct_gpg_applier(
        tmp_path, trusted=False
    ).build_github_actions_release()
    assert "printf '%s'" in text or "printf '%s'" in text


def test_direct_gpg_github_non_trusted_has_twine_and_gpg_secrets(tmp_path):
    text = _make_direct_gpg_applier(
        tmp_path, trusted=False
    ).build_github_actions_release()
    assert 'TWINE_PASSWORD' in text
    assert 'GPG_SECRET_SIGNING_SUBKEY_B64' in text


def test_direct_gpg_trusted_github_has_no_ci_secret_no_twine(tmp_path):
    text = _make_direct_gpg_applier(
        tmp_path, trusted=True
    ).build_github_actions_release()
    # CI_SECRET must not be referenced as a secret in the job env; it may
    # still appear in footer comments explaining the two transport modes.
    assert 'secrets.CI_SECRET' not in text
    assert 'TWINE_PASSWORD' not in text
    assert 'GPG_SECRET_SIGNING_SUBKEY_B64' in text
    assert 'pypa/gh-action-pypi-publish' in text


def test_default_transport_matches_explicit_direct_ci(tmp_path):
    """The ``ci_gpg_secret_transport`` default must produce identical output
    whether the key is left at its default or set to its named value
    (``direct_ci``).
    """
    baseline = _make_applier(
        tmp_path, trusted=False, enable_gpg=True
    ).build_github_actions_release()
    explicit = _make_applier(tmp_path, trusted=False, enable_gpg=True)
    explicit.config['ci_gpg_secret_transport'] = 'direct_ci'
    assert baseline == explicit.build_github_actions_release()


def test_direct_gpg_github_job_has_environment_set(tmp_path):
    """deploy jobs must declare the GitHub environment so environment-scoped
    secrets are injected by the runner."""
    text = _make_direct_gpg_applier(
        tmp_path, trusted=False
    ).build_github_actions_release()
    assert 'environment: pypi' in text
    assert 'environment: testpypi' in text


# ---------------------------------------------------------------------------
# Template generation — GitLab CI
# ---------------------------------------------------------------------------


def test_direct_gpg_gitlab_no_ci_secret_no_openssl(tmp_path):
    text = _make_direct_gpg_applier(
        tmp_path, trusted=False, tags=['gitlab', 'kitware', 'purepy']
    ).build_gitlab_ci()
    # The gpgsign job must not contain openssl decrypt commands or CI_SECRET
    # (they may appear in other jobs, so check gpgsign-specific markers)
    assert 'openssl enc' not in text
    assert 'GPG_SECRET_SIGNING_SUBKEY_B64' in text
    assert 'base64 -d' in text


def test_direct_gpg_gitlab_reads_anchor_and_verifies(tmp_path):
    text = _make_direct_gpg_applier(
        tmp_path, trusted=False, tags=['gitlab', 'kitware', 'purepy']
    ).build_gitlab_ci()
    assert 'cat dev/public_gpg_key' in text
    assert 'IMPORTED_FPR' in text
    assert 'fingerprint' in text.lower()


def test_direct_gpg_gitlab_no_secrets_configuration_in_gpgsign_job(tmp_path):
    """In direct_ci mode the gpgsign job must not use VARNAME_CI_SECRET.
    (It may still appear in other jobs for push-token and Twine lookup.)"""
    text = _make_direct_gpg_applier(
        tmp_path, trusted=False, tags=['gitlab', 'kitware', 'purepy']
    ).build_gitlab_ci()
    # In encrypted_repo mode the gpgsign job contains these two together;
    # in direct_ci mode neither should appear.
    assert 'openssl enc' not in text
    assert 'CI_SECRET=${!VARNAME_CI_SECRET}' not in text


def test_default_transport_gitlab_matches_explicit_direct_ci(tmp_path):
    """Default GitLab CI output must be identical to setting
    ``ci_gpg_secret_transport='direct_ci'`` explicitly.
    """
    baseline = _make_applier(
        tmp_path,
        trusted=False,
        enable_gpg=True,
        tags=['gitlab', 'kitware', 'purepy'],
    ).build_gitlab_ci()
    explicit = _make_applier(
        tmp_path,
        trusted=False,
        enable_gpg=True,
        tags=['gitlab', 'kitware', 'purepy'],
    )
    explicit.config['ci_gpg_secret_transport'] = 'direct_ci'
    assert baseline == explicit.build_gitlab_ci()


# ---------------------------------------------------------------------------
# rotate_secrets orchestration
# ---------------------------------------------------------------------------


def test_rotate_secrets_direct_gpg_calls_gpg_upload_not_encrypt(
    monkeypatch, tmp_path
):
    _FakeQueue.created.clear()
    monkeypatch.setitem(
        sys.modules, 'cmd_queue', types.SimpleNamespace(Queue=_FakeQueue)
    )

    self = _make_direct_gpg_applier(tmp_path, trusted=False)
    _patch_rotate_secret_shell(monkeypatch)
    self.rotate_secrets()

    joined = '\n'.join(_FakeQueue.created[-1].commands)
    assert 'export_encrypted_code_signing_keys' not in joined
    assert 'upload_github_gpg_secrets' in joined
    # non-trusted: Twine secrets still uploaded (direct_gpg mode)
    assert 'upload_github_secrets direct_gpg' in joined
    # CI_SECRET must not appear in the orchestration script
    assert 'CI_SECRET' not in joined
    assert _FakeQueue.created[-1].ran


def test_rotate_secrets_direct_gpg_trusted_skips_non_gpg_upload(
    monkeypatch, tmp_path
):
    _FakeQueue.created.clear()
    monkeypatch.setitem(
        sys.modules, 'cmd_queue', types.SimpleNamespace(Queue=_FakeQueue)
    )

    self = _make_direct_gpg_applier(tmp_path, trusted=True)
    _patch_rotate_secret_shell(monkeypatch)
    self.rotate_secrets()

    joined = '\n'.join(_FakeQueue.created[-1].commands)
    assert 'upload_github_gpg_secrets' in joined
    # trusted publishing + direct GPG: nothing else to upload
    assert 'upload_github_secrets' not in joined
    assert 'no additional CI secrets' in joined
    assert _FakeQueue.created[-1].ran


def test_rotate_secrets_direct_gpg_gitlab_excludes_ci_secret(
    monkeypatch, tmp_path
):
    """GitLab direct_ci rotate: gpg secrets uploaded, repo secrets called with
    direct_gpg mode (excluding CI_SECRET), and CI_SECRET not in any command."""
    _FakeQueue.created.clear()
    monkeypatch.setitem(
        sys.modules, 'cmd_queue', types.SimpleNamespace(Queue=_FakeQueue)
    )

    self = _make_direct_gpg_applier(
        tmp_path, trusted=False, tags=['gitlab', 'kitware', 'purepy']
    )
    _patch_rotate_secret_shell(monkeypatch)
    self.rotate_secrets()

    joined = '\n'.join(_FakeQueue.created[-1].commands)
    assert 'upload_gitlab_gpg_secrets' in joined
    assert 'upload_gitlab_repo_secrets direct_gpg' in joined
    # CI_SECRET must not be referenced in the orchestration script
    assert 'CI_SECRET' not in joined
    assert _FakeQueue.created[-1].ran


def test_rotate_secrets_encrypted_repo_behavior_unchanged(
    monkeypatch, tmp_path
):
    """Regression: when ``ci_gpg_secret_transport='encrypted_repo'`` is
    selected explicitly, rotate_secrets must still produce the legacy
    encrypted-repo orchestration (``export_encrypted_code_signing_keys`` +
    ``upload_github_secrets``) without falling through to the new
    ``upload_github_gpg_secrets`` path.
    """
    _FakeQueue.created.clear()
    monkeypatch.setitem(
        sys.modules, 'cmd_queue', types.SimpleNamespace(Queue=_FakeQueue)
    )

    self = _make_applier(tmp_path, trusted=False, enable_gpg=True)
    self.config['ci_gpg_secret_transport'] = 'encrypted_repo'
    _patch_rotate_secret_shell(monkeypatch)
    self.rotate_secrets()

    joined = '\n'.join(_FakeQueue.created[-1].commands)
    assert 'export_encrypted_code_signing_keys' in joined
    assert 'upload_github_secrets' in joined
    assert 'upload_github_gpg_secrets' not in joined
    assert _FakeQueue.created[-1].ran
