from __future__ import annotations

import datetime as datetime_mod

import pytest

from xcookie.versioning import VersionBumper


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
