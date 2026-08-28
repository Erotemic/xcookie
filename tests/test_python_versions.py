from xcookie.constants import is_prerelease_python_version


def test_python_315_is_prerelease():
    assert is_prerelease_python_version('3.15')
    assert is_prerelease_python_version('3.15.0-beta.4')
    assert not is_prerelease_python_version('3.14')
    assert not is_prerelease_python_version('999.0')


def test_cv2_requirements_do_not_emit_empty_python_interval(tmp_path):
    from xcookie.main import TemplateApplier, XCookieConfig

    repodir = tmp_path / 'demo'
    repodir.mkdir()
    config = XCookieConfig(
        repodir=repodir,
        mod_name='demo_mod',
        repo_name='demo_mod',
        tags=['github', 'purepy', 'cv2'],
        min_python='3.10',
        max_python='3.15',
        interactive=False,
        init_new_remotes=False,
        use_vcs=False,
    )
    applier = TemplateApplier(config)
    text = applier.build_cv2_graphics_requirements_txt()

    assert "python_version < '3.10' and python_version >= '3.10'" not in text
    expected = (
        "opencv-python>=4.5.4.58 ; "
        "python_version < '3.11' and python_version >= '3.10'"
    )
    assert expected in text
