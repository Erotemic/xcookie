import os









import ubelt as ub


class NotFound(Exception):
    pass


class Ambiguous(Exception):
    pass


def _return_one(found):
    if len(found) == 0:
        raise NotFound()
    elif len(found) == 1:
        return found[0]
    else:
        raise Ambiguous


class GitlabRemote:
    """
    pip install python-gitlab

    Ignore:
        load_secrets
        HOST=https://gitlab.kitware.com
        export PRIVATE_GITLAB_TOKEN=$(git_token_for "$HOST")

    """
    def __init__(self, proj_name, proj_group, url):
        import gitlab
        self.url = url
        self.proj_name = proj_name
        self.proj_path = proj_name
        self.proj_group = proj_group
        self.visibility = 'public'
        self.gitlab = gitlab.Gitlab(
            url=self.url, private_token=os.environ['PRIVATE_GITLAB_TOKEN'])

    def auth(self):
        self.gitlab.auth()
        return self

    @property
    def group(self):
        gl = self.gitlab
        groups = gl.groups.list()
        found = [g for g in groups if g.name == self.proj_group]
        return _return_one(found)

    @property
    def project(self):
        group = self.group
        found = [p for p in group.projects.list() if p.path == self.proj_path]
        group_project = _return_one(found)
        project = self.gitlab.projects.get(group_project.id)
        return project

    def new_project(self):
        """
        Ignore:
            from xcookie.vcs_remotes import *  # NOQA
            url = 'https://gitlab.kitware.com'
            proj_name = 'kwimage_ext'
            proj_group = 'computer-vision'
            visibility = 'public'
            self = GitlabRemote(proj_name, proj_group, url).auth()
        """
        # https://docs.gitlab.com/ee/api/projects.html#create-project
        group = self.group
        try:
            self.project
        except NotFound:
            pass
        else:
            raise Exception('project already exist')

        new_proj_data = {
            'name': self.proj_name,
            'path': self.proj_path,
            'namespace_id': group.id,
            'initialize_with_readme': False,
            'visibility': self.visibility,
        }
        new_proj = self.gitlab.projects.create(new_proj_data)
        print(new_proj)

    def set_protected_branches(self):
        project = self.project

        existing_protected_branches = project.protectedbranches.list()
        expected_protected_branches = [
            'release', 'main', 'master'
        ]

        existing = {b.name for b in existing_protected_branches}
        missing = [bname for bname in expected_protected_branches
                   if bname not in existing]

        for name in missing:
            # https://docs.gitlab.com/ee/api/protected_branches.html#protect-repository-branches
            project.protectedbranches.create({
                'name': name,
                'allow_force_push': False,
            })
        # if hasattr(gitlab.const, 'AccessLevel'):
        #     maintainer = gitlab.const.AccessLevel.MAINTAINER
        # else:
        #     maintainer = gitlab.const.MAINTAINER_ACCESS
        # perm = [{'access_level': maintainer}]

        if not missing:
            protected_branches = existing_protected_branches
        else:
            protected_branches = project.protectedbranches.list()

        # TODO: figure out how to change access levels
        for branch in protected_branches:
            print('---')
            print('branch = {}'.format(ub.repr2(branch, nl=1)))
            print('branch.push_access_levels = {}'.format(ub.repr2(branch.push_access_levels, nl=1)))
            print('branch.merge_access_levels = {}'.format(ub.repr2(branch.merge_access_levels, nl=1)))
            print('branch.allow_force_push = {}'.format(ub.repr2(branch.allow_force_push, nl=1)))
        # if 0:
        #         # API doesnt directly support this, hack it in
        #         post_data = {
        #             'name': branch.get_id(),
        #             'allowed_to_push': perm,
        #             'allowed_to_merge': perm,
        #         }
        #         # branch.manager.gitlab.http_post(
        #         #     f'/projects/{project.id}/protected_branches',
        #         #     post_data=post_data,
        #         # )


class GithubRemote:
    def new_project(self):
        """
        TODO:
            gh repo create {self.repo_name} --public
        """
