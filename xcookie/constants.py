from typing import List, Dict

KNOWN_PYTHON_VERSIONS: List[str]  = [
    '2.7', '3.4', '3.5', '3.6', '3.7', '3.8', '3.9', '3.10', '3.11', '3.12',
    '3.13',
    '3.14'
]

DEV_PYTHON_VERSIONS: List[str] = [
    # '3.13',
    '3.14',
]


KNOWN_CPYTHON_DOCKER_IMAGES: Dict[str, str]  = {
    # TODO allow rc?
    'cp314': 'python:3.14-rc',
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
KNOWN_PYTHON_VERSION_INFO: List[dict]  = [
    {'version': '3.14', 'end_of_life': '2030-10', 'github_action_version': '3.14.0-rc.1', 'is_prerelease': True},
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
