"""Resolve the correct GitHub secret target before executing any upload."""

import shutil
import subprocess
from unittest.mock import MagicMock

import pytest

import xcookie.secrets as secrets_mod
from xcookie.secrets import SecretRotator


class _Config(dict):
    def confirm(self, message):
        return True


def _config(tmp_path, *, tags=('github', 'erotemic'), **kwargs):
    return _Config(
        repodir=tmp_path,
        repo_name='ubelt',
        tags=list(tags),
        enable_gpg=True,
        ci_gpg_secret_transport='direct_ci',
        ci_pypi_trusted_publishing=True,
        **kwargs,
    )


def _add_remotes(tmp_path, remotes):
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    for name, url in remotes.items():
        subprocess.run(
            ['git', '-C', str(tmp_path), 'remote', 'add', name, url],
            check=True,
        )


def test_secret_rotation_selects_tagged_repo_with_multiple_remotes(
    monkeypatch, tmp_path
):
    """Owner tags identify the target despite additional Git remotes."""
    _add_remotes(
        tmp_path,
        {
            'origin': 'git@github.com:Erotemic/ubelt.git',
            'fork': 'https://github.com/someone/ubelt.git',
            'other': 'https://github.com/someone/different.git',
        },
    )
    queue = MagicMock()
    queue.sync.return_value = queue
    queue.submit.return_value = queue
    monkeypatch.setattr(secrets_mod, 'make_command_queue', lambda **kw: queue)

    rotator = SecretRotator(_config(tmp_path))
    assert rotator._configured_github_repo_full_name() == 'Erotemic/ubelt'
    rotator.rotate_secrets()

    commands = [call.args[0] for call in queue.submit.call_args_list]
    script = '\n'.join(commands)
    assert (
        'if [[ -z "${GH_REPO:-}" ]]; then '
        'export GH_REPO=Erotemic/ubelt; fi'
    ) in script
    assert 'upload_github_gpg_secrets' in script
    assert 'upload_github_secrets' not in script
    assert queue.run.called


def test_secret_rotation_configured_github_url_takes_precedence(tmp_path):
    cfg = _config(
        tmp_path,
        github_url='https://github.com/OtherOwner/actual_repo.git',
    )
    assert (
        SecretRotator(cfg)._configured_github_repo_full_name()
        == 'OtherOwner/actual_repo'
    )


def test_secret_rotation_remote_group_takes_precedence(tmp_path):
    cfg = _config(
        tmp_path,
        remote_host='https://github.com',
        remote_group='DifferentOwner',
    )
    assert (
        SecretRotator(cfg)._configured_github_repo_full_name()
        == 'DifferentOwner/ubelt'
    )


def test_secret_rotation_can_match_project_remote_without_owner_tag(tmp_path):
    _add_remotes(
        tmp_path,
        {
            'origin': 'https://github.com/Erotemic/other-project.git',
            'mirror': 'git@github.com:Erotemic/ubelt.git',
            'gitlab': 'https://gitlab.example.org/group/ubelt.git',
        },
    )
    rotator = SecretRotator(_config(tmp_path, tags=('github',)))
    assert rotator._configured_github_repo_full_name() == 'Erotemic/ubelt'
    assert (
        rotator._github_org_environ()
        == 'setup_package_environs_github_erotemic'
    )


def test_secret_rotation_refuses_ambiguous_same_name_remotes(tmp_path):
    _add_remotes(
        tmp_path,
        {
            'origin': 'git@github.com:owner-one/ubelt.git',
            'mirror': 'https://github.com/owner-two/ubelt',
        },
    )
    rotator = SecretRotator(_config(tmp_path, tags=('github',)))
    with pytest.raises(ValueError, match='Ambiguous GitHub targets'):
        rotator._configured_github_repo_full_name()


def test_explicit_gh_repo_overrides_ambiguous_remotes(monkeypatch, tmp_path):
    _add_remotes(
        tmp_path,
        {
            'origin': 'git@github.com:owner-one/ubelt.git',
            'mirror': 'https://github.com/owner-two/ubelt',
        },
    )
    monkeypatch.setenv('GH_REPO', 'github.com/Erotemic/ubelt')
    rotator = SecretRotator(_config(tmp_path, tags=('github',)))
    assert rotator._configured_github_repo_full_name() == 'Erotemic/ubelt'
    assert (
        rotator._github_org_environ()
        == 'setup_package_environs_github_erotemic'
    )


def test_secret_rotation_preserves_explicit_gh_repo(monkeypatch, tmp_path):
    """The generated shell must not clobber a user-provided GH_REPO."""
    queue = MagicMock()
    queue.sync.return_value = queue
    queue.submit.return_value = queue
    monkeypatch.setattr(secrets_mod, 'make_command_queue', lambda **kw: queue)
    SecretRotator(_config(tmp_path)).rotate_secrets()
    script = '\n'.join(
        call.args[0] for call in queue.submit.call_args_list
    )
    assert 'if [[ -z "${GH_REPO:-}" ]]; then' in script
    assert '"${GH_REPO#github.com/}"' in script

    commands = [
        line for line in script.splitlines()
        if 'GH_REPO' in line or line.startswith('github_repo_full_name()')
    ]
    if shutil.which('bash') is None:
        return  # Shell execution is checked where Bash is available.
    for initial, expected in [
        ('', 'Erotemic/ubelt'),
        ('someone/another-repo', 'someone/another-repo'),
        ('github.com/someone/other', 'someone/other'),
    ]:
        result = subprocess.run(
            ['bash', '-c', '\n'.join(commands) + '\ngithub_repo_full_name'],
            capture_output=True,
            text=True,
            check=True,
            env={'GH_REPO': initial},
        )
        assert result.stdout == expected
