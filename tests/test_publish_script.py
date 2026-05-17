from pathlib import Path


def test_publish_template_uses_pyproject_build_not_setup_py() -> None:
    text = Path('xcookie/rc/publish.sh.in').read_text()
    assert 'python -m build --sdist' in text
    assert 'python -m build --wheel' in text
    assert 'python setup.py' not in text
    assert 'import setup; print(setup.VERSION)' not in text
    assert 'project_version()' in text


def test_generated_publish_script_matches_template_when_regenerated() -> None:
    template_text = Path('xcookie/rc/publish.sh.in').read_text()
    script_text = Path('publish.sh').read_text()
    assert script_text == template_text
