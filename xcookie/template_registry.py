from __future__ import annotations

import os
from collections.abc import Iterator, MutableMapping
from dataclasses import dataclass, field
from typing import Any, cast

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
    source: str = ''
    tags: frozenset[str] = field(default_factory=frozenset)
    perms: str = ''
    path_type: str = 'file'
    skip: bool = False
    stage_fpath: ub.Path | None = None
    repo_fpath: ub.Path | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    _field_names = frozenset({
        'fname', 'template', 'overwrite', 'enabled', 'input_fname', 'dynamic',
        'source', 'tags', 'perms', 'path_type', 'skip', 'stage_fpath',
        'repo_fpath',
    })

    @classmethod
    def coerce(cls, data: TemplateInfo | MutableMapping[str, Any]) -> TemplateInfo:
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

    def tag_requirements_met(self, active_tags: set[str] | frozenset[str]) -> bool:
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
        rel_mod_dpath = ub.Path(config['rel_mod_parent_dpath']) / config['mod_name']
        rel_mod_dpath_text = os.fspath(rel_mod_dpath)
        return cls(
            repo_name=str(config['repo_name']),
            mod_name=str(config['mod_name']),
            rel_mod_dpath=rel_mod_dpath_text,
            rel_mod_dpath_posix=rel_mod_dpath.as_posix(),
            author=str(config['author']),
            author_email=str(config['author_email']),
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
