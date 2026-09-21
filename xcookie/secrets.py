"""Repository secret-rotation action used by the modal CLI."""

from __future__ import annotations

import shlex
from typing import Any

import ubelt as ub

from xcookie.publishing import trusted_publishing_enabled
from xcookie.util_command import make_command_queue
from xcookie.vcs.url import GitURL


class SecretRotator:
    """Rotate configured CI secrets for an existing xcookie repository."""

    def __init__(self, config: Any) -> None:
        self.config = config
        self.repodir = ub.Path(config['repodir'])

    def _configured_github_repo_full_name(self) -> str | None:
        """Return ``owner/repo`` for an explicitly configured GitHub URL."""
        candidate_urls = [
            self.config.get('github_url', None),
            self.config.get('url', None),
        ]
        for url in candidate_urls:
            if not isinstance(url, str) or not url:
                continue
            try:
                info = GitURL(url).info
            except (IndexError, ValueError):
                continue
            if info.get('host', '').lower() != 'github.com':
                continue
            owner = info.get('group', '')
            repo_name = info.get('repo_name', '').removesuffix('.git')
            if owner and repo_name:
                return f'{owner}/{repo_name}'
        return None

    def _github_org_environ(self) -> str:
        """Resolve the org-specific GitHub environment export function."""
        tags = self.config['tags']
        if 'erotemic' in tags:
            return 'setup_package_environs_github_erotemic'
        if 'pyutils' in tags:
            return 'setup_package_environs_github_pyutils'

        owner_to_environ = {
            'erotemic': 'setup_package_environs_github_erotemic',
            'pyutils': 'setup_package_environs_github_pyutils',
        }
        repo_full_name = self._configured_github_repo_full_name()
        owner = (
            repo_full_name.partition('/')[0].lower()
            if repo_full_name is not None
            else None
        )
        environ = owner_to_environ.get(owner) if owner is not None else None
        if environ is None:
            raise Exception(
                'Cannot determine which GitHub org secret-config to use for '
                'the github backend. Add an org tag (e.g. "erotemic" or '
                f'"pyutils") to tags, or extend _github_org_environ for '
                f'owner={owner!r}.'
            )
        return environ

    def _secret_rotation_backends(self) -> list[dict[str, Any]]:
        """Determine the CI backends whose secrets should be rotated."""
        tags = self.config['tags']
        backends = []

        if {'github', 'erotemic', 'pyutils'} & set(tags):
            backends.append(
                {
                    'name': 'github',
                    'environ_export': self._github_org_environ(),
                    'upload_secret_cmd': 'upload_github_secrets',
                    'gpg_upload_cmd': 'upload_github_gpg_secrets',
                    'is_github': True,
                    'repo_full_name': self._configured_github_repo_full_name(),
                }
            )

        if {'gitlab', 'kitware'} & set(tags):
            backends.append(
                {
                    'name': 'gitlab',
                    'environ_export': 'setup_package_environs_gitlab_kitware',
                    'upload_secret_cmd': 'upload_gitlab_repo_secrets',
                    'gpg_upload_cmd': 'upload_gitlab_gpg_secrets',
                    'is_github': False,
                }
            )

        if not backends:
            raise Exception(
                'No known CI backend in tags; expected one of '
                '{github, erotemic, pyutils, gitlab, kitware}. '
                f'Got tags={tags!r}'
            )
        return backends

    def rotate_secrets(self) -> None:
        """Print the rotation plan, confirm it, then execute it."""
        setup_secrets_fpath = self.repodir / 'dev/setup_secrets.sh'
        enable_gpg = self.config['enable_gpg']
        ci_gpg_transport = self.config.get(
            'ci_gpg_secret_transport', 'encrypted_repo'
        )
        use_direct_gpg = ci_gpg_transport == 'direct_ci'
        backends = self._secret_rotation_backends()

        script = make_command_queue(
            cwd=self.repodir, backend='serial', log=False
        )
        script.submit(f'source {setup_secrets_fpath}', log=False)

        for backend in backends:
            environ_export = backend['environ_export']
            upload_secret_cmd = backend['upload_secret_cmd']
            gpg_upload_cmd = backend['gpg_upload_cmd']
            provider = backend['name']
            is_github = backend['is_github']
            use_trusted_publishing = trusted_publishing_enabled(
                self.config, provider
            )

            script.sync().submit(
                f'echo "===== Rotating secrets for {backend["name"]}'
                ' backend ====="',
                log=False,
            )
            if is_github and backend.get('repo_full_name'):
                repo_full_name = shlex.quote(backend['repo_full_name'])
                script.sync().submit(
                    f'export GH_REPO={repo_full_name}', log=False
                )
                # Older generated setup_secrets.sh files only inspect origin.
                # Override their helper so xcookie secrets works immediately
                # for a GitLab-primary checkout with an explicit GitHub mirror.
                script.sync().submit(
                    "github_repo_full_name(){ printf '%s' \"$GH_REPO\"; }",
                    log=False,
                )
            script.sync().submit(f'{environ_export}', log=False)

            if enable_gpg:
                if use_direct_gpg:
                    script.sync().submit(gpg_upload_cmd, log=False)
                else:
                    script.sync().submit(
                        'export_encrypted_code_signing_keys', log=False
                    )

            skip_non_gpg = (
                use_trusted_publishing
                and is_github
                and (not enable_gpg or use_direct_gpg)
            )

            if skip_non_gpg:
                script.sync().submit(
                    'echo "Trusted publishing + direct GPG (or no GPG):'
                    ' no additional CI secrets to upload."',
                    log=False,
                )
            elif use_trusted_publishing:
                if is_github:
                    mode = 'trusted_publishing'
                else:
                    mode = (
                        'trusted_publishing_direct_gpg'
                        if use_direct_gpg or not enable_gpg
                        else 'trusted_publishing_encrypted_gpg'
                    )
                script.sync().submit(
                    f'{upload_secret_cmd} {mode}', log=False
                )
            elif use_direct_gpg:
                script.sync().submit(
                    f'{upload_secret_cmd} direct_gpg', log=False
                )
            else:
                script.sync().submit(f'{upload_secret_cmd}', log=False)

        script.rprint()
        if self.config.confirm('Ready to rotate secrets?'):
            script.run()
