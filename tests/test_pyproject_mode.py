import toml


def test_use_setup_py_false_generates_pep621(tmp_path) -> None:
    """
    When setup.py generation is disabled, ensure we emit a PEP 621 style
    pyproject.toml and do not stage a setup.py file.
    """
    from xcookie.main import TemplateApplier, XCookieConfig

    repodir = tmp_path / 'demo'
    repodir.mkdir()

    config = XCookieConfig(
        repodir=repodir,
        mod_name='demo_mod',
        repo_name='demo_mod',
        tags=['github', 'purepy'],
        rotate_secrets=False,
        init_new_remotes=False,
        interactive=False,
        use_setup_py=False,
        use_vcs=False,
    )

    applier = TemplateApplier(config)
    applier.setup()

    staged_fnames = {info['fname'] for info in applier.staging_infos}
    assert 'setup.py' not in staged_fnames

    pyproject_text = (applier.staging_dpath / 'pyproject.toml').read_text()
    pyproject_data = toml.loads(pyproject_text)

    project_block = pyproject_data['project']
    assert project_block['name'] == config['pkg_name']
    assert 'dependencies' in project_block['dynamic']
    assert (
        pyproject_data['build-system']['build-backend']
        == 'setuptools.build_meta'
    )

    setuptools_dynamic = pyproject_data['tool']['setuptools']['dynamic']
    assert setuptools_dynamic['dependencies']['file'] == [
        'requirements/runtime.txt'
    ]
    assert 'tests' in setuptools_dynamic['optional-dependencies']

    package_data = pyproject_data['tool']['setuptools']['package-data']
    assert package_data['*'] == ['requirements/*.txt']


