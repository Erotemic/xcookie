# Agent Guidelines for xcookie

This file applies to the entire repository.

## Project overview
- **Purpose:** `xcookie` generates and updates Python project boilerplate (CI workflows, packaging files, etc.) using CLI options defined in `xcookie/main.py`.
- **Key code areas:**
  - `xcookie/builders/` contains file generators for assets like `pyproject.toml`, `setup.py`, CI configs, and requirements files.
  - `xcookie/main.py` defines `XCookieConfig`, parses CLI flags, and orchestrates staging template outputs into target repositories.
  - `tests/` exercises generation logic; see `tests/test_pyproject_mode.py` for pyproject-only behavior.
- **Supporting docs:** The root `README.rst` explains CLI usage and expectations. The root `pyproject.toml` contains a commented WIP PEP 621 block that serves as an example of fully generated metadata.

## Development practices
- Install deps with `uv pip install -e .[all] -v` from the repo root.
- Run tests with `pytest -q -W ignore::DeprecationWarning -W ignore::PendingDeprecationWarning` unless a different command is requested.
- Avoid noisy recursive listings (`ls -R`, `grep -R`); prefer `rg` for searches.
- Keep changes focused; regeneration of template outputs should be deliberate and called out in commits/PRs if performed.

## PR expectations
- Include a concise summary of changes and the tests executed.
- Cite files and line numbers in summaries where feasible to help reviewers locate modifications.

## Release workflow invariants
- Before modifying GitHub release generation, read `docs/source/manual/release_workflow_design.rst`.
- The intended release trigger is `git push origin main:release`; maintainers do not manually create the release tag.
- The release commit is already expected to have passed review and CI on `main`. Do not add a full release-time test rerun or byte-identical artifact-promotion system unless explicitly requested.
- Live PyPI publication intentionally happens before the version tag is created. PyPI uploads are not repairable, whereas tags and GitHub releases are.
- After PyPI succeeds, create or verify `v$VERSION`, then associate the GitHub release with that exact tag. Never use the triggering release-branch ref as `tag_name`.
- Retries may reuse an existing version tag only when it points to the same release commit; never move an existing release tag automatically.
