import ubelt as ub


class Actions:
    """
    Help build action JSON objects
    """
    action_versions = {
        'checkout': 'actions/checkout@v3',
        'setup-python': 'actions/setup-python@v4',
    }
    @classmethod
    def _generic_action(cls, *args, **kwargs):
        action = kwargs.copy()
        for _ in args:
            if _ is not None:
                action.update(_)
        if 'name' in action:
            reordered = ub.dict_isect(action, ['name', 'uses'])
            action = ub.dict_union(reordered, ub.dict_diff(action, reordered))
        return action

    @classmethod
    def checkout(cls, *args, **kwargs):
        return cls._generic_action({
            'name': 'Checkout source',
            'uses': 'actions/checkout@v3'
        }, *args, **kwargs)

    @classmethod
    def setup_python(cls, *args, **kwargs):
        return cls._generic_action({
            'name': 'Setup Python',
            'uses': 'actions/setup-python@v4.5.0'
        }, *args, **kwargs)

    @classmethod
    def codecov_action(cls, *args, **kwargs):
        return cls._generic_action({
            'uses': 'codecov/codecov-action@v3'
        }, *args, **kwargs)

    @classmethod
    def upload_artifact(cls, *args, **kwargs):
        return cls._generic_action({
            'uses': 'actions/upload-artifact@v3'
        }, *args, **kwargs)

    @classmethod
    def download_artifact(cls, *args, **kwargs):
        return cls._generic_action({
            'uses': 'actions/download-artifact@v3',
        }, *args, **kwargs)

    @classmethod
    def msvc_dev_cmd(cls, *args, osvar=None, bits=None, **kwargs):
        if osvar is not None:
            # hack, just keep it this way for now
            if bits == 32:
                kwargs['if'] = "matrix.os == 'windows-latest' && matrix.cibw_skip == '*-win_amd64'"
            else:
                kwargs['if'] = "matrix.os == 'windows-latest' && matrix.cibw_skip == '*-win32'"
        if bits is None:
            name = 'Enable MSVC'
        else:
            name = fr'Enable MSVC {bits}bit'
            if str(bits) == '64':
                ...
            elif str(bits) == '32':
                kwargs['with'] = {
                    'arch': 'x86'
                }
            else:
                raise NotImplementedError(str(bits))
        return cls._generic_action({
            'name': name,
            'uses': 'ilammy/msvc-dev-cmd@v1',
        }, *args, **kwargs)

    @classmethod
    def setup_qemu(cls, *args, sensible=False, **kwargs):
        if sensible:
            kwargs.update({
                'if': "runner.os == 'Linux' && matrix.arch != 'auto'",
                'with': {
                    'platforms': 'all'
                }
            })

        # Emulate aarch64 ppc64le s390x under linux
        return cls._generic_action({
            'name': 'Set up QEMU',
            'uses': 'docker/setup-qemu-action@v2',
        }, *args, **kwargs)

    @classmethod
    def setup_xcode(cls, *args, sensible=False, **kwargs):
        if sensible:
            kwargs.update({
                'if': "matrix.os == 'macOS-latest'",
                'with': {'xcode-version': 'latest-stable'}
            })

        # Emulate aarch64 ppc64le s390x under linux
        return cls._generic_action({
            'name': 'Install Xcode',
            'uses': 'maxim-lobanov/setup-xcode@v1',
        }, *args, **kwargs)

    @classmethod
    def cibuildwheel(cls, *args, sensible=False, **kwargs):
        if sensible:
            kwargs.update({
                'with': {
                    'output-dir': "wheelhouse",
                    'config-file': 'pyproject.toml',
                },
                'env': {
                    # 'CIBW_BUILD_VERBOSITY': 1,
                    'CIBW_SKIP': '${{ matrix.cibw_skip }}',
                    # 'CIBW_BUILD': '${{ matrix.cibw_build }}',
                    # 'CIBW_TEST_REQUIRES': '-r requirements/tests.txt'0
                    # 'CIBW_TEST_COMMAND': 'python {project}/run_tests.py',
                    # configure cibuildwheel to build native archs ('auto'), or emulated ones
                    'CIBW_ARCHS_LINUX': '${{ matrix.arch }}'
                }
            })

        # Emulate aarch64 ppc64le s390x under linux
        return cls._generic_action({
            'name': 'Build binary wheels',
            'uses': 'pypa/cibuildwheel@v2.11.2',
        }, *args, **kwargs)


