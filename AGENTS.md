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
