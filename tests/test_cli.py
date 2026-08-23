from __future__ import annotations


def test_modal_root_help_is_command_oriented() -> None:
    from xcookie.cli import XCookieCLI

    help_text = XCookieCLI().argparse().format_help()
    assert 'generate' in help_text
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