def build_github_actions(self):
    """
    cat ~/code/xcookie/xcookie/rc/tests.yml.in | yq  .jobs.lint
    cat ~/code/xcookie/xcookie/rc/tests.yml.in | yq  .jobs.build_and_test_purepy_wheels
    cat ~/code/xcookie/xcookie/rc/tests.yml.in | yq  .jobs.build_and_test_sdist
    cat ~/code/xcookie/xcookie/rc/tests.yml.in | yq  .jobs.deploy
    cat ~/code/xcookie/xcookie/rc/tests.yml.in | yq  .
    build_and_test_purepy_wheels
    """

    jobs = {}
    jobs['lint_job'] = lint_job(self)

    if 'purepy' in self.tags:
        name = 'PurePy Build and Test'
        purepy_jobs = {}
        purepy_jobs['build_and_test_sdist'] = build_and_test_sdist(self)
        purepy_jobs['build_and_test_purepy_wheels'] = build_and_test_purepy_wheels(self)
        needs = list(purepy_jobs.keys())
        jobs.update(purepy_jobs)
    elif 'binpy' in self.tags:
        name = 'BinPy Build and Test'
        binpy_jobs = {}
        binpy_jobs['build_and_test_sdist'] = build_and_test_sdist(self)
        binpy_jobs['build_and_test_binpy_wheels'] = build_and_test_binpy_wheels(self)
        needs = list(binpy_jobs.keys())
        jobs.update(binpy_jobs)
    else:
        raise Exception('Need to specify binpy or purepy in tags')

    jobs['test_deploy'] = build_deploy(self, mode='test', needs=needs)
    jobs['live_deploy'] = build_deploy(self, mode='live', needs=needs)

    defaultbranch = self.config['defaultbranch']
    run_on_branches = ub.oset([defaultbranch, 'main'])
    run_on_branches_str = ', '.join(run_on_branches)

    # For some reason, it doesn't like the on block
    header = ub.codeblock(
        f'''
        # This workflow will install Python dependencies, run tests and lint with a variety of Python versions
        # For more information see: https://help.github.com/actions/language-and-framework-guides/using-python-with-github-actions
        # Based on ~/code/xcookie/xcookie/rc/tests.yml.in
        # Now based on ~/code/xcookie/xcookie/builders/github_actions.py

        name: {name}

        on:
          push:
          pull_request:
            branches: [ {run_on_branches_str} ]

        ''')

    walker = ub.IndexableWalker(jobs)
    for p, v in walker:
        k = p[-1]
        if k == 'run':
            if isinstance(v, list):
                v2 = '\n'.join(v)
                walker[p] = v2

    body = {
        'jobs': jobs
    }

    footer = ub.codeblock(
        r'''
        ###
        # Unfortunately we cant (yet) use the yaml docstring trick here
        # https://github.community/t/allow-unused-keys-in-workflow-yaml-files/172120
        #__doc__: |
        #    # How to run locally
        #    # https://packaging.python.org/guides/using-testpypi/
        #    git clone https://github.com/nektos/act.git $HOME/code/act
        #    chmod +x $HOME/code/act/install.sh
        #    (cd $HOME/code/act && ./install.sh -b $HOME/.local/opt/act)
        #
        #    load_secrets
        #    unset GITHUB_TOKEN
        #    $HOME/.local/opt/act/act \
        #        --secret=EROTEMIC_TWINE_PASSWORD=$EROTEMIC_TWINE_PASSWORD \
        #        --secret=EROTEMIC_TWINE_USERNAME=$EROTEMIC_TWINE_USERNAME \
        #        --secret=EROTEMIC_CI_SECRET=$EROTEMIC_CI_SECRET \
        #        --secret=EROTEMIC_TEST_TWINE_USERNAME=$EROTEMIC_TEST_TWINE_USERNAME \
        #        --secret=EROTEMIC_TEST_TWINE_PASSWORD=$EROTEMIC_TEST_TWINE_PASSWORD
        ''')

    from xcookie import util_yaml
    text = header + '\n\n' + util_yaml.yaml_dumps(body) + '\n\n' + footer
    return text


