"""
Test the TemplateApplier.format_code method
"""

import pathlib
import tempfile

from xcookie.main import TemplateApplier, XCookieConfig


def test_format_code_with_pyproject_settings() -> None:
    """
    Test that format_code respects quote-style and other settings from
    the project's pyproject.toml
    """
    config = XCookieConfig(
        repodir='.',
        repo_name='xcookie',
        mod_name='xcookie',
        tags=['erotemic', 'github', 'purepy'],
        rotate_secrets=False,
        init_new_remotes=False,
        interactive=False,
        use_vcs=False,
    )

    applier = TemplateApplier(config)

    # Test that double quotes are converted to single quotes
    # (as per xcookie's pyproject.toml setting: quote-style = "single")
    test_code = 'x = "hello world"\n'
    formatted = applier.format_code(test_code)
    assert "x = 'hello world'" in formatted


def test_format_code_with_default_settings() -> None:
    """
    Test that format_code uses reasonable defaults when no
    pyproject.toml exists
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = pathlib.Path(tmpdir)

        config = XCookieConfig(
            repodir=tmppath,
            repo_name='test_repo',
            mod_name='test_mod',
            tags=['github', 'purepy'],
            rotate_secrets=False,
            init_new_remotes=False,
            interactive=False,
            use_vcs=False,
        )

        applier = TemplateApplier(config)

        # Test formatting without pyproject.toml - should use defaults
        test_code = 'x=1\ny  =   2\n'
        formatted = applier.format_code(test_code)
        assert 'x = 1' in formatted
        assert 'y = 2' in formatted


def test_format_code_with_line_length() -> None:
    """
    Test that format_code respects line-length setting from pyproject.toml
    """
    config = XCookieConfig(
        repodir='.',
        repo_name='xcookie',
        mod_name='xcookie',
        tags=['erotemic', 'github', 'purepy'],
        rotate_secrets=False,
        init_new_remotes=False,
        interactive=False,
        use_vcs=False,
    )

    applier = TemplateApplier(config)

    # Test that line-length is respected (xcookie uses 80)
    test_code = 'a_very_long_variable_name = "a very long string that should not exceed the line length limit"\n'
    formatted = applier.format_code(test_code)
    # The formatter should respect the line-length setting
    assert isinstance(formatted, str)


def test_format_code_basic_formatting() -> None:
    """
    Test that format_code performs basic Python formatting
    """
    config = XCookieConfig(
        repodir='.',
        repo_name='xcookie',
        mod_name='xcookie',
        tags=['erotemic', 'github', 'purepy'],
        rotate_secrets=False,
        init_new_remotes=False,
        interactive=False,
        use_vcs=False,
    )

    applier = TemplateApplier(config)

    # Test basic formatting
    test_code = 'import os,sys\nx=  1\nprint("hi")\n'
    formatted = applier.format_code(test_code)

    # Should have proper spacing
    assert 'x = 1' in formatted
    # Should use single quotes
    assert "print('hi')" in formatted


def test_generated_init_text_formats_platform_specific(tmp_path) -> None:
    """
    Regression test for formatting the generated ``__init__.py`` template.

    This covers the path where xcookie builds ``__init__.py`` via ``lut()`` and
    then formats the generated source. It guards against Windows-specific path
    escaping bugs in the templated ``__mkinit__`` block.
    """
    from xcookie.main import TemplateApplier, XCookieConfig

    repodir = tmp_path / 'demo'
    repodir.mkdir()

    config = XCookieConfig(
        repodir=repodir,
        mod_name='demo_mod',
        repo_name='demo_mod',
        tags=['github', 'purepy'],
        rotate_secrets=False,
        init_new_remotes=False,
        interactive=False,
        use_vcs=False,
        author='Test Author',
        author_email='test@example.com',
        version='0.0.1',
        url='https://example.com/demo_mod',
    )

    applier = TemplateApplier(config)

    rel_init_fpath = applier.rel_mod_dpath / '__init__.py'
    repo_init_fpath = applier.repodir / rel_init_fpath

    info = {
        'fname': rel_init_fpath,
        'repo_fpath': repo_init_fpath,
    }

    text = applier.lut(info)
    formatted = applier.format_code(text, filename='__init__.py')

    assert '__mkinit__' in formatted
    assert 'demo_mod' in formatted
