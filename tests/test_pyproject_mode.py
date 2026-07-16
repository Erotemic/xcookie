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


def test_typed_package_data_uses_inline_annotations(tmp_path) -> None:
    """Typed projects ship ``py.typed`` without reserving a stub glob."""
    from xcookie.main import TemplateApplier, XCookieConfig

    repodir = tmp_path / 'demo'
    repodir.mkdir()

    config = XCookieConfig(
        repodir=repodir,
        mod_name='demo_mod',
        repo_name='demo_mod',
        tags=['github', 'purepy'],
        typed=True,
        rotate_secrets=False,
        init_new_remotes=False,
        interactive=False,
        use_setup_py=False,
        use_vcs=False,
    )

    applier = TemplateApplier(config)
    applier.setup()

    pyproject_text = (applier.staging_dpath / 'pyproject.toml').read_text()
    pyproject_data = toml.loads(pyproject_text)
    package_data = pyproject_data['tool']['setuptools']['package-data']
    assert package_data['demo_mod'] == ['py.typed']
    assert '*.pyi' not in pyproject_text

    setup_text = applier.build_setup()
    assert "'demo_mod': ['py.typed']" in setup_text
    assert '*.pyi' not in setup_text


def test_all_extra_aggregates_runtime_optional_requirements(tmp_path) -> None:
    """
    The legacy ``[all]`` convenience extra must be regenerated so users can
    run ``pip install pkg[all]``. It aggregates the runtime-optional extras
    via a multi-file dynamic entry and excludes development-only extras
    (tests/docs/linting). There is intentionally no ``all-strict`` (the
    loose/strict split is handled by lock-file constraints in CI).
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

    pyproject_text = (applier.staging_dpath / 'pyproject.toml').read_text()
    pyproject_data = toml.loads(pyproject_text)

    optional = pyproject_data['tool']['setuptools']['dynamic'][
        'optional-dependencies'
    ]
    assert 'all' in optional, 'the all convenience extra must be present'
    assert 'all-strict' not in optional, 'strict is handled via lock files'

    all_files = optional['all']['file']
    assert 'requirements/optional.txt' in all_files
    # Development-only extras must not be pulled into the user-facing ``all``.
    assert 'requirements/tests.txt' not in all_files
    assert 'requirements/docs.txt' not in all_files

    # The rewritten file must keep a trailing newline.
    assert pyproject_text.endswith('\n')


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
    # The version is inferred from standard project/setuptools metadata for
    # config defaults, but should not be written back into tool.xcookie unless
    # it was explicitly present there.  The authoritative packaging version is
    # the PEP 621 / setuptools dynamic version declaration above.
    assert 'version' not in pyproject_data['tool']['xcookie']


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


def test_dynamic_pyproject_extras_are_available_to_ci(tmp_path) -> None:
    """
    Regression test for projects whose extras are exposed dynamically via
    setuptools. These still support ``pip install .[tests]``, so CI should not
    filter them out just because ``[project.optional-dependencies]`` is absent.
    """
    from xcookie.builders import common_ci
    from xcookie.main import TemplateApplier, XCookieConfig

    repodir = tmp_path / 'demo'
    pkgdir = repodir / 'src' / 'demo_mod'
    reqdir = repodir / 'requirements'
    pkgdir.mkdir(parents=True)
    reqdir.mkdir()
    (pkgdir / '__init__.py').write_text("__version__ = '1.2.3'\n")
    (reqdir / 'runtime.txt').write_text('ubelt>=1.3.3\n')
    (reqdir / 'tests.txt').write_text('pytest>=8.0\ncoverage>=7.0\n')
    (reqdir / 'optional.txt').write_text('rich>=14\n')
    (repodir / 'pyproject.toml').write_text(
        toml.dumps(
            {
                'project': {
                    'name': 'demo-pkg',
                    'description': 'Demo package',
                    'requires-python': '>=3.11',
                    'version': '1.2.3',
                    'dynamic': ['dependencies', 'optional-dependencies'],
                },
                'tool': {
                    'xcookie': {
                        'mod_name': 'demo_mod',
                        'rel_mod_parent_dpath': 'src',
                        'tags': ['github', 'erotemic', 'purepy'],
                        'min_python': '3.11',
                    },
                    'setuptools': {
                        'dynamic': {
                            'dependencies': {'file': ['requirements/runtime.txt']},
                            'optional-dependencies': {
                                'tests': {'file': ['requirements/tests.txt']},
                                'optional': {'file': ['requirements/optional.txt']},
                            },
                        }
                    },
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
    applier._presetup()
    available = common_ci.get_pyproject_optional_dependency_keys(applier)
    text = applier.build_github_actions_tests()

    assert {'tests', 'optional'} <= available
    assert '-e ".[tests]"' in text
    assert 'install-extras: tests' in text
    assert 'install-extras: tests,optional' in text
    assert 'install-extras: \'\'' not in text


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


def test_gitlab_test_matrix_install_extras_are_filtered_to_existing(tmp_path) -> None:
    """
    GitLab CI should use the same pyproject extra filtering as GitHub Actions.
    For a project that only declares ``tests``, generated GitLab test jobs must
    not request missing extras such as ``optional`` or ``tests-strict``.
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
        tags=['gitlab', 'kitware', 'purepy'],
    )
    applier = TemplateApplier(config)
    applier._presetup()
    text = applier.build_gitlab_ci()

    assert 'INSTALL_EXTRAS="tests"' in text
    assert 'tests,optional' not in text
    assert 'tests-strict' not in text
    assert 'runtime-strict' not in text
    assert 'optional-strict' not in text
    assert '${WHEEL_FPATH}[${INSTALL_EXTRAS}]' in text
    assert '${WHEEL_FPATH}[]' not in text