def lint_job(self):
    job = {
        'runs-on': 'ubuntu-latest',
        'steps': [
            Actions.checkout(),
            Actions.setup_python({
                'name': 'Set up Python 3.8',
                'with': {
                    'python-version': 3.8,
                }
            }),
            {
                'name': 'Install dependencies',
                'run': ub.codeblock(
                    '''
                    python -m pip install --upgrade pip
                    python -m pip install flake8
                    ''')
            },
            {
                'name': 'Lint with flake8',
                'run': ub.codeblock(
                    f'''
                    # stop the build if there are Python syntax errors or undefined names
                    flake8 ./{self.rel_mod_dpath} --count --select=E9,F63,F7,F82 --show-source --statistics
                    ''')
            },
            {
                'name': 'Typecheck with mypy',
                'run': ub.codeblock(
                    f'''
                    python -m pip install mypy
                    mypy --install-types --non-interactive ./{self.rel_mod_dpath}
                    mypy ./{self.rel_mod_dpath}
                    ''')
            }
        ]
    }
    return job


def build_and_test_sdist(self):
    job = {
        'name': 'Test sdist Python 3.8',
        'runs-on': 'ubuntu-latest',
        'steps': [
            Actions.checkout(),
            Actions.setup_python({'name': 'Set up Python 3.8', 'with': {'python-version': 3.8}}),
            {
                'name': 'Upgrade pip',
                'run': [_ for _ in [
                    'python -m pip install --upgrade pip',
                    'python -m pip install -r requirements/tests.txt',
                    'python -m pip install -r requirements/runtime.txt',
                    'python -m pip install -r requirements/headless.txt' if 'cv2' in self.tags else None,
                    'python -m pip install -r requirements/gdal.txt' if 'gdal' in self.tags else None,
                ] if _ is not None]
            },
            {
                'name': 'Build sdist',
                # "run": "python setup.py sdist\n"
                'shell': 'bash',
                'run': [
                    # "python -m pip install setuptools>=0.8 wheel",
                    # "python -m pip wheel --wheel-dir wheelhouse .",
                    'python -m pip install pip -U',
                    'python -m pip install setuptools>=0.8 wheel build',
                    'python -m build --sdist --outdir wheelhouse',
                ]
            },
            {
                'name': 'Install sdist',
                'run': [
                    'ls -al ./wheelhouse',
                    f'pip install wheelhouse/{self.mod_name}*.tar.gz -v',
                ]
            },
            {
                'name': 'Test minimal loose sdist',
                'run': [
                    'pwd',
                    'ls -al',
                    # "# Run the tests",
                    # "# Get path to installed package",
                    '# Run in a sandboxed directory',
                    'WORKSPACE_DNAME="testsrcdir_minimal_${CI_PYTHON_VERSION}_${GITHUB_RUN_ID}_${RUNNER_OS}"',
                    'mkdir -p $WORKSPACE_DNAME',
                    'cd $WORKSPACE_DNAME',
                    '# Run the tests',
                    '# Get path to installed package',
                    f'MOD_DPATH=$(python -c "import {self.mod_name}, os; print(os.path.dirname({self.mod_name}.__file__))")',
                    'echo "MOD_DPATH = $MOD_DPATH"',
                    # 'python -m pytest -p pytester -p no:doctest --xdoctest --cov={self.mod_name} $MOD_DPATH ../tests',
                    # TODO: change to test command
                    'python -m pytest --cov={self.mod_name} $MOD_DPATH ../tests',
                    'cd ..',
                ]
            },
            {
                'name': 'Test full loose sdist',
                'run': [
                    'pwd',
                    'ls -al',
                    # 'python -m pip install -r requirements/optional.txt',  # todo: use the extra-spec
                    # 'python -m pip install -r requirements/ipython.txt',  # hack for line-profiler
                    'python -m pip install -r requirements/headless.txt' if 'cv2' in self.tags else 'true',
                    '# Run in a sandboxed directory',
                    'WORKSPACE_DNAME="testsrcdir_full_${CI_PYTHON_VERSION}_${GITHUB_RUN_ID}_${RUNNER_OS}"',
                    'mkdir -p $WORKSPACE_DNAME',
                    'cd $WORKSPACE_DNAME',
                    '# Run the tests',
                    '# Get path to installed package',
                    f'MOD_DPATH=$(python -c "import {self.mod_name}, os; print(os.path.dirname({self.mod_name}.__file__))")',
                    'echo "MOD_DPATH = $MOD_DPATH"',
                    # TODO: change to test command
                    'python -m pytest --cov={self.mod_name} $MOD_DPATH ../tests',
                    # 'python -m pytest -p pytester -p no:doctest --xdoctest --cov={self.mod_name} $MOD_DPATH ../tests',
                    # Move coverage file to a new name
                    # 'mv .coverage "../.coverage.$WORKSPACE_DNAME"',
                    'cd ..',
                ]
            },
            {
                'name': 'Upload sdist artifact',
                'uses': 'actions/upload-artifact@v3',
                'with': {
                    'name': 'wheels',
                    'path': './wheelhouse/*.tar.gz'
                }
            }
        ]
    }
    return job


