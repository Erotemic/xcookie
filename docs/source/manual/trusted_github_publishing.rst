Trusted Publishing with GitHub Actions
======================================

Overview
--------

xcookie can generate GitHub Actions workflows that publish to PyPI and TestPyPI
using `PyPI Trusted Publishing`_ instead of long-lived Twine password secrets.

When trusted publishing is enabled, GitHub Actions authenticates to PyPI using
GitHub's OIDC identity token exchange. This removes the need to store a reusable
PyPI API token in GitHub secrets.

This changes only the **PyPI authentication** path.

It does **not** remove the optional GPG / OpenTimestamps signing flow. If
``enable_gpg = true``, the current xcookie flow still expects the GPG signing
materials to be handled by the existing encrypted-key path, so ``CI_SECRET`` and
the encrypted GPG files are still relevant.

xcookie configuration
---------------------

Enable trusted publishing in ``[tool.xcookie]``:

.. code-block:: toml

    [tool.xcookie]
    ci_pypi_trusted_publishing = true

If you still want detached signatures and OpenTimestamps on release artifacts:

.. code-block:: toml

    [tool.xcookie]
    ci_pypi_trusted_publishing = true
    enable_gpg = true

If a repository does not use GPG signing:

.. code-block:: toml

    [tool.xcookie]
    ci_pypi_trusted_publishing = true
    enable_gpg = false

What xcookie generates
----------------------

When ``ci_pypi_trusted_publishing = true``, the generated GitHub workflow uses:

* ``pypa/gh-action-pypi-publish@release/v1``
* job-scoped ``permissions:``

  .. code-block:: yaml

      permissions:
        contents: read
        id-token: write

* a separate TestPyPI publish step with:

  .. code-block:: yaml

      repository-url: https://test.pypi.org/legacy/

What is no longer required
--------------------------

When trusted publishing is enabled, these GitHub secrets are no longer required
for publishing to PyPI / TestPyPI:

* ``TWINE_USERNAME``
* ``TWINE_PASSWORD``
* ``TEST_TWINE_USERNAME``
* ``TEST_TWINE_PASSWORD``

If ``enable_gpg = true``, ``CI_SECRET`` is still required for the current GPG
signing flow.

Step-by-step setup
------------------

1. Regenerate the GitHub workflow
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Regenerate the repository after setting:

.. code-block:: toml

    [tool.xcookie]
    ci_pypi_trusted_publishing = true

Then inspect the generated workflow and confirm that the deploy jobs contain:

* ``uses: pypa/gh-action-pypi-publish@release/v1``
* ``permissions: id-token: write``
* ``repository-url: https://test.pypi.org/legacy/`` on the test publish job

2. Commit and push the workflow file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Trusted publishing is bound to the **exact workflow filename** registered on
PyPI / TestPyPI. Do not register a workflow path until the final filename and
basic structure are stable.

For the current xcookie GitHub workflow layout, the relevant file is:

.. code-block:: text

    .github/workflows/release.yml

3. Register a trusted publisher on PyPI
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Open the PyPI project settings and configure a trusted publisher for GitHub.

Official docs:

* PyPI Trusted Publishers overview:
  https://docs.pypi.org/trusted-publishers/
* PyPI: using a publisher:
  https://docs.pypi.org/trusted-publishers/using-a-publisher/
* PyPI security model:
  https://docs.pypi.org/trusted-publishers/security-model/

When configuring the publisher, use:

* Owner: the GitHub organization or user
* Repository name: the repository name
* Workflow filename: ``.github/workflows/release.yml``

If you are using GitHub protected environments, also set the matching
environment name in PyPI.

4. Register a trusted publisher on TestPyPI
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you want the generated ``test_deploy`` job to publish to TestPyPI, repeat the
same configuration on TestPyPI.

Official docs:

* TestPyPI:
  https://test.pypi.org/
* PyPI docs for trusted publishers are also applicable to TestPyPI:
  https://docs.pypi.org/trusted-publishers/using-a-publisher/

Use the same:

* Owner
* Repository name
* Workflow filename: ``.github/workflows/release.yml``

5. Run a non-release push and check TestPyPI
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The generated test deployment job publishes to TestPyPI on ordinary pushes that
are **not** release-branch pushes and **not** tag pushes.

Confirm in the GitHub Actions UI that:

* the test deploy job runs
* the publish step succeeds
* no Twine password secret is used
* the package appears on TestPyPI

6. Run a release publish and check PyPI
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The generated live deployment job publishes to PyPI on:

* release-branch pushes, or
* tag pushes

After the workflow succeeds, verify:

* the package exists on PyPI
* GitHub release artifacts contain the expected ``.asc`` and ``.ots`` files if
  GPG signing is enabled
* no reusable PyPI token is stored in GitHub secrets

Secure environment recommendations
----------------------------------

Trusted publishing removes long-lived PyPI credentials, but the trusted workflow
is still security-sensitive because it controls the build, signing, and publish
steps.

Recommended hardening:

1. Use GitHub protected environments
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

GitHub environments can require manual approval and restrict which branches or
tags may deploy.

Official docs:

* GitHub OIDC / security hardening:
  https://docs.github.com/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect
* GitHub environments:
  https://docs.github.com/actions/deployment/targeting-different-environments/using-environments-for-deployment

Recommended environment names:

* ``testpypi``
* ``pypi``

2. Keep ``id-token: write`` job-scoped
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Do not grant OIDC token permissions at workflow scope. Keep them only on the
publish jobs.

3. Restrict who can modify the release workflow
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The trusted publishing boundary is not just the publish action step. It includes
the build and signing steps that produce the exact artifacts that will be
published.

Treat changes to those steps as release-surface changes and review them
accordingly.

4. Keep the workflow filename stable
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Once a trusted publisher is registered, changing the workflow filename requires
updating the PyPI / TestPyPI configuration.

Current limitations
-------------------

* Local ``act`` runs cannot emulate the real OIDC publish path.
* If ``enable_gpg = true``, the current xcookie implementation still uses the
  legacy encrypted-key mechanism for signing.
* Trusted publishing removes PyPI secrets, but it does not by itself remove the
  GPG secret handling path.

References
----------

.. _PyPI Trusted Publishing: https://docs.pypi.org/trusted-publishers/
