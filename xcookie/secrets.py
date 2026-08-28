"""Repository secret-rotation action used by the modal CLI."""

from __future__ import annotations

from typing import Any

import ubelt as ub

from xcookie.util_command import make_command_queue


class SecretRotator:
    """Rotate configured CI secrets for an existing xcookie repository."""

    def __init__(self, config: Any) -> None:
        self.config = config
        self.repodir = ub.Path(config['repodir'])

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
        owner = None
        url = self.config.get('url', None)
        if isinstance(url, str) and 'github' in url:
            parts = url.split('github.com/', 1)[-1].strip('/').split('/')
            if parts and parts[0]:
                owner = parts[0].lower()
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
        use_trusted_publishing = self.config.get(
            'ci_pypi_trusted_publishing', False
        )
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
            is_github = backend['is_github']

            script.sync().submit(
                f'echo "===== Rotating secrets for {backend["name"]}'
                ' backend ====="',
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
            elif use_trusted_publishing and is_github:
                script.sync().submit(
                    f'{upload_secret_cmd} trusted_publishing', log=False
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
