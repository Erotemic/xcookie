from __future__ import annotations

import ubelt as ub


def test_modal_root_help_is_command_oriented() -> None:
    from xcookie.cli import XCookieCLI

    help_text = XCookieCLI().argparse().format_help()
    assert 'generate' in help_text
    assert 'bump' in help_text
    assert 'rotate-secrets' in help_text
    assert 'refresh-docs' in help_text
    assert '--regen' not in help_text


def test_generate_help_contains_existing_generator_options() -> None:
    from xcookie.cli import XCookieCLI

    parser = XCookieCLI().argparse()
    generate_parser = next(
        action.choices['generate']
        for action in parser._actions
        if hasattr(action, 'choices') and action.choices
    )
    help_text = generate_parser.format_help()
    assert '--regen' in help_text
    assert '--rotate_secrets' not in help_text
    assert '--refresh_docs' not in help_text
    assert 'repodir' in help_text


def test_generate_dispatch_forwards_explicit_values(monkeypatch) -> None:
    from xcookie.cli import XCookieCLI
    from xcookie.main import XCookieConfig

    called = {}

    def fake_main(cls, argv=False, **kwargs):
        called['argv'] = argv
        called['kwargs'] = kwargs
        return 17

    monkeypatch.setattr(XCookieConfig, 'main', classmethod(fake_main))

    result = XCookieCLI.main(
        argv=[
            'generate',
            'demo-repo',
            '--regen=setup.py',
            '--interactive=False',
        ],
        autocomplete=False,
    )

    assert result == 17
    assert called == {
        'argv': False,
        'kwargs': {
            'strict': True,
            'autocomplete': 'auto',
            'repodir': 'demo-repo',
            'regen': 'setup.py',
            'interactive': False,
        },
    }


def test_modal_version_matches_package_version(capsys) -> None:
    import xcookie
    from xcookie.cli import XCookieCLI

    result = XCookieCLI.main(argv=['--version'], autocomplete=False)
    captured = capsys.readouterr()

    assert result == 0
    assert captured.out.strip() == xcookie.__version__


def test_rotate_secrets_dispatches_as_separate_action(monkeypatch) -> None:
    from xcookie.cli import XCookieCLI
    from xcookie.main import XCookieConfig
    from xcookie.secrets import SecretRotator

    loaded = {}
    rotated = {}

    def fake_load(cls, argv=False, **kwargs):
        loaded['argv'] = argv
        loaded['kwargs'] = kwargs
        return {'repodir': kwargs['repodir']}

    def fake_rotate(self):
        rotated['repodir'] = self.repodir

    monkeypatch.setattr(
        XCookieConfig, 'load_from_cli_and_pyproject', classmethod(fake_load)
    )
    monkeypatch.setattr(SecretRotator, 'rotate_secrets', fake_rotate)

    result = XCookieCLI.main(
        argv=['rotate-secrets', 'demo-repo', '--yes'],
        autocomplete=False,
    )

    assert isinstance(result, SecretRotator)
    assert loaded == {
        'argv': False,
        'kwargs': {
            'repodir': 'demo-repo',
            'interactive': True,
            'yes': True,
        },
    }
    assert str(rotated['repodir']) == 'demo-repo'


def test_refresh_docs_dispatches_as_separate_action(monkeypatch) -> None:
    from xcookie.cli import XCookieCLI
    from xcookie.docs import DocsRefresher
    from xcookie.main import XCookieConfig

    loaded = {}
    refreshed = {}

    def fake_load(cls, argv=False, **kwargs):
        loaded['argv'] = argv
        loaded['kwargs'] = kwargs
        return {'repodir': kwargs['repodir']}

    def fake_refresh(self):
        refreshed['repodir'] = self.repodir

    monkeypatch.setattr(
        XCookieConfig, 'load_from_cli_and_pyproject', classmethod(fake_load)
    )
    monkeypatch.setattr(DocsRefresher, 'refresh_docs', fake_refresh)

    result = XCookieCLI.main(
        argv=['refresh-docs', 'demo-repo'],
        autocomplete=False,
    )

    assert isinstance(result, DocsRefresher)
    assert loaded == {
        'argv': False,
        'kwargs': {'repodir': 'demo-repo'},
    }
    assert str(refreshed['repodir']) == 'demo-repo'


