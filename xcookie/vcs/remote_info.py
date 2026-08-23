"""Resolve repository hosting metadata from config, tags, and Git."""

from __future__ import annotations

from typing import Any

import ubelt as ub

from xcookie.vcs.url import GitURL


def resolve_remote_info(config: Any, repodir: ub.Path) -> ub.udict:
    """Resolve the remote host/group/url while preserving legacy defaults."""
    tags = set(config['tags'])
    remote_info = ub.udict({'type': 'unknown'})

    if isinstance(config.url, str) and config.url.lower() in {'none', 'null'}:
        config.url = None

    if config.url is None:
        git_dpath = repodir / '.git'
        if git_dpath.exists():
            resp = ub.cmd(['git', 'remote', 'get-url', 'origin'], cwd=repodir)
            if resp['ret'] == 0:
                remote_url = resp['out'].strip()
                try:
                    config.url = GitURL(remote_url).to_https()
                    if config.url.endswith('.git'):
                        config.url = config.url[:-4]
                except (IndexError, ValueError):
                    pass

    if config['remote_host'] is not None:
        remote_info['host'] = config['remote_host']
    if config['remote_group'] is not None:
        remote_info['group'] = config['remote_group']

    url = config.get('url', None)
    if url is not None:
        info = GitURL(url).info
        remote_info['group'] = info['group']
        remote_info['host'] = info['host']
        remote_info['repo_name'] = info['repo_name']
        if 'github' in remote_info['host']:
            remote_info['type'] = 'github'
        if 'gitlab' in remote_info['host']:
            remote_info['type'] = 'gitlab'

    if 'gitlab' in tags:
        remote_info['type'] = 'gitlab'
    if 'github' in tags:
        remote_info['type'] = 'github'

    defaults = ub.udict()
    if remote_info['type'] == 'gitlab' and 'kitware' in tags:
        defaults['host'] = 'https://gitlab.kitware.com'
        defaults['group'] = 'computer-vision'
    if remote_info['type'] == 'github':
        defaults['host'] = 'https://github.com'
        if 'erotemic' in tags:
            defaults['group'] = 'Erotemic'
        if 'pyutils' in tags:
            defaults['group'] = 'pyutils'

    remote_info = defaults | remote_info
    remote_info['repo_name'] = config['repo_name']

    if 'group' in remote_info and 'host' in remote_info:
        config['remote_host'] = remote_info['host']
        config['remote_group'] = remote_info['group']
        remote_info['url'] = '/'.join(
            [remote_info['host'], remote_info['group'], config['repo_name']]
        )
        remote_info['git_url'] = remote_info['url'] + '.git'

    return remote_info
