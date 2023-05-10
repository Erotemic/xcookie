import ubelt as ub


class BadgeBuilder:
    def __init__(self):
        self.badges = {}

    def build_templates(self, group, repo_name, main_branch, workflow):
        repo_dashname = repo_name.replace('_', '-')
        badges = self.badges = {}
        badges['CircleCI'] = {
            'image': f'https://circleci.com/gh/{group}/{repo_name}.svg?style=svg',
            'target': f'https://circleci.com/gh/{group}/{repo_name}',
        }
        badges['Appveyor'] = {
            'image': f'https://ci.appveyor.com/api/projects/status/github/{group}/{repo_name}?branch={main_branch}&svg=True',
            'target': f'https://ci.appveyor.com/project/{group}/{repo_name}/branch/{main_branch}',
        }
        badges['Codecov'] = {
            'image': f'https://codecov.io/github/{group}/{repo_name}/badge.svg?branch={main_branch}&service=github',
            'target': f'https://codecov.io/github/{group}/{repo_name}?branch={main_branch}',
        }
        badges['Pypi'] = {
            'image': f'https://img.shields.io/pypi/v/{repo_name}.svg',
            'target': f'https://pypi.python.org/pypi/{repo_name}',
        }
        badges['PypiDownloads'] = {
            'image': f'https://img.shields.io/pypi/dm/{repo_name}.svg',
            'target': f'https://pypistats.org/packages/{repo_name}',
        }
        badges['ReadTheDocs'] = {
            'image': f'https://readthedocs.org/projects/{repo_dashname}/badge/?version=latest',
            'target': f'http://{repo_dashname}.readthedocs.io/en/latest/',
        }
        badges['GithubActions'] = {
            'image': f'https://github.com/{group}/{repo_name}/actions/workflows/{workflow}.yml/badge.svg?branch={main_branch}',
            'target': f'https://github.com/{group}/{repo_name}/actions?query=branch%3A{main_branch}',
        }
        return badges


def build_readme(self):
    badges = {}
    remote_info = self.remote_info
    main_branch = 'main'
    group = remote_info['group']
    repo_name = remote_info['repo_name']

    if 'binpy' in self.config['tags']:
        workflow = 'test_binaries'
    else:
        workflow = 'tests'
    badges = BadgeBuilder().build_templates(group, repo_name, main_branch, workflow)

    # badges['CodeQuality'] = {
    #     'image': f'image:: https://api.codacy.com/project/badge/Grade/4d815305fc014202ba7dea09c4676343',
    #     'target': f'https://www.codacy.com/manual/{group}/{repo_name}?utm_source=github.com&amp;utm_medium=referral&amp;utm_content={group}/{repo_name}&amp;utm_campaign=Badge_Grade',
    # }

    parts = []

    title = f'The {repo_name} Module'
    title = title + '\n' + ('=' * len(title))
    parts.append(title)
    parts.append('')

    chosen_badges = ['Pypi', 'PypiDownloads']
    if 'github' in self.config['tags']:
        chosen_badges += ['GithubActions', 'Codecov']

    badge_header = ' '.join(['|{}|'.format(b) for b in chosen_badges])
    parts.append(badge_header)
    parts.append('')

    for b in chosen_badges:
        badge = badges[b]
        badge_def = ub.codeblock(
            f'''
            .. |{b}| image:: {badge['image']}
                :target: {badge['target']}
            '''
        )
        parts.append(badge_def)

    readme_text = '\n\n'.join(parts)
    return readme_text


def _ibeis_badges(repo_names):
    """
    repo_names = [
        'ibeis',
        'utool',
        'vtool_ibeis',
        'plottool_ibeis',
        'guitool_ibeis',
        'pyhesaff',
        'pyflann_ibeis',
        'vtool_ibeis_ext',
        'graphid',
    ]
    """
    group = 'Erotemic'
    main_branch = 'main'
    workflow = 'tests'
    lines = []
    for repo_name in repo_names:
        badges = BadgeBuilder().build_templates(group, repo_name, main_branch, workflow)
        b = 'GithubActions'
        kw = badges[b]
        badge_name = repo_name + b
        text = ub.codeblock(
            '''
            .. |{badge_name}| image:: {image}
                :target: {target}
            '''
        ).format(**kw, badge_name=badge_name)
        lines.append(text)

        print(f'|{badge_name}|')
    print('\n'.join(lines))
