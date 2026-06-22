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



def test_template_info_bool_strings_are_coerced():
    info = TemplateInfo.coerce({
        'fname': 'demo.txt',
        'overwrite': 'false',
        'enabled': '0',
        'skip': 'none',
        'template': 'yes',
    })
    assert info.overwrite is False
    assert info.enabled is False
    assert info.skip is False
    assert info.template is True

    info['overwrite'] = 'true'
    assert info.overwrite is True


def test_template_info_rejects_ambiguous_bool_strings():
    import pytest

    with pytest.raises(ValueError):
        TemplateInfo.coerce({'fname': 'demo.txt', 'overwrite': 'sometimes'})


def test_template_info_auto_bool_sentinel_is_truthy_for_legacy_config():
    info = TemplateInfo.coerce({
        'fname': 'setup.py',
        'enabled': 'auto',
    })
    assert info.enabled is True


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
    # PyPy auto-selection should lock onto the supported python range rather
    # than the legacy hardcoded 3.9.
    assert resolved.ci_pypy_versions == ('3.11',)
    resolved.apply_to_config(config)
    assert config['repo_name'] == resolved.repo_name
    assert config['supported_python_versions'] == ['3.11']
    assert config['ci_pypy_versions'] == ['3.11']


def _resolve_pypy(tmp_path, *, tags, min_python, max_python=None,
                  ci_pypy_versions='auto'):
    config = {
        'repodir': tmp_path,
        'repo_name': None,
        'mod_name': None,
        'pkg_name': None,
        'rel_mod_parent_dpath': 'src',
        'tags': tags,
        'os': 'linux',
        'is_new': 'auto',
        'rotate_secrets': 'auto',
        'refresh_docs': 'auto',
        'author': 'Example Author',
        'author_email': 'author@example.com',
        'license': None,
        'version': None,
        'description': None,
        'supported_python_versions': 'auto',
        'ci_cpython_versions': 'auto',
        'ci_pypy_versions': ci_pypy_versions,
        'use_uv': 'auto',
        'min_python': min_python,
        'max_python': max_python,
    }
    return ResolvedXCookieConfig.from_config(config)


def test_pypy_auto_locks_to_supported_range(tmp_path):
    # A project requiring python >= 3.10 must not request pypy 3.9.
    resolved = _resolve_pypy(tmp_path, tags='github,purepy', min_python='3.10')
    assert '3.9' not in resolved.ci_pypy_versions
    for pyver in resolved.ci_pypy_versions:
        assert pyver in resolved.supported_python_versions


def test_pypy_auto_disabled_without_purepy(tmp_path):
    resolved = _resolve_pypy(tmp_path, tags='github,binpy', min_python='3.8')
    assert resolved.ci_pypy_versions == ()


def test_pypy_auto_empty_when_no_compatible_release(tmp_path):
    # PyPy has not released a 3.13-only interpreter, so a 3.13-min project gets
    # no pypy job rather than an invalid one.
    resolved = _resolve_pypy(tmp_path, tags='github,purepy', min_python='3.13')
    assert resolved.ci_pypy_versions == ()


def test_pypy_explicit_versions_pass_through(tmp_path):
    resolved = _resolve_pypy(
        tmp_path, tags='github,purepy', min_python='3.9',
        ci_pypy_versions=['3.10', '3.11'],
    )
    assert resolved.ci_pypy_versions == ('3.10', '3.11')
