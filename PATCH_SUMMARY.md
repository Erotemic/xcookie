# xcookie GitLab CI hardening overlay

This overlay fixes the PR #31 test failures and completes the pyproject-only deploy metadata path.

- Adds a ruamel.yaml merge-key compatibility helper for GitLab CI generation.
- Replaces all GitLab CI `add_yaml_merge([(0, ...)])` calls with the helper.
- Adds shared shell-safe static project-version helpers in `common_ci`.
- Uses the shared version helper from GitHub Actions release generation.
- Updates GitLab deploy/tag/artifact/release generation to avoid importing `setup.py` when `use_setup_py = false`.
- Adds regression tests for GitLab pyproject-only deploy output and current ruamel merge-key dumping.
