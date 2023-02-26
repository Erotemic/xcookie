import os
import ubelt as ub
from packaging.version import parse as LooseVersion


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
    def __init__(self, proj_name, proj_group, url, visibility='public',
                 private_token='env:PRIVATE_GITLAB_TOKEN'):
        import gitlab  # type: ignore
        self.url = url
        self.proj_name = proj_name
        self.proj_path = proj_name
        self.proj_group = proj_group
        self.visibility = visibility
        if private_token.startswith('env:'):
            private_token = os.environ[private_token[4:]]
        self.gitlab = gitlab.Gitlab(url=self.url, private_token=private_token)

    def auth(self):
        self.gitlab.auth()
        return self

    @property
    def group(self):
        gl = self.gitlab
        # Is there a better way to query?
        groups = gl.groups.list(iterator=True)
        found = [g for g in groups if g.name.lower() == self.proj_group.lower()]
        # if not found:
        #     # allow case insensitivity
        #     found = [g for g in groups if g.name.lower() == self.proj_group.lower()]
        return _return_one(found)

    @property
    def project(self):
        group = self.group
        found = [p for p in group.projects.list(iterator=True)
                 if p.path.lower() == self.proj_path.lower()]
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
    def __init__(self, proj_name):
        self.proj_name = proj_name

    def new_project(self):
        ub.cmd(f'gh repo create {self.proj_name} --public', verbose=3, system=True)

    def publish_release(self):
        """
        POC for making a release script

        References:
            https://cli.github.com/manual/gh_release_create
        """

        fpath = "CHANGELOG.md"
        version_changelines = _parse_changelog(fpath)

        latest_version, latest_notes = ub.peek(version_changelines.items())
        VERSION = ub.cmd('python -c "import setup; print(setup.VERSION)"')['out'].strip()
        DEPLOY_REMOTE = 'origin'
        TAG_NAME = f'v{VERSION}'
        assert latest_version == LooseVersion(VERSION)

        tag_exists = ub.cmd(f'git rev-parse {TAG_NAME}')['ret'] == 0
        if not tag_exists:
            ub.cmd(f'git tag "{TAG_NAME}" -m "tarball tag {VERSION}"', verbose=2)
            ub.cmd(f'git push --tags {DEPLOY_REMOTE}', verbose=2)

        import tempfile
        release_notes_fpath = ub.Path(tempfile.mktemp('.txt'))
        release_notes_fpath.write_text('\n'.join(latest_notes[1:]))

        title = f'Version {latest_version}'
        command = f'gh release create "{TAG_NAME}" --notes-file "{release_notes_fpath}" --title "{title}"'
        print(command)
        ub.cmd(command, verbose=3)


def version_bump():
    #### Do a version bump on the repo
    # Update the changelog
    VERSION = LooseVersion(ub.cmd('python -c "import setup; print(setup.VERSION)"')['out'].strip())
    DEPLOY_REMOTE = 'origin'
    fpath = "CHANGELOG.md"
    changelog_fpath = ub.Path(fpath)
    NEXT_VERSION = '{}.{}.{}'.format(VERSION.major, VERSION.minor,
                                     VERSION.micro + 1)
    text = changelog_fpath.read_text()
    text = text.replace('Unreleased', 'Released ' + ub.timeparse(ub.timestamp()).date().isoformat())
    lines = text.split(chr(10))
    for ix, line in enumerate(lines):
        if 'Version ' in line:
            break
    newline = fr'## Version {NEXT_VERSION} - Unreleased'
    newlines = lines[:ix] + [newline, '', ''] + lines[ix:]
    new_text = chr(10).join(newlines)
    changelog_fpath.write_text(new_text)

    init_fpath = ub.Path('src/xdoctest/__init__.py')  # hack, hard code
    init_text = init_fpath.read_text()
    init_text = init_text.replace(f'__version__ = {VERSION!r}', f'__version__ = {NEXT_VERSION!r}', )
    init_fpath.write_text(init_text)

    ub.cmd(f'git co -b "dev/{NEXT_VERSION}"')
    ub.cmd(f'git commit -am "Start branch for {NEXT_VERSION}"')
    ub.cmd(f'git push "{DEPLOY_REMOTE}"')

    ub.cmd(f'gh pr create --title "Start branch for {NEXT_VERSION}" --body "auto created PR" --base main --assignee @me', verbose=2)
    # Github create PR


def _parse_changelog(fpath):
    """
    Helper to parse the changelog for the version to verify versions agree.

    CommandLine:
        xdoctest -m dev/parse_changelog.py _parse_changelog --dev
        fpath = "CHANGELOG.md"
    """
    import re
    pat = re.compile(r'#.*Version ([0-9]+\.[0-9]+\.[0-9]+)')
    # We can statically modify this to a constant value when we deploy

    version = None
    versions = {}
    version_changelines = ub.ddict(list)
    with open(fpath, 'r') as file:
        for line in file.readlines():
            line = line.rstrip()
            if line:
                parsed = pat.search(line)
                if parsed:
                    print('parsed = {!r}'.format(parsed))
                    try:
                        version_text = parsed.groups()[0]
                        version = LooseVersion(version_text)
                        versions.append(version)
                    except Exception:
                        print('Failed to parse = {!r}'.format(line))
            if version is not None:
                version_changelines[version].append(line)
    return version_changelines
