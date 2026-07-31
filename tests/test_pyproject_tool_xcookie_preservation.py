import toml


def test_pyproject_regen_does_not_write_inferred_tool_xcookie_defaults(
    tmp_path,
):
    """Self-regeneration should not persist resolver defaults as config."""
    from xcookie.main import TemplateApplier, XCookieConfig

    repodir = tmp_path / 'demo'
    pkgdir = repodir / 'demo_mod'
    pkgdir.mkdir(parents=True)
    (pkgdir / '__init__.py').write_text("__version__ = '2.0.0'\n")
    (repodir / 'pyproject.toml').write_text(
        toml.dumps(
            {
                'tool': {
                    'xcookie': {
                        'tags': ['github', 'purepy'],
                        'mod_name': 'demo_mod',
                        'repo_name': 'demo_mod',
                        'author': 'Existing Author',
                        'author_email': 'author@example.com',
                        'url': 'https://github.com/example/demo_mod',
                        'description': 'Demo module',
                        'min_python': '3.10',
                        'typed': True,
                    }
                }
            }
        )
    )

    config = XCookieConfig.load_from_cli_and_pyproject(
        argv=0,
        repodir=repodir,
        interactive=False,
        rotate_secrets=False,
        init_new_remotes=False,
        use_vcs=False,
        use_setup_py=False,
        use_pyproject_requirements=False,
    )

    applier = TemplateApplier(config)
    applier.setup()

    pyproject_data = toml.loads(
        (applier.staging_dpath / 'pyproject.toml').read_text()
    )
    xcookie_block = pyproject_data['tool']['xcookie']

    assert xcookie_block['use_setup_py'] is False
    assert xcookie_block['use_pyproject_requirements'] is False
    assert xcookie_block['tags'] == ['github', 'purepy']
    assert xcookie_block['mod_name'] == 'demo_mod'

    # These values are all resolvable defaults.  Writing them creates noisy
    # self-update diffs and, for version, can conflict with PEP 621 dynamic
    # version metadata.
    assert 'version' not in xcookie_block
    assert 'pkg_name' not in xcookie_block
    assert 'rel_mod_parent_dpath' not in xcookie_block
    assert 'os' not in xcookie_block
    assert 'license' not in xcookie_block
    assert 'dev_status' not in xcookie_block
    assert 'remote_host' not in xcookie_block
    assert 'remote_group' not in xcookie_block


def test_pyproject_regen_preserves_explicit_tool_xcookie_values(tmp_path):
    """Existing explicit tool.xcookie values should survive regeneration."""
    from xcookie.main import TemplateApplier, XCookieConfig

    repodir = tmp_path / 'demo'
    pkgdir = repodir / 'src' / 'demo_mod'
    pkgdir.mkdir(parents=True)
    (pkgdir / '__init__.py').write_text("__version__ = '2.0.0'\n")
    (repodir / 'pyproject.toml').write_text(
        toml.dumps(
            {
                'tool': {
                    'xcookie': {
                        'tags': ['github', 'purepy'],
                        'mod_name': 'demo_mod',
                        'repo_name': 'demo_repo',
                        'pkg_name': 'demo-pkg',
                        'rel_mod_parent_dpath': 'src',
                        'os': ['linux'],
                        'version': '2.0.0',
                        'license': 'Apache-2.0',
                        'dev_status': 'beta',
                        'remote_host': 'github.com',
                        'remote_group': 'example',
                        'typecheck_extra_paths': [
                            'tests/typecheck_consumer.py'
                        ],
                        'entry_points': {
                            'console_scripts': [
                                'demo=demo_mod.__main__:main',
                            ]
                        },
                    }
                }
            }
        )
    )

    config = XCookieConfig.load_from_cli_and_pyproject(
        argv=0,
        repodir=repodir,
        interactive=False,
        rotate_secrets=False,
        init_new_remotes=False,
        use_vcs=False,
        use_setup_py=False,
        use_pyproject_requirements=False,
    )

    applier = TemplateApplier(config)
    applier.setup()

    pyproject_data = toml.loads(
        (applier.staging_dpath / 'pyproject.toml').read_text()
    )
    xcookie_block = pyproject_data['tool']['xcookie']

    assert xcookie_block['pkg_name'] == 'demo-pkg'
    assert xcookie_block['rel_mod_parent_dpath'] == 'src'
    assert xcookie_block['os'] == ['linux']
    assert xcookie_block['version'] == '2.0.0'
    assert xcookie_block['license'] == 'Apache-2.0'
    assert xcookie_block['dev_status'] == 'beta'
    assert xcookie_block['remote_host'] == 'github.com'
    assert xcookie_block['remote_group'] == 'example'
    assert xcookie_block['typecheck_extra_paths'] == [
        'tests/typecheck_consumer.py'
    ]
    assert xcookie_block['entry_points']['console_scripts'] == [
        'demo=demo_mod.__main__:main',
    ]
