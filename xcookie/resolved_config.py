from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import ubelt as ub
from packaging.version import parse as Version


@dataclass(frozen=True)
class ResolvedXCookieConfig:
    """Resolved, builder-facing view of :class:`XCookieConfig`.

    ``XCookieConfig`` remains the CLI / pyproject input container.  This class
    centralizes the inference that used to live directly in
    ``XCookieConfig.__post_init__`` so downstream code can depend on explicit
    resolved values instead of knowing which config fields may still be
    ``None`` or ``"auto"``.
    """

    repodir: ub.Path
    repo_name: str
    mod_name: str
    pkg_name: str
    rel_mod_parent_dpath: str
    tags: tuple[str, ...]
    os: tuple[str, ...]
    is_new: bool
    rotate_secrets: bool
    refresh_docs: bool
    author: str
    author_email: str
    license: str
    version: str
    description: str
    supported_python_versions: tuple[str, ...]
    ci_cpython_versions: tuple[str, ...]
    ci_pypy_versions: tuple[str, ...]
    use_uv: bool

    @classmethod
    def from_config(cls, config: Any) -> ResolvedXCookieConfig:
        """Resolve the mutable scriptconfig object into explicit values."""
        repodir = _resolve_repodir(config['repodir'])
        tags = _normalize_tags(config['tags'])
        os_values = _normalize_os(config['os'])

        repo_name = config['repo_name']
        if repo_name is None:
            repo_name = repodir.name

        mod_name = config['mod_name']
        if mod_name is None:
            mod_name = repo_name.replace('-', '_')

        pkg_name = config['pkg_name']
        if pkg_name is None:
            pkg_name = mod_name

        is_new = config['is_new']
        if is_new == 'auto':
            is_new = not (repodir / '.git').exists()
        is_new = bool(is_new)

        rotate_secrets = config['rotate_secrets']
        if rotate_secrets == 'auto':
            rotate_secrets = is_new
        rotate_secrets = bool(rotate_secrets)

        refresh_docs = config['refresh_docs']
        if refresh_docs == 'auto':
            refresh_docs = is_new
        refresh_docs = bool(refresh_docs)

        author = config['author']
        if author is None:
            if 'erotemic' in tags:
                author = 'Jon Crall'
            else:
                author = ub.cmd('git config user.name')['out'].strip()
                if author == 'joncrall':
                    author = 'Jon Crall'

        license_text = config['license']
        if license_text is None:
            license_text = 'Apache-2.0'

        author_email = config['author_email']
        if author_email is None:
            if 'erotemic' in tags:
                author_email = 'erotemic@gmail.com'
            else:
                author_email = ub.cmd('git config user.email')['out'].strip()

        version = config['version']
        if version is None:
            version = '0.0.1'

        description = config['description']
        if description is None:
            description = f'The {mod_name} module'

        supported_python_versions = config['supported_python_versions']
        if supported_python_versions == 'auto':
            supported_python_versions = _infer_supported_python_versions(
                config['min_python'], config['max_python']
            )
        supported_python_versions = _coerce_tuple(supported_python_versions)

        ci_cpython_versions = config['ci_cpython_versions']
        if ci_cpython_versions == 'auto':
            ci_cpython_versions = supported_python_versions
        ci_cpython_versions = _coerce_tuple(ci_cpython_versions)

        ci_pypy_versions = config['ci_pypy_versions']
        if ci_pypy_versions == 'auto':
            ci_pypy_versions = ('3.9',) if 'purepy' in tags else ()
        ci_pypy_versions = _coerce_tuple(ci_pypy_versions)

        use_uv = config['use_uv']
        if use_uv == 'auto':
            # Can only use uv if the min python >= 3.8
            min_python = supported_python_versions[0]
            use_uv = Version(min_python) >= Version('3.8')
        use_uv = bool(use_uv)

        return cls(
            repodir=repodir,
            repo_name=str(repo_name),
            mod_name=str(mod_name),
            pkg_name=str(pkg_name),
            rel_mod_parent_dpath=str(config['rel_mod_parent_dpath']),
            tags=tags,
            os=os_values,
            is_new=is_new,
            rotate_secrets=rotate_secrets,
            refresh_docs=refresh_docs,
            author=str(author),
            author_email=str(author_email),
            license=str(license_text),
            version=str(version),
            description=str(description),
            supported_python_versions=supported_python_versions,
            ci_cpython_versions=ci_cpython_versions,
            ci_pypy_versions=ci_pypy_versions,
            use_uv=use_uv,
        )

    @property
    def rel_mod_dpath(self) -> ub.Path:
        return ub.Path(self.rel_mod_parent_dpath) / self.mod_name

    @property
    def mod_dpath(self) -> ub.Path:
        return self.repodir / self.rel_mod_dpath

    def apply_to_config(self, config: Any) -> None:
        """Update a scriptconfig object with resolved compatibility values."""
        updates = {
            'repodir': self.repodir,
            'repo_name': self.repo_name,
            'mod_name': self.mod_name,
            'pkg_name': self.pkg_name,
            'tags': list(self.tags),
            'os': list(self.os),
            'is_new': self.is_new,
            'rotate_secrets': self.rotate_secrets,
            'refresh_docs': self.refresh_docs,
            'author': self.author,
            'author_email': self.author_email,
            'license': self.license,
            'version': self.version,
            'description': self.description,
            'supported_python_versions': list(self.supported_python_versions),
            'ci_cpython_versions': list(self.ci_cpython_versions),
            'ci_pypy_versions': list(self.ci_pypy_versions),
            'use_uv': self.use_uv,
        }
        for key, value in updates.items():
            config[key] = value


