The xcookie Module
==================

|GithubActions| |ReadTheDocs| |Pypi| |Downloads| |Codecov|


The ``xcookie`` module. A helper for templating python projects.


+------------------+----------------------------------------------+
| Read the docs    | https://xcookie.readthedocs.io               |
+------------------+----------------------------------------------+
| Github           | https://github.com/Erotemic/xcookie          |
+------------------+----------------------------------------------+
| Pypi             | https://pypi.org/project/xcookie             |
+------------------+----------------------------------------------+

The goal is to be able to setup and update Python project structures with consistent
boilerplate for things like CI, ``setup.py``, and requirements.

It handles:

* Multiple version control remotes:

  + Github

  + Gitlab

* pure python packages

* python packages with scikit-build binary extensions

* rotating secrets

* CI scripts for github or gitlab where the general pattern is:

  + Lint the project

  + Build the pure python or binary wheels

  + Test the wheels in the supported environments (i.e. different operating systems / versions of Python)

  + Optionally sign the wheels with online GPG keys

  + Upload the wheels to test pypi or live pypi.

This is primarily driven by the needs of my projects and thus has some logic
that is specific to things I'm doing. However, these are all generally behind
checks for the "erotemic" tag. I am working on slowly making this into a proper
CLI that is externally usable.


The top level CLI is:


.. code::

    positional arguments:
      repodir               path to the new or existing repo

    options:
      -h, --help            show this help message and exit
      --repodir REPODIR     path to the new or existing repo (default: .)
      --repo_name REPO_NAME
                            defaults to ``repodir.name`` (default: None)
      --mod_name MOD_NAME   The name of the importable Python module. defaults to ``repo_name`` (default: None)
      --pkg_name PKG_NAME   The name of the installable Python package. defaults to ``mod_name`` (default: None)
      --rel_mod_parent_dpath REL_MOD_PARENT_DPATH
                            The location of the module directory relative to the repository root. This defaults to simply placing the module in
                            ".", but another common pattern is to specify this as "./src". (default: .)
      --rotate_secrets [ROTATE_SECRETS], --no-rotate_secrets
                            If True will execute secret rotation (default: auto)
      --refresh_docs [REFRESH_DOCS], --no-refresh_docs
                            If True will refresh the docs (default: auto)
      --os OS               all or any of win,osx,linux (default: all)
      --is_new IS_NEW       If the repo is detected or specified as being new, then steps to create a project for the repo on github/gitlab and
                            other initialization procedures will be executed. Otherwise we assume that we are updating an existing repo. (default:
                            auto)
      --min_python MIN_PYTHON
      --typed TYPED         Should be None, False, True, partial or full (default: None)
      --supported_python_versions SUPPORTED_PYTHON_VERSIONS
                            can specify as a list of explicit major.minor versions. Auto will use everything above the min_python version (default:
                            auto)
      --ci_cpython_versions CI_CPYTHON_VERSIONS
                            Specify the major.minor CPython versions to use on the CI. Will default to the supported_python_versions. E.g. ["3.7",
                            "3.10"] (default: auto)
      --ci_pypy_versions CI_PYPY_VERSIONS
                            Specify the major.minor PyPy versions to use on the CI. Defaults will depend on purepy vs binpy tags. (default: auto)
      --ci_versions_minimal_strict CI_VERSIONS_MINIMAL_STRICT
                            todo: sus out (default: min)
      --ci_versions_full_strict CI_VERSIONS_FULL_STRICT
      --ci_versions_minimal_loose CI_VERSIONS_MINIMAL_LOOSE
      --ci_versions_full_loose CI_VERSIONS_FULL_LOOSE
      --remote_host REMOTE_HOST
                            if unspecified, attempt to infer from tags (default: None)
      --remote_group REMOTE_GROUP
                            if unspecified, attempt to infer from tags (default: None)
      --autostage AUTOSTAGE
                            if true, automatically add changes to version control (default: False)
      --visibility VISIBILITY
                            or private. Does limit what we can do (default: public)
      --version VERSION     repo metadata: url for the project (default: None)
      --url URL             repo metadata: url for the project (default: None)
      --author AUTHOR       repo metadata: author for the project (default: None)
      --author_email AUTHOR_EMAIL
                            repo metadata (default: None)
      --description DESCRIPTION
                            repo metadata (default: None)
      --license LICENSE     repo metadata (default: None)
      --dev_status DEV_STATUS
      --enable_gpg ENABLE_GPG
      --defaultbranch DEFAULTBRANCH
      --xdoctest_style XDOCTEST_STYLE
                            type of xdoctest style (default: google)
      --ci_pypi_live_password_varname CI_PYPI_LIVE_PASSWORD_VARNAME
                            variable of the live twine password in your secrets (default: TWINE_PASSWORD)
      --ci_pypi_test_password_varname CI_PYPI_TEST_PASSWORD_VARNAME
                            variable of the test twine password in your secrets (default: TEST_TWINE_PASSWORD)
      --regen REGEN         if specified, any modified template file that matches this pattern will be considered for re-write (default: None)
      --tags [TAGS ...]     Tags modify what parts of the template are used. Valid tags are: "binpy" - do we build binpy wheels? "erotemic" - this
                            is an erotemic repo "kitware" - this is an kitware repo "pyutils" - this is an pyutils repo "purepy" - this is a pure
                            python repo "gdal" - add in our gdal hack # TODO "cv2" - enable the headless hack "notypes" - disable mypy in lint
                            checks (default: auto)
      --interactive INTERACTIVE
      --yes YES             Say yes to everything (default: False)
      --linter LINTER       if true enables lint checks in CI (default: True)



