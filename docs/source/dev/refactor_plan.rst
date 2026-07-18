Refactor plan
===============

This plan groups the next xcookie cleanup work into chunks that are safe to
review and land independently.  The current code does not promise a stable
Python public API, so these chunks lean toward cleaner internal names,
intermediate models, and provider-neutral planning objects rather than
compatibility wrappers.

Chunk 0: generated-output safety net
------------------------------------

Add invariant tests before deep rewrites.  These tests should exercise generated
GitHub Actions, GitLab CI, and staged template files without waiting for hosted
CI failures.

* Parse generated YAML where possible.
* Assert no wheel install target contains empty extras such as ``[]``.
* Assert CI install extras are declared by the target project.
* Assert shell-facing generated paths use POSIX slashes.
* Assert GitHub and GitLab agree on shared policy: extras, strict/loose
  variants, wheelhouse names, and artifact names.
* Add Windows-path simulation tests that run on any platform.

Chunk 1: typed template registry and staging layer
--------------------------------------------------

Replace raw template dictionaries and regex-style substitutions with explicit
models.

* Add ``TemplateInfo`` for template registry entries.
* Add ``TemplateContext`` for replacement values.
* Normalize raw registry dictionaries as soon as the registry is built.
* Route staging through typed attributes instead of ad-hoc dictionary keys.
* Replace regex-backed token substitution with simple ``str.replace`` over an
  explicit replacement map.
* Normalize path substitutions that are rendered into portable shell/YAML text.

This chunk reduces Windows escape bugs and makes template staging easier to
inspect and type-check.

Chunk 2: raw config versus resolved config
------------------------------------------

Separate CLI / pyproject inputs from inferred values consumed by builders.

* Keep ``XCookieConfig`` as the user-facing scriptconfig object.
* Add ``ResolvedXCookieConfig`` as a deterministic, builder-facing view.
* Move tag normalization, OS normalization, repo/module/package name inference,
  author inference, Python-version expansion, and ``use_uv`` inference into the
  resolver.
* Keep compatibility write-back only while older builders still read
  ``config[...]`` directly.

Chunk 3: shared CI plan model
-----------------------------

Prevent GitHub/GitLab drift by making both providers render from a common plan.

Initial implementation status:

* ``xcookie.builders.ci_plan.CIPlan`` owns provider-neutral CI policy for
  optional-dependency discovery, test variants, typecheck extras, and sdist
  test extras.
* ``TestVariant`` records strict/loose mode, minimal/full scope, install extras,
  and the pyproject/uv resolution policy used by provider matrices.
* GitHub Actions and GitLab CI both consume the shared plan for wheel-test
  variant extras instead of duplicating the same filtering policy.
* ``common_ci`` keeps compatibility wrappers for older builder call sites while
  forwarding optional-dependency filtering and install-target formatting to the
  plan module.

Remaining follow-up work for this chunk:

* Add artifact and deployment plan records.
* Move provider-specific matrix expansion details into dedicated renderer helper
  methods once the shared policy layer is stable.
* Continue adding generated-output invariant tests around the plan so GitHub and
  GitLab cannot drift again.

Chunk 4: thin provider renderers
--------------------------------

After ``CIPlan`` exists, make GitHub and GitLab builders mostly syntax renderers.

Initial implementation status:

* ``GitHubActionsRenderer`` owns test/release workflow rendering and receives a
  single ``CIPlan`` for the whole workflow.
* ``GitLabCIRenderer`` owns provider selection and threads the same ``CIPlan``
  into pure-Python and binary GitLab render paths.
* Module-level builder functions remain as thin wrappers around the renderer
  classes while existing template call sites are migrated.
* Leaf job builders accept an optional plan, so tests and higher-level renderers
  can avoid reconstructing CI policy in multiple places.

Remaining follow-up work for this chunk:

* Move more provider-specific matrix expansion into renderer methods with small
  typed helper records.
* Move deployment and artifact policy into the shared plan once those records
  exist.
* Expand generated-output invariant tests so GitHub/GitLab renderers are
  compared on plan-derived content rather than exact full YAML text.

Chunk 5: secret rotation plan
-----------------------------

Make secret rotation testable without fake queues and shell inspection.

* Add ``SecretPlan`` for provider, GPG transport, trusted publishing, setup
  command, GPG upload command, repo-secret upload command, and explanatory notes.
* Test plan generation directly.
* Keep ``cmd_queue`` and subprocess execution in a narrow execution layer.

Chunk 6: generated CI helper commands
-------------------------------------

Move fragile inline shell and ``python -c`` snippets into normal Python helpers.

* Add ``python -m xcookie.ci_helpers`` commands for artifact discovery,
  install-target construction, module-path resolution, and artifact validation.
* Unit-test the helpers directly.
* Make generated CI call helpers instead of embedding complex quoting logic.

Chunk 7: split ``TemplateApplier`` into focused modules
-------------------------------------------------------

Make ``xcookie/main.py`` a small CLI / compatibility entrypoint.

Suggested layout::

    xcookie/config.py              XCookieConfig and config loading
    xcookie/resolved_config.py     ResolvedXCookieConfig
    xcookie/applier.py             TemplateApplier orchestration
    xcookie/template_registry.py   TemplateInfo and TemplateContext
    xcookie/staging.py             staging, rendering, directives
    xcookie/secrets.py             SecretPlan and rotation execution
    xcookie/ci_helpers.py          generated CI helper commands
    xcookie/builders/ci_plan.py    CIPlan and builder

Chunk 8: inline typing pass
---------------------------

Once the structure settles, add inline annotations throughout the refactored
internals.

* Use ``from __future__ import annotations`` in touched files.
* Prefer dataclasses over loose dictionaries.
* Use ``Literal`` for provider names, dependency modes, artifact kinds, and GPG
  transports.
* Remove stub files or compatibility annotations that are no longer useful.

Chunk 9: remove legacy paths
----------------------------

After the new paths are stable, delete compatibility and duplication.

* Remove provider-specific extra filtering that moved into ``CIPlan``.
* Remove regex substitution helpers from staging.
* Remove shell-inspection test doubles made obsolete by ``SecretPlan``.
* Clean up stale comments describing legacy behavior.
