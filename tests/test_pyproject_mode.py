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
                    'authors': [
                        {
                            'name': 'Existing Author',
                            'email': 'author@example.com',
                        }
                    ],
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
    assert pyproject_data['tool']['ruff']['line-length'] == 123
    assert pyproject_data['tool']['setuptools']['dynamic']['version']['attr'] == (
        'demo_mod.__version__'
    )
    assert pyproject_data['tool']['xcookie']['author'] == 'Existing Author'
    assert pyproject_data['tool']['xcookie']['version'] == '1.2.3'
