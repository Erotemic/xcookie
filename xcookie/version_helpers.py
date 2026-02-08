from packaging.specifiers import SpecifierSet
from packaging.version import Version


def parse_minimum_python_version(requires_python: str) -> str | None:
    """
    Given a requires-python string (e.g., '>=3.7,<4'),
    return the minimum version as a string (e.g., '3.7').
    Returns None if no lower bound is found.

    Examples:
        print(get_minimum_python_version(">=3.7,<4"))       # '3.7'
        print(get_minimum_python_version(">3.8,<=3.10"))    # '3.8.1'
        print(get_minimum_python_version("==3.9.*"))        # '3.9'
        print(get_minimum_python_version("<3.6"))           # None

    """
    spec_set = SpecifierSet(requires_python)
    min_version = None

    for spec in spec_set:
        if spec.operator in ('>=', '>', '=='):
            v = Version(spec.version)
            # If ">" is used, bump by a patch so it's valid
            if spec.operator == '>':
                v = Version(f'{v.major}.{v.minor}.{v.micro + 1}')
            if min_version is None or v < min_version:
                min_version = v

    return str(min_version) if min_version else None
