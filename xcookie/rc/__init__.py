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
        rc_dpath = ub.Path(importlib_resources.files('xcookie.rc'))
    except Exception:
        # FIXME: does this work on < 3.9?
        rc_dpath = ub.Path(ub.modname_to_modpath('xcookie.rc')).absolute()
    fpath = rc_dpath / fname
    return fpath