def build_and_test_binpy_wheels(self):
    """
    cat ~/code/xcookie/xcookie/rc/test_binaries.yml.in | yq  .jobs.build_and_test_wheels

    Notes:
        Supported Action platforms:
            https://raw.githubusercontent.com/actions/python-versions/main/versions-manifest.json
    """
    supported_platform_info = get_supported_platform_info(self)
    os_list = supported_platform_info['os_list']
    included_runs = [
        {'os': 'windows-latest', 'arch': 'auto', 'cibw_skip': "*-win_amd64"},
    ]
    job = {
        'name': '${{ matrix.os }}, arch=${{ matrix.arch }}',
        'runs-on': '${{ matrix.os }}',
        'strategy': {
            'matrix': {
                'os': os_list,
                'cibw_skip': ['*-win32'],
                'arch': ['auto'],
                'include': included_runs,
            }
        },
        'steps': None,
    }

    job['steps'] = [
        Actions.checkout(),
        # Configure compilers for Windows 64bit.
        Actions.msvc_dev_cmd(bits=64, osvar='matrix.os'),
        # Configure compilers for Windows 32bit.
        Actions.msvc_dev_cmd(bits=32, osvar='matrix.os'),
        # Actions.setup_xcode(sensible=True),
        # Emulate aarch64 ppc64le s390x under linux
        Actions.setup_qemu(sensible=True),
        Actions.cibuildwheel(sensible=True),

        {
            "name": "Show built files",
            "shell": "bash",
            "run": "ls -la wheelhouse"
        },

        Actions.setup_python({
            'name': 'Set up Python 3.8 to combine coverage Linux',
            'if': "runner.os == 'Linux'",
            'with': {
                'python-version': 3.8
            }
        }),
        {
            'name': 'Combine coverage Linux',
            'if': "runner.os == 'Linux'",
            'run': ub.codeblock(
                '''
                echo '############ PWD'
                pwd
                cp .wheelhouse/.coverage* . || true
                ls -al
                python -m pip install coverage[toml]
                echo '############ combine'
                coverage combine . || true
                echo '############ XML'
                coverage xml -o ./tests/coverage.xml || true
                echo '############ FIND'
                find . -name .coverage.* || true
                find . -name coverage.xml  || true
                '''
            )

        },
        Actions.codecov_action({
            'name': 'Codecov Upload',
            'with': {
                'file': './tests/coverage.xml'
            }
        }),
        Actions.upload_artifact({
            'name': 'Upload wheels artifact',
            'with': {
                'name': 'wheels',
                'path': f"./wheelhouse/{self.mod_name}*.whl"
            }
        })
    ]
    return job


def get_supported_platform_info(self):
    os_list = []
    if 'linux' in self.config['os']:
        os_list.append('ubuntu-latest')
    if 'osx' in self.config['os']:
        os_list.append('macOS-latest')
    if 'win' in self.config['os']:
        os_list.append('windows-latest')

    cpython_versions = self.config['ci_cpython_versions']
    pypy_versions = [
        f'pypy-{v}'
        for v in self.config['ci_pypy_versions']
    ]
    # 3.4 is broken on github actions it seems
    cpython_versions_non34 = [v for v in cpython_versions if v != '3.4']

    supported_platform_info = {
        'os_list': os_list,
        'cpython_versions': cpython_versions_non34,
        'pypy_versions': pypy_versions,
        'min_python_version': self.config['supported_python_versions'][0],
        'max_python_version': self.config['supported_python_versions'][-1],
    }
    return supported_platform_info


