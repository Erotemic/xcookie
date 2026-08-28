"""Git remote URL parsing and protocol conversion."""

from __future__ import annotations

import ubelt as ub


class GitURL(str):
    """
    Represents a url to a git repo and can parse info about / modify the
    protocol

    References:
        https://git-scm.com/docs/git-clone#_git_urls

    TODO: can use git-well as a helper here.

    CommandLine:
        xdoctest -m xcookie.vcs.url GitURL

    Example:
        >>> urls = [
        >>>     GitURL('https://foo.bar/user/repo.git'),
        >>>     GitURL('ssh://foo.bar/user/repo.git'),
        >>>     GitURL('ssh://git@foo.bar/user/repo.git'),
        >>>     GitURL('git@foo.bar:group/repo.git'),
        >>>     GitURL('host:path/to/my/repo/.git'),
        >>> ]
        >>> for url in urls:
        >>>     print('---')
        >>>     print(f'url = {url}')
        >>>     print(ub.urepr(url.info))
        >>>     print('As git   : ' + url.to_git())
        >>>     print('As ssh   : ' + url.to_ssh())
        >>>     print('As https : ' + url.to_https())

    """

    def __init__(self, data):
        # note: inheriting from str so data is handled in __new__
        self._info = None

    def _parse(self):
        import parse

        parse.Parser('ssh://{user}')

    @property
    def info(self):
        if self._info is None:
            url = self
            info = {}
            if url == '':
                ...
            elif url.startswith('https://'):
                parts = url.split('https://')[1].split('/', 3)
                info['host'] = parts[0]
                info['group'] = parts[1]
                info['repo_name'] = parts[2]
                info['user'] = None
                info['protocol'] = 'https'
            elif url.startswith('git@'):
                parts = url.split('git@')[1].split(':')
                info['host'] = parts[0]
                info['group'] = parts[1].split('/')[0]
                info['repo_name'] = parts[1].split('/')[1]
                info['user'] = 'git'
                info['protocol'] = 'git'
            elif url.startswith('ssh://'):
                parts = url.split('ssh://')[1].split('/', 3)
                user = None
                if '@' in parts[0]:
                    user, host = parts[0].split('@')
                else:
                    host = parts[0]
                info['host'] = host
                info['user'] = user
                info['group'] = parts[1]
                info['repo_name'] = parts[2]
                info['protocol'] = 'ssh'
            elif url.endswith('/.git'):
                # An ssh protocol to an explicit directory
                host, rest = url.split(':', 1)
                parts = rest.rsplit('/', 2)
                info['host'] = host
                info['group'] = parts[0]
                # info['group'] = ''
                info['repo_name'] = parts[1] + '/.git'
                info['protocol'] = 'scp'
            elif '//' not in url and '@' not in url:
                parts = url.split(':')
                info['host'] = parts[0]
                info['group'] = parts[1].split('/')[0]
                info['repo_name'] = parts[1].split('/')[1]
                info['protocol'] = 'ssh'
            else:
                raise ValueError(url)
            info['url'] = url
            self._info = info
        return self._info

    def to_git(self):
        info = self.info
        new_url = (
            'git@'
            + info['host']
            + ':'
            + info['group']
            + '/'
            + info['repo_name']
        )
        return self.__class__(new_url)

    def to_ssh(self):
        info = self.info
        user = info.get('user', None)
        if user is None:
            user_part = ''
        else:
            user_part = user + '@'
        new_url = (
            'ssh://'
            + user_part
            + info['host']
            + '/'
            + info['group']
            + '/'
            + info['repo_name']
        )
        return self.__class__(new_url)

    def to_https(self):
        info = self.info
        new_url = (
            'https://'
            + info['host']
            + '/'
            + info['group']
            + '/'
            + info['repo_name']
        )
        return self.__class__(new_url)

