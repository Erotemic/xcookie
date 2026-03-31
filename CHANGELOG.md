# Changelog

We are currently working on porting this changelog to the specifications in
[Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## Version 0.3.2 - Unreleased

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
