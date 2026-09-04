"""
Provider-neutral CI planning helpers.

The GitHub Actions and GitLab CI renderers should share decisions about which
extras, variants, and install targets are valid.  This module keeps that policy
in one place while the provider-specific modules remain responsible for YAML
shape and provider syntax.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Iterable, Literal, Mapping

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from xcookie.requirements_layout import DEFAULT_LOCKS_RELPATH

VariantKey = Literal[
    'minimal-loose',
    'full-loose',
    'minimal-strict',
    'full-strict',
]
DependencyMode = Literal['loose', 'strict']
TestScope = Literal['minimal', 'full']

VARIANT_KEYS: tuple[VariantKey, ...] = (
    'minimal-loose',
    'full-loose',
    'minimal-strict',
    'full-strict',
)


@dataclass(frozen=True)
class TestVariant:
    """A provider-neutral test dependency variant."""

    key: VariantKey
    scope: TestScope
    dependency_mode: DependencyMode
    extras: tuple[str, ...]

    @property
    def is_strict(self) -> bool:
        return self.dependency_mode == 'strict'

    @property
    def is_loose(self) -> bool:
        return self.dependency_mode == 'loose'

    @property
    def install_extras(self) -> str:
        """Comma-separated extras string used by generated CI matrices."""
        return ','.join(self.extras)

    @property
    def use_lockfile(self) -> bool:
        """Whether this variant should install from the checked-in lockfile.

        In pyproject-only mode, the old ``*-strict`` extras are replaced by a
        checked-in lockfile. Loose jobs resolve normally, while strict jobs
        export dependency constraints from ``uv.lock``.
        """
        return self.is_strict


@dataclass(frozen=True)
class CIArtifact:
    """A project-owned artifact that xcookie should build and carry through CI."""

    key: str
    name: str
    runner: str
    shell: str
    python_version: str | None
    setup_commands: tuple[str, ...]
    build_commands: tuple[str, ...]
    post_build_commands: tuple[str, ...]
    artifact_paths: tuple[str, ...]
    release_paths: tuple[str, ...]
    test: bool
    release: bool

    @property
    def job_key(self) -> str:
        return f'build_{self.key.replace("-", "_")}'

    @property
    def artifact_name(self) -> str:
        return self.key.replace('_', '-')

    @property
    def release_artifact_name(self) -> str:
        return self.artifact_name + '-release'


@dataclass(frozen=True)
class WorkspaceMember:
    """One additional Python distribution maintained in the repository."""

    key: str
    path: str
    pkg_name: str
    mod_name: str
    rel_mod_parent_dpath: str
    version: str | None
    dependencies: tuple[str, ...]
    optional_dependency_keys: frozenset[str]
    typecheck_extra_paths: tuple[str, ...]
    typed: bool
    publish: bool

    @property
    def rel_mod_dpath(self) -> str:
        parent = self.rel_mod_parent_dpath.strip('./')
        if parent:
            return f'{self.path}/{parent}/{self.mod_name}'
        return f'{self.path}/{self.mod_name}'

    @property
    def test_dpath(self) -> str:
        return f'{self.path}/tests'

    @property
    def artifact_name(self) -> str:
        return f'workspace-{self.key.replace("_", "-")}'

    @property
    def release_artifact_name(self) -> str:
        return f'{self.artifact_name}-release'

    @property
    def dist_prefix(self) -> str:
        return re.sub(r'[-.]+', '_', self.pkg_name)

    @property
    def dependency_free(self) -> bool:
        return not self.dependencies

    @property
    def test_extras(self) -> tuple[str, ...]:
        if 'tests' in self.optional_dependency_keys:
            return ('tests',)
        return tuple()


def _coerce_string_list(value: Any) -> tuple[str, ...]:
    if value is None:
        return tuple()
    if isinstance(value, str):
        return (value,)
    return tuple(str(item) for item in value)


def _infer_member_module_metadata(
    data: Mapping[str, Any], pkg_name: str
) -> tuple[str, str]:
    tool = data.get('tool', {}) or {}
    xcookie = tool.get('xcookie', {}) or {}
    mod_name = xcookie.get('mod_name')
    rel_parent = xcookie.get('rel_mod_parent_dpath')

    setuptools = tool.get('setuptools', {}) or {}
    packages = setuptools.get('packages', {}) or {}
    find_config = packages.get('find', {}) if isinstance(packages, Mapping) else {}
    if rel_parent is None and isinstance(find_config, Mapping):
        where = find_config.get('where', []) or []
        if isinstance(where, str):
            where = [where]
        if where:
            rel_parent = str(where[0])

    if mod_name is None and isinstance(find_config, Mapping):
        include = find_config.get('include', []) or []
        if isinstance(include, str):
            include = [include]
        if len(include) == 1:
            candidate = str(include[0]).rstrip('*').rstrip('.')
            if candidate and '/' not in candidate and '\\' not in candidate:
                mod_name = candidate

    if mod_name is None:
        mod_name = pkg_name.replace('-', '_').replace('.', '_')
    if rel_parent is None:
        rel_parent = '.'
    return str(mod_name), str(rel_parent)


def load_workspace_members(config: Mapping[str, Any]) -> tuple[WorkspaceMember, ...]:
    """Load additional distributions declared by ``workspace_members``."""
    raw_members = config.get('workspace_members') or []
    if isinstance(raw_members, str):
        raw_members = [raw_members]
    if not raw_members:
        return tuple()

    tags = config.get('tags', []) or []
    if isinstance(tags, str):
        tags = [tags]
    if 'github' not in tags:
        raise ValueError(
            'workspace_members currently requires the github xcookie tag'
        )

    repodir = Path(config['repodir']).resolve()
    members: list[WorkspaceMember] = []
    seen_keys: set[str] = set()
    seen_packages: set[str] = set()
    for raw_path in raw_members:
        relpath = Path(str(raw_path))
        if relpath.is_absolute():
            raise ValueError(
                f'workspace member paths must be repository-relative: {raw_path!r}'
            )
        member_dpath = (repodir / relpath).resolve()
        try:
            normalized_relpath = member_dpath.relative_to(repodir).as_posix()
        except ValueError as ex:
            raise ValueError(
                f'workspace member escapes repository root: {raw_path!r}'
            ) from ex

        pyproject_fpath = member_dpath / 'pyproject.toml'
        if not pyproject_fpath.exists():
            raise ValueError(
                f'workspace member {normalized_relpath!r} has no pyproject.toml'
            )
        import toml

        data = toml.loads(pyproject_fpath.read_text())
        project = data.get('project', {}) or {}
        pkg_name = project.get('name')
        if not isinstance(pkg_name, str) or not pkg_name:
            raise ValueError(
                f'workspace member {normalized_relpath!r} requires [project].name'
            )
        normalized_pkg = re.sub(r'[-_.]+', '-', pkg_name).lower()
        key = re.sub(r'[^a-zA-Z0-9_]+', '_', normalized_pkg.replace('-', '_'))
        if key in seen_keys or normalized_pkg in seen_packages:
            raise ValueError(f'duplicate workspace package {pkg_name!r}')
        seen_keys.add(key)
        seen_packages.add(normalized_pkg)

        mod_name, rel_parent = _infer_member_module_metadata(data, pkg_name)
        dependencies = _coerce_string_list(project.get('dependencies'))
        optional = project.get('optional-dependencies', {}) or {}
        if not isinstance(optional, Mapping):
            optional = {}

        tool = data.get('tool', {}) or {}
        xcookie = tool.get('xcookie', {}) or {}
        typecheck_extra_paths = _coerce_string_list(
            xcookie.get('typecheck_extra_paths')
        )
        typed_value = xcookie.get('typed', True)
        typed = typed_value not in {False, None, 'false', 'none', 'off'}
        publish = bool(xcookie.get('deploy_pypi', True))

        from xcookie.versioning import find_version_source

        version_source = find_version_source(
            member_dpath, data=data, required=False
        )
        version = None if version_source is None else version_source.version
        members.append(
            WorkspaceMember(
                key=key,
                path=normalized_relpath,
                pkg_name=pkg_name,
                mod_name=mod_name,
                rel_mod_parent_dpath=rel_parent,
                version=version,
                dependencies=dependencies,
                optional_dependency_keys=frozenset(str(k) for k in optional),
                typecheck_extra_paths=typecheck_extra_paths,
                typed=typed,
                publish=publish,
            )
        )
    return tuple(members)



def validate_workspace_sync(
    self: Any, members: tuple[WorkspaceMember, ...]
) -> None:
    """Reject a workspace whose synchronized package versions have drifted."""
    if not members or not self.config.get('workspace_sync_versions', False):
        return

    root_version = str(self.config.get('version') or '')
    if not root_version:
        raise ValueError(
            'workspace_sync_versions requires a resolved root package version'
        )

    pyproject = self.config._load_pyproject_config() or {}
    dependencies = pyproject.get('project', {}).get('dependencies', []) or []
    parsed_requirements = []
    for item in dependencies:
        if not isinstance(item, str):
            continue
        try:
            parsed_requirements.append(Requirement(item))
        except Exception:
            continue

    for member in members:
        if member.version != root_version:
            raise ValueError(
                f'workspace member {member.pkg_name!r} version '
                f'{member.version!r} does not match root version '
                f'{root_version!r}'
            )
        member_name = canonicalize_name(member.pkg_name)
        matching = [
            req
            for req in parsed_requirements
            if canonicalize_name(req.name) == member_name
            and str(req.specifier) == f'=={root_version}'
            and req.marker is None
        ]
        if len(matching) != 1:
            raise ValueError(
                'workspace_sync_versions requires exactly one root dependency '
                f'pin {member.pkg_name}=={root_version}'
            )


@dataclass(frozen=True)
class CIPlan:
    """Provider-neutral CI decisions shared by GitHub and GitLab renderers."""

    optional_dependency_keys: frozenset[str]
    test_variants: tuple[TestVariant, ...]
    active_test_variants: tuple[TestVariant, ...]
    typecheck_extras: tuple[str, ...]
    sdist_test_extras: tuple[str, ...]
    ci_artifacts: tuple[CIArtifact, ...]
    workspace_members: tuple[WorkspaceMember, ...]

    def variants_by_key(self) -> dict[VariantKey, TestVariant]:
        return {variant.key: variant for variant in self.test_variants}

    def active_variants_by_key(self) -> dict[VariantKey, TestVariant]:
        return {variant.key: variant for variant in self.active_test_variants}

    def active_install_extras(self) -> dict[VariantKey, str]:
        return {
            variant.key: variant.install_extras
            for variant in self.active_test_variants
        }

    def iter_active_variants(
        self, keys: Iterable[VariantKey] | None = None
    ) -> Iterable[TestVariant]:
        if keys is None:
            yield from self.active_test_variants
        else:
            lookup = self.active_variants_by_key()
            for key in keys:
                variant = lookup.get(key)
                if variant is not None:
                    yield variant


def uses_pyproject_dependency_mode(self: Any) -> bool:
    """Return True when CI should avoid legacy setup.py synthesized extras.

    Legacy setup.py mode exposes generated extras such as ``tests-strict`` and
    ``runtime-strict``.  Pyproject-only repositories do not, even when their
    dependencies are still dynamically read from ``requirements/*.txt``.
    In those repositories, strictness is modeled by the installer / lock
    resolution policy instead of by synthetic extra names.
    """
    return bool(
        self.config.get('use_pyproject_requirements')
        or not self.config.get('use_setup_py', True)
    )


def uses_lockfile_ci(self: Any) -> bool:
    """Return True when CI should use checked-in lock constraints."""
    return bool(
        uses_pyproject_dependency_mode(self) and self.config.get('use_uv')
    )


LOCK_REQUIREMENTS_DPATH = DEFAULT_LOCKS_RELPATH.as_posix()


def lock_requirements_name(extras: Iterable[str]) -> str:
    """Return the checked-in lock requirements stem for an extras set."""
    normalized = _unique(str(extra).strip() for extra in extras)
    if not normalized:
        return 'runtime'
    return '-'.join(normalized)


def lock_requirements_path(extras: Iterable[str]) -> str:
    """Return the checked-in lock requirements path for an extras set."""
    return f'{LOCK_REQUIREMENTS_DPATH}/{lock_requirements_name(extras)}.txt'


def _unique(items: Iterable[str]) -> tuple[str, ...]:
    """Return unique non-empty strings while preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if not item:
            continue
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return tuple(result)


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value]


def _load_ci_extras(config: Mapping[str, Any]) -> dict[str, list[str]]:
    """Load user-configured CI extras into a normalized dictionary."""
    ci_extras = config.get('ci_extras')
    if not ci_extras:
        return {}
    if isinstance(ci_extras, str):
        from xcookie.util_yaml import Yaml

        ci_extras = Yaml.loads(ci_extras)
    if not isinstance(ci_extras, Mapping):
        raise TypeError(f'ci_extras must be a mapping, got {type(ci_extras)!r}')
    return {str(key): _as_list(value) for key, value in ci_extras.items()}


def _as_commands(value: Any) -> tuple[str, ...]:
    if value is None:
        return tuple()
    if isinstance(value, str):
        return (value,)
    return tuple(str(item) for item in value)


def _validate_artifact_key(key: str) -> None:
    if not key:
        raise ValueError('ci_artifacts keys must be non-empty')
    if not (key[0].isalpha() or key[0] == '_'):
        raise ValueError(
            f'ci_artifacts key must start with a letter or underscore: {key!r}'
        )
    invalid = [c for c in key if not (c.isalnum() or c in {'_', '-'})]
    if invalid:
        raise ValueError(
            f'ci_artifacts key contains unsupported characters: {key!r}'
        )


def load_ci_artifacts(config: Mapping[str, Any]) -> tuple[CIArtifact, ...]:
    """Normalize project-owned artifact build declarations.

    The artifact build itself remains in the target repository. xcookie only
    renders the checkout/setup/build/upload plumbing and, for release artifacts,
    carries the produced files through signing and GitHub release creation.
    """
    raw = config.get('ci_artifacts')
    if not raw:
        return tuple()
    if isinstance(raw, str):
        from xcookie.util_yaml import Yaml

        raw = Yaml.loads(raw)
    if not isinstance(raw, Mapping):
        raise TypeError(f'ci_artifacts must be a mapping, got {type(raw)!r}')

    artifacts = []
    for key_, item in raw.items():
        key = str(key_)
        _validate_artifact_key(key)
        if not isinstance(item, Mapping):
            raise TypeError(
                f'ci_artifacts[{key!r}] must be a mapping, got {type(item)!r}'
            )

        build_commands = _as_commands(
            item.get('build_commands', item.get('build_command'))
        )
        artifact_paths = _as_commands(item.get('artifact_paths'))
        if not build_commands:
            raise ValueError(
                f'ci_artifacts[{key!r}] requires build_command/build_commands'
            )
        if not artifact_paths:
            raise ValueError(
                f'ci_artifacts[{key!r}] requires artifact_paths'
            )

        release_paths = _as_commands(item.get('release_paths'))
        release = bool(item.get('release', bool(release_paths)))
        if release and not release_paths:
            release_paths = artifact_paths

        python_version = item.get('python_version')
        if python_version is not None:
            python_version = str(python_version)

        artifacts.append(
            CIArtifact(
                key=key,
                name=str(
                    item.get(
                        'name',
                        key.replace('_', ' ').replace('-', ' ').title(),
                    )
                ),
                runner=str(item.get('runner', 'ubuntu-latest')),
                shell=str(item.get('shell', 'bash')),
                python_version=python_version,
                setup_commands=_as_commands(item.get('setup_commands')),
                build_commands=build_commands,
                post_build_commands=_as_commands(
                    item.get('post_build_commands')
                ),
                artifact_paths=artifact_paths,
                release_paths=release_paths,
                test=bool(item.get('test', True)),
                release=release,
            )
        )
    return tuple(artifacts)


def get_pyproject_optional_dependency_keys(self: Any) -> set[str]:
    """Return static and setuptools-dynamic optional dependency keys."""
    pyproj_config = self.config._load_pyproject_config() or {}
    project_block = pyproj_config.get('project', {}) or {}
    optional_deps = project_block.get('optional-dependencies', {}) or {}

    tool_block = pyproj_config.get('tool', {}) or {}
    setuptools_block = tool_block.get('setuptools', {}) or {}
    setuptools_dynamic = setuptools_block.get('dynamic', {}) or {}
    dynamic_optional_deps = (
        setuptools_dynamic.get('optional-dependencies', {}) or {}
    )

    return set(optional_deps.keys()) | set(dynamic_optional_deps.keys())


def filter_pyproject_extras(
    self: Any, desired_extras: Iterable[str]
) -> tuple[str, ...]:
    """Filter desired extras to those declared by the target pyproject."""
    pyproject_fpath = self.config['repodir'] / 'pyproject.toml'
    desired = _unique(str(extra) for extra in desired_extras)
    if not pyproject_fpath.exists():
        # New repo path: nothing to filter against, trust the desired list.
        return desired
    available = get_pyproject_optional_dependency_keys(self)
    return tuple(extra for extra in desired if extra in available)


def format_pyproject_install_target(
    extras: Iterable[str], target: str = '.', editable: bool = False
) -> str:
    """
    Build a pip install target, omitting brackets when extras are empty.
    """
    extras = _unique(extras)
    extras_part = ''
    if extras:
        extras_part = '[' + ','.join(extras) + ']'
    quoted = f'"{target}{extras_part}"'
    if editable:
        return f'-e {quoted}'
    return quoted


def _variant_parts(key: VariantKey) -> tuple[TestScope, DependencyMode]:
    scope_text, mode_text = key.split('-', 1)
    scope: TestScope = 'minimal' if scope_text == 'minimal' else 'full'
    mode: DependencyMode = 'strict' if mode_text == 'strict' else 'loose'
    return scope, mode


def _base_variant_extras(self: Any) -> dict[VariantKey, list[str]]:
    """Return desired extras for each variant before user overrides/filtering."""
    special_loose_tags: list[str] = []
    if 'cv2' in self.tags:
        special_loose_tags.append('headless')

    use_pyproject = uses_pyproject_dependency_mode(self)
    if use_pyproject:
        # In pyproject mode the optional dependency table is authoritative.
        # Reuse the normal extras for strict jobs and let uv's resolver decide
        # lowest/highest constraints instead of inventing '-strict' extras.
        special_strict_tags = list(special_loose_tags)
        return {
            'minimal-loose': ['tests'] + special_loose_tags,
            'full-loose': ['tests', 'optional'] + special_loose_tags,
            'minimal-strict': ['tests'] + special_strict_tags,
            'full-strict': ['tests', 'optional'] + special_strict_tags,
        }
    else:
        special_strict_tags = [tag + '-strict' for tag in special_loose_tags]
        return {
            'minimal-loose': ['tests'] + special_loose_tags,
            'full-loose': ['tests', 'optional'] + special_loose_tags,
            'minimal-strict': ['tests-strict', 'runtime-strict']
            + special_strict_tags,
            'full-strict': [
                'tests-strict',
                'runtime-strict',
                'optional-strict',
            ]
            + special_strict_tags,
        }


# Maps a user-facing ci_extras key to the variant keys it expands to.
# Expressed as a lookup table (rather than an if/elif chain with an
# ``in VARIANT_KEYS`` membership test) so type checkers do not need to
# narrow a plain ``str`` key to ``VariantKey`` — narrowing semantics for
# membership tests differ across checkers and versions.
_CI_EXTRAS_TARGETS: dict[str, tuple[VariantKey, ...]] = {
    'loose': ('minimal-loose', 'full-loose'),
    'strict': ('minimal-strict', 'full-strict'),
    **{key: (key,) for key in VARIANT_KEYS},
}


def _apply_ci_extras(
    variant_extras: dict[VariantKey, list[str]],
    ci_extras: Mapping[str, list[str]],
) -> None:
    """Apply user extras in-place to variant-specific desired extras."""
    for variant_key, extras_list in ci_extras.items():
        target_keys = _CI_EXTRAS_TARGETS.get(variant_key)
        if target_keys is None:
            continue
        for key in target_keys:
            variant_extras[key] = variant_extras[key] + list(extras_list)


def make_ci_plan(self: Any) -> CIPlan:
    """Build the provider-neutral CI plan for an xcookie applier."""
    variant_extras = _base_variant_extras(self)
    _apply_ci_extras(variant_extras, _load_ci_extras(self.config))

    use_pyproject = uses_pyproject_dependency_mode(self)
    if use_pyproject:
        variant_extras = {
            key: list(filter_pyproject_extras(self, extras))
            for key, extras in variant_extras.items()
        }

    variants: list[TestVariant] = []
    for key in VARIANT_KEYS:
        scope, dependency_mode = _variant_parts(key)
        variants.append(
            TestVariant(
                key=key,
                scope=scope,
                dependency_mode=dependency_mode,
                extras=_unique(variant_extras[key]),
            )
        )

    requested_variant_keys = tuple(self.config['test_variants'])
    requested_set = set(requested_variant_keys)
    active_variants = tuple(
        variant for variant in variants if variant.key in requested_set
    )

    if use_pyproject:
        configured_typecheck_extras = self.config.get(
            'typecheck_install_extras', ['tests']
        )
        desired_typecheck_extras = _as_list(configured_typecheck_extras)
        desired_sdist_extras = ['tests']
        if 'cv2' in self.tags:
            desired_sdist_extras.append('headless')
        if 'gdal' in self.tags:
            desired_sdist_extras.append('gdal')
        typecheck_extras = filter_pyproject_extras(
            self, desired_typecheck_extras
        )
        sdist_test_extras = filter_pyproject_extras(self, desired_sdist_extras)
    else:
        typecheck_extras = tuple()
        sdist_test_extras = tuple()

    workspace_members = load_workspace_members(self.config)
    validate_workspace_sync(self, workspace_members)

    return CIPlan(
        optional_dependency_keys=frozenset(
            get_pyproject_optional_dependency_keys(self)
        ),
        test_variants=tuple(variants),
        active_test_variants=active_variants,
        typecheck_extras=tuple(typecheck_extras),
        sdist_test_extras=tuple(sdist_test_extras),
        ci_artifacts=load_ci_artifacts(self.config),
        workspace_members=workspace_members,
    )
