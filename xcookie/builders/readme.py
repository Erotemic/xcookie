import ubelt as ub


def build_readme(self):
    badges = {}
    remote_info = self.remote_info
    main_branch = 'main'
    group = remote_info['group']
    repo_name = remote_info['repo_name']

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
        'image': f'https://readthedocs.org/projects/{repo_name}/badge/?version=latest',
        'target': f'http://{repo_name}.readthedocs.io/en/latest/',
    }
    if 'binpy' in self.config['tags']:
        badges['GithubActions'] = {
            'image': f'https://github.com/{group}/{repo_name}/actions/workflows/test_binaries.yml/badge.svg?branch={main_branch}',
            'target': f'https://github.com/{group}/{repo_name}/actions?query=branch%3A{main_branch}',
        }
    else:
        badges['GithubActions'] = {
            'image': f'https://github.com/{group}/{repo_name}/actions/workflows/tests.yml/badge.svg?branch={main_branch}',
            'target': f'https://github.com/{group}/{repo_name}/actions?query=branch%3A{main_branch}',
        }
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
