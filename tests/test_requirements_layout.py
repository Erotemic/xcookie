import toml


def _make_packaged_requirements_layout(repodir, mod_name='demo_mod'):
    """Create a KWCOCO-style requirements symlink into package resources."""
    package_dpath = repodir / mod_name / 'rc' / 'requirements'
    package_dpath.mkdir(parents=True)
    for dpath in [
        repodir / mod_name,
        repodir / mod_name / 'rc',
        package_dpath,
    ]:
        (dpath / '__init__.py').write_text('')
    (package_dpath / 'runtime.txt').write_text('ubelt\n')
    (package_dpath / 'tests.txt').write_text('pytest\n')
    locks_dpath = package_dpath / 'locks'
    locks_dpath.mkdir()
    (locks_dpath / 'tests.txt').write_text('pytest==8.4.1\n')
    try:
        (repodir / 'requirements').symlink_to(
            package_dpath.relative_to(repodir), target_is_directory=True
        )
    except OSError as ex:
        import pytest

        pytest.skip(f'symlinks unavailable: {ex}')
    return package_dpath


def _make_config(repodir, *, use_setup_py=False, use_pyproject_requirements=False):
    from xcookie.main import XCookieConfig

    return XCookieConfig(
        repodir=repodir,
        mod_name='demo_mod',
        repo_name='demo_mod',
        tags=['github', 'purepy'],
        init_new_remotes=False,
        interactive=False,
        use_setup_py=use_setup_py,
        use_pyproject_requirements=use_pyproject_requirements,
        use_vcs=False,
        min_python='3.11',
    )


def test_packaged_requirements_are_inferred_and_persisted(tmp_path) -> None:
    from xcookie.main import TemplateApplier

    repodir = tmp_path / 'demo'
    repodir.mkdir()
    _make_packaged_requirements_layout(repodir)

    config = _make_config(repodir)
    assert config['requirements_package'] == 'demo_mod.rc.requirements'

    applier = TemplateApplier(config)
    applier.setup()
    pyproject_data = toml.loads(
        (applier.staging_dpath / 'pyproject.toml').read_text()
    )
    assert (
        pyproject_data['tool']['xcookie']['requirements_package']
        == 'demo_mod.rc.requirements'
    )


def test_pep621_packages_regular_and_locked_requirements(tmp_path) -> None:
    from xcookie.main import TemplateApplier

    repodir = tmp_path / 'demo'
    repodir.mkdir()
    _make_packaged_requirements_layout(repodir)

    applier = TemplateApplier(_make_config(repodir))
    applier.setup()
    pyproject_data = toml.loads(
        (applier.staging_dpath / 'pyproject.toml').read_text()
    )
    package_data = pyproject_data['tool']['setuptools']['package-data']
    assert package_data['demo_mod.rc.requirements'] == [
        '*.txt',
        'locks/*.txt',
    ]


def test_legacy_setup_packages_regular_and_locked_requirements(tmp_path) -> None:
    from xcookie.main import TemplateApplier

    repodir = tmp_path / 'demo'
    repodir.mkdir()
    _make_packaged_requirements_layout(repodir)

    applier = TemplateApplier(_make_config(repodir, use_setup_py=True))
    applier._presetup()
    setup_text = applier.build_setup()
    assert "'demo_mod.rc.requirements': ['*.txt', 'locks/*.txt']" in setup_text


def test_refresh_locks_targets_shared_packaged_tree(tmp_path) -> None:
    from xcookie.main import TemplateApplier

    repodir = tmp_path / 'demo'
    repodir.mkdir()
    _make_packaged_requirements_layout(repodir)

    config = _make_config(
        repodir,
        use_pyproject_requirements=True,
    )
    config['test_variants'] = ['minimal-strict']
    config['enable_gpg'] = False
    config['deploy'] = False
    applier = TemplateApplier(config)
    applier._presetup()
    text = applier.build_refresh_locks_sh()

    assert 'mkdir -p requirements/locks' in text
    assert 'shipped as package resources under demo_mod.rc.requirements' in text
    assert '-o requirements/locks/tests.txt' in text
