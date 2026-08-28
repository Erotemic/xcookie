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


def test_explicit_vcs_disable_does_not_warn_about_remote_metadata(tmp_path):
    import warnings

    from xcookie.main import TemplateApplier

    repodir = tmp_path / 'demo'
    repodir.mkdir()
    config = XCookieConfig(
        repodir=repodir,
        repo_name='demo',
        mod_name='demo',
        tags=['github', 'purepy'],
        interactive=False,
        use_vcs=False,
        init_new_remotes=False,
    )

    with warnings.catch_warnings(record=True) as records:
        warnings.simplefilter('always')
        applier = TemplateApplier(config)
        applier.setup()
        applier.close()

    vcs_warnings = [
        record
        for record in records
        if 'VCS system' in str(record.message)
        or 'Unknown user / group' in str(record.message)
    ]
    assert not vcs_warnings


def test_template_applier_finalizer_cleans_staging_without_resource_warning(
    tmp_path,
):
    import gc
    import warnings

    from xcookie.main import TemplateApplier

    repodir = tmp_path / 'demo'
    repodir.mkdir()
    config = XCookieConfig(
        repodir=repodir,
        repo_name='demo',
        mod_name='demo',
        tags=['github', 'purepy'],
        interactive=False,
        use_vcs=False,
        init_new_remotes=False,
    )

    with warnings.catch_warnings(record=True) as records:
        warnings.simplefilter('always', ResourceWarning)
        applier = TemplateApplier(config)
        staging_dpath = applier.staging_dpath
        assert staging_dpath.exists()
        del applier
        gc.collect()

    assert not staging_dpath.exists()
    resource_warnings = [
        record
        for record in records
        if issubclass(record.category, ResourceWarning)
    ]
    assert not resource_warnings
