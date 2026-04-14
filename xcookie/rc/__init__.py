from importlib import resources as importlib_resources


def resource_fpath(fname):
    """
    Example:
        >>> from xcookie.rc import *  # NOQA
        >>> fname = 'setup.py.in'
        >>> fpath = resource_fpath(fname)
        >>> assert fpath.name == fname
        >>> assert fpath.exists()
    """
    # https://importlib-resources.readthedocs.io/en/latest/using.html#migrating-from-legacy
    import ubelt as ub

    try:
        rc_dpath = ub.Path(importlib_resources.files('xcookie.rc'))  # type: ignore
    except Exception:
        # FIXME: does this work on < 3.9?
        modpath = ub.modname_to_modpath('xcookie.rc')
        assert modpath is not None
        rc_dpath = ub.Path(modpath).absolute()
    fpath = rc_dpath / fname
    return fpath
