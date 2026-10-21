from __future__ import annotations

import datetime as datetime_mod
import subprocess

import pytest

from xcookie.versioning import (
    VersionBumper,
    build_initial_changelog,
    find_version_source,
)


def _write_dynamic_attr_repo(tmp_path, version='1.2.3'):
    (tmp_path / 'demo').mkdir()
    (tmp_path / 'demo' / '__init__.py').write_text(
        f'"""Demo."""\n\n__version__ = {version!r}\n'
    )
    (tmp_path / 'pyproject.toml').write_text(
        '''
[project]
name = "demo"
dynamic = ["version"]

[tool.setuptools.dynamic]
version = {attr = "demo.__version__"}

[tool.setuptools.packages.find]
where = ["."]
'''.lstrip()
    )
    (tmp_path / 'CHANGELOG.md').write_text(
        f'# Changelog\n\n## Version {version} - Unreleased\n\n### Changed\n* work\n'
    )


def test_resolve_relative_version_bumps():
    assert VersionBumper.resolve_next_version('1.2.3', 'patch') == '1.2.4'
    assert VersionBumper.resolve_next_version('1.2.3', 'micro') == '1.2.4'
    assert VersionBumper.resolve_next_version('1.2.3', 'minor') == '1.3.0'
    assert VersionBumper.resolve_next_version('1.2.3', 'major') == '2.0.0'
    assert VersionBumper.resolve_next_version('1.2.3', '3.1.4') == '3.1.4'


@pytest.mark.parametrize(
    ('target', 'expected'),
    [
        ('patch', '1.2.4'),
        ('minor', '1.3.0'),
        ('major', '2.0.0'),
        ('2.7.1', '2.7.1'),
    ],
)
def test_bump_dynamic_attr_and_changelog(tmp_path, target, expected):
    _write_dynamic_attr_repo(tmp_path)
    bumper = VersionBumper(tmp_path)
    plan = bumper.bump(
        target, release_date=datetime_mod.date(2026, 8, 22)
    )

    assert plan.current_version == '1.2.3'
    assert plan.next_version == expected
    init_text = (tmp_path / 'demo' / '__init__.py').read_text()
    assert f"__version__ = '{expected}'" in init_text
    changelog = (tmp_path / 'CHANGELOG.md').read_text()
    assert f'## Version {expected} - Unreleased' in changelog
    assert '## Version 1.2.3 - Released 2026-08-22' in changelog
    assert changelog.index(expected) < changelog.index('1.2.3')


def test_bump_static_pyproject_version(tmp_path):
    (tmp_path / 'pyproject.toml').write_text(
        '''
[project]
name = "demo"
version = "4.5.6"

[tool.demo]
version = "do-not-touch"
'''.lstrip()
    )
    (tmp_path / 'CHANGELOG.md').write_text(
        '# Changelog\n\n## Version 4.5.6 - Unreleased\n'
    )

    VersionBumper(tmp_path).bump(
        'minor', release_date=datetime_mod.date(2026, 8, 22)
    )

    pyproject = (tmp_path / 'pyproject.toml').read_text()
    assert 'version = "4.6.0"' in pyproject
    assert 'version = "do-not-touch"' in pyproject


def test_bump_accepts_already_released_current_changelog(tmp_path):
    _write_dynamic_attr_repo(tmp_path)
    changelog_path = tmp_path / 'CHANGELOG.md'
    changelog_path.write_text(
        changelog_path.read_text().replace(
            'Version 1.2.3 - Unreleased',
            'Version 1.2.3 - Released 2026-08-20',
        )
    )

    VersionBumper(tmp_path).bump(
        'patch', release_date=datetime_mod.date(2026, 8, 22)
    )
    changelog = changelog_path.read_text()
    assert '## Version 1.2.4 - Unreleased' in changelog
    assert '## Version 1.2.3 - Released 2026-08-20' in changelog


