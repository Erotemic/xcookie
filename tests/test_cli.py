from __future__ import annotations


def test_modal_root_help_is_command_oriented() -> None:
    from xcookie.cli import XCookieCLI

    help_text = XCookieCLI().argparse().format_help()
    assert 'generate' in help_text
    assert '--regen' not in help_text
    assert '--rotate-secrets' not in help_text


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
    assert '--rotate_secrets' in help_text
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
            '--rotate-secrets=False',
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
            'rotate_secrets': False,
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