Invocations to create a new github repo:

.. code:: bash

    # Create a new python repo
    python -m xcookie.main --repo_name=cookiecutter_purepy --repodir=$HOME/code/cookiecutter_purepy --tags="github,purepy"

    # Create a new binary repo
    python -m xcookie.main --repo_name=cookiecutter_binpy --repodir=$HOME/code/cookiecutter_binpy --tags="github,binpy,gdal"


Given an initalized repository the general usage pattern is to edit the
generated ``pyproject.toml`` and modify values in the ``[tool.xcookie]``
section and then rerun ``xcookie`` in that directory. It will then present you
with a diff of the proposed changes that you can reject, accept entirely, or
accept selectively.

For some files where the user is likely to do custom work, xcookie won't try to
overwrite the file unless you tell it to regenerate it.  The ``setup.py`` is
the main example of this, so if you want xcookie to update your setup.py you
would run ``xcookie --regen setup.py``

For rotating secrets, the interface is a bit weird. I haven't gotten it to work
within an xcookie invocation due to the interactive nature of some of the
secret tools, but if you run ``xcookie --rotate-secrets``, when it ask you
``"Ready to rotate secrets?"``, say no, and it will list the commands that it
would have run. So you can just copy / paste those manually. I hope to make
this easier in the future.

.. |CircleCI| image:: https://circleci.com/gh/Erotemic/xcookie.svg?style=svg
    :target: https://circleci.com/gh/Erotemic/xcookie

.. |Appveyor| image:: https://ci.appveyor.com/api/projects/status/github/Erotemic/xcookie?branch=main&svg=True
   :target: https://ci.appveyor.com/project/Erotemic/xcookie/branch/main

.. |Codecov| image:: https://codecov.io/github/Erotemic/xcookie/badge.svg?branch=main&service=github
   :target: https://codecov.io/github/Erotemic/xcookie?branch=main

.. |Pypi| image:: https://img.shields.io/pypi/v/xcookie.svg
   :target: https://pypi.python.org/pypi/xcookie

.. |Downloads| image:: https://img.shields.io/pypi/dm/xcookie.svg
   :target: https://pypistats.org/packages/xcookie

.. |ReadTheDocs| image:: https://readthedocs.org/projects/xcookie/badge/?version=latest
    :target: http://xcookie.readthedocs.io/en/latest/

.. |CodeQuality| image:: https://api.codacy.com/project/badge/Grade/4d815305fc014202ba7dea09c4676343
    :target: https://www.codacy.com/manual/Erotemic/xcookie?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=Erotemic/xcookie&amp;utm_campaign=Badge_Grade

.. |GithubActions| image:: https://github.com/Erotemic/xcookie/actions/workflows/tests.yml/badge.svg?branch=main
    :target: https://github.com/Erotemic/xcookie/actions?query=branch%3Amain
