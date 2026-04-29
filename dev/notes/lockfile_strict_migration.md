# Lockfile strict migration

This branch moves xcookie's strict dependency policy out of package metadata and
into generated lockfile profiles.

## Motivation

Historically xcookie generated extras such as `runtime-strict`, `tests-strict`,
and `optional-strict`.  Those extras were convenient for CI, but they had two
important drawbacks:

1. They were not standards-based lock artifacts.
2. They only pinned direct requirements by rewriting lower bounds; transitive
   dependencies were still resolved fresh.

Strict/minimum testing is an environment policy, not a public package extra.

## New model

Normal package metadata exposes normal extras only:

- `tests`
- `optional`
- `docs`
- domain-specific extras such as `headless`, `graphics`, `gdal`, or
  `postgresql`

Strict CI/dev profiles are generated as named lockfiles:

- `requirements/locks/pylock.ci-minimal-strict.toml`
- `requirements/locks/pylock.ci-full-strict.toml`
- `requirements/locks/pylock.ci-full-current.toml`

The strict profiles use uv's `lowest-direct` resolver mode.  That preserves the
old xcookie intent of testing direct lower bounds, but records the full
transitive environment in a standard `pylock.toml` artifact.

The generated lock helper includes optional platform requirement files when they
exist, currently:

- `requirements/headless.txt`
- `requirements/gdal.txt`
- `requirements/postgresql.txt`

## CI behavior

Existing strict CI rows may still set legacy-looking values such as:

```bash
INSTALL_EXTRAS="tests-strict,runtime-strict"
```

The shared install helper treats `*-strict` in `INSTALL_EXTRAS` as a lockfile
profile selector rather than as real package extras:

- `tests-strict,runtime-strict` -> `pylock.ci-minimal-strict.toml`
- `tests-strict,runtime-strict,optional-strict` -> `pylock.ci-full-strict.toml`

For strict jobs, CI now syncs the lockfile before installing the built artifact:

```bash
uv pip sync requirements/locks/pylock.ci-minimal-strict.toml
python -m pip install --no-deps "$WHEEL_FPATH"
python -m pip check
python -m pytest
```

The package under test is deliberately installed with `--no-deps` so its wheel
metadata cannot mutate the locked environment.

Loose jobs remain loose installs, e.g.:

```bash
python -m pip install "${WHEEL_FPATH}[tests,optional]"
python -m pytest
```

This keeps one CI lane useful for catching new upstream breakage while strict
lanes remain reproducible.

## Refreshing lockfiles

Run:

```bash
python dev/make_lockfiles.py
```

or refresh one profile:

```bash
python dev/make_lockfiles.py --profile ci-minimal-strict
```

Use `--dry` to print commands without executing them.

## Setup metadata

Generated `setup.py` metadata no longer publishes `*-strict` extras.  The setup
requirement parser also no longer has a strict/minimum mode; strictness belongs
to lockfiles.

## Binary / cibuildwheel templates

Generated cibuildwheel configuration no longer uses strict test extras. Binary
wheel testing uses normal test extras, while strict/minimum coverage is handled
by regular CI lockfile profiles.