def test_wheel_install_command_omits_empty_extra_brackets(tmp_path) -> None:
    """
    Shared wheel-test install commands should omit ``[]`` when filtering leaves
    a test variant with no declared extras. This matters for both GitHub and
    GitLab generated CI.
    """
    from xcookie.builders import common_ci
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

    parts = common_ci.make_install_and_test_wheel_parts(
        applier,
        'wheelhouse',
        special_install_lines=[],
        workspace_dname='sandbox',
    )
    install_text = '\n'.join(parts['install_wheel_commands'])

    assert 'INSTALL_TARGET="${WHEEL_FPATH}"' in install_text
    assert '"${WHEEL_FPATH}[${INSTALL_EXTRAS}]"' in install_text
    assert '"${WHEEL_FPATH}[]"' not in install_text



def test_legacy_comma_author_metadata_generates_valid_files(tmp_path) -> None:
    """
    Legacy ``tool.xcookie`` metadata often stores multiple authors in a single
    comma-delimited string. Regenerating from that metadata should not produce
    invalid Python source, and the PEP 621 authors table should be split into
    valid per-author entries.
    """
    import py_compile

    from xcookie.main import TemplateApplier, XCookieConfig

    repodir = tmp_path / 'demo'
    pkgdir = repodir / 'demo_mod'
    pkgdir.mkdir(parents=True)
    (pkgdir / '__init__.py').write_text("__version__ = '1.2.3'\n")
    (repodir / 'pyproject.toml').write_text(
        toml.dumps(
            {
                'project': {
                    'name': 'demo-mod',
                    'description': 'Demo module',
                    'requires-python': '>=3.10',
                    'dynamic': ['version'],
                },
                'tool': {
                    'xcookie': {
                        'mod_name': 'demo_mod',
                        'repo_name': 'demo-mod',
                        'pkg_name': 'demo-mod',
                        'tags': ['github', 'purepy'],
                        'author': 'Kitware Inc., Jon Crall',
                        'author_email': (
                            'kitware@kitware.com, jon.crall@kitware.com'
                        ),
                        'use_setup_py': False,
                        'use_pyproject_requirements': True,
                    }
                },
            }
        )
    )

    config = XCookieConfig.load_from_cli_and_pyproject(
        argv=False,
        repodir=repodir,
        interactive=False,
        rotate_secrets=False,
        init_new_remotes=False,
        use_vcs=False,
        use_setup_py=False,
        use_pyproject_requirements=True,
    )

    assert config['author'] == 'Kitware Inc., Jon Crall'
    assert config['author_email'] == 'kitware@kitware.com, jon.crall@kitware.com'

    applier = TemplateApplier(config)
    applier.setup()

    init_fpath = applier.staging_dpath / 'demo_mod' / '__init__.py'
    py_compile.compile(str(init_fpath), doraise=True)
    init_text = init_fpath.read_text()
    assert "__author__ = 'Kitware Inc., Jon Crall'" in init_text
    assert "__author_email__ = 'kitware@kitware.com, jon.crall@kitware.com'" in init_text

    pyproject_data = toml.loads((applier.staging_dpath / 'pyproject.toml').read_text())
    assert pyproject_data['project']['authors'] == [
        {'name': 'Kitware Inc.', 'email': 'kitware@kitware.com'},
        {'name': 'Jon Crall', 'email': 'jon.crall@kitware.com'},
    ]


