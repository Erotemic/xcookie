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


The top level CLI is command-oriented:


.. code::

    usage: xcookie [-h] [--version] {generate,bump,refresh-docs,rotate-secrets} ...

    commands:
      {generate,bump,refresh-docs,rotate-secrets}
        generate            generate or update project boilerplate
        bump                bump the package version and changelog
        refresh-docs        regenerate Sphinx API documentation
        rotate-secrets      rotate CI secrets for an existing repository

Run ``xcookie generate --help`` for the project-generation options.

Version bumps are a separate maintenance command. They update the authoritative
package version and roll ``CHANGELOG.md`` from the current release into the next
``Unreleased`` section::

    xcookie bump              # patch, by default
    xcookie bump patch
    xcookie bump minor
    xcookie bump major
    xcookie bump 2.0.0        # explicit target version


Invocations to create a new github repo:

.. code:: bash

    # Create a new python repo
    xcookie generate --repo_name=cookiecutter_purepy --repodir=$HOME/code/cookiecutter_purepy --tags="github,purepy"

    # Create a new binary repo
    xcookie generate --repo_name=cookiecutter_binpy --repodir=$HOME/code/cookiecutter_binpy --tags="github,binpy,gdal"


Given an initialized repository the general usage pattern is to edit the
generated ``pyproject.toml`` and modify values in the ``[tool.xcookie]``
section and then rerun ``xcookie generate`` in that directory. It will then
present you
with a diff of the proposed changes that you can reject, accept entirely, or
accept selectively.

For some files where the user is likely to do custom work, xcookie won't try to
overwrite the file unless you tell it to regenerate it.  The ``setup.py`` is
the main example of this, so if you want xcookie to update your setup.py you
would run ``xcookie generate --regen setup.py``

Documentation refresh is also a separate maintenance command:

.. code:: bash

    xcookie refresh-docs

Secret rotation is a separate maintenance command rather than a generation
option:

.. code:: bash

    xcookie rotate-secrets

The command loads the repository's xcookie configuration, prints the commands
it plans to run, and asks for confirmation before executing them.

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
