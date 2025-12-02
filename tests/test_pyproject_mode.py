import toml


def test_use_setup_py_false_generates_pep621(tmp_path):
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
    assert pyproject_data['build-system']['build-backend'] == 'setuptools.build_meta'

    setuptools_dynamic = pyproject_data['tool']['setuptools']['dynamic']
    assert setuptools_dynamic['dependencies']['file'] == ['requirements/runtime.txt']
    assert 'tests' in setuptools_dynamic['optional-dependencies']

    package_data = pyproject_data['tool']['setuptools']['package-data']
    assert package_data[''] == ['requirements/*.txt']
