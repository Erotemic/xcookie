"""Small project files generated directly from resolved xcookie metadata."""

from __future__ import annotations

import ubelt as ub

from xcookie.util.util_metadata import metadata_text
from xcookie.versioning import build_initial_changelog


def build_changelog(applier, info):
    """Build the initial changelog using the configured package version."""
    return build_initial_changelog(metadata_text(applier.config['version']))


def build_test_import(applier, info):
    """Build the package import smoke test."""
    return ub.codeblock(
        f"""
        def test_import():
            import {applier.config['mod_name']}
        """
    )


def build_package_init(applier, info):
    """Build the package ``__init__.py`` metadata scaffold."""
    mkinit_target = ub.Path(info.repo_fpath).as_posix()
    version = metadata_text(applier.config['version'])
    author = metadata_text(applier.config['author'])
    author_email = metadata_text(applier.config['author_email'])
    url = metadata_text(applier.config['url'])
    return ub.codeblock(
        f'''
        """
        Basic
        """
        __version__ = {version!r}
        __author__ = {author!r}
        __author_email__ = {author_email!r}
        __url__ = {url!r}

        __mkinit__ = """
        mkinit {mkinit_target}
        """
        '''
    )


def build_requirement_metadata(applier, info):
    """Build a metadata-only companion for a pip requirements file."""
    from xcookie.builders.pyproject import (
        _build_setuptools_requirement_metadata_text,
    )

    fname = ub.Path(info.fname).name
    if not fname.endswith('-metadata.txt'):
        raise ValueError(f'Expected metadata requirements path, got {fname!r}')
    source_name = fname[: -len('-metadata.txt')] + '.txt'
    source_fpath = applier.repodir / 'requirements' / source_name
    return _build_setuptools_requirement_metadata_text(source_fpath)
