from types import SimpleNamespace

import ubelt as ub


class AttrDict(dict):
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError as ex:
            raise AttributeError(key) from ex


def _fake_builder_self(tmp_path):
    config = AttrDict(
        repodir=tmp_path,
        repo_name='demo_pkg',
        pkg_name='demo_pkg',
        mod_name='demo_pkg',
        rel_mod_parent_dpath='src',
        tags=['github', 'purepy'],
        url='https://github.com/example/demo_pkg',
        author='Demo Author',
        render_doc_images=False,
    )
    return SimpleNamespace(
        config=config,
        rel_mod_dpath=ub.Path('src/demo_pkg'),
        repodir=ub.Path(tmp_path),
    )


def test_docs_index_uses_single_apidoc_entry(tmp_path):
    """Avoid duplicate toctree entries when auto/modules links auto/{mod_name}."""
    from xcookie.builders.docs import build_docs_index

    text = build_docs_index(_fake_builder_self(tmp_path))

    assert '   auto/modules' in text
    assert '   auto/demo_pkg' not in text


def test_generated_conf_uses_modern_sphinx_defaults(tmp_path, monkeypatch):
    """Generated conf.py should avoid stale Sphinx warning patterns."""
    from xcookie.builders.docs import build_docs_conf
    from xcookie.util import util_code_format

    monkeypatch.setattr(util_code_format, 'format_code', lambda text, *a, **kw: text)

    text = build_docs_conf(_fake_builder_self(tmp_path))

    assert 'import sphinx_rtd_theme' not in text
    assert 'html_theme_path' not in text
    assert "source_suffix = ['.rst', '.md']" not in text
    assert "'.rst': 'restructuredtext'" in text
    assert "'.md': 'markdown'" in text
    assert "'display_version'" not in text
    assert 'html_static_path = []' in text
    assert 'myst_heading_anchors = 3' in text
