Trusted GitHub Publishing
=========================

Overview
--------

Set ``ci_pypi_trusted_publishing = true`` in ``[tool.xcookie]`` to switch
GitHub deploy jobs from long-lived Twine password secrets to PyPI Trusted
Publishing through GitHub OIDC.

This changes the PyPI authentication mechanism only. It does not change the
optional GPG / OpenTimestamps signing flow.

Required external steps
-----------------------

After regenerating ``.github/workflows/tests.yml``, you must also register the
generated GitHub workflow as a trusted publisher on the package index.

For PyPI and/or TestPyPI, configure a trusted publisher with:

* the repository owner
* the repository name
* the workflow filename: ``.github/workflows/tests.yml``

Repeat the registration on TestPyPI if you want the generated ``test_deploy``
job to publish there.

Operational notes
-----------------

* Keep the workflow filename stable after registering it with PyPI / TestPyPI.
* ``TWINE_USERNAME`` / ``TWINE_PASSWORD`` and their test equivalents are not
  needed when trusted publishing is enabled.
* If ``enable_gpg = true``, the current xcookie flow still expects the GPG
  signing materials to be handled by the legacy encrypted-key path, so
  ``CI_SECRET`` and the encrypted GPG files are still relevant.
* If ``enable_gpg = false``, there is no GPG key export step and, for GitHub
  trusted publishing, there may be no CI secrets to upload at all.
* Local ``act`` runs can approximate the build and signing portions of the
  workflow, but they do not emulate the real OIDC publish path.

Suggested xcookie configuration
-------------------------------

Example::

    [tool.xcookie]
    ci_pypi_trusted_publishing = true
    enable_gpg = true

or, if detached signatures are not needed::

    [tool.xcookie]
    ci_pypi_trusted_publishing = true
    enable_gpg = false
