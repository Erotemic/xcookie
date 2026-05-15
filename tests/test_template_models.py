from xcookie.resolved_config import ResolvedXCookieConfig
from xcookie.template_registry import TemplateContext, TemplateInfo
from xcookie.staging import apply_template_context


def test_template_info_normalizes_tags():
    info = TemplateInfo.coerce({
        'fname': 'demo.txt',
        'tags': 'github,purepy',
        'overwrite': 1,
    })
    assert info.fname == 'demo.txt'
    assert info.tags == frozenset({'github', 'purepy'})
    assert info.tag_requirements_met({'github', 'purepy', 'erotemic'})
    assert not info.tag_requirements_met({'github'})
    assert info['overwrite'] is True


def test_template_context_uses_posix_module_path(tmp_path):
    config = {
        'repo_name': 'demo_pkg',
        'mod_name': 'demo_mod',
        'rel_mod_parent_dpath': 'src',
        'author': 'Example Author',
        'author_email': 'author@example.com',
    }
    context = TemplateContext.from_config(config)
    text = apply_template_context(
        'xcookie <mod_name> <rel_mod_dpath> <AUTHOR> <AUTHOR_EMAIL>',
        context,
    )
    assert text == 'demo_pkg demo_mod src/demo_mod Example Author author@example.com'


def test_resolved_config_apply_to_config(tmp_path):
    config = {
        'repodir': tmp_path,
        'repo_name': None,
        'mod_name': None,
        'pkg_name': None,
        'rel_mod_parent_dpath': 'src',
        'tags': 'github,purepy',
        'os': 'all',
        'is_new': 'auto',
        'rotate_secrets': 'auto',
        'refresh_docs': 'auto',
        'author': 'Example Author',
        'author_email': 'author@example.com',
        'license': None,
        'version': None,
        'description': None,
        'supported_python_versions': ['3.11'],
        'ci_cpython_versions': 'auto',
        'ci_pypy_versions': 'auto',
        'use_uv': 'auto',
        'min_python': '3.11',
        'max_python': None,
    }
    resolved = ResolvedXCookieConfig.from_config(config)
    assert resolved.repo_name == tmp_path.name
    assert resolved.mod_name == tmp_path.name.replace('-', '_')
    assert resolved.pkg_name == resolved.mod_name
    assert resolved.tags == ('github', 'purepy')
    assert set(resolved.os) == {'linux', 'osx', 'win'}
    resolved.apply_to_config(config)
    assert config['repo_name'] == resolved.repo_name
    assert config['supported_python_versions'] == ['3.11']
