# Changelog

We are currently working on porting this changelog to the specifications in
[Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## Version 0.4.0 - Unreleased

### Changed
* Migrated `XCookieConfig` from scriptconfig to kwconf. CLI behavior is
  unchanged (fuzzy hyphens, flags, aliases, autocomplete); kwconf only applies
  string parsers to CLI/env input, so list-valued TOML metadata such as
  multi-author `tool.xcookie.author` now survives config loading intact.

### Fixed
* Multi-author repos no longer generate a syntactically invalid `docs/conf.py`
  (and mangled PEP 621 author entries): list-valued author metadata was being
  flattened to its Python repr by the resolved-config round trip and template
  renderers.

### Added
* Added a structured `PatchPlan` staging model with explicit copy, permission, and directory tasks.
* Added tests for staging-plan classification, selective application, search-style generation filters, and template boolean coercion.
* Added `KNOWN_PYPY_VERSIONS` constant enumerating the released PyPy interpreters.
* Restored the legacy `all` convenience extra in pure-pyproject mode so users
  can run `pip install pkg[all]`. It aggregates the runtime-optional extras via
  a multi-file dynamic `optional-dependencies` entry and excludes development
  extras (`tests`, `docs`, `linting`). The loose/strict split remains handled by
  lock-file constraints in CI, so there is intentionally no `all-strict`.

### Fixed
* The generated `pyproject.toml` now keeps a trailing newline and re-emits the
  `[tool.uv] exclude-newer` supply-chain comment that `toml.dumps` would
  otherwise strip.

### Changed
* The default `[tool.uv] exclude-newer` supply-chain guard is now a relative
  `P7D` window (ignore packages published in the last 7 days) instead of a
  hard-coded current date, so the value no longer goes stale. Existing values
  on disk are still preserved, and `uv_exclude_newer=False` disables the guard.
* Auto-selection of `ci_pypy_versions` now locks onto the supported python range
  instead of hardcoding PyPy 3.9. Purepy repos test on the most recent released
  PyPy compatible with the supported python versions (e.g. a `python >= 3.10`
  project now uses PyPy 3.11), and emit no PyPy job when no released PyPy is
  compatible. Explicit `ci_pypy_versions` outside the supported range now warn.
* Refactored staged-file gathering so it returns a side-effect-light plan instead of a pair of nested dictionaries.
* Moved patch-plan rendering and generation-filter matching into testable helper code.
* Cleaned up generated Sphinx configuration defaults to avoid stale theme path, source suffix, static path, and unsupported theme-option warnings.
* Stopped placing both `auto/{mod_name}` and `auto/modules` in the generated docs index to avoid duplicate toctree entries.
* Hardened `TemplateInfo` boolean coercion so strings like `"false"` no longer behave as truthy values.


## Version 0.3.3 - Released 2026-04-12


## Version 0.3.2 - Released 2026-04-09

### Added
* New `ci_extras` configuration option in `pyproject.toml` to specify extra CI test dependencies.
  Supports keys: `loose`, `strict`, `minimal-loose`, `full-loose`, `minimal-strict`, `full-strict`.
  Values are lists of extra package names to add to the corresponding test variant.
  Example: `ci_extras = 'full-loose: [tests-binary]'`

### Changed
* working towards pure pyproject.toml support
* Using ruff as the backend formatter now

## Version 0.3.1 - Released 2025-08-04

### Changed

* Prerelease versions are no longer considered as "max" versions.


## [Version 0.3.0] - 

### Added

* Lots more undocumented stuff while working on making this generally useful

## [Version 0.2.0] - Release 2023-06-23

### Added
* so much stuff

## [Version 0.1.0] - Release 2022-06-14

### Added
* Initial version