def test_xcookie_help_does_not_emit_scriptconfig_transition_warnings() -> None:
    """The console entrypoint should use ``argv`` instead of dict cmdline shims."""
    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, '-m', 'xcookie.main', '--help'],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert proc.returncode == 0
    assert 'FutureWarning' not in proc.stderr
    assert 'cmdline' not in proc.stderr
    assert 'description' not in proc.stderr


def test_uv_exclude_newer_is_stamped_on_fresh_repo(tmp_path) -> None:
    """A fresh uv-using repo should get a relative [tool.uv] exclude-newer."""
    from xcookie.builders.pyproject import (
        DEFAULT_UV_EXCLUDE_NEWER,
        build_pyproject,
    )
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
        use_uv=True,
    )
    applier = TemplateApplier(config)
    pyproject_text = build_pyproject(applier)
    pyproject_data = (
        toml.loads(pyproject_text)
        if isinstance(pyproject_text, str)
        else pyproject_text
    )
    # The default is a relative window so the value does not go stale the
    # way a hard-coded absolute date would.
    assert pyproject_data['tool']['uv']['exclude-newer'] == (
        DEFAULT_UV_EXCLUDE_NEWER
    )
    # ``toml.dumps`` cannot emit comments, so the supply-chain rationale is
    # re-injected as a comment above the pin and the file ends with a newline.
    assert (
        '# Supply-chain guard: ignore packages published too recently.'
        in pyproject_text
    )
    assert pyproject_text.endswith('\n')


def test_uv_exclude_newer_preserves_existing_value(tmp_path) -> None:
    """Regen must not bump a user's chosen exclude-newer date."""
    from xcookie.builders.pyproject import build_pyproject
    from xcookie.main import TemplateApplier, XCookieConfig

    repodir = tmp_path / 'demo'
    repodir.mkdir()
    (repodir / 'pyproject.toml').write_text(
        toml.dumps(
            {
                'project': {'name': 'demo-mod'},
                'tool': {
                    'uv': {'exclude-newer': '2024-01-15'},
                    'xcookie': {
                        'mod_name': 'demo_mod',
                        'use_uv': True,
                    },
                },
            }
        )
    )
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
        use_uv=True,
    )
    applier = TemplateApplier(config)
    pyproject_text = build_pyproject(applier)
    pyproject_data = (
        toml.loads(pyproject_text)
        if isinstance(pyproject_text, str)
        else pyproject_text
    )
    assert pyproject_data['tool']['uv']['exclude-newer'] == '2024-01-15'


def test_uv_exclude_newer_disabled_by_config(tmp_path) -> None:
    """Setting uv_exclude_newer=False should omit the setting entirely."""
    from xcookie.builders.pyproject import build_pyproject
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
        use_uv=True,
        uv_exclude_newer=False,
    )
    applier = TemplateApplier(config)
    pyproject_text = build_pyproject(applier)
    pyproject_data = (
        toml.loads(pyproject_text)
        if isinstance(pyproject_text, str)
        else pyproject_text
    )
    assert 'exclude-newer' not in pyproject_data.get('tool', {}).get('uv', {})


def test_explicit_packages_list_is_converted_to_find_dict(tmp_path) -> None:
    """
    When an existing pyproject.toml uses the explicit list form for
    ``[tool.setuptools] packages``, xcookie must not crash trying to subscript
    it like a dict.  The list should be replaced with the ``find`` style.
    """
    from xcookie.builders.pyproject import build_pyproject
    from xcookie.main import TemplateApplier, XCookieConfig

    repodir = tmp_path / 'demo'
    pkgdir = repodir / 'demo_mod'
    pkgdir.mkdir(parents=True)
    (pkgdir / '__init__.py').write_text("__version__ = '0.1.0'\n")
    (repodir / 'pyproject.toml').write_text(
        toml.dumps(
            {
                'project': {
                    'name': 'demo-mod',
                    'description': 'Demo module',
                    'requires-python': '>=3.10',
                    'version': '0.1.0',
                },
                'tool': {
                    'xcookie': {
                        'mod_name': 'demo_mod',
                        'tags': ['github', 'purepy'],
                    },
                    'setuptools': {
                        'packages': ['demo_mod', 'demo_mod.sub'],
                        'include-package-data': True,
                    },
                },
            }
        )
    )

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
    pyproject_text = build_pyproject(applier)
    pyproject_data = (
        toml.loads(pyproject_text)
        if isinstance(pyproject_text, str)
        else pyproject_text
    )

    packages = pyproject_data['tool']['setuptools']['packages']
    assert isinstance(packages, dict), (
        "packages must be converted from a list to a find-dict"
    )
    assert 'find' in packages
    assert 'where' in packages['find']
    assert 'include' in packages['find']
