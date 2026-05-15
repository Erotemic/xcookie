"""
Provider-neutral CI planning helpers.

The GitHub Actions and GitLab CI renderers should share decisions about which
extras, variants, and install targets are valid.  This module keeps that policy
in one place while the provider-specific modules remain responsible for YAML
shape and provider syntax.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Literal, Mapping, cast

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
    def uv_resolution(self) -> str:
        """Resolution policy used when pyproject/uv installs are enabled."""
        if self.is_strict:
            return 'lowest-direct'
        return 'highest'


@dataclass(frozen=True)
class CIPlan:
    """Provider-neutral CI decisions shared by GitHub and GitLab renderers."""

    optional_dependency_keys: frozenset[str]
    test_variants: tuple[TestVariant, ...]
    active_test_variants: tuple[TestVariant, ...]
    typecheck_extras: tuple[str, ...]
    sdist_test_extras: tuple[str, ...]

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

    use_pyproject = bool(self.config['use_pyproject_requirements'])
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


def _apply_ci_extras(
    variant_extras: dict[VariantKey, list[str]], ci_extras: Mapping[str, list[str]]
) -> None:
    """Apply user extras in-place to variant-specific desired extras."""
    for variant_key, extras_list in ci_extras.items():
        if variant_key == 'loose':
            target_keys: tuple[VariantKey, ...] = ('minimal-loose', 'full-loose')
        elif variant_key == 'strict':
            target_keys = ('minimal-strict', 'full-strict')
        elif variant_key in VARIANT_KEYS:
            target_keys = (cast(VariantKey, variant_key),)
        else:
            continue
        for key in target_keys:
            variant_extras[key] = variant_extras[key] + list(extras_list)


def make_ci_plan(self: Any) -> CIPlan:
    """Build the provider-neutral CI plan for an xcookie applier."""
    variant_extras = _base_variant_extras(self)
    _apply_ci_extras(variant_extras, _load_ci_extras(self.config))

    if self.config['use_pyproject_requirements']:
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

    if self.config['use_pyproject_requirements']:
        desired_typecheck_extras = ['tests']
        desired_sdist_extras = ['tests']
        if 'cv2' in self.tags:
            desired_sdist_extras.append('headless')
        if 'gdal' in self.tags:
            desired_sdist_extras.append('gdal')
        typecheck_extras = filter_pyproject_extras(
            self, desired_typecheck_extras
        )
        sdist_test_extras = filter_pyproject_extras(
            self, desired_sdist_extras
        )
    else:
        typecheck_extras = tuple()
        sdist_test_extras = tuple()

    return CIPlan(
        optional_dependency_keys=frozenset(
            get_pyproject_optional_dependency_keys(self)
        ),
        test_variants=tuple(variants),
        active_test_variants=active_variants,
        typecheck_extras=tuple(typecheck_extras),
        sdist_test_extras=tuple(sdist_test_extras),
    )