def build_and_test_purepy_wheels(self):
    supported_platform_info = get_supported_platform_info(self)

    os_list = supported_platform_info['os_list']
    cpython_versions = supported_platform_info['cpython_versions']
    pypy_versions = supported_platform_info['pypy_versions']
    min_python_version = supported_platform_info['min_python_version']
    max_python_version = supported_platform_info['max_python_version']

    # Map the min/full loose/strict terminology to specific extra packages
    import ubelt as ub
    special_loose_tags = []
    if 'cv2' in self.tags:
        special_loose_tags.append('headless')
    special_strict_tags = [t + '-strict' for t in special_loose_tags]
    install_extra_tags = ub.udict({
        'minimal-loose'  : ['tests'] + special_loose_tags,
        'full-loose'     : ['tests', 'optional'] + special_loose_tags,
        'minimal-strict' : ['tests-strict', 'runtime-strict'] + special_strict_tags,
        'full-strict'    : ['tests-strict', 'runtime-strict', 'optional-strict'] + special_strict_tags,
    })
    install_extras = ub.udict({k: ','.join(v) for k, v in install_extra_tags.items()})

    test_env = {
        'INSTALL_EXTRAS': '${{ matrix.install-extras }}',
        'CI_PYTHON_VERSION': 'py${{ matrix.python-version }}'
    }
    special_install_lines = []
    special_strict_test_env = {}
    special_loose_test_env = {}
    if 'gdal' in self.tags:
        test_env['GDAL_REQUIREMENT_TXT'] = 'py${{ matrix.gdal-requirement-txt }}'
        special_install_lines.append('pip install -r $GDAL_REQUIREMENT_TXT')
        special_loose_test_env['gdal-requirement-txt'] = 'requirements/gdal.txt'
        # TODO: need to have logic for a gdal strict
        # special_strict_test_env['gdal-requirement-txt'] = 'requirements-strict/gdal.txt'
        special_strict_test_env['gdal-requirement-txt'] = 'requirements/gdal.txt'

    # Reduce the CI load, don't specify the entire product space
    arch = 'auto'
    include = []
    for osname in os_list:
        for extra in install_extras.take(['minimal-strict']):
            for pyver in [min_python_version]:
                include.append({'python-version': pyver, 'os': osname, 'install-extras': extra, 'arch': arch, **special_strict_test_env})

    for osname in os_list:
        for extra in install_extras.take(['full-strict']):
            for pyver in [max_python_version]:
                include.append({'python-version': pyver, 'os': osname, 'install-extras': extra, 'arch': arch, **special_strict_test_env})

    for osname in os_list[1:]:
        for extra in install_extras.take(['minimal-loose']):
            for pyver in [max_python_version]:
                include.append({'python-version': pyver, 'os': osname, 'install-extras': extra, 'arch': arch, **special_loose_test_env})

    for osname in os_list:
        for extra in install_extras.take(['full-loose']):
            for pyver in cpython_versions:
                include.append({'python-version': pyver, 'os': osname, 'install-extras': extra, 'arch': arch, **special_loose_test_env})

    for osname in os_list:
        for extra in install_extras.take(['full-loose']):
            for pyver in pypy_versions:
                include.append({'python-version': pyver, 'os': osname, 'install-extras': extra, 'arch': arch, **special_loose_test_env})

    for item in include:
        if item['python-version'] == '3.6' and item['os'] == 'ubuntu-latest':
            item['os'] = 'ubuntu-20.04'

    job = {
        'name': '${{ matrix.python-version }} on ${{ matrix.os }}, arch=${{ matrix.arch }} with ${{ matrix.install-extras }}',
        'runs-on': '${{ matrix.os }}',
        'strategy': {
            'matrix': {
                # 'os': os_list,
                # 'python-version': python_versions_non34,
                # 'install-extras': list(install_extras.take(['minimal-loose', 'full-loose'])),
                # 'arch': [
                #     'auto'
                # ],
                'include': include,
            }
        },
        'steps': None,
    }

    special_install_lines = []

    if 1:
        wheelhouse_dpath = 'wheelhouse'
        # get_modname_python = "import tomli; print(tomli.load(open('pyproject.toml', 'rb'))['tool']['xcookie']['mod_name'])"
        # get_modname_bash = f'python -c "{get_modname_python}"'

        get_wheel_fpath_python = f"import pathlib; print(str(sorted(pathlib.Path('{wheelhouse_dpath}').glob('$MOD_NAME*.whl'))[-1]).replace(chr(92), chr(47)))"
        get_wheel_fpath_bash = f'python -c "{get_wheel_fpath_python}"'

        get_mod_version_python = "from pkginfo import Wheel; print(Wheel('$WHEEL_FPATH').version)"
        get_mod_version_bash = f'python -c "{get_mod_version_python}"'

        # get_modpath_python = "import ubelt; print(ubelt.modname_to_modpath('${MOD_NAME}'))"
        get_modpath_python = f"import {self.mod_name}, os; print(os.path.dirname({self.mod_name}.__file__))"
        get_modpath_bash = f'python -c "{get_modpath_python}"'

    job['steps'] = [
        Actions.checkout(),
        Actions.msvc_dev_cmd(bits=64, osvar='matrix.os'),
        Actions.msvc_dev_cmd(bits=32, osvar='matrix.os'),
        Actions.setup_qemu(sensible=True),
        Actions.setup_python({
            'with': {'python-version': '${{ matrix.python-version }}'}
        }),
        {
            'name': 'Build pure wheel',
            'shell': 'bash',
            'run': [
                'python -m pip install pip -U',
                'python -m pip install setuptools>=0.8 build',
                f'python -m build --wheel --outdir {wheelhouse_dpath}',
            ]
        },
        {
            'name': 'Test wheel with ${{ matrix.install-extras }}',
            'shell': 'bash',
            'env': test_env,
            'run': [
                '# Find the path to the wheel',
                # f'WHEEL_FPATH=$(ls wheelhouse/{self.mod_name}*.whl)',

                f'ls {wheelhouse_dpath}',

                'pip install tomli pkginfo',
                f'MOD_NAME={self.mod_name}',
                'echo "MOD_NAME=$MOD_NAME"',
                f'WHEEL_FPATH=$({get_wheel_fpath_bash})',
                'echo "WHEEL_FPATH=$WHEEL_FPATH"',
                f'MOD_VERSION=$({get_mod_version_bash})',
                'echo "MOD_VERSION=$MOD_VERSION"',
            ] + special_install_lines +
            [
                '# Install the wheel (ensure we are using the version we just built)',
                # FIXME: remove all ambiguity in getting the wheel to have the right version
                '# NOTE: THE VERSION MUST BE NEWER THAN AN EXISTING PYPI VERSION OR THIS MAY FAIL',
                # 'python -m pip install ${WHEEL_FPATH}[${INSTALL_EXTRAS}]',
                f'pip install "$MOD_NAME[$INSTALL_EXTRAS]==$MOD_VERSION" -f {wheelhouse_dpath}',

                '# Create a sandboxed directory',
                'WORKSPACE_DNAME="testdir_${CI_PYTHON_VERSION}_${GITHUB_RUN_ID}_${RUNNER_OS}"',
                'mkdir -p $WORKSPACE_DNAME',
                'cd $WORKSPACE_DNAME',
                '# Get the path to the installed package and run the tests',
                f'MOD_DPATH=$({get_modpath_bash})',
                'echo "MOD_DPATH = $MOD_DPATH"',
                'python -m pytest -p pytester -p no:doctest --xdoctest --cov-config ../pyproject.toml --cov-report term --cov="$MOD_NAME" "$MOD_DPATH" ../tests',
                '# Move coverage file to a new name',
                'mv .coverage "../.coverage.$WORKSPACE_DNAME"',
                'cd ..',
            ]
        },
        {
            'name': 'Show built files',
            'shell': 'bash',
            'run': 'ls -la wheelhouse'
        },
        Actions.setup_python({
            'name': 'Set up Python 3.8 to combine coverage Linux',
            'if': "runner.os == 'Linux'",
            'with': {
                'python-version': 3.8
            }
        }),
        {
            'name': 'Combine coverage Linux',
            'if': "runner.os == 'Linux'",
            'run': ub.codeblock(
                '''
                echo '############ PWD'
                pwd
                ls -al
                python -m pip install coverage[toml]
                echo '############ combine'
                coverage combine .
                echo '############ XML'
                coverage xml -o ./tests/coverage.xml
                echo '############ FIND'
                find . -name .coverage.*
                find . -name coverage.xml
                '''
            )

        },
        Actions.codecov_action({
            'name': 'Codecov Upload',
            'with': {
                'file': './tests/coverage.xml'
            }
        }),
        Actions.upload_artifact({
            'name': 'Upload wheels artifact',
            'with': {
                'name': 'wheels',
                'path': f"./wheelhouse/{self.mod_name}*.whl"
            }
        })
    ]
    return job


