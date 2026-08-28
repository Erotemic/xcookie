"""Initialization of a newly generated repository and its remote."""

from __future__ import annotations

from typing import Any

import ubelt as ub

from xcookie.util_command import make_command_queue


class RepositoryInitializer:
    """Perform the Git/hosting setup that belongs to new-repo generation."""

    def __init__(self, config: Any, repodir: ub.Path, remote_info: dict) -> None:
        self.config = config
        self.repodir = repodir
        self.remote_info = remote_info
        self.repo_name = config['repo_name']
        self.tags = set(config['tags'])

    def initialize(self) -> None:
        if not self.config['is_new']:
            return

        create_new_repo_info = ub.codeblock(
            f"""
            TODO: call the APIS
            git init
            gh repo create {self.repo_name} --public
            # https://cli.github.com/manual/gh_repo_create
            """
        )
        print(create_new_repo_info)
        queue = make_command_queue(cwd=self.repodir)
        git_dpath = self.repodir / '.git'
        if not git_dpath.exists():
            queue.submit('git init')
            queue.sync().submit(
                f'git remote add origin {self.remote_info["url"]}'
            )

        if 'erotemic' in self.tags:
            queue.sync().submit('git config --local user.name "Jon Crall"')
            queue.sync().submit(
                'git config --local user.email "erotemic@gmail.com"'
            )
            queue.sync().submit('git config --local commit.gpgsign true')
            queue.sync().submit(
                'git config --local user.signingkey 4AC8B478335ED6ED667715F3622BE571405441B4'
            )

        if queue.jobs:
            queue.rprint()
            if self.config.confirm('Do git init?'):
                self.repodir.ensuredir()
                queue.run()

        if self.config['init_new_remotes'] and self.config.confirm(
            'Do you want to create the repo on the remote?'
        ):
            self._create_remote()

    def _create_remote(self) -> None:
        if 'gitlab' in self.tags:
            from xcookie.vcs.gitlab import GitlabRemote

            vcs_remote = GitlabRemote(
                proj_name=self.remote_info['repo_name'],
                proj_group=self.remote_info['group'],
                url=self.remote_info['host'],
                visibility=self.config['visibility'],
            )
            vcs_remote.auth()
            vcs_remote.new_project()
        elif 'github' in self.tags:
            from xcookie.vcs.github import GithubRemote

            vcs_remote = GithubRemote(self.remote_info['repo_name'])
            vcs_remote.new_project()
        else:
            raise NotImplementedError('unknown vcs remote')
