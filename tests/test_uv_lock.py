import os
from pathlib import Path
import subprocess

import pytest

from xcookie.util_command import find_bash_executable

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_uv_lock_is_checked_in_and_sanitized() -> None:
    lock_fpath = REPO_ROOT / 'uv.lock'
    if not lock_fpath.exists():
        pytest.skip(
            f'uv.lock not present at {lock_fpath} (non-source test run)'
        )
    text = lock_fpath.read_text()
    assert 'name = "xcookie"' in text
    assert 'https://pypi.org/simple' in text
    assert 'files.pythonhosted.org' in text
    assert 'applied-caas' not in text
    assert 'internal.api.openai.org' not in text
    assert 'reader:' not in text


def test_checked_lock_requirement_exports_are_present_and_sanitized() -> None:
    lock_dpath = REPO_ROOT / 'requirements/locks'
    if not lock_dpath.exists():
        pytest.skip(f'{lock_dpath} not present (non-source test run)')
    expected = {
        'runtime.txt',
        'tests.txt',
        'optional.txt',
        'docs.txt',
        'tests-optional.txt',
    }
    assert expected <= {p.name for p in lock_dpath.glob('*.txt')}
    for fpath in lock_dpath.glob('*.txt'):
        text = fpath.read_text()
        assert '==' in text
        assert 'applied-caas' not in text
        assert 'internal.api.openai.org' not in text
        assert 'reader:' not in text


def test_generated_github_ci_exports_lock_requirements_at_install(
    tmp_path,
) -> None:
    from xcookie.main import TemplateApplier, XCookieConfig

    cfg = XCookieConfig(
        repodir=tmp_path,
        repo_name='demo_pkg',
        mod_name='demo_pkg',
        tags=['github', 'purepy'],
        interactive=False,
        use_setup_py=False,
        use_pyproject_requirements=False,
        min_python='3.10',
        test_variants=['minimal-strict', 'full-loose'],
    )
    cfg['enable_gpg'] = False
    cfg['deploy'] = False
    self = TemplateApplier(cfg)
    self._presetup()
    text = self.build_github_actions_tests()
    assert 'use-lockfile:' in text
    assert 'lock-requirements:' in text
    assert 'LOCK_REQUIREMENTS: ${{ matrix.lock-requirements }}' in text
    assert 'requirements/locks/tests.txt' in text
    assert 'python -m uv export --locked --no-emit-project' in text
    assert 'Missing checked-in lock requirements' not in text
    assert 'python -m uv pip compile' not in text
    # Generated paths are output targets, not files that must already exist.
    assert 'mkdir -p "$(dirname "$LOCK_REQUIREMENTS")"' in text


def test_strict_ci_can_export_constraints_when_only_uv_lock_exists(
    tmp_path,
) -> None:
    """Exercise the generated bash without a network or installed uv."""
    from xcookie.builders import common_ci
    from xcookie.main import TemplateApplier, XCookieConfig

    cfg = XCookieConfig(
        repodir=tmp_path,
        repo_name='demo_pkg',
        mod_name='demo_pkg',
        tags=['github', 'purepy'],
        interactive=False,
        use_uv=True,
        use_setup_py=False,
        use_pyproject_requirements=False,
    )
    cfg['enable_gpg'] = False
    cfg['deploy'] = False
    self = TemplateApplier(cfg)
    self._presetup()
    parts = common_ci.make_install_and_test_wheel_parts(
        self, 'wheelhouse', [], 'sandbox'
    )
    commands = parts['install_wheel_commands']
    lock_start = commands.index('LOCK_ARGS=()')
    lock_script = '\n'.join(commands[lock_start:])
    assert 'uv export --locked' in lock_script

    bash_executable = find_bash_executable()
    if bash_executable is None:
        pytest.skip('Bash is required (Git Bash on Windows)')

    # The shell fake records uv's argv and writes a minimal requirements file.
    # This exercises the actual generated quoting and --extra expansion.
    fake_uv = r'''
python() {
    if [[ "$1" == '-m' && "$2" == 'uv' && "$3" == 'export' ]]; then
        printf '%s\n' "$@" > export_args.txt
        while [[ $# -gt 0 ]]; do
            if [[ "$1" == '-o' ]]; then
                shift
                printf 'some-dependency==1.2.3\n' > "$1"
                return 0
            fi
            shift
        done
        return 2
    elif [[ "$1" == '-m' && "$2" == 'uv' && "$3" == 'pip' ]]; then
        printf '%s\n' "$@" > install_args.txt
        return 0
    fi
    return 3
}
'''
    lock_relp = Path('requirements/locks/tests-optional.txt')
    assert not (tmp_path / lock_relp).exists()
    env = {
        'USE_UV_LOCK': 'true',
        'INSTALL_EXTRAS': 'tests,optional',
        'LOCK_REQUIREMENTS': lock_relp.as_posix(),
        'INSTALL_TARGET': 'wheelhouse/demo_pkg-1.0.whl[tests,optional]',
    }
    # Empty uv.lock content is enough for the shell fake; the real --locked
    # flag independently rejects a stale lock during CI.
    (tmp_path / 'uv.lock').write_text('')
    run = subprocess.run(
        [bash_executable, '-c', 'set -euo pipefail\n' + fake_uv + lock_script],
        cwd=tmp_path,
        env={**os.environ, **env},
        text=True,
        capture_output=True,
    )
    assert run.returncode == 0, (run.stdout, run.stderr)
    assert (tmp_path / lock_relp).read_text() == 'some-dependency==1.2.3\n'
    export_args = (tmp_path / 'export_args.txt').read_text().splitlines()
    assert '--locked' in export_args
    assert '--no-emit-project' in export_args
    assert export_args[export_args.index('--extra') + 1] == 'tests'
    second_extra = export_args.index('--extra', export_args.index('--extra') + 1)
    assert export_args[second_extra + 1] == 'optional'
    assert export_args[-2:] == ['-o', lock_relp.as_posix()]
    install_args = (tmp_path / 'install_args.txt').read_text().splitlines()
    assert install_args[install_args.index('--constraint') + 1] == lock_relp.as_posix()
    assert install_args[-1] == env['INSTALL_TARGET']

    # Missing authoritative uv.lock should fail visibly, not silently
    # install an unlocked dependency set.
    (tmp_path / 'uv.lock').unlink()
    (tmp_path / lock_relp).unlink()
    run = subprocess.run(
        [bash_executable, '-c', 'set -euo pipefail\n' + fake_uv + lock_script],
        cwd=tmp_path,
        env={**os.environ, **env},
        text=True,
        capture_output=True,
    )
    assert run.returncode != 0
    assert 'Missing uv.lock' in run.stdout


