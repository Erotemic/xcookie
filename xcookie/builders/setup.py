def build_setup(self):
    from xcookie import rc
    import ubelt as ub
    import re
    # from distutils.version import Version
    # from packaging.version import parse as Version

    pkg_name = self.config['pkg_name']
    min_python = self.config['min_python']
    # min_py_version = str(self.config['min_python'])
    dev_status = self.config['dev_status']

    fpath = rc.resource_fpath('setup.py.in')

    template_text = fpath.read_text()
    parts = re.split('(### xcookie: .*$)', template_text, flags=re.MULTILINE)

    lut = {}
    for p in parts:
        if not p.strip():
            continue
        if p.startswith('### xcookie: +'):
            key = p.split('+')[1]
        elif p.startswith('### xcookie: -'):
            assert key in lut
        else:
            assert key not in lut, f'{key=}'
            lut[key] = p

    parts = []
    parts.append(ub.codeblock(
        '''
        #!/usr/bin/env python
        # Generated by ~/code/xcookie/xcookie/builders/setup.py
        # based on part ~/code/xcookie/xcookie/rc/setup.py.in
        import sys
        import re
        from os.path import exists, dirname, join
        from setuptools import find_packages
        '''))

    if 'binpy' in self.tags:
        parts.append(lut['IF(binpy)'])
    else:
        parts.append(ub.codeblock(
            '''
            from setuptools import setup
            '''))

    parts.append(lut['HELPERS'])
    parts.append(ub.codeblock(
        f'''
        NAME = '{pkg_name}'
        INIT_PATH = '{self.rel_mod_dpath}/__init__.py'
        VERSION = parse_version(INIT_PATH)
        '''))

    version_classifiers = []
    for ver in self.config['supported_python_versions']:
        version_classifiers.append(f'Programming Language :: Python :: {ver}')

    # List of classifiers available at:
    dev_status = dev_status.lower()
    if dev_status == 'planning':
        dev_status = 'Development Status :: 1 - Planning'
    elif dev_status == 'pre-alpha':
        dev_status = 'Development Status :: 2 - Pre-Alpha'
    elif dev_status == 'alpha':
        dev_status = 'Development Status :: 3 - Alpha'
    elif dev_status == 'beta':
        dev_status = 'Development Status :: 4 - Beta'
    elif dev_status in {'stable', 'production'}:
        dev_status = 'Development Status :: 5 - Production/Stable'
    elif dev_status == 'mature':
        dev_status = 'Development Status :: 6 - Mature'
    elif dev_status == 'inactive':
        dev_status = 'Development Status :: 7 - Inactive'

    other_classifiers = [
        # https://pypi.python.org/pypi?%3Aaction=list_classifiers
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Utilities',
        # This should be interpreted as Apache License v2.0
        'License :: OSI Approved :: Apache Software License',
    ]

    disk_config = self.config._load_pyproject_config()
    if disk_config is None:
        disk_config = {}
    other_classifiers += disk_config.get('project', {}).get('classifiers', [])

    pyproject_settings = self.config._load_xcookie_pyproject_settings()
    if pyproject_settings is not None and 'classifiers' in pyproject_settings:
        other_classifiers += pyproject_settings['classifiers']

    classifiers = [dev_status] + other_classifiers + version_classifiers

    classifiers = list(ub.oset(classifiers))

    # if 0:
    #     setupkw['entry_points'] = {
    #         # the console_scripts entry point creates the package CLI
    #         'console_scripts': [
    #             'xcookie = xcookie.__main__:main'
    #         ]
    #     }

    extras = ['runtime', 'tests', 'optional']

    parts.append(ub.identity(
        '''
if __name__ == '__main__':
    setupkw = {}

    setupkw['install_requires'] = parse_requirements('requirements/runtime.txt', versions='loose')
    setupkw['extras_require'] = {

        '''))
    # 'all': parse_requirements('requirements.txt', versions='loose'),
    # 'tests': parse_requirements('requirements/tests.txt', versions='loose'),
    # 'optional': parse_requirements('requirements/optional.txt', versions='loose'),

    # cv2_part = ub.identity(
    #     '''
    #     'headless': parse_requirements('requirements/headless.txt', versions='loose'),
    #     'graphics': parse_requirements('requirements/graphics.txt', versions='loose'),
    #     # Strict versions
    #     'headless-strict': parse_requirements('requirements/headless.txt', versions='strict'),
    #     'graphics-strict': parse_requirements('requirements/graphics.txt', versions='strict'),
    #     ''')
    if 'cv2' in self.tags:
        extras = ['headless', 'graphics']
    #     parts.append(cv2_part)

    # postgresql_part = '''
    #     'postgresql': parse_requirements('requirements/postgresql.txt', versions='loose'),
    #     'postgresql-strict': parse_requirements('requirements/postgresql.txt', versions='strict'),
    # '''

    if 'postgresql' in self.tags:
        extras += ['postgresql']
    #     parts.append(postgresql_part)

    requirements_dpath = self.repodir / 'requirements'
    if requirements_dpath.exists():
        # Hack to add in relevant extras
        existing_req_files = sorted(requirements_dpath.glob('*.txt'))
        extras += [f.stem for f in existing_req_files]

    if extras:
        extra_keyvalues = {}
        extras = ub.oset(extras)
        extra_lines = []
        extra_keyvalues['all'] = "parse_requirements('requirements.txt', versions='loose')"
        for name in extras:
            extra_keyvalues[name] = f"parse_requirements('requirements/{name}.txt', versions='loose')"
        extra_keyvalues['all-strict'] = "parse_requirements('requirements.txt', versions='strict')"
        for name in extras:
            extra_keyvalues[name + '-strict'] = f"parse_requirements('requirements/{name}.txt', versions='strict')"

        for name, line in extra_keyvalues.items():
            extra_lines.append(f"'{name}': {line},")

        parts.append(ub.indent('\n'.join(extra_lines)) + '\n}')

    # parts.append(ub.identity(
    #     '''
    #     'all-strict': parse_requirements('requirements.txt', versions='strict'),
    #     'runtime-strict': parse_requirements('requirements/runtime.txt', versions='strict'),
    #     'tests-strict': parse_requirements('requirements/tests.txt', versions='strict'),
    #     'optional-strict': parse_requirements('requirements/optional.txt', versions='strict'),
    #     }
    #     '''))

    classifier_text = ub.urepr(classifiers)

    # author=static_parse('__author__', INIT_PATH),
    # author_email=static_parse('__author_email__', INIT_PATH),
    # url=static_parse('__url__', INIT_PATH),

    # TODO: Try placing most of this into a setup.cfg instead
    setupkw_parts = {}
    setupkw_parts['name'] = 'NAME'
    setupkw_parts['version'] = 'VERSION'
    if isinstance(self.config["author"], list):
        setupkw_parts['author'] = repr(', '.join(self.config["author"]))
    else:
        setupkw_parts['author'] = f'{self.config["author"]!r}'
    if isinstance(self.config["author_email"], list):
        setupkw_parts['author_email'] = repr(', '.join(self.config["author_email"]))
    else:
        setupkw_parts['author_email'] = f'{self.config["author_email"]!r}'
    setupkw_parts['url'] = f'{self.config["url"]!r}'
    setupkw_parts['description'] = f'{self.config["description"]!r}'
    setupkw_parts['long_description'] = 'parse_description()'
    setupkw_parts['long_description_content_type'] = "'text/x-rst'"
    setupkw_parts['license'] = f'{self.config["license"]!r}'
    setupkw_parts['packages'] = f"find_packages({self.config['rel_mod_parent_dpath']!r})"
    setupkw_parts['python_requires'] = f"'>={min_python}'"
    setupkw_parts['classifiers'] = f'{classifier_text}'

    package_data = {}
    package_data[''] = ['requirements/*.txt']
    if self.config['typed']:
        package_data[self.mod_name] = ['py.typed', '*.pyi']

    if package_data:
        setupkw_parts['package_data'] = package_data

    if self.config['rel_mod_parent_dpath'] != '.':
        # https://codefellows.github.io/sea-python-401d4/lectures/python_packaging_1.html
        # We use a key of an empty string to indicate that the directory we are
        # pointing to should be considered the root. Then the value is src, telling
        # setuptools to use that directory as the root of our source.
        setupkw_parts['package_dir'] = ub.urepr(
            {'': self.config['rel_mod_parent_dpath']}
        )

    # hack
    if pyproject_settings is None:
        pyproject_settings = {}
    if 'entry_points' in pyproject_settings:
        setupkw_parts['entry_points'] = ub.urepr(pyproject_settings['entry_points'])
    if 'scripts' in pyproject_settings:
        setupkw_parts['scripts'] = ub.urepr(pyproject_settings['scripts'])
    if 'package_data' in pyproject_settings:
        setupkw_parts.setdefault('package_data', {})
        setupkw_parts['package_data'].update(pyproject_settings['package_data'])

    for k, v in setupkw_parts.items():
        parts.append(ub.indent(f"setupkw[{k!r}] = {v}"))

    if 'setuptools' in pyproject_settings:
        for k, v in pyproject_settings['setuptools'].items():
            parts.append(ub.indent(f"setupkw[{k!r}] = {v!r}"))
    parts.append(ub.indent('setup(**setupkw)'))

    text = '\n'.join(parts)
    # print(text)

    # Its annoying, but other than that insufferable quote issue, black is very
    # good. I have a patch, but I need to find the best way to integrate it.
    # it is kinda nice to have the '"' = hints at autogenerated text convention
    # though. I suppose that is something that can be said for it.
    try:
        import black
        text = black.format_str(text, mode=black.Mode(string_normalization=True))
    except Exception:
        print(text)
        raise
    return text
