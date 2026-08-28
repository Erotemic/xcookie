from __future__ import annotations

import os
from collections.abc import Iterator, MutableMapping
from dataclasses import dataclass, field
from typing import Any, Callable, cast

import ubelt as ub


@dataclass
class TemplateInfo(MutableMapping[str, Any]):
    """Typed record describing one generated template output."""

    fname: str | os.PathLike[str]
    template: bool = False
    overwrite: bool = False
    enabled: bool = True
    input_fname: str | os.PathLike[str] | None = None
    dynamic: str = ''
    builder: Callable[[Any, 'TemplateInfo'], str | None] | None = None
    source: str = ''
    tags: frozenset[str] = field(default_factory=frozenset)
    perms: str = ''
    path_type: str = 'file'
    skip: bool = False
    stage_fpath: ub.Path | None = None
    repo_fpath: ub.Path | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    _field_names = frozenset(
        {
            'fname',
            'template',
            'overwrite',
            'enabled',
            'input_fname',
            'dynamic',
            'builder',
            'source',
            'tags',
            'perms',
            'path_type',
            'skip',
            'stage_fpath',
            'repo_fpath',
        }
    )

    @classmethod
    def coerce(
        cls, data: TemplateInfo | MutableMapping[str, Any]
    ) -> TemplateInfo:
        if isinstance(data, cls):
            return data
        known = {}
        extra = {}
        for key, value in data.items():
            if key == 'tags':
                value = _normalize_tags(value)
            elif key in {'template', 'overwrite', 'enabled', 'skip'}:
                value = _coerce_bool(value)
            if key in cls._field_names:
                known[key] = value
            else:
                extra[key] = value
        info = cls(**known)  # type: ignore
        info.extra.update(extra)
        return info

    def __getitem__(self, key: str) -> Any:
        if key in self._field_names:
            return getattr(self, key)
        return self.extra[key]

    def __setitem__(self, key: str, value: Any) -> None:
        if key == 'tags':
            value = _normalize_tags(value)
        elif key in {'template', 'overwrite', 'enabled', 'skip'}:
            value = _coerce_bool(value)
        if key in self._field_names:
            setattr(self, key, value)
        else:
            self.extra[key] = value

    def __delitem__(self, key: str) -> None:
        if key in self._field_names:
            raise KeyError(f'cannot delete TemplateInfo field {key!r}')
        del self.extra[key]

    def __iter__(self) -> Iterator[str]:
        yield from self._field_names
        yield from self.extra

    def __len__(self) -> int:
        return len(self._field_names) + len(self.extra)

    def keys(self):
        return self.to_dict().keys()

    def items(self):
        return self.to_dict().items()

    def values(self):
        return self.to_dict().values()

    def get(self, key: object, default: Any = None) -> Any:
        try:
            return self[cast(str, key)]
        except KeyError:
            return default

    def to_dict(self) -> dict[str, Any]:
        data = {key: getattr(self, key) for key in self._field_names}
        data.update(self.extra)
        return data

    def tag_requirements_met(
        self, active_tags: set[str] | frozenset[str]
    ) -> bool:
        return not self.tags or set(active_tags).issuperset(self.tags)


@dataclass(frozen=True)
class TemplateContext:
    """Replacement values for old-style xcookie template tokens."""

    repo_name: str
    mod_name: str
    rel_mod_dpath: str
    rel_mod_dpath_posix: str
    author: str
    author_email: str

    @classmethod
    def from_config(cls, config: Any) -> TemplateContext:
        from xcookie.util.util_metadata import metadata_text

        rel_mod_dpath = (
            ub.Path(config['rel_mod_parent_dpath']) / config['mod_name']
        )
        rel_mod_dpath_text = os.fspath(rel_mod_dpath)
        return cls(
            repo_name=str(config['repo_name']),
            mod_name=str(config['mod_name']),
            rel_mod_dpath=rel_mod_dpath_text,
            rel_mod_dpath_posix=rel_mod_dpath.as_posix(),
            # metadata_text flattens list-valued metadata to "A, B" text;
            # str() on a list would leak its Python repr into templates.
            author=metadata_text(config['author']),
            author_email=metadata_text(config['author_email']),
        )

    def replacements(self) -> dict[str, str]:
        return {
            'xcookie': self.repo_name,
            '<mod_name>': self.mod_name,
            '<rel_mod_dpath>': self.rel_mod_dpath_posix,
            '<AUTHOR>': self.author,
            '<AUTHOR_EMAIL>': self.author_email,
        }


