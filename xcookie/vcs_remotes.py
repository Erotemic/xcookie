class GitlabRemote:
    """
    pip install python-gitlab
    """
    def __init__(self):
        pass

    def new_project():
        """
        url = 'https://gitlab.kitware.com'
        new_proj_name = 'kwimage_ext'
        target_group = 'computer-vision'
        visibility = 'public'
        """
        import os
        import gitlab
        gl = gitlab.Gitlab(url=url, private_token=os.environ['PRIVATE_GITLAB_TOKEN'])
        gl.auth()

        groups = gl.groups.list()
        found = [g for g in groups if g.name == target_group]
        assert len(found) == 1
        group = found[0]
        # https://docs.gitlab.com/ee/api/projects.html#create-project

        if any(proj.name == new_proj_name for proj in group.projects.list()):
            raise Exception('project already exists')

        new_proj_data = {
            'name': new_proj_name,
            'path': new_proj_name,
            'namespace_id': group.id,
            'initialize_with_readme': False,
            'visibility': visibility,
        }
        new_proj = gl.projects.create(new_proj_data)
        print(new_proj)


class GithubRemote:
    def new_project(self):
        """
        TODO:
            gh repo create {self.repo_name} --public
        """
