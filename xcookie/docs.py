"""Documentation maintenance action used by the modal CLI."""

from __future__ import annotations

from typing import Any

import ubelt as ub


class DocsRefresher:
    """Regenerate Sphinx API pages for an existing xcookie repository."""

    def __init__(self, config: Any) -> None:
        self.config = config
        self.repodir = ub.Path(config['repodir'])

    @property
    def has_git(self) -> bool:
        return (self.repodir / '.git').exists()

    def refresh_docs(self) -> None:
        """Run sphinx-apidoc and stage its generated API pages when in Git."""
        from xcookie.builders import docs

        docs_builder = docs.DocsBuilder(self.config)
        docs_dpath = docs_builder.docs_dpath
        docs_auto_outdir = docs_builder.docs_auto_outdir
        command = docs_builder.sphinx_apidoc_invocation()

        ub.cmd(command, verbose=3, check=True, cwd=docs_dpath)
        if self.has_git:
            ub.cmd(
                f'git add {docs_auto_outdir}/*.rst',
                verbose=3,
                check=True,
                cwd=docs_dpath,
            )