def coerce_template_infos(
    infos: list[MutableMapping[str, Any] | TemplateInfo],
) -> list[TemplateInfo]:
    """Normalize raw registry dictionaries into typed template records."""
    return [TemplateInfo.coerce(info) for info in infos]


def _coerce_bool(value: Any) -> bool:
    """Coerce common TOML/CLI bool-like values without string truth traps.

    ``auto`` is a historical xcookie sentinel used by several config values.
    Template registry booleans previously used ``bool(value)``, so ``auto``
    behaved as enabled/true. Preserve that behavior explicitly while still
    rejecting genuinely ambiguous strings such as ``sometimes``.
    """
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {'1', 'true', 'yes', 'y', 'on', 'auto'}:
            return True
        if lowered in {'0', 'false', 'no', 'n', 'off', 'none', 'null', ''}:
            return False
        raise ValueError(f'Cannot coerce {value!r} to bool')
    return bool(value)


def _normalize_tags(value: Any) -> frozenset[str]:
    if value is None or value == '':
        return frozenset()
    if isinstance(value, str):
        value = value.split(',')
    tags: list[str] = []
    for item in value:
        tags.extend(part.strip() for part in str(item).split(','))
    return frozenset(tag for tag in tags if tag)


def build_template_registry(applier: Any) -> list[TemplateInfo]:
    """Build the active template inventory for a configured applier."""
    from xcookie import rc
    from xcookie.builders import ci_plan
    from xcookie.builders.basic import (
        build_changelog,
        build_package_init,
        build_requirement_metadata,
        build_test_import,
    )

    rel_mod_dpath = applier.rel_mod_dpath

    raw_template_infos: list[TemplateInfo | MutableMapping[str, Any]] = [
        # {'template': 1, 'overwrite': False, 'fname': '.circleci/config.yml'},
        # {'template': 1, 'overwrite': False, 'fname': '.travis.yml'},
        {
            'template': 0,
            'overwrite': 1,
            'fname': 'dev/setup_secrets.sh',
            'enabled': applier.config['enable_gpg'],
            'input_fname': rc.resource_fpath('setup_secrets.sh.in'),
        },
        {
            'template': 0,
            'overwrite': 0,
            'fname': '.gitignore',
            'input_fname': rc.resource_fpath('gitignore.in'),
        },
        # {'template': 1, 'overwrite': 1, 'fname': '.coveragerc'},
        {
            'template': 1,
            'overwrite': 1,
            'fname': '.readthedocs.yml',
            'dynamic': 'build_readthedocs',
        },
        # {'template': 0, 'overwrite': 1, 'fname': 'pytest.ini'},
        {
            'template': 0,
            'overwrite': 0,
            'fname': 'pyproject.toml',
            'dynamic': 'build_pyproject',
        },
        {
            'template': 1,
            'overwrite': 0,
            'fname': 'setup.py',
            # 'input_fname': rc.resource_fpath('setup.py.in'),
            'dynamic': 'build_setup',
            'enabled': applier.config['use_setup_py'],
            'perms': 'x',
        },
        {
            'template': 0,
            'overwrite': 0,
            'fname': 'docs/source/index.rst',
            'dynamic': 'build_docs_index',
        },
        {
            'template': 0,
            'overwrite': 0,
            'fname': 'README.rst',
            'dynamic': 'build_readme',
        },
        #
        {'builder': build_changelog, 'overwrite': 0, 'fname': 'CHANGELOG.md'},
        {
            'builder': build_package_init,
            'overwrite': 0,
            'fname': rel_mod_dpath / '__init__.py',
        },
        {
            'builder': build_test_import,
            'overwrite': 0,
            'fname': 'tests/test_import.py',
        },
        {
            'template': 0,
            'overwrite': 1,
            'fname': '.github/dependabot.yml',
            'tags': 'github',
            'input_fname': rc.resource_fpath('dependabot.yml.in'),
        },
        # {'template': 0, 'overwrite': 1,
        #  'tags': 'binpy,github',
        #  'fname': '.github/workflows/test_binaries.yml',
        #  'input_fname': rc.resource_fpath('test_binaries.yml.in')},
        {
            'template': 1,
            'overwrite': 1,
            'tags': 'github',
            'fname': '.github/workflows/tests.yml',
            'dynamic': 'build_github_actions_tests',
        },
        {
            'template': 1,
            'overwrite': 1,
            'tags': 'github',
            'fname': '.github/workflows/release.yml',
            'dynamic': 'build_github_actions_release',
        },
        {
            'template': 0,
            'overwrite': 1,
            'fname': '.gitlab-ci.yml',
            'tags': 'gitlab,purepy',
            # 'input_fname': rc.resource_fpath('gitlab-ci.purepy.yml.in')
            'dynamic': 'build_gitlab_ci',
        },
        {
            'template': 0,
            'overwrite': 1,
            'fname': '.gitlab-ci.yml',
            'tags': 'gitlab,binpy',
            'dynamic': 'build_gitlab_ci',
        },
        # {'template': 1, 'overwrite': False, 'fname': 'appveyor.yml'},
        {
            'template': 1,
            'overwrite': 0,
            'fname': 'CMakeLists.txt',
            'tags': 'binpy',
            'input_fname': rc.resource_fpath('CMakeLists.txt.in'),
        },
        # {'template': 0, 'overwrite': 1, 'fname': 'dev/make_strict_req.sh', 'perms': 'x'},
        {
            'template': 0,
            'overwrite': 1,
            'fname': 'requirements.txt',
            'enabled': not applier.config['use_pyproject_requirements'],
            'dynamic': 'build_requirements_txt',
        },
        {
            'template': 1,
            'overwrite': 1,
            'fname': 'requirements/graphics.txt',
            'tags': 'cv2',
            'enabled': not applier.config['use_pyproject_requirements'],
            'dynamic': 'build_cv2_graphics_requirements_txt',
        },
        {
            'template': 1,
            'overwrite': 1,
            'fname': 'requirements/headless.txt',
            'tags': 'cv2',
            'enabled': not applier.config['use_pyproject_requirements'],
            'dynamic': 'build_cv2_headless_requirements_txt',
        },
        {
            'template': 1,
            'overwrite': 1,
            'fname': 'requirements/gdal.txt',
            'tags': 'gdal',
            'enabled': not applier.config['use_pyproject_requirements'],
            'dynamic': 'build_gdal_requirements_txt',
        },
        {
            'template': 0,
            'overwrite': 0,
            'fname': 'requirements/optional.txt',
            'enabled': not applier.config['use_pyproject_requirements'],
            'dynamic': 'build_optional_requirements',
        },
        {
            'template': 0,
            'overwrite': 0,
            'fname': 'requirements/runtime.txt',
            'enabled': not applier.config['use_pyproject_requirements'],
            'dynamic': 'build_runtime_requirements',
        },
        {
            'template': 0,
            'overwrite': 0,
            'fname': 'requirements/tests.txt',
            'enabled': not applier.config['use_pyproject_requirements'],
            'dynamic': 'build_tests_requirements',
        },
        {
            'template': 0,
            'overwrite': 0,
            'fname': 'requirements/docs.txt',
            'enabled': not applier.config['use_pyproject_requirements'],
            'dynamic': 'build_docs_requirements',
        },
        {
            'template': 1,
            'overwrite': 1,
            'fname': 'docs/source/conf.py',
            'dynamic': 'build_docs_conf',
        },
        {
            'template': 1,
            'overwrite': 1,
            'fname': 'docs/Makefile',
            'input_fname': rc.resource_fpath('docs_makefile.in'),
        },
        {
            'template': 1,
            'overwrite': 1,
            'fname': 'docs/make.bat',
            'input_fname': rc.resource_fpath('docs_make.bat.in'),
        },
        # {'template': 0, 'overwrite': 0, 'fname': 'docs/source/_static', 'path_type': 'dir'},
        # {'template': 0, 'overwrite': 0, 'fname': 'docs/source/_templates', 'path_type': 'dir'},
        {
            'template': 0,
            'overwrite': 1,
            'fname': 'publish.sh',
            'perms': 'x',
            'input_fname': rc.resource_fpath('publish.sh.in'),
        },
        {
            'template': 1,
            'overwrite': 1,
            'fname': 'build_wheels.sh',
            'perms': 'x',
            'tags': 'binpy',
        },
        {
            'template': 1,
            'overwrite': 1,
            'fname': 'run_doctests.sh',
            'perms': 'x',
            'dynamic': 'build_run_doctests',
        },  # TODO: template with xdoctest-style
        {
            'template': 0,
            'overwrite': 0,
            'fname': 'run_linter.sh',
            'perms': 'x',
            'dynamic': 'build_run_linter',
        },
        {
            # Helper that re-exports requirements/locks/*.txt from uv.lock
            # for every strict CI variant. Only meaningful when the project
            # uses pyproject + uv (lockfile-driven CI); skipped otherwise.
            'template': 0,
            'overwrite': 1,
            'fname': 'dev/refresh_locks.sh',
            'perms': 'x',
            'enabled': ci_plan.uses_lockfile_ci(applier),
            'dynamic': 'build_refresh_locks_sh',
        },
        # TODO: template a clean script
        {
            'template': 1,
            'overwrite': 0,
            'fname': 'run_tests.py',
            'perms': 'x',
            'tags': 'binpy',
            'input_fname': rc.resource_fpath('run_tests.binpy.py.in'),
        },
        {
            'template': 1,
            'overwrite': 0,
            'fname': 'run_tests.py',
            'perms': 'x',
            'tags': 'purepy',
            'input_fname': rc.resource_fpath('run_tests.purepy.py.in'),
        },
    ]

    # Dynamic PEP 621 dependency metadata cannot directly consume pip
    # directives such as ``-r`` or index-selection options. Preserve
    # installer-facing files and stage metadata-only companions only when
    # a user-managed requirements file actually needs one.
    if (
        not applier.config['use_pyproject_requirements']
        and not applier.config['use_setup_py']
    ):
        from xcookie.builders.pyproject import (
            _requirement_file_needs_metadata_copy,
        )

        requirements_dpath = applier.repodir / 'requirements'
        if requirements_dpath.exists():
            known_fnames = {
                os.fspath(info.get('fname', '')) for info in raw_template_infos
            }
            for req_fpath in sorted(requirements_dpath.glob('*.txt')):
                if req_fpath.stem.endswith('-metadata'):
                    continue
                if req_fpath.name == 'gdal.txt' and 'gdal' in applier.tags:
                    # The staged GDAL file is generated metadata-safe; its
                    # custom wheel index remains CI installer policy.
                    continue
                if _requirement_file_needs_metadata_copy(req_fpath):
                    metadata_relpath = ub.Path('requirements') / (
                        req_fpath.stem + '-metadata.txt'
                    )
                    if os.fspath(metadata_relpath) not in known_fnames:
                        raw_template_infos.append(
                            {
                                'builder': build_requirement_metadata,
                                'overwrite': 1,
                                'fname': metadata_relpath,
                            }
                        )
                        known_fnames.add(os.fspath(metadata_relpath))

    template_infos = coerce_template_infos(raw_template_infos)

    # The user specified some files to not overwrite by default
    skip_autogen = {
        os.fspath(p) for p in (applier.config['skip_autogen'] or [])
    }
    if skip_autogen:
        for item in template_infos:
            if os.fspath(item.fname) in skip_autogen:
                item.overwrite = False
                item.skip = True

    return template_infos
