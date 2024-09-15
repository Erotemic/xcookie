KNOWN_PYTHON_VERSIONS = [
    '2.7', '3.4', '3.5', '3.6', '3.7', '3.8', '3.9', '3.10', '3.11', '3.12',
    # '3.13',
]

DEV_PYTHON_VERSIONS = [
    '3.13',
]


KNOWN_CPYTHON_DOCKER_IMAGES = {
    # TODO allow rc?
    # 'cp313': 'python:3.13.0rc2',
    'cp312': 'python:3.12',
    'cp311': 'python:3.11',
    'cp310': 'python:3.10',
    'cp39': 'python:3.9',
    'cp38': 'python:3.8',
    'cp37': 'python:3.7',
    'cp36': 'python:3.6',
}
