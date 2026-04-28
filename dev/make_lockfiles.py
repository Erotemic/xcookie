#!/usr/bin/env python
"""
Refresh lockfiles for xcookie-style dependency profiles.

This intentionally treats lockfiles as environment artifacts, not package
metadata.  The normal requirements files remain the source of public package
requirements, while generated pylock files capture reproducible CI/dev test
environments.

CommandLine:
    python dev/make_lockfiles.py
    python dev/make_lockfiles.py --profile ci-minimal-strict
    python dev/make_lockfiles.py --dry
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess


REPO_DPATH = pathlib.Path(__file__).resolve().parents[1]
LOCK_DPATH = REPO_DPATH / 'requirements' / 'locks'

# Requirement files that historically participated in CI installs when their
# tags were enabled.  Profiles include only files that exist in the checkout, so
# this list is safe for projects without these optional dependency groups.
PLATFORM_REQUIREMENTS = [
    'requirements/headless.txt',
    'requirements/gdal.txt',
    'requirements/postgresql.txt',
]


PROFILES = {
    # Replacement for the old tests-strict,runtime-strict CI policy.
    # Direct requirements are resolved at their lower bounds, while the full
    # transitive environment is recorded in the lockfile.
    'ci-minimal-strict': {
        'requirements': [
            'requirements/runtime.txt',
            'requirements/tests.txt',
            *PLATFORM_REQUIREMENTS,
        ],
        'resolution': 'lowest-direct',
    },
    # Replacement for the old tests-strict,runtime-strict,optional-strict CI
    # policy.
    'ci-full-strict': {
        'requirements': [
            'requirements/runtime.txt',
            'requirements/tests.txt',
            'requirements/optional.txt',
            *PLATFORM_REQUIREMENTS,
        ],
        'resolution': 'lowest-direct',
    },
    # A reproducible snapshot of the normal loose/full test environment.
    'ci-full-current': {
        'requirements': [
            'requirements/runtime.txt',
            'requirements/tests.txt',
            'requirements/optional.txt',
            *PLATFORM_REQUIREMENTS,
        ],
        'resolution': None,
    },
}


def existing_requirement_files(paths):
    """Return profile inputs that exist in this checkout."""
    existing = []
    for rel in paths:
        fpath = REPO_DPATH / rel
        if fpath.exists():
            existing.append(rel)
    return existing


def make_compile_command(profile_name, profile):
    """Build the uv command used to generate a named pylock file."""
    output_fpath = LOCK_DPATH / f'pylock.{profile_name}.toml'
    req_fpaths = existing_requirement_files(profile['requirements'])
    if not req_fpaths:
        raise RuntimeError(f'Profile {profile_name!r} has no existing inputs')

    cmd = [
        'uv',
        'pip',
        'compile',
        '--universal',
        '--format',
        'pylock.toml',
        '--output-file',
        str(output_fpath),
    ]
    resolution = profile.get('resolution')
    if resolution:
        cmd += ['--resolution', resolution]
    cmd += req_fpaths
    return cmd


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--profile',
        action='append',
        choices=sorted(PROFILES),
        help='Profile to refresh. May be specified multiple times.',
    )
    parser.add_argument(
        '--dry',
        action='store_true',
        help='Print commands without running them.',
    )
    args = parser.parse_args(argv)

    profile_names = args.profile or sorted(PROFILES)
    LOCK_DPATH.mkdir(parents=True, exist_ok=True)

    for profile_name in profile_names:
        profile = PROFILES[profile_name]
        cmd = make_compile_command(profile_name, profile)
        print('+ ' + ' '.join(cmd))
        if not args.dry:
            subprocess.check_call(cmd, cwd=REPO_DPATH)


if __name__ == '__main__':
    main()
