from enum import Enum
from typing import Dict, List


class PrereleasePythonPolicy(str, Enum):
    """Policy for unreleased CPython interpreter jobs in test CI."""

    ALLOW_FAILURE = 'allow-failure'
    STRICT = 'strict'
    SKIP = 'skip'

    def __str__(self) -> str:
        return self.value


KNOWN_PYTHON_VERSIONS: List[str] = [
    '2.7',
    '3.4',
    '3.5',
    '3.6',
    '3.7',
    '3.8',
    '3.9',
    '3.10',
    '3.11',
    '3.12',
    '3.13',
    '3.14',
    '3.15',
]

DEV_PYTHON_VERSIONS: List[str] = [
    '3.15',
]

# The major.minor PyPy versions that have been released and that GitHub Actions
# / pypy.org currently distribute. PyPy tracks CPython compatibility, so each
# entry corresponds to the CPython language level that version implements.
# Update this as new PyPy releases land (e.g. pypy3.12).
# References:
# https://www.pypy.org/download.html
# https://github.com/actions/setup-python (supports pypy-3.x)
KNOWN_PYPY_VERSIONS: List[str] = [
    '3.9',
    '3.10',
    '3.11',
]


KNOWN_CPYTHON_DOCKER_IMAGES: Dict[str, str] = {
    'cp315': 'python:3.15-rc',
    'cp314': 'python:3.14',
    'cp313': 'python:3.13',
    'cp312': 'python:3.12',
    'cp311': 'python:3.11',
    'cp310': 'python:3.10',
    'cp39': 'python:3.9',
    'cp38': 'python:3.8',
    'cp37': 'python:3.7',
    'cp36': 'python:3.6',
}

# Github Actions supported versions
# https://github.com/actions/python-versions
# https://github.com/actions/python-versions/blob/main/versions-manifest.json

# TODO: make a table of details about each version
# https://devguide.python.org/versions/
KNOWN_PYTHON_VERSION_INFO: List[dict] = [
    {
        'version': '3.15',
        'end_of_life': '2031-10',
        'github_action_version': '3.15',
        'is_prerelease': True,
    },
    {
        'version': '3.14',
        'end_of_life': '2030-10',
        'github_action_version': '3.14',
        'is_prerelease': False,
    },
    {'version': '3.13', 'end_of_life': '2029-10'},
    {'version': '3.12', 'end_of_life': '2028-10'},
    {'version': '3.11', 'end_of_life': '2027-10'},
    {'version': '3.10', 'end_of_life': '2026-10'},
    {'version': '3.9', 'end_of_life': '2025-10'},
    {'version': '3.8', 'end_of_life': '2024-10'},
    {'version': '3.7', 'end_of_life': '2023-06-27'},
    {'version': '3.6', 'end_of_life': '2021-12-23'},
    {'version': '3.5', 'end_of_life': '2020-09-30'},
    {'version': '3.4', 'end_of_life': '2019-03-18'},
    {'version': '2.7', 'end_of_life': '2020-01-01'},
]


def is_prerelease_python_version(version: str) -> bool:
    """Return whether a configured CPython line is still a prerelease."""
    version_parts = str(version).split('.')
    version_key = '.'.join(version_parts[:2])
    for info in KNOWN_PYTHON_VERSION_INFO:
        if info['version'] == version_key:
            return bool(info.get('is_prerelease', False))
    return False
