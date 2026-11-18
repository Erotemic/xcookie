"""Regressions for native ARM test jobs and cross-compiled wheel artifacts."""

import pytest

from xcookie.builders import ci_model
from xcookie.builders.github_actions import _wheel_artifact_build_runner
from xcookie.main import TemplateApplier, XCookieConfig
from xcookie.util_yaml import Yaml


def _make_applier(tmp_path, *, binpy=True, windows_arm64=True):
    if windows_arm64:
        (tmp_path / 'pyproject.toml').write_text(
            '[tool.cibuildwheel.windows]\narchs = ["AMD64", "ARM64"]\n'
        )
    cfg = XCookieConfig(
        repodir=tmp_path,
        repo_name='demo_pkg',
        mod_name='demo_pkg',
        tags=['github', 'binpy' if binpy else 'purepy'],
        os=['win'],
        min_python='3.11',
        max_python='3.13',
        interactive=False,
        init_new_remotes=False,
        deploy=False,
    )
    applier = TemplateApplier(cfg)
    applier._presetup()
    return applier


def test_native_windows_arm_tests_download_cross_compiled_artifact(tmp_path):
    """The ARM test runner consumes wheels built by windows-latest."""
    applier = _make_applier(tmp_path)
    workflow = Yaml.loads(applier.build_github_actions_tests())
    build_job = workflow['jobs']['build_binpy_wheels']
    test_job = workflow['jobs']['test_binpy_wheels']
    assert build_job['strategy']['matrix']['os'] == ['windows-latest']
    rows = test_job['strategy']['matrix']['include']
    arm_rows = [row for row in rows if row['os'] == 'windows-11-arm']
    x64_rows = [row for row in rows if row['os'] == 'windows-latest']
    assert arm_rows and x64_rows
    assert all(row['wheel-artifact-os'] == 'windows-latest' for row in arm_rows)
    assert all(row['wheel-artifact-os'] == 'windows-latest' for row in x64_rows)
    assert all(row['arch'] == 'auto' for row in rows)
    downloader = next(
        step for step in test_job['steps']
        if step.get('name') == 'Download wheel for this platform'
    )
    assert downloader['with']['name'] == (
        'wheels-${{ matrix.wheel-artifact-os }}-${{ matrix.arch }}'
    )
    uploader = next(
        step for step in build_job['steps']
        if step.get('name') == 'Upload wheels artifact'
    )
    assert uploader['with']['name'] == (
        'wheels-${{ matrix.os }}-${{ matrix.arch }}'
    )


def test_regular_windows_matrix_uses_own_builder(tmp_path):
    applier = _make_applier(tmp_path, windows_arm64=False)
    workflow = Yaml.loads(applier.build_github_actions_tests())
    rows = workflow['jobs']['test_binpy_wheels']['strategy']['matrix'][
        'include'
    ]
    assert rows
    assert all(
        row['os'] == row['wheel-artifact-os'] == 'windows-latest'
        for row in rows
    )


def test_purepy_matrix_does_not_gain_binary_wheel_artifact_os(tmp_path):
    applier = _make_applier(tmp_path, binpy=False)
    workflow = Yaml.loads(applier.build_github_actions_tests())
    job = workflow['jobs']['test_purepy_wheels']
    rows = job['strategy']['matrix']['include']
    assert rows
    assert all('wheel-artifact-os' not in row for row in rows)
    downloader = next(
        step
        for step in job['steps']
        if 'Download wheel' in step.get('name', '')
    )
    assert downloader['with']['pattern'] == 'wheels-*'


def test_unmatched_or_ambiguous_wheel_builder_is_detected():
    win_arm_platform = ci_model.CIPlatform(
        logical_os='win', github_os='windows-11-arm', arch='auto'
    )
    assert (
        _wheel_artifact_build_runner(win_arm_platform, ['windows-latest'])
        == 'windows-latest'
    )
    with pytest.raises(
        ValueError, match='Cannot identify wheel artifact builder'
    ):
        _wheel_artifact_build_runner(win_arm_platform, ['ubuntu-latest'])
    with pytest.raises(
        ValueError, match='Cannot identify wheel artifact builder'
    ):
        _wheel_artifact_build_runner(
            win_arm_platform, ['windows-2025', 'windows-2022']
        )