def test_existing_pyproject_metadata_is_inferred_and_preserved(tmp_path) -> None:
    """
    Existing pyproject metadata should seed xcookie defaults, and unrelated
    sections should survive a regen.
    """
    from xcookie.main import TemplateApplier, XCookieConfig

    repodir = tmp_path / 'demo'
    pkgdir = repodir / 'src' / 'demo_mod'
    pkgdir.mkdir(parents=True)
    (pkgdir / '__init__.py').write_text("__version__ = '1.2.3'\n")
    (repodir / 'pyproject.toml').write_text(
        toml.dumps(
            {
                'project': {
                    'name': 'demo-pkg',
                    'description': 'Demo package',
                    'requires-python': '>=3.10',
                    'dynamic': ['version'],
                    'dependencies': [
                        'package-a>=1.0',
                        'package-b>=2.0',
                    ],
                    'authors': [
                        {
                            'name': 'Existing Author',
                            'email': 'author@example.com',
                        }
                    ],
                    'optional-dependencies': {
                        'tests': ['pytest>=8.0', 'coverage>=7.0'],
                    },
                },
                'tool': {
                    'xcookie': {
                        'mod_name': 'demo_mod',
                        'rel_mod_parent_dpath': 'src',
                    },
                    'setuptools': {
                        'packages': {
                            'find': {
                                'where': ['src'],
                                'include': ['demo_mod*'],
                                'namespaces': True,
                            }
                        },
                        'dynamic': {
                            'version': {'attr': 'demo_mod.__version__'}
                        },
                    },
                    'ruff': {'line-length': 123},
                },
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
        use_pyproject_requirements=True,
    )

    assert config['author'] == 'Existing Author'
    assert config['author_email'] == 'author@example.com'
    assert config['version'] == '1.2.3'

    applier = TemplateApplier(config)
    applier.setup()

    pyproject_text = (applier.staging_dpath / 'pyproject.toml').read_text()
    pyproject_data = toml.loads(pyproject_text)

    assert pyproject_data['project']['authors'][0]['name'] == 'Existing Author'
    assert pyproject_data['project']['dynamic'] == ['version']
    assert pyproject_data['project']['dependencies'] == [
        'package-a>=1.0',
        'package-b>=2.0',
    ]
    assert sorted(pyproject_data['project']['optional-dependencies']['tests']) == [
        'coverage>=7.0',
        'pytest>=8.0',
    ]
    # Don't assert a specific TOML formatting style here. ``pyproject_fmt`` is
    # an optional dependency; when it's missing, ``build_pyproject`` falls
    # back to ``toml.dumps`` which emits arrays inline. The structural
    # assertions above already verify the data is preserved.
    assert 'package-a>=1.0' in pyproject_text
    assert pyproject_data['tool']['ruff']['line-length'] == 123
    assert pyproject_data['tool']['setuptools']['dynamic']['version']['attr'] == (
        'demo_mod.__version__'
    )
    assert 'dependencies' not in pyproject_data['tool']['setuptools']['dynamic']
    assert 'optional-dependencies' not in pyproject_data['tool']['setuptools']['dynamic']
    assert pyproject_data['tool']['xcookie']['author'] == 'Existing Author'
    assert pyproject_data['tool']['xcookie']['version'] == '1.2.3'


def test_pyproject_requirements_mode_preserves_project_dependencies(tmp_path) -> None:
    """
    When pyproject dependencies are authoritative, xcookie should not emit
    setuptools dynamic dependency files or requirements.txt scaffolding.
    """
    from xcookie.main import TemplateApplier, XCookieConfig

    repodir = tmp_path / 'demo'
    pkgdir = repodir / 'src' / 'demo_mod'
    pkgdir.mkdir(parents=True)
    (pkgdir / '__init__.py').write_text("__version__ = '1.2.3'\n")
    (repodir / 'pyproject.toml').write_text(
        toml.dumps(
            {
                'project': {
                    'name': 'demo-pkg',
                    'description': 'Demo package',
                    'requires-python': '>=3.10',
                    'version': '1.2.3',
                    'dependencies': ['package-a>=1.0', 'package-b>=2.0'],
                    'optional-dependencies': {
                        'tests': ['pytest>=8.0', 'coverage>=7.0'],
                    },
                },
                'tool': {
                    'xcookie': {
                        'mod_name': 'demo_mod',
                        'rel_mod_parent_dpath': 'src',
                    },
                    'ruff': {'line-length': 123},
                },
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
        use_pyproject_requirements=True,
    )

    applier = TemplateApplier(config)
    applier.setup()

    staged_fnames = {info['fname'] for info in applier.staging_infos}
    assert 'requirements/runtime.txt' not in staged_fnames
    assert 'requirements/tests.txt' not in staged_fnames
    assert 'requirements/optional.txt' not in staged_fnames
    assert 'requirements/docs.txt' not in staged_fnames
    assert 'requirements.txt' not in staged_fnames

    pyproject_text = (applier.staging_dpath / 'pyproject.toml').read_text()
    pyproject_data = toml.loads(pyproject_text)

    project_block = pyproject_data['project']
    assert project_block['dependencies'] == [
        'package-a>=1.0',
        'package-b>=2.0',
    ]
    assert sorted(project_block['optional-dependencies']['tests']) == [
        'coverage>=7.0',
        'pytest>=8.0',
    ]
    assert project_block['dynamic'] == ['version']
    assert 'dependencies' not in pyproject_data['tool']['setuptools']['dynamic']
    assert 'optional-dependencies' not in pyproject_data['tool']['setuptools']['dynamic']


def test_markdown_readme_is_preserved_and_reflected_in_metadata(tmp_path) -> None:
    """
    If a repo already uses README.md, xcookie should leave it alone and point
    packaging metadata at Markdown instead of reStructuredText.
    """
    from xcookie.main import TemplateApplier, XCookieConfig

    repodir = tmp_path / 'demo'
    pkgdir = repodir / 'src' / 'demo_mod'
    pkgdir.mkdir(parents=True)
    (pkgdir / '__init__.py').write_text("__version__ = '1.2.3'\n")
    (repodir / 'README.md').write_text('# Demo Package\n\nSome markdown.\n')
    (repodir / 'pyproject.toml').write_text(
        toml.dumps(
            {
                'project': {
                    'name': 'demo-pkg',
                    'description': 'Demo package',
                    'requires-python': '>=3.10',
                    'version': '1.2.3',
                },
                'tool': {
                    'xcookie': {
                        'mod_name': 'demo_mod',
                        'rel_mod_parent_dpath': 'src',
                    }
                },
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
        use_pyproject_requirements=True,
    )

    applier = TemplateApplier(config)
    applier.setup()

    staged_fnames = {info['fname'] for info in applier.staging_infos}
    assert 'README.rst' not in staged_fnames
    assert (repodir / 'README.md').read_text() == '# Demo Package\n\nSome markdown.\n'

    pyproject_text = (applier.staging_dpath / 'pyproject.toml').read_text()
    pyproject_data = toml.loads(pyproject_text)
    assert pyproject_data['tool']['setuptools']['dynamic']['readme']['file'] == [
        'README.md'
    ]
    assert pyproject_data['tool']['setuptools']['dynamic']['readme'][
        'content-type'
    ] == 'text/markdown'

    setup_text = applier.build_setup()
    assert 'get_readme_fpath()' in setup_text
    assert 'text/markdown' in setup_text


def test_xcookie_tags_are_not_written_as_project_keywords(tmp_path) -> None:
    """
    xcookie's ``tags`` (e.g. ``github``, ``purepy``, ``kitware``) are internal
    scaffolding selectors, not user-facing project keywords. They must not
    leak into ``[project.keywords]`` in the generated pyproject.toml.
    """
    from xcookie.main import TemplateApplier, XCookieConfig

    repodir = tmp_path / 'demo'
    pkgdir = repodir / 'src' / 'demo_mod'
    pkgdir.mkdir(parents=True)
    (pkgdir / '__init__.py').write_text("__version__ = '1.2.3'\n")
    (repodir / 'pyproject.toml').write_text(
        toml.dumps(
            {
                'project': {
                    'name': 'demo-pkg',
                    'description': 'Demo package',
                    'requires-python': '>=3.10',
                    'version': '1.2.3',
                    'keywords': ['existing', 'domain-keywords'],
                },
                'tool': {
                    'xcookie': {
                        'mod_name': 'demo_mod',
                        'rel_mod_parent_dpath': 'src',
                        'tags': ['github', 'erotemic', 'purepy'],
                    }
                },
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
        use_pyproject_requirements=True,
    )
    applier = TemplateApplier(config)
    applier.setup()

    pyproject_text = (applier.staging_dpath / 'pyproject.toml').read_text()
    pyproject_data = toml.loads(pyproject_text)

    keywords = pyproject_data['project'].get('keywords', [])
    # Existing user-defined keywords must survive a regen.
    assert 'existing' in keywords
    assert 'domain-keywords' in keywords
    # Scaffolding tags must not be turned into keywords.
    for tag in ['github', 'erotemic', 'purepy', 'gitlab', 'kitware', 'binpy']:
        assert tag not in keywords, (
            f"xcookie tag {tag!r} leaked into project keywords"
        )


def _write_pyproject_with_extras(repodir, optional_dependencies):
    pkgdir = repodir / 'src' / 'demo_mod'
    pkgdir.mkdir(parents=True)
    (pkgdir / '__init__.py').write_text("__version__ = '1.2.3'\n")
    (repodir / 'pyproject.toml').write_text(
        toml.dumps(
            {
                'project': {
                    'name': 'demo-pkg',
                    'description': 'Demo package',
                    'requires-python': '>=3.11',
                    'version': '1.2.3',
                    'dependencies': ['package-a>=1.0'],
                    'optional-dependencies': optional_dependencies,
                },
                'tool': {
                    'xcookie': {
                        'mod_name': 'demo_mod',
                        'rel_mod_parent_dpath': 'src',
                        'tags': ['github', 'erotemic', 'purepy'],
                        'min_python': '3.11',
                    },
                },
            }
        )
    )


def test_sdist_install_step_omits_empty_extras_brackets(tmp_path) -> None:
    """
    Regression test: when ``use_pyproject_requirements=True`` and the project
    declares no extras at all, the generated GitHub Actions sdist job must
    not emit ``pip install -e ".[]"`` (which is rejected by pip).
    """
    from xcookie.main import TemplateApplier, XCookieConfig

    repodir = tmp_path / 'demo'
    _write_pyproject_with_extras(repodir, optional_dependencies={})

    config = XCookieConfig.load_from_cli_and_pyproject(
        argv=0,
        repodir=repodir,
        interactive=False,
        rotate_secrets=False,
        init_new_remotes=False,
        use_vcs=False,
        use_setup_py=False,
        use_pyproject_requirements=True,
    )
    applier = TemplateApplier(config)
    applier._presetup()
    text = applier.build_github_actions_tests()

    assert '".[]"' not in text
    assert '-e ".[]"' not in text


def test_sdist_install_step_uses_tests_extra_when_available(tmp_path) -> None:
    """
    When the project's pyproject.toml declares a ``tests`` extra, the sdist
    job's pre-install step should reference it so pytest is available before
    the test steps run.
    """
    from xcookie.main import TemplateApplier, XCookieConfig

    repodir = tmp_path / 'demo'
    _write_pyproject_with_extras(
        repodir,
        optional_dependencies={
            'tests': ['pytest>=8.0', 'coverage>=7.0'],
            'optional': ['rich>=14'],
        },
    )

    config = XCookieConfig.load_from_cli_and_pyproject(
        argv=0,
        repodir=repodir,
        interactive=False,
        rotate_secrets=False,
        init_new_remotes=False,
        use_vcs=False,
        use_setup_py=False,
        use_pyproject_requirements=True,
    )
    applier = TemplateApplier(config)
    applier._presetup()
    text = applier.build_github_actions_tests()

    assert '-e ".[tests]"' in text
    assert '".[]"' not in text


def test_test_matrix_install_extras_are_filtered_to_existing(tmp_path) -> None:
    """
    The matrix-based test_wheels job should only reference extras that the
    pyproject.toml actually declares — for a project with only ``tests``,
    the install-extras values must not contain ``optional``.
    """
    from xcookie.main import TemplateApplier, XCookieConfig

    repodir = tmp_path / 'demo'
    _write_pyproject_with_extras(
        repodir,
        optional_dependencies={
            'tests': ['pytest>=8.0'],
        },
    )

    config = XCookieConfig.load_from_cli_and_pyproject(
        argv=0,
        repodir=repodir,
        interactive=False,
        rotate_secrets=False,
        init_new_remotes=False,
        use_vcs=False,
        use_setup_py=False,
        use_pyproject_requirements=True,
    )
    applier = TemplateApplier(config)
    applier._presetup()
    text = applier.build_github_actions_tests()

    assert 'install-extras: tests' in text
    assert 'install-extras: tests,optional' not in text
    assert 'install-extras: optional' not in text
    assert 'install-extras: ,' not in text
