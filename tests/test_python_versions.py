from xcookie.constants import is_prerelease_python_version


def test_python_315_is_prerelease():
    assert is_prerelease_python_version('3.15')
    assert is_prerelease_python_version('3.15.0-beta.4')
    assert not is_prerelease_python_version('3.14')
    assert not is_prerelease_python_version('999.0')
