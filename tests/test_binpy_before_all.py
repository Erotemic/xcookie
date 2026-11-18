"""Native wheel build hooks must be opt-in rather than hard-coded."""

import toml

from xcookie.main import TemplateApplier, XCookieConfig


def _render_binary_pyproject(tmp_path, cibuildwheel=None):
    if cibuildwheel is not None:
        (tmp_path / 'pyproject.toml').write_text(
            toml.dumps({'tool': {'cibuildwheel': cibuildwheel}})
        )
    cfg = XCookieConfig(
        repodir=tmp_path,
        repo_name='demo_pkg',
        mod_name='demo_pkg',
        tags=['github', 'binpy'],
        init_new_remotes=False,
        interactive=False,
        use_vcs=False,
        use_setup_py=False,
        min_python='3.10',
        max_python='3.15',
    )
    applier = TemplateApplier(cfg)
    applier._presetup()
    return toml.loads(applier.build_pyproject())['tool']['cibuildwheel']


def test_binpy_does_not_install_unused_native_dependencies(tmp_path):
    """New binary projects must not need Chocolatey, yum, or Homebrew."""
    cibw = _render_binary_pyproject(tmp_path)
    for platform in ['windows', 'linux', 'macos']:
        assert 'before-all' not in cibw.get(platform, {})


def test_binpy_removes_legacy_lz4_hooks_on_regeneration(tmp_path):
    """Old generated lz4 commands must not persist through regeneration."""
    cibw = _render_binary_pyproject(
        tmp_path,
        {
            'windows': {'before-all': 'choco install lz4 -y'},
            'linux': {'before-all': 'yum install epel-release lz4 lz4-devel -y'},
            'macos': {'before-all': 'brew install lz4'},
        },
    )
    for platform in ['windows', 'linux', 'macos']:
        assert 'before-all' not in cibw.get(platform, {})


def test_binpy_preserves_project_defined_native_build_hooks(tmp_path):
    """Only exact legacy defaults may be removed from existing projects."""
    hooks = {
        'windows': {'before-all': 'vcpkg install fmt:x64-windows'},
        'linux': {'before-all': 'yum install -y libffi-devel'},
        'macos': {'before-all': ['brew install pkg-config', 'echo prepared']},
    }
    cibw = _render_binary_pyproject(tmp_path, hooks)
    for platform, settings in hooks.items():
        assert cibw[platform]['before-all'] == settings['before-all']