def build_deploy(self, mode='live', needs=None):

    enable_gpg = self.config['enable_gpg']

    assert mode in {'live', 'test'}
    if mode == 'live':
        env = {
            'TWINE_REPOSITORY_URL': 'https://upload.pypi.org/legacy/',
            'TWINE_USERNAME': '${{ secrets.TWINE_USERNAME }}',
            'TWINE_PASSWORD': '${{ secrets.TWINE_PASSWORD }}',
        }
        if enable_gpg:
            # TODO: make this not me-specific
            env['CI_SECRET'] = '${{ secrets.CI_SECRET }}'
        condition = "github.event_name == 'push' && (startsWith(github.event.ref, 'refs/tags') || startsWith(github.event.ref, 'refs/heads/release'))"
    elif mode == 'test':
        env = {
            'TWINE_REPOSITORY_URL': 'https://test.pypi.org/legacy/',
            'TWINE_USERNAME': '${{ secrets.TEST_TWINE_USERNAME }}',
            'TWINE_PASSWORD': '${{ secrets.TEST_TWINE_PASSWORD }}',
        }
        if enable_gpg:
            # TODO: make this not me-specific
            env['CI_SECRET'] = '${{ secrets.CI_SECRET }}'

        condition = "github.event_name == 'push' && ! startsWith(github.event.ref, 'refs/tags') && ! startsWith(github.event.ref, 'refs/heads/release')"
    else:
        raise KeyError(mode)

    if needs is None:
        needs = []

    if enable_gpg:
        run = [
            # 'ls -al',
            'GPG_EXECUTABLE=gpg',
            '$GPG_EXECUTABLE --version',
            'openssl version',
            '$GPG_EXECUTABLE --list-keys',
            'echo "Decrypting Keys"',
            'openssl enc -aes-256-cbc -pbkdf2 -md SHA512 -pass env:CI_SECRET -d -a -in dev/ci_public_gpg_key.pgp.enc | $GPG_EXECUTABLE --import',
            'openssl enc -aes-256-cbc -pbkdf2 -md SHA512 -pass env:CI_SECRET -d -a -in dev/gpg_owner_trust.enc | $GPG_EXECUTABLE --import-ownertrust',
            'openssl enc -aes-256-cbc -pbkdf2 -md SHA512 -pass env:CI_SECRET -d -a -in dev/ci_secret_gpg_subkeys.pgp.enc | $GPG_EXECUTABLE --import',
            'echo "Finish Decrypt Keys"',
            '$GPG_EXECUTABLE --list-keys || true',
            '$GPG_EXECUTABLE --list-keys  || echo "first invocation of gpg creates directories and returns 1"',
            '$GPG_EXECUTABLE --list-keys',
            'VERSION=$(python -c "import setup; print(setup.VERSION)")',
            'pip install twine',
            # 'pip install six pyopenssl ndg-httpsclient pyasn1 -U --user',
            # 'pip install urllib3 requests[security] twine --user',
            'pip install urllib3 requests[security] twine',
            'GPG_KEYID=$(cat dev/public_gpg_key)',
            '''echo "GPG_KEYID = '$GPG_KEYID'"''',
            ('DO_GPG=True GPG_KEYID=$GPG_KEYID TWINE_REPOSITORY_URL=${TWINE_REPOSITORY_URL} '
             'TWINE_PASSWORD=$TWINE_PASSWORD TWINE_USERNAME=$TWINE_USERNAME '
             'GPG_EXECUTABLE=$GPG_EXECUTABLE DO_UPLOAD=True DO_TAG=False '
             './publish.sh'),
        ]
    else:
        run = [
            # 'pip install requests[security] twine pyopenssl ndg-httpsclient pyasn1 -U',
            'pip install urllib3 requests[security] twine -U',
            'twine upload --username=__token__ --password=$TWINE_PASSWORD --repository-url "$TWINE_REPOSITORY_URL" wheelhouse/* --skip-existing --verbose || { echo "failed to twine upload" ; exit 1; }',
        ]

    job = {
        'name': f"Uploading {mode.capitalize()} to PyPi",
        'runs-on': 'ubuntu-latest',
        'if': condition,
        'needs': list(needs),
        'steps': [
            Actions.checkout(name='Checkout source'),
            Actions.download_artifact({'name': 'Download wheels and sdist', 'with': {'name': 'wheels', 'path': 'wheelhouse'}}),
            {'name': 'Show files to upload', 'shell': 'bash', 'run': 'ls -la wheelhouse'},
            # TODO: it might make sense to make this a script that is invoked
            {
                'name': 'Sign and Publish',
                'env': env,
                'run': run,
            }
        ]
    }
    return job
