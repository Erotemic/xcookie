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