def test_refresh_locks_sh_emits_one_export_per_strict_variant(tmp_path) -> None:
    from xcookie.main import TemplateApplier, XCookieConfig

    cfg = XCookieConfig(
        repodir=tmp_path,
        repo_name='demo_pkg',
        mod_name='demo_pkg',
        tags=['github', 'purepy'],
        interactive=False,
        use_setup_py=False,
        use_pyproject_requirements=True,
        min_python='3.11',
        test_variants=['minimal-strict', 'full-strict', 'full-loose'],
    )
    cfg['enable_gpg'] = False
    cfg['deploy'] = False
    self = TemplateApplier(cfg)
    self._presetup()
    text = self.build_refresh_locks_sh()

    assert text.startswith('#!/usr/bin/env bash\n')
    assert 'set -euo pipefail' in text
    assert 'uv lock' in text
    # The two strict variants for a vanilla purepy project are tests and
    # tests,optional; each should emit its own export line.
    assert '-o requirements/locks/tests.txt' in text
    assert '-o requirements/locks/tests-optional.txt' in text
    assert text.count('uv export --frozen --no-emit-project') == 2
    # Generator must wire the script into the template registry only when uv
    # lockfile CI is in use.
    self._build_template_registry()
    infos = [
        info
        for info in self.template_infos
        if str(info.get('fname', '')) == 'dev/refresh_locks.sh'
    ]
    assert len(infos) == 1
    assert infos[0].enabled is True
    assert 'x' in infos[0].perms


def test_refresh_locks_sh_disabled_for_legacy_setup_py_repos(tmp_path) -> None:
    from xcookie.main import TemplateApplier, XCookieConfig

    cfg = XCookieConfig(
        repodir=tmp_path,
        repo_name='legacy_pkg',
        mod_name='legacy_pkg',
        tags=['github', 'purepy'],
        interactive=False,
        use_setup_py=True,
        use_pyproject_requirements=False,
        min_python='3.11',
    )
    cfg['enable_gpg'] = False
    cfg['deploy'] = False
    self = TemplateApplier(cfg)
    self._presetup()
    self._build_template_registry()
    # Legacy setup.py + non-pyproject-requirements projects use generated
    # ``*-strict`` extras instead of a checked-in lockfile, so the refresh
    # script has nothing to do; it should be present but disabled.
    infos = [
        info
        for info in self.template_infos
        if str(info.get('fname', '')) == 'dev/refresh_locks.sh'
    ]
    assert len(infos) == 1
    assert infos[0].enabled is False


def test_refresh_locks_omits_workspace_members_from_constraints(tmp_path) -> None:
    from xcookie.main import TemplateApplier, XCookieConfig

    member = tmp_path / 'packages' / 'demo-theory'
    member.mkdir(parents=True)
    (member / 'pyproject.toml').write_text(
        '[project]\nname = "demo-theory"\nversion = "1.0.0"\n'
    )
    (tmp_path / 'pyproject.toml').write_text(
        '''
[project]
name = "demo"
version = "1.0.0"

[project.optional-dependencies]
tests = []

[tool.xcookie]
workspace_members = ["packages/demo-theory"]
'''.lstrip()
    )
    config = XCookieConfig(
        repodir=tmp_path,
        tags=['github', 'purepy'],
        use_uv=True,
        use_setup_py=False,
        use_pyproject_requirements=True,
        workspace_members=['packages/demo-theory'],
    )
    applier = TemplateApplier(config)
    applier._presetup()
    text = applier.build_refresh_locks_sh()
    assert '--no-emit-workspace' in text
    assert '--no-emit-project' not in text
    workflow = applier.build_github_actions_tests()
    assert 'uv export --locked --no-emit-workspace' in workflow