def resolve_xcookie_config(config: Any) -> ResolvedXCookieConfig:
    """Resolve and write back compatibility values for existing builders."""
    resolved = ResolvedXCookieConfig.from_config(config)
    resolved.apply_to_config(config)
    return resolved


def _resolve_repodir(value: Any) -> ub.Path:
    if value is None:
        repodir = ub.Path.cwd()
    else:
        repodir = ub.Path(value).absolute()

    try:
        repodir = _find_git_root(repodir)
    except Exception:
        print('assuming the root was given and we are not in a repo yet')
    return repodir


def _normalize_tags(value: Any) -> tuple[str, ...]:
    if not value:
        return ()
    if isinstance(value, str):
        value = [value]
    normalized = []
    for item in value:
        normalized.extend([p.strip() for p in str(item).split(',')])
    return tuple(p for p in normalized if p)


def _normalize_os(value: Any) -> tuple[str, ...]:
    if not value:
        return ()
    if isinstance(value, str):
        value = [value]
    normalized = []
    for item in value:
        normalized.extend([p.strip() for p in str(item).split(',')])
    os_values = set(p for p in normalized if p)
    if 'all' in os_values:
        os_values.update({'win', 'osx', 'linux'})
        os_values.remove('all')
    os_normalizer = {
        'windows': 'win',
        'win32': 'win',
        'darwin': 'osx',
        'apple': 'osx',
    }
    return tuple(sorted(os_normalizer.get(item, item) for item in os_values))


def _infer_supported_python_versions(
    min_python: Any, max_python: Any
) -> tuple[str, ...]:
    from xcookie.constants import KNOWN_PYTHON_VERSIONS

    min_python = str(min_python).lower()
    max_python = str(max_python).lower()

    def satisfies_minmax(version: str) -> bool:
        parsed_version = Version(version)
        if min_python != 'none':
            min_version = Version(min_python)
            if parsed_version < min_version:
                return False
        if max_python != 'none':
            max_version = Version(max_python)
            if parsed_version > max_version:
                return False
        return True

    return tuple(
        version for version in KNOWN_PYTHON_VERSIONS if satisfies_minmax(version)
    )


def _coerce_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(item) for item in value)


def _find_git_root(dpath: Any) -> ub.Path:
    cwd = ub.Path(dpath).resolve()
    parts = cwd.parts
    found = None
    for i in reversed(range(0, len(parts) + 1)):
        subparts = parts[0:i]
        if len(subparts) == 0:
            break
        path = ub.Path(*subparts)
        candidate = path / '.git'
        if candidate.exists():
            found = path
            break
    if found is None:
        raise Exception('cannot find git root')
    return found
