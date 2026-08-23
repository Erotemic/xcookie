from __future__ import annotations

from xcookie.main import XCookieConfig
from xcookie.vcs.remote_info import resolve_remote_info
from xcookie.vcs.url import GitURL


def test_git_url_protocol_conversion():
    url = GitURL('git@github.com:pyutils/demo.git')
    assert url.info['host'] == 'github.com'
    assert str(url.to_https()) == 'https://github.com/pyutils/demo.git'


def test_remote_info_defaults_from_tags(tmp_path):
    config = XCookieConfig(
        repodir=tmp_path,
        repo_name='demo',
        mod_name='demo',
        tags=['github', 'pyutils', 'purepy'],
        interactive=False,
        use_vcs=False,
        author='Example Author',
        author_email='author@example.com',
    )
    info = resolve_remote_info(config, tmp_path)
    assert info['type'] == 'github'
    assert info['host'] == 'https://github.com'
    assert info['group'] == 'pyutils'
    assert info['url'] == 'https://github.com/pyutils/demo'


def test_main_preserves_legacy_vcs_helper_imports(tmp_path):
    from xcookie.main import GitURL as MainGitURL
    from xcookie.main import find_git_root

    assert MainGitURL is GitURL
    repo = tmp_path / 'repo'
    nested = repo / 'a' / 'b'
    (repo / '.git').mkdir(parents=True)
    nested.mkdir(parents=True)
    assert find_git_root(nested) == repo