def test_bump_accepts_legacy_stale_changelog(tmp_path):
    _write_dynamic_attr_repo(tmp_path, version='2.3.0')
    changelog_path = tmp_path / 'CHANGELOG.md'
    changelog_path.write_text(
        '''
# Changelog

## [Version 2.2.0] -

### Fixed:
* old fix

## [Version 2.1.2]

### Changed
* old change
'''.lstrip()
    )

    VersionBumper(tmp_path).bump(
        'patch', release_date=datetime_mod.date(2026, 8, 23)
    )

    changelog = changelog_path.read_text()
    assert '## Version 2.3.1 - Unreleased' in changelog
    assert '## [Version 2.2.0] -' in changelog
    assert '## Version 2.3.0 - Released' not in changelog
    assert changelog.index('2.3.1') < changelog.index('2.2.0')


def test_bump_normalizes_legacy_current_changelog_heading(tmp_path):
    _write_dynamic_attr_repo(tmp_path, version='2.3.0')
    changelog_path = tmp_path / 'CHANGELOG.md'
    changelog_path.write_text(
        '# Changelog\n\n## [Version 2.3.0] -\n\n### Fixed\n* work\n'
    )

    VersionBumper(tmp_path).bump(
        'patch', release_date=datetime_mod.date(2026, 8, 23)
    )

    changelog = changelog_path.read_text()
    assert '## Version 2.3.1 - Unreleased' in changelog
    assert '## Version 2.3.0 - Released 2026-08-23' in changelog


@pytest.mark.parametrize(
    ('current_heading', 'expected_prefix'),
    [
        ('## Version: 1.3.0 - Unreleased', '## Version:'),
        ('## Version: 1.3.0 - Released 2026-10-20', '## Version:'),
        ('## Version: 1.3.0', '## Version:'),
        ('## Version 1.3.0 - Unreleased', '## Version'),
    ],
)
def test_bump_preserves_colon_heading_style(
    tmp_path, current_heading, expected_prefix
):
    """The xcookie bump handles mkinit's long-standing `Version:` headings."""
    _write_dynamic_attr_repo(tmp_path, version='1.3.0')
    changelog = tmp_path / 'CHANGELOG.md'
    changelog.write_text(
        '# Changelog\n\n'
        f'{current_heading}\n\n'
        '### Changed\n* Changed packaging\n\n'
        '## Version: 1.2.0 - Released 2025-12-02\n\n'
        '### Fixed\n* Older fix\n'
    )

    plan = VersionBumper(tmp_path).bump(
        'patch', release_date=datetime_mod.date(2026, 10, 21)
    )

    assert plan.current_version == '1.3.0'
    assert plan.next_version == '1.3.1'
    updated = changelog.read_text()
    assert f'{expected_prefix} 1.3.1 - Unreleased' in updated
    if 'Released' in current_heading:
        assert current_heading in updated
    else:
        assert f'{expected_prefix} 1.3.0 - Released 2026-10-21' in updated
    assert '* Changed packaging' in updated
    assert '## Version: 1.2.0 - Released 2025-12-02' in updated
    assert '* Older fix' in updated
    assert updated.index('1.3.1') < updated.index('1.3.0')
    assert "__version__ = '1.3.1'" in (
        tmp_path / 'demo' / '__init__.py'
    ).read_text()


def test_bump_colon_heading_creates_branch(tmp_path):
    """Regression for `xcookie bump --branch` on mkinit's changelog."""
    _write_dynamic_attr_repo(tmp_path, version='1.3.0')
    changelog = tmp_path / 'CHANGELOG.md'
    changelog.write_text(
        '# Changelog\n\n## Version: 1.3.0 - Unreleased\n\n'
        '### Changed\n* Keep these release notes\n\n'
        '## Version: 1.2.0 - Released 2025-12-02\n'
    )
    subprocess.run(['git', 'init', '-q'], cwd=tmp_path, check=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=tmp_path, check=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'XCookie Test'],
        cwd=tmp_path, check=True,
    )
    subprocess.run(['git', 'add', '.'], cwd=tmp_path, check=True)
    subprocess.run(
        ['git', 'commit', '-qm', 'initial'], cwd=tmp_path, check=True
    )

    VersionBumper(tmp_path).bump(
        'patch', branch=True, release_date=datetime_mod.date(2026, 10, 21)
    )

    branch = subprocess.run(
        ['git', 'branch', '--show-current'],
        cwd=tmp_path, check=True, capture_output=True, text=True,
    ).stdout.strip()
    assert branch == 'dev/1.3.1'
    assert '## Version: 1.3.1 - Unreleased' in changelog.read_text()
    assert '## Version: 1.3.0 - Released 2026-10-21' in changelog.read_text()
    assert '* Keep these release notes' in changelog.read_text()


