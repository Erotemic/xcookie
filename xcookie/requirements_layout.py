"""Shared model for project requirement files and packaged requirement resources."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import ubelt as ub


DEFAULT_REQUIREMENTS_RELPATH = ub.Path('requirements')
DEFAULT_LOCKS_RELPATH = DEFAULT_REQUIREMENTS_RELPATH / 'locks'


@dataclass(frozen=True)
class RequirementsLayout:
    """Describe where requirement files live and whether they are packaged.

    Most projects keep ``requirements/`` only at the repository root. Some
    projects, such as KWCOCO, make that path a symlink into an importable
    package so the exact requirements used for a release remain available as
    runtime resources. In that mode the generated lock files belong to the
    same resource tree and should be included in built distributions as well.
    """

    repodir: ub.Path
    project_relpath: ub.Path = DEFAULT_REQUIREMENTS_RELPATH
    package: str | None = None
    package_relpath: ub.Path | None = None

    @classmethod
    def from_config(cls, config: Any) -> 'RequirementsLayout':
        repodir = ub.Path(config['repodir'])
        package = resolve_requirements_package(config)

        package_relpath = None
        if package is not None:
            package_relpath = _package_relpath(config, package)
            _validate_shared_requirements_tree(
                repodir=repodir,
                project_relpath=DEFAULT_REQUIREMENTS_RELPATH,
                package_relpath=package_relpath,
            )

        return cls(
            repodir=repodir,
            package=package,
            package_relpath=package_relpath,
        )

    @property
    def project_dpath(self) -> ub.Path:
        return self.repodir / self.project_relpath

    @property
    def lock_relpath(self) -> ub.Path:
        return self.project_relpath / 'locks'

    @property
    def lock_dpath(self) -> ub.Path:
        return self.repodir / self.lock_relpath

    @property
    def package_dpath(self) -> ub.Path | None:
        if self.package_relpath is None:
            return None
        return self.repodir / self.package_relpath

    @property
    def package_data_patterns(self) -> list[str]:
        """Package-data patterns for the requirements resource package."""
        if self.package is None:
            return []
        return ['*.txt', 'locks/*.txt']


def resolve_requirements_package(
    config: Any,
    *,
    repodir: ub.Path | None = None,
    mod_name: str | None = None,
    rel_mod_parent_dpath: str | None = None,
) -> str | None:
    """Resolve the configured requirements resource package."""
    value = config.get('requirements_package', 'auto')
    if value == 'auto':
        return infer_requirements_package(
            config,
            repodir=repodir,
            mod_name=mod_name,
            rel_mod_parent_dpath=rel_mod_parent_dpath,
        )
    if value in {False, None, '', 'none', 'None', 'false', 'False', 'off'}:
        return None
    return str(value)


def infer_requirements_package(
    config: Any,
    *,
    repodir: ub.Path | None = None,
    mod_name: str | None = None,
    rel_mod_parent_dpath: str | None = None,
) -> str | None:
    """Infer an import package when ``requirements/`` aliases package data."""
    if repodir is None:
        repodir = ub.Path(config['repodir'])
    else:
        repodir = ub.Path(repodir)
    if mod_name is None:
        mod_name = config.get('mod_name')
    if rel_mod_parent_dpath is None:
        rel_mod_parent_dpath = config.get('rel_mod_parent_dpath', '.')
    requirements_dpath = repodir / DEFAULT_REQUIREMENTS_RELPATH
    if not requirements_dpath.is_symlink():
        return None

    try:
        target_dpath = requirements_dpath.resolve()
    except OSError:
        return None

    source_root = (repodir / ub.Path(rel_mod_parent_dpath)).resolve()
    try:
        package_relpath = target_dpath.relative_to(source_root)
    except ValueError:
        return None

    parts = package_relpath.parts
    if not parts or parts[0] != str(mod_name):
        return None

    cursor = source_root
    for part in parts:
        cursor = cursor / part
        if not (cursor / '__init__.py').exists():
            return None
    return '.'.join(parts)


def _package_relpath(config: Any, package: str) -> ub.Path:
    """Translate an import package into its repository-relative directory."""
    rel_mod_parent = ub.Path(config.get('rel_mod_parent_dpath', '.'))
    return rel_mod_parent.joinpath(*package.split('.'))


def _validate_shared_requirements_tree(
    *,
    repodir: ub.Path,
    project_relpath: ub.Path,
    package_relpath: ub.Path,
) -> None:
    """Reject split trees when both requirements locations already exist."""
    project_dpath = repodir / project_relpath
    package_dpath = repodir / package_relpath
    if not project_dpath.exists() or not package_dpath.exists():
        return
    try:
        is_same = project_dpath.samefile(package_dpath)
    except OSError:
        is_same = project_dpath.resolve() == package_dpath.resolve()
    if not is_same:
        raise ValueError(
            'requirements_package must refer to the same requirement tree as '
            f'{project_relpath}. Got project requirements at {project_dpath} '
            f'and package resources at {package_dpath}. Use a symlink (for '
            'example, requirements -> <package>/rc/requirements) or disable '
            'requirements_package.'
        )