def test_bump_dispatches_as_separate_action(monkeypatch) -> None:
    from xcookie.cli import XCookieCLI
    from xcookie.versioning import VersionBumper

    called = {}

    def fake_bump(self, target='patch', *, branch=False):
        called['repodir'] = self.repodir
        called['target'] = target
        called['branch'] = branch

    monkeypatch.setattr(VersionBumper, 'bump', fake_bump)

    result = XCookieCLI.main(
        argv=['bump', 'minor', 'demo-repo'],
        autocomplete=False,
    )

    assert isinstance(result, VersionBumper)
    assert called['target'] == 'minor'
    assert called['branch'] is False
    assert called['repodir'].name == 'demo-repo'


def test_bump_defaults_to_patch_in_current_directory(monkeypatch) -> None:
    from xcookie.cli import XCookieCLI
    from xcookie.versioning import VersionBumper

    called = {}

    def fake_bump(self, target='patch', *, branch=False):
        called['repodir'] = self.repodir
        called['target'] = target
        called['branch'] = branch

    monkeypatch.setattr(VersionBumper, 'bump', fake_bump)

    result = XCookieCLI.main(argv=['bump'], autocomplete=False)

    assert isinstance(result, VersionBumper)
    assert called['target'] == 'patch'
    assert called['branch'] is False
    assert called['repodir'].name == ub.Path.cwd().name


def test_bump_forwards_optional_branch(monkeypatch) -> None:
    from xcookie.cli import XCookieCLI
    from xcookie.versioning import VersionBumper

    called = {}

    def fake_bump(self, target='patch', *, branch=False):
        called['target'] = target
        called['branch'] = branch

    monkeypatch.setattr(VersionBumper, 'bump', fake_bump)

    XCookieCLI.main(
        argv=[
            'bump',
            'patch',
            'demo-repo',
            '--branch',
        ],
        autocomplete=False,
    )

    assert called == {'target': 'patch', 'branch': True}


def test_modal_short_aliases_dispatch(monkeypatch) -> None:
    from xcookie.cli import XCookieCLI
    from xcookie.docs import DocsRefresher
    from xcookie.main import XCookieConfig
    from xcookie.secrets import SecretRotator
    from xcookie.versioning import VersionBumper

    generated = {}
    bumped = {}
    refreshed = {}
    rotated = {}

    def fake_generate(cls, argv=False, **kwargs):
        generated.update(kwargs)
        return 'generated'

    def fake_bump(self, target='patch', *, branch=False):
        bumped.update(target=target, branch=branch)

    def fake_load(cls, argv=False, **kwargs):
        return {'repodir': kwargs['repodir']}

    def fake_refresh(self):
        refreshed['repodir'] = str(self.repodir)

    def fake_rotate(self):
        rotated['repodir'] = str(self.repodir)

    monkeypatch.setattr(XCookieConfig, 'main', classmethod(fake_generate))
    monkeypatch.setattr(VersionBumper, 'bump', fake_bump)
    monkeypatch.setattr(
        XCookieConfig, 'load_from_cli_and_pyproject', classmethod(fake_load)
    )
    monkeypatch.setattr(DocsRefresher, 'refresh_docs', fake_refresh)
    monkeypatch.setattr(SecretRotator, 'rotate_secrets', fake_rotate)

    assert (
        XCookieCLI.main(
            argv=['g', 'demo-repo', '--interactive=False'],
            autocomplete=False,
        )
        == 'generated'
    )
    XCookieCLI.main(argv=['b', 'minor', 'demo-repo'], autocomplete=False)
    XCookieCLI.main(argv=['docs', 'demo-repo'], autocomplete=False)
    XCookieCLI.main(argv=['secrets', 'demo-repo', '--yes'], autocomplete=False)

    assert generated['repodir'] == 'demo-repo'
    assert bumped == {'target': 'minor', 'branch': False}
    assert refreshed == {'repodir': 'demo-repo'}
    assert rotated == {'repodir': 'demo-repo'}