def test_bump_colon_heading_rejects_duplicate_target_without_edits(tmp_path):
    _write_dynamic_attr_repo(tmp_path, version='1.3.0')
    changelog = tmp_path / 'CHANGELOG.md'
    changelog.write_text(
        '# Changelog\n\n'
        '## Version: 1.3.1 - Unreleased\n\n'
        '## Version: 1.3.0 - Unreleased\n'
    )
    before_version = (tmp_path / 'demo' / '__init__.py').read_text()
    before_changelog = changelog.read_text()

    with pytest.raises(RuntimeError, match='already contains version 1.3.1'):
        VersionBumper(tmp_path).bump('patch')
    assert (tmp_path / 'demo' / '__init__.py').read_text() == before_version
    assert changelog.read_text() == before_changelog


def test_bump_can_create_version_branch(tmp_path):
    _write_dynamic_attr_repo(tmp_path)
    subprocess.run(['git', 'init', '-q'], cwd=tmp_path, check=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'XCookie Test'],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(['git', 'add', '.'], cwd=tmp_path, check=True)
    subprocess.run(
        ['git', 'commit', '-qm', 'initial'], cwd=tmp_path, check=True
    )

    VersionBumper(tmp_path).bump(
        'patch',
        branch=True,
        release_date=datetime_mod.date(2026, 8, 23),
    )

    branch = subprocess.run(
        ['git', 'branch', '--show-current'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert branch == 'dev/1.2.4'
    assert "__version__ = '1.2.4'" in (
        tmp_path / 'demo' / '__init__.py'
    ).read_text()


def test_branch_failure_does_not_apply_bump(tmp_path, monkeypatch):
    _write_dynamic_attr_repo(tmp_path)
    init_path = tmp_path / 'demo' / '__init__.py'
    changelog_path = tmp_path / 'CHANGELOG.md'
    before_init = init_path.read_text()
    before_changelog = changelog_path.read_text()

    def fail_branch(self, branch_name):
        raise RuntimeError(f'cannot create {branch_name}')

    monkeypatch.setattr(VersionBumper, 'create_branch', fail_branch)

    with pytest.raises(RuntimeError, match='cannot create dev/1.2.4'):
        VersionBumper(tmp_path).bump('patch', branch=True)

    assert init_path.read_text() == before_init
    assert changelog_path.read_text() == before_changelog


def test_bump_validates_changelog_before_writing_version(tmp_path):
    _write_dynamic_attr_repo(tmp_path)
    init_path = tmp_path / 'demo' / '__init__.py'
    before = init_path.read_text()
    (tmp_path / 'CHANGELOG.md').write_text(
        '# Changelog\n\n## Version 9.9.9 - Unreleased\n'
    )

    with pytest.raises(RuntimeError, match='changelog'):
        VersionBumper(tmp_path).bump('patch')
    assert init_path.read_text() == before



def _write_rst_repo(tmp_path, version='5.0.2', draft='5.0.3'):
    """Mimic line_profiler's changelog and static package version layout."""
    _write_dynamic_attr_repo(tmp_path, version)
    (tmp_path / 'CHANGELOG.md').unlink()
    (tmp_path / 'CHANGELOG.rst').write_text(
        'Changes\n=======\n\n'
        f'{draft}\n' + '-' * len(draft) + '\n'
        '* FIX: Unreleased fix awaiting publication (#427)\n'
        '* CHANGE: Drop support for Python 3.8 and 3.9\n'
        '\n'
        '5.0.2\n~~~~~\n'
        '* ENH: Older published change\n'
        '\n'
        '5.0.1\n~~~~~\n'
        '* FIX: Earlier published change\n'
    )


@pytest.mark.parametrize(
    ('target', 'expected'),
    [('patch', '5.0.3'), ('minor', '5.1.0'), ('major', '6.0.0')],
)
def test_bump_rst_retitles_existing_draft_without_losing_notes(
    tmp_path, target, expected
):
    _write_rst_repo(tmp_path)
    changelog_path = tmp_path / 'CHANGELOG.rst'
    original = changelog_path.read_text()

    plan = VersionBumper(tmp_path).bump(
        target, release_date=datetime_mod.date(2026, 10, 18)
    )

    assert plan.changelog_path == changelog_path
    assert plan.current_version == '5.0.2'
    assert plan.next_version == expected
    assert f"__version__ = '{expected}'" in (
        tmp_path / 'demo' / '__init__.py'
    ).read_text()
    updated = changelog_path.read_text()
    assert updated.startswith(f'Changes\n=======\n\n{expected}\n-----\n')
    assert '* FIX: Unreleased fix awaiting publication (#427)' in updated
    assert '* CHANGE: Drop support for Python 3.8 and 3.9' in updated
    assert '5.0.2\n~~~~~\n* ENH: Older published change' in updated
    assert '5.0.1\n~~~~~\n* FIX: Earlier published change' in updated
    if target == 'patch':
        # A prepared section for precisely this bump is already in place.
        assert updated == original
    else:
        assert '5.0.3\n-----' not in updated
        assert updated == original.replace('5.0.3\n-----', expected + '\n-----')


@pytest.mark.parametrize('first_version', ['5.0.2', '5.0.1'])
def test_bump_rst_starts_new_section_if_no_existing_draft(
    tmp_path, first_version
):
    _write_dynamic_attr_repo(tmp_path, version='5.0.2')
    (tmp_path / 'CHANGELOG.md').unlink()
    (tmp_path / 'CHANGELOG.rst').write_text(
        'Changes\n=======\n\n'
        f'{first_version}\n~~~~~\n* Older release note\n'
    )

    VersionBumper(tmp_path).bump('minor')

    changelog = (tmp_path / 'CHANGELOG.rst').read_text()
    assert changelog.startswith(
        'Changes\n=======\n\n'
        '5.1.0\n~~~~~\n\n'
        f'{first_version}\n~~~~~\n* Older release note'
    )


def test_bump_rst_adjusts_version_underline_width(tmp_path):
    _write_dynamic_attr_repo(tmp_path, version='5.9.8')
    (tmp_path / 'CHANGELOG.md').unlink()
    (tmp_path / 'CHANGELOG.rst').write_text(
        'Changes\n=======\n\n5.9.9\n-----\n* Draft\n'
    )
    VersionBumper(tmp_path).bump('minor')
    changelog = (tmp_path / 'CHANGELOG.rst').read_text()
    assert '5.10.0\n------\n* Draft\n' in changelog


def test_bump_rst_rejects_draft_newer_than_target_before_writing(tmp_path):
    _write_rst_repo(tmp_path, draft='5.1.0')
    version_path = tmp_path / 'demo' / '__init__.py'
    original_version = version_path.read_text()
    changelog_path = tmp_path / 'CHANGELOG.rst'
    original_changelog = changelog_path.read_text()

    with pytest.raises(RuntimeError, match='newer than the requested'):
        VersionBumper(tmp_path).bump('patch')

    assert version_path.read_text() == original_version
    assert changelog_path.read_text() == original_changelog


def test_bump_rst_rejects_multiple_ahead_of_package_drafts(tmp_path):
    _write_rst_repo(tmp_path)
    path = tmp_path / 'CHANGELOG.rst'
    path.write_text(path.read_text().replace(
        '5.0.2\n~~~~~', '5.0.4\n~~~~~'
    ))
    with pytest.raises(RuntimeError, match='multiple entries newer'):
        VersionBumper(tmp_path).bump('major')


def test_bump_rejects_ambiguous_changelog_paths_before_writing(tmp_path):
    _write_dynamic_attr_repo(tmp_path)
    (tmp_path / 'CHANGELOG.rst').write_text('Changes\n=======\n')
    before = (tmp_path / 'demo' / '__init__.py').read_text()

    with pytest.raises(RuntimeError, match='both CHANGELOG.md and CHANGELOG.rst'):
        VersionBumper(tmp_path).bump('minor')

    assert (tmp_path / 'demo' / '__init__.py').read_text() == before


def test_bump_rst_branch_via_cli(tmp_path, monkeypatch):
    from xcookie.cli import main

    _write_rst_repo(tmp_path)
    subprocess.run(['git', 'init', '-q'], cwd=tmp_path, check=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'XCookie Test'],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(['git', 'add', '.'], cwd=tmp_path, check=True)
    subprocess.run(
        ['git', 'commit', '-qm', 'initial'], cwd=tmp_path, check=True
    )

    monkeypatch.chdir(tmp_path)
    main(['bump', '--target', 'minor', '--branch'])

    branch = subprocess.run(
        ['git', 'branch', '--show-current'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert branch == 'dev/5.1.0'
    assert '5.1.0\n-----' in (tmp_path / 'CHANGELOG.rst').read_text()
    assert "__version__ = '5.1.0'" in (
        tmp_path / 'demo' / '__init__.py'
    ).read_text()



def _write_legacy_setup_repo(tmp_path, script_version='5.0.2'):
    """Set up the pre-PEP-621 static setup.py pattern used by line_profiler."""
    (tmp_path / 'demo').mkdir()
    (tmp_path / 'demo' / 'model.py').write_text(
        "__version__ = '5.0.2'\n"
    )
    (tmp_path / 'demo' / '__init__.py').write_text(
        "__version__ = '5.0.2'\n"
    )
    (tmp_path / 'democli.py').write_text(
        f"__version__ = '{script_version}'\n"
    )
    (tmp_path / 'setup.py').write_text(
        "INIT_PATH = 'demo/model.py'\n"
        'VERSION = parse_version(INIT_PATH)\n'
    )
    (tmp_path / 'pyproject.toml').write_text(
        '[tool.xcookie]\n'
        'mod_name = "demo"\n\n'
        '[tool.xcookie.entry_points]\n'
        'console_scripts = ["democli=democli:main"]\n'
    )
    (tmp_path / 'CHANGELOG.rst').write_text(
        'Changes\n=======\n\n5.0.3\n-----\n* Draft fix\n'
        '\n5.0.2\n~~~~~\n* Published fix\n'
    )


def test_bump_legacy_setup_py_and_entry_point_version_mirrors(tmp_path):
    _write_legacy_setup_repo(tmp_path)
    before_setup = (tmp_path / 'setup.py').read_text()

    plan = VersionBumper(tmp_path).bump('minor')

    assert plan.version_source.path == tmp_path / 'demo' / 'model.py'
    assert plan.current_version == '5.0.2'
    assert plan.next_version == '5.1.0'
    for relpath in ('demo/model.py', 'demo/__init__.py', 'democli.py'):
        assert "__version__ = '5.1.0'" in (tmp_path / relpath).read_text()
    assert (tmp_path / 'setup.py').read_text() == before_setup
    assert '5.1.0\n-----\n* Draft fix' in (
        tmp_path / 'CHANGELOG.rst'
    ).read_text()


def test_bump_skips_independent_entry_point_version(tmp_path):
    _write_legacy_setup_repo(tmp_path, script_version='9.9.9')
    VersionBumper(tmp_path).bump('minor')
    assert "__version__ = '9.9.9'" in (
        tmp_path / 'democli.py'
    ).read_text()
    assert "__version__ = '5.1.0'" in (
        tmp_path / 'demo' / 'model.py'
    ).read_text()


def test_setup_py_fallback_rejects_path_outside_repository(tmp_path):
    _write_legacy_setup_repo(tmp_path)
    (tmp_path.parent / 'outside.py').write_text("__version__ = '5.0.2'\n")
    setup_path = tmp_path / 'setup.py'
    setup_path.write_text(
        "INIT_PATH = '../outside.py'\n"
        'VERSION = parse_version(INIT_PATH)\n'
    )
    with pytest.raises(RuntimeError, match='editable package version'):
        VersionBumper(tmp_path).plan('minor')


def test_project_version_takes_precedence_over_legacy_setup(tmp_path):
    _write_legacy_setup_repo(tmp_path)
    path = tmp_path / 'pyproject.toml'
    path.write_text(
        '[project]\nname = "demo"\nversion = "5.0.2"\n\n'
        + path.read_text()
    )

    plan = VersionBumper(tmp_path).bump('minor')

    assert plan.version_source.path == path
    assert 'version = "5.1.0"' in path.read_text()
    assert "__version__ = '5.1.0'" in (
        tmp_path / 'demo' / 'model.py'
    ).read_text()



def test_bump_rejects_mismatched_setup_py_version_source(tmp_path):
    _write_legacy_setup_repo(tmp_path)
    path = tmp_path / 'pyproject.toml'
    path.write_text(
        '[project]\nname = "demo"\nversion = "5.0.1"\n\n'
        + path.read_text()
    )
    before = (tmp_path / 'CHANGELOG.rst').read_text()

    with pytest.raises(RuntimeError, match='setup.py package version'):
        VersionBumper(tmp_path).bump('minor')

    assert (tmp_path / 'CHANGELOG.rst').read_text() == before
    assert 'version = "5.0.1"' in path.read_text()


def test_relative_bump_rejects_prerelease():
    with pytest.raises(ValueError, match='explicit target'):
        VersionBumper.resolve_next_version('1.2.3rc1', 'patch')



def test_initial_changelog_matches_bump_contract():
    text = build_initial_changelog('2.3.4')
    assert '## Version 2.3.4 - Unreleased' in text
    assert 'Version 0.0.1' not in text


def test_shared_version_discovery_for_config_inference(tmp_path):
    _write_dynamic_attr_repo(tmp_path, version='5.6.7')
    import toml

    data = toml.loads((tmp_path / 'pyproject.toml').read_text())
    source = find_version_source(tmp_path, data=data, required=False)
    assert source is not None
    assert source.version == '5.6.7'
    assert source.path == tmp_path / 'demo' / '__init__.py'


def test_version_discovery_skips_valueless_annotation(tmp_path):
    (tmp_path / 'demo').mkdir()
    (tmp_path / 'demo' / '__init__.py').write_text(
        "__version__: str\n__version__ = '7.8.9'\n"
    )
    (tmp_path / 'pyproject.toml').write_text(
        '''
[project]
name = "demo"
dynamic = ["version"]

[tool.setuptools.dynamic]
version = {attr = "demo.__version__"}
'''.lstrip()
    )

    source = find_version_source(tmp_path)
    assert source is not None
    assert source.version == '7.8.9'


def test_bump_synchronizes_workspace_versions_and_dependency_pin(tmp_path):
    _write_dynamic_attr_repo(tmp_path, version='1.2.3')
    root_pyproject = tmp_path / 'pyproject.toml'
    text = root_pyproject.read_text()
    text = text.replace(
        '[project]\nname = "demo"\ndynamic = ["version"]',
        '[project]\nname = "demo"\ndynamic = ["version"]\n'
        'dependencies = ["demo-theory==1.2.3"]',
    )
    text += (
        '\n[tool.xcookie]\n'
        'workspace_members = ["packages/demo-theory"]\n'
        'workspace_sync_versions = true\n'
    )
    root_pyproject.write_text(text)

    member = tmp_path / 'packages' / 'demo-theory'
    (member / 'src' / 'demo_theory').mkdir(parents=True)
    (member / 'src' / 'demo_theory' / '__init__.py').write_text(
        "__version__ = '1.2.3'\n"
    )
    (member / 'pyproject.toml').write_text(
        '''
[project]
name = "demo-theory"
dynamic = ["version"]

[tool.setuptools.dynamic]
version = {attr = "demo_theory.__version__"}

[tool.setuptools.packages.find]
where = ["src"]
include = ["demo_theory*"]
'''.lstrip()
    )

    plan = VersionBumper(tmp_path).bump(
        'patch', release_date=datetime_mod.date(2026, 9, 3)
    )
    assert plan.next_version == '1.2.4'
    assert "__version__ = '1.2.4'" in (
        member / 'src' / 'demo_theory' / '__init__.py'
    ).read_text()
    assert 'demo-theory==1.2.4' in root_pyproject.read_text()


def test_bump_synchronizes_reverse_workspace_dependency_and_cargo(tmp_path):
    _write_dynamic_attr_repo(tmp_path, version='1.2.3')
    root_pyproject = tmp_path / 'pyproject.toml'
    root_pyproject.write_text(
        root_pyproject.read_text()
        + '\n[tool.xcookie]\n'
        + 'workspace_members = ["packages/demo-accel"]\n'
        + 'workspace_sync_versions = true\n'
    )

    member = tmp_path / 'packages' / 'demo-accel'
    member.mkdir(parents=True)
    (member / 'pyproject.toml').write_text(
        '''
[project]
name = "demo-accel"
version = "1.2.3"
dependencies = ["demo==1.2.3"]

[tool.maturin]
manifest-path = "Cargo.toml"
'''.lstrip()
    )
    (member / 'Cargo.toml').write_text(
        '''
[package]
name = "demo-accel"
version = "1.2.3"
edition = "2021"
'''.lstrip()
    )

    plan = VersionBumper(tmp_path).bump(
        'patch', release_date=datetime_mod.date(2026, 9, 3)
    )
    assert plan.next_version == '1.2.4'
    member_pyproject_text = (member / 'pyproject.toml').read_text()
    assert 'version = "1.2.4"' in member_pyproject_text
    assert 'demo==1.2.4' in member_pyproject_text
    assert 'version = "1.2.4"' in (member / 'Cargo.toml').read_text()


def test_bump_accepts_legacy_double_dash_release_heading(tmp_path):
    from xcookie.versioning import update_changelog_for_bump
    import datetime as datetime_mod

    text = (
        '# Changelog\n\n'
        '## Version 0.0.2 -- Released 2026-05-08\n\n'
        '## Version 0.0.1 -- Released 2025-10-28\n'
    )
    updated = update_changelog_for_bump(
        text,
        '0.0.2',
        '0.0.3',
        datetime_mod.date(2026, 9, 3),
    )
    assert '## Version 0.0.3 - Unreleased' in updated
    assert '## Version 0.0.2 -- Released 2026-05-08' in updated


def test_bump_syncs_matching_python_and_maturin_version_mirrors(tmp_path):
    (tmp_path / 'demo').mkdir()
    (tmp_path / 'demo' / '__init__.py').write_text(
        "__version__ = '4.5.6'\n"
    )
    (tmp_path / 'rust').mkdir()
    (tmp_path / 'rust' / 'Cargo.toml').write_text(
        '''
[package]
name = "demo-rust"
version = "4.5.6"
edition = "2021"
'''.lstrip()
    )
    (tmp_path / 'Cargo.toml').write_text(
        '''
[package]
name = "unrelated-root-crate"
version = "0.1.0"
'''.lstrip()
    )
    (tmp_path / 'pyproject.toml').write_text(
        '''
[project]
name = "demo"
version = "4.5.6"

[tool.xcookie]
mod_name = "demo"

[tool.maturin]
manifest-path = "rust/Cargo.toml"
'''.lstrip()
    )
    (tmp_path / 'CHANGELOG.md').write_text(
        '# Changelog\n\n## Version 4.5.6 - Unreleased\n'
    )

    plan = VersionBumper(tmp_path).bump(
        'minor', release_date=datetime_mod.date(2026, 9, 20)
    )

    assert plan.next_version == '4.6.0'
    assert 'version = "4.6.0"' in (tmp_path / 'pyproject.toml').read_text()
    assert "__version__ = '4.6.0'" in (
        tmp_path / 'demo' / '__init__.py'
    ).read_text()
    assert 'version = "4.6.0"' in (
        tmp_path / 'rust' / 'Cargo.toml'
    ).read_text()
    assert 'version = "0.1.0"' in (tmp_path / 'Cargo.toml').read_text()


def test_bump_leaves_mismatched_local_versions_independent(tmp_path):
    (tmp_path / 'demo').mkdir()
    (tmp_path / 'demo' / '__init__.py').write_text(
        "__version__ = '9.9.9'\n"
    )
    (tmp_path / 'rust').mkdir()
    (tmp_path / 'rust' / 'Cargo.toml').write_text(
        '''
[package]
name = "demo-rust"
version = "1.0.0"
'''.lstrip()
    )
    (tmp_path / 'pyproject.toml').write_text(
        '''
[project]
name = "demo"
version = "4.5.6"

[tool.xcookie]
mod_name = "demo"

[tool.maturin]
manifest-path = "rust/Cargo.toml"
'''.lstrip()
    )
    (tmp_path / 'CHANGELOG.md').write_text(
        '# Changelog\n\n## Version 4.5.6 - Unreleased\n'
    )

    VersionBumper(tmp_path).bump(
        'patch', release_date=datetime_mod.date(2026, 9, 20)
    )

    assert "__version__ = '9.9.9'" in (
        tmp_path / 'demo' / '__init__.py'
    ).read_text()
    assert 'version = "1.0.0"' in (
        tmp_path / 'rust' / 'Cargo.toml'
    ).read_text()
