import ubelt as ub
from packaging.version import parse as LooseVersion
from xcookie.vcs.gitlab import GitlabRemote  # NOQA


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
