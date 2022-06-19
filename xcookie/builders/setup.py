def build_setup(self):
    from xcookie import rc
    import ubelt as ub
    fpath = rc.resource_fpath('setup.py.in')
    helper_text = fpath.read_text().split('### HELPERS')[1]

    repo_name = self.config['repo_name']

    parts = []
    parts.append(ub.codeblock(
        '''
        import sys
        from os.path import exists
        from setuptools import find_packages
        '''))

    if 'binpy' in self.tags:
        parts.append(ub.codeblock(
            '''
            if exists('CMakeLists.txt'):
                try:
                    import os
                    # Hack to disable all compiled extensions
                    val = os.environ.get('DISABLE_C_EXTENSIONS', '').lower()
                    use_setuptools = val in {'true', 'on', 'yes', '1'}

                    if '--universal' in sys.argv:
                        use_setuptools = True

                    if '--disable-c-extensions' in sys.argv:
                        sys.argv.remove('--disable-c-extensions')
                        use_setuptools = True

                except ImportError:
                    use_setuptools = True
            else:
                use_setuptools = True

            if not use_setuptools:
                from skbuild import skb_setup
                setup = skb_setup  # NOQA
            '''))
    else:
        parts.append(ub.codeblock(
            '''
            from setuptools import setup
            '''))

    parts.append(helper_text)
    parts.append(ub.codeblock(
        f'''
        NAME = '{repo_name}'
        INIT_PATH = '{repo_name}/__init__.py'
        VERSION = parse_version('{repo_name}/__init__.py')
        '''))

    version_classifiers = []
    from distutils.version import LooseVersion
    min_python = self.config['min_python']
    min_py_version = str(self.config['min_python'])
    min_py_version = LooseVersion(min_py_version)
    known_pythons_versions = ['2.7', '3.5', '3.6', '3.7', '3.8', '3.9', '3.10']
    for ver in known_pythons_versions:
        if ver >= min_py_version:
            version_classifiers.append(f'Programming Language :: Python :: {ver}')

    # List of classifiers available at:
    dev_status = self.config['dev_status']
    if dev_status == 'planning':
        dev_status = 'Development Status :: 1 - Planning'
    elif dev_status == 'pre-alpha':
        dev_status = 'Development Status :: 2 - Pre-Alpha'
    elif dev_status == 'alpha':
        dev_status = 'Development Status :: 3 - Alpha'
    elif dev_status == 'beta':
        dev_status = 'Development Status :: 4 - Beta'
    elif dev_status == 'stable':
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

    classifiers = [dev_status] + other_classifiers + version_classifiers

    parts.append(ub.identity(
        '''
if __name__ == '__main__':
    setupkw = {}

    if 0:
        setupkw['entry_points'] = {
            # the console_scripts entry point creates the package CLI
            'console_scripts': [
                'xcookie = xcookie.__main__:main'
            ]
        }
    setupkw['install_requires'] = parse_requirements('requirements/runtime.txt')
    setupkw['extras_require'] = {
        'all': parse_requirements('requirements.txt'),
        'tests': parse_requirements('requirements/tests.txt'),
        'optional': parse_requirements('requirements/optional.txt'),

        '''))

    cv2_part = ub.identity(
        '''
        'headless': parse_requirements('requirements/headless.txt'),
        'graphics': parse_requirements('requirements/graphics.txt'),
        # Strict versions
        'headless-strict': parse_requirements('requirements/headless.txt', versions='strict'),
        'graphics-strict': parse_requirements('requirements/graphics.txt', versions='strict'),
        ''')
    if 'cv2' in self.tags:
        parts.append(cv2_part)

    parts.append(ub.identity(
        '''
        'all-strict': parse_requirements('requirements.txt', versions='strict'),
        'runtime-strict': parse_requirements('requirements/runtime.txt', versions='strict'),
        'tests-strict': parse_requirements('requirements/tests.txt', versions='strict'),
        'optional-strict': parse_requirements('requirements/optional.txt', versions='strict'),
        }
        '''))

    classifier_text = ub.indent(ub.repr2(classifiers), ' ' * 8)

    description = self.config['description']

    # author=static_parse('__author__', INIT_PATH),
    # author_email=static_parse('__author_email__', INIT_PATH),
    # url=static_parse('__url__', INIT_PATH),

    parts.append(
        f'''
    setup(
        name=NAME,
        version=VERSION,
        author={self.config['author']!r},
        author_email={self.config['author_email']!r},
        url={self.config['url']!r},
        description={description!r},
        long_description=parse_description(),
        long_description_content_type='text/x-rst',
        license='Apache 2',
        packages=find_packages('.'),
        python_requires='>={min_python}',
        classifiers={classifier_text},
        **setupkw,
        )
        ''')

    text = '\n'.join(parts)

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
