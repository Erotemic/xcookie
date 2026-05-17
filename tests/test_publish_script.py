from pathlib import Path

import pytest


def _publish_template_text() -> str:
    from xcookie import rc

    return Path(rc.resource_fpath('publish.sh.in')).read_text()


def test_publish_template_uses_pyproject_build_not_setup_py() -> None:
    text = _publish_template_text()
    assert 'python -m build --sdist' in text
    assert 'python -m build --wheel' in text
    assert 'python setup.py' not in text
    assert 'import setup; print(setup.VERSION)' not in text
    assert 'project_version()' in text


def test_generated_publish_script_matches_template_when_regenerated() -> None:
    script_fpath = Path('publish.sh')
    if not script_fpath.exists():
        pytest.skip('source-tree publish.sh is not available in installed-package tests')
    template_text = _publish_template_text()
    script_text = script_fpath.read_text()
    assert script_text == template_text
