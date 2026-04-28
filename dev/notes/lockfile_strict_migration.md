# Lockfile strict migration

This branch starts moving xcookie's strict dependency policy out of package
metadata and into generated lockfile profiles.

## Motivation

Historically xcookie generated extras such as `runtime-strict`, `tests-strict`,
and `optional-strict`.  Those extras were convenient for CI, but they had two
important drawbacks:

1. They were not standards-based lock artifacts.
2. They only pinned direct requirements by rewriting lower bounds; transitive
   dependencies were still resolved fresh.

Strict/minimum testing is an environment policy, not a public package extra.

## New model

Normal package metadata should expose normal extras only:

- `tests`
- `optional`
- `docs`
- domain-specific extras such as `headless`, `graphics`, or `postgresql`

Strict CI/dev profiles should be generated as named lockfiles:

- `requirements/locks/pylock.ci-minimal-strict.toml`
- `requirements/locks/pylock.ci-full-strict.toml`
- `requirements/locks/pylock.ci-full-current.toml`

The strict profiles use uv's `lowest-direct` resolver mode.  That preserves the
old xcookie intent of testing direct lower bounds, but records the full
transitive environment in a standard `pylock.toml` artifact.

## Intended CI shape

For strict jobs, sync the lockfile before installing the built artifact:

```bash
uv pip sync requirements/locks/pylock.ci-minimal-strict.toml
python -m pip install --no-deps "$WHEEL_FPATH"
python -m pip check
python -m pytest
```

The package under test is deliberately installed with `--no-deps` so its wheel
metadata cannot mutate the locked environment.

Loose jobs should remain loose installs, e.g.:

```bash
python -m pip install "${WHEEL_FPATH}[tests,optional]"
python -m pytest
```

This keeps one CI lane useful for catching new upstream breakage while strict
lanes remain reproducible.

## Follow-up work

- Remove generated `*-strict` extras from `setup.py` templates and builders.
- Change GitHub/GitLab strict CI rows from `INSTALL_EXTRAS=...-strict` to a
  `LOCKFILE=...` install mode.
- Prefer `use_setup_py=false` for pure-Python projects once strict extras are no
  longer needed from `setup.py`.
- Handle binary/cibuildwheel templates separately, likely by syncing the strict
  lockfile in the test environment instead of using `test-extras`.
