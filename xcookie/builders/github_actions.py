import ubelt as ub
from xcookie.builders import common_ci
from xcookie.util_yaml import Yaml


class Actions:
    """
    Help build Github Action JSON objects

    Example:
        >>> from xcookie.builders.github_actions import Actions
        >>> import types
        >>> for attr_name in dir(Actions):
        >>>     if not attr_name.startswith('_'):
        >>>         attr = getattr(Actions, attr_name)
        >>>         if isinstance(attr, types.MethodType):
        >>>             print(attr_name)
        >>>             action = attr()

    Example:
        >>> action = Actions.codecov_action(Yaml.coerce(
            '''
            name: Codecov Upload
            with:
              file: ./coverage.xml
              token: ${{ secrets.CODECOV_TOKEN }}
            '''))
        >>> print(type(action))
        >>> print(f'action = {ub.urepr(action, nl=1)}')
    """
    action_versions = {
        'checkout': 'actions/checkout@v3',
        'setup-python': 'actions/setup-python@v5',
    }

    @classmethod
    def _available_action_methods(Actions):
        import types
        for attr_name in dir(Actions):
            if not attr_name.startswith('_'):
                attr = getattr(Actions, attr_name)
                if isinstance(attr, types.MethodType):
                    if attr.__self__ is Actions:
                        yield attr

    @classmethod
    def _check_for_updates(Actions):
        # List all actions
        # https://api.github.com/repos/pypa/cibuildwheel/releases/latest
        import requests
        update_lines = []
        for attr in Actions._available_action_methods():
            action = attr()
            if 'uses' in action:
                suffix, current = action['uses'].split('@')
                url = f'https://api.github.com/repos/{suffix}/releases/latest'
                resp = requests.get(url)
                data = resp.json()
                latest = data['tag_name']
                if current != latest:
                    update_line = (f'Update: {suffix} from {current} to {latest}')
                    update_lines.append(update_line)
                    print(update_line)
                    print('data = {}'.format(ub.urepr(data, nl=1)))
        print('\n'.join(update_lines))

    @classmethod
    def action(cls, *args, **kwargs):
        """
        The generic action.

        TODO: support commented YAML maps
        """
        action = ub.udict(kwargs.copy())
        for _ in args:
            if _ is not None:
                action.update(_)
        if 'name' in action:
            reordered = action & ['name', 'uses']
            action = reordered | (action - reordered)
        return dict(action)

    @classmethod
    def checkout(cls, *args, **kwargs):
        return cls.action({
            'name': 'Checkout source',
            'uses': 'actions/checkout@v4.2.2'
        }, *args, **kwargs)

    @classmethod
    def setup_python(cls, *args, **kwargs):
        return cls.action({
            'name': 'Setup Python',
            'uses': 'actions/setup-python@v5.6.0'
        }, *args, **kwargs)

    @classmethod
    def codecov_action(cls, *args, **kwargs):
        """
        References:
            https://github.com/codecov/codecov-action
        """
        return cls.action({
            'uses': 'codecov/codecov-action@v5.4.3',
        }, *args, **kwargs)

    @classmethod
    def combine_coverage(cls, *args, **kwargs):
        return cls.action({
            'name': 'Combine coverage Linux',
            'if': "runner.os == 'Linux'",
            'run': ub.codeblock(
                '''
                echo '############ PWD'
                pwd
                cp .wheelhouse/.coverage* . || true
                ls -al
                uv pip install coverage[toml] | pip install coverage[toml]
                echo '############ combine'
                coverage combine . || true
                echo '############ XML'
                coverage xml -o ./coverage.xml || true
                echo '### The cwd should now have a coverage.xml'
                ls -altr
                pwd
                '''
            )

        }, *args, **kwargs)

    @classmethod
    def upload_artifact(cls, *args, **kwargs):
        return cls.action({
            'uses': 'actions/upload-artifact@v4.4.0'
            # Rollback to 3.x due to
            # https://github.com/actions/upload-artifact/issues/478
            # todo: migrate
            # https://github.com/actions/upload-artifact/blob/main/docs/MIGRATION.md#multiple-uploads-to-the-same-named-artifact
            # 'uses': 'actions/upload-artifact@v3.1.3'
        }, *args, **kwargs)

    @classmethod
    def download_artifact(cls, *args, **kwargs):
        return cls.action({
            'uses': 'actions/download-artifact@v4.1.8',
            # 'uses': 'actions/download-artifact@v2.1.1',
        }, *args, **kwargs)

    @classmethod
    def msvc_dev_cmd(cls, *args, osvar=None, bits=None, test_condition=None, **kwargs):
        if osvar is not None:
            # hack, just keep it this way for now
            if bits == 32:
                # FIXME; we dont want to rely on the cibw_skip variable
                # kwargs['if'] = "matrix.os == 'windows-latest' && matrix.cibw_skip == '*-win_amd64'"
                if test_condition is not None:
                    kwargs['if'] = "matrix.os == 'windows-latest' && " + test_condition
                else:
                    kwargs['if'] = "matrix.os == 'windows-latest'"
            else:
                if test_condition is not None:
                    kwargs['if'] = "matrix.os == 'windows-latest' && " + test_condition
                else:
                    kwargs['if'] = "matrix.os == 'windows-latest'"
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
        return cls.action({
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
        return cls.action({
            'name': 'Set up QEMU',
            'uses': 'docker/setup-qemu-action@v3.0.0',
        }, *args, **kwargs)

    @classmethod
    def setup_xcode(cls, *args, sensible=False, **kwargs):
        if sensible:
            kwargs.update({
                'if': "matrix.os == 'macOS-latest'",
                'with': {'xcode-version': 'latest-stable'}
            })

        # Emulate aarch64 ppc64le s390x under linux
        return cls.action({
            'name': 'Install Xcode',
            'uses': 'maxim-lobanov/setup-xcode@v1',
        }, *args, **kwargs)

    @classmethod
    def setup_ipfs(cls, *args, **kwargs):
        # https://github.com/marketplace/actions/ipfs-setup-action
        return cls.action({
            'name': 'Set up IPFS',
            'uses': 'ibnesayeed/setup-ipfs@0.6.0',
            'with': {
                'ipfs_version': '0.14.0',
                'run_daemon': True,
            },
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
                    'CIBW_ARCHS_LINUX': '${{ matrix.arch }}',
                    'CIBW_ENVIRONMENT': 'PYTHONUTF8=1',  # for windows
                    'PYTHONUTF8': '1',  # for windows
                }
            })

        # Emulate aarch64 ppc64le s390x under linux
        return cls.action({
            'name': 'Build binary wheels',
            # 'uses': 'pypa/cibuildwheel@v2.16.2',
            # 'uses': 'pypa/cibuildwheel@v2.17.0',
            # 'uses': 'pypa/cibuildwheel@v2.21.0',
            'uses': 'pypa/cibuildwheel@v3.1.2',
        }, *args, **kwargs)


def build_github_actions(self):
    """
    Ignore:
        cat ~/code/xcookie/xcookie/rc/tests.yml.in | yq  .jobs.lint
        cat ~/code/xcookie/xcookie/rc/tests.yml.in | yq  .jobs.build_and_test_sdist
        cat ~/code/xcookie/xcookie/rc/tests.yml.in | yq  .jobs.deploy
        cat ~/code/xcookie/xcookie/rc/tests.yml.in | yq  .

    CommandLine:
        xdoctest -m xcookie.builders.github_actions build_github_actions

    Example:
        >>> from xcookie.builders.github_actions import *  # NOQA
        >>> from xcookie.main import XCookieConfig
        >>> from xcookie.main import TemplateApplier
        >>> config = XCookieConfig(tags=['purepy'], repo_name='mymod')
        >>> config['ci_cpython_versions'] = config['ci_cpython_versions'][-2:]
        >>> self = TemplateApplier(config)
        >>> text = build_github_actions(self)
        >>> print(ub.highlight_code(text, 'yaml'))
    """
    jobs = Yaml.Dict({})
    if self.config.linter:
        jobs['lint_job'] = lint_job(self)
        jobs['lint_job'].yaml_set_start_comment(ub.codeblock(
            '''
            ##
            Run quick linting and typing checks.
            To disable all linting add "linter=false" to the xcookie config.
            To disable type checks add "notypes" to the xcookie tags.
            ##
            '''), indent=4)

    if 'purepy' in self.tags:
        name = 'PurePyCI'
        purepy_jobs = Yaml.Dict({})
        if 'nosrcdist' not in self.tags:
            purepy_jobs['build_and_test_sdist'] = build_and_test_sdist_job(self)
            purepy_jobs['build_and_test_sdist'].yaml_set_start_comment(ub.codeblock(
                '''
                ##
                Build the pure python package from source and test it in the
                same environment.
                ##
                '''), indent=4)

        purepy_jobs['build_purepy_wheels'] = Yaml.Dict(build_purewheel_job(self))
        purepy_jobs['test_purepy_wheels'] = Yaml.Dict(test_wheels_job(self, needs=['build_purepy_wheels']))

        purepy_jobs['build_purepy_wheels'].yaml_set_start_comment(ub.codeblock(
            '''
            ##
            Build the pure-python wheels independently on a per-platform basis.
            These will be tested later in the build_purepy_wheels step.
            ##
            '''), indent=4)
        purepy_jobs['build_purepy_wheels'].yaml_set_start_comment(ub.codeblock(
            '''
            ##
            Download and test the pure-python wheels that were build in the
            build_purepy_wheels and test them in this independent environment.
            ##
            '''), indent=4)

        deploy_needs = list(purepy_jobs.keys())
        deploy_needs = set(deploy_needs) - {'test_purepy_wheels'}
        jobs.update(purepy_jobs)
    elif 'binpy' in self.tags:
        name = 'BinPyCI'
        binpy_jobs = Yaml.Dict({})
        if 'nosrcdist' not in self.tags:
            binpy_jobs['build_and_test_sdist'] = build_and_test_sdist_job(self)
            binpy_jobs['build_and_test_sdist'].yaml_set_start_comment(ub.codeblock(
                '''
                ##
                Build the binary package from source and test it in the same
                environment.
                ##
                '''), indent=4)

        binpy_jobs['build_binpy_wheels'] = Yaml.Dict(build_binpy_wheels_job(self))
        binpy_jobs['test_binpy_wheels'] = Yaml.Dict(test_wheels_job(self, needs=['build_binpy_wheels']))

        binpy_jobs['build_binpy_wheels'].yaml_set_start_comment(ub.codeblock(
            '''
            ##
            Build the binary wheels. Note: even though cibuildwheel will test
            them internally here, we will test them independently later in the
            test_binpy_wheels step.
            ##
            '''), indent=4)
        binpy_jobs['test_binpy_wheels'].yaml_set_start_comment(ub.codeblock(
            '''
            ##
            Download the previously build binary wheels from the
            build_binpy_wheels step, and test them in an independent
            environment.
            ##
            '''), indent=4)
        deploy_needs = list(binpy_jobs.keys())
        deploy_needs = set(deploy_needs) - {'test_binpy_wheels'}
        jobs.update(binpy_jobs)
    else:
        raise Exception('Need to specify binpy or purepy in tags')

    jobs['test_deploy'] = build_deploy(self, mode='test', needs=deploy_needs)
    jobs['live_deploy'] = build_deploy(self, mode='live', needs=deploy_needs)

    if 1:
        # New action to create a proper release
        jobs['release'] = build_github_release(self, needs=['live_deploy'])

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
        # See: https://github.com/Erotemic/xcookie

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

    if 'erotemic' in self.tags:
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
    else:
        footer = ''

    text = header + '\n\n' + Yaml.dumps(body) + '\n\n' + footer
    return text


def lint_job(self):
    supported_platform_info = common_ci.get_supported_platform_info(self)
    main_python_version = supported_platform_info['main_python_version']
    job = {
        'runs-on': 'ubuntu-latest',
        'steps': [
            Actions.checkout(),
            Actions.setup_python({
                'name': f'Set up Python {main_python_version} for linting',
                'with': {
                    'python-version': main_python_version,
                }
            }),
            {
                'name': 'Install dependencies',
                'run': ub.codeblock(
                    f'''
                    {self.UPDATE_PIP}
                    {self.PIP_INSTALL} flake8
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
        ]
    }

    if 'notypes' not in self.tags:
        mypy_check_commands = common_ci.make_mypy_check_parts(self)
        job['steps'].append(
            {
                'name': 'Typecheck with mypy',
                'run': mypy_check_commands
            }
        )
    return Yaml.Dict(job)


def build_and_test_sdist_job(self):
    supported_platform_info = common_ci.get_supported_platform_info(self)
    main_python_version = supported_platform_info['main_python_version']
    wheelhouse_dpath = 'wheelhouse'

    build_parts = common_ci.make_build_sdist_parts(self, wheelhouse_dpath)

    job = {
        'name': 'Build sdist',
        'runs-on': 'ubuntu-latest',
        'steps': [
            Actions.checkout(),
            Actions.setup_python({
                'name': f'Set up Python {main_python_version}',
                'with': {'python-version': main_python_version}}),
            {
                'name': 'Upgrade pip',
                'run': [_ for _ in [
                    f'{self.UPDATE_PIP}',
                    f'{self.PIP_INSTALL_PREFER_BINARY} -r requirements/tests.txt',
                    f'{self.PIP_INSTALL_PREFER_BINARY} -r requirements/runtime.txt',
                    f'{self.PIP_INSTALL_PREFER_BINARY} -r requirements/headless.txt' if 'cv2' in self.tags else None,
                    f'{self.PIP_INSTALL_PREFER_BINARY} -r requirements/gdal.txt' if 'gdal' in self.tags else None,
                ] if _ is not None]
            },
            {
                'name': 'Build sdist',
                # "run": "python setup.py sdist\n"
                'shell': 'bash',
                'run': build_parts['commands'],
            },
            {
                'name': 'Install sdist',
                'run': [
                    f'ls -al {wheelhouse_dpath}',
                    f'{self.PIP_INSTALL_PREFER_BINARY} {wheelhouse_dpath}/{self.pkg_name}*.tar.gz -v',
                ]
            },
            {
                'name': 'Test minimal loose sdist',
                'env': {
                    # So far not needed, but once we bump to 3.14 this needs to be
                    # set whenever `pytest` is run with `coverage`
                    # (see the `test_binpy_wheels` jobs)
                    'COVERAGE_CORE': 'ctrace'
                },
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
                    f'python -m pytest --verbose --cov={self.mod_name} $MOD_DPATH ../tests',
                    'cd ..',
                ]
            },
            {
                'name': 'Test full loose sdist',
                'env': {
                    'COVERAGE_CORE': 'ctrace'
                },
                'run': [
                    'pwd',
                    'ls -al',
                    f'{self.PIP_INSTALL_PREFER_BINARY} -r requirements/headless.txt' if 'cv2' in self.tags else 'true',
                    '# Run in a sandboxed directory',
                    'WORKSPACE_DNAME="testsrcdir_full_${CI_PYTHON_VERSION}_${GITHUB_RUN_ID}_${RUNNER_OS}"',
                    'mkdir -p $WORKSPACE_DNAME',
                    'cd $WORKSPACE_DNAME',
                    '# Run the tests',
                    '# Get path to installed package',
                    f'MOD_DPATH=$(python -c "import {self.mod_name}, os; print(os.path.dirname({self.mod_name}.__file__))")',
                    'echo "MOD_DPATH = $MOD_DPATH"',
                    # TODO: change to test command
                    f'python -m pytest --verbose --cov={self.mod_name} $MOD_DPATH ../tests',
                    # 'python -m pytest -p pytester -p no:doctest --xdoctest --cov={self.mod_name} $MOD_DPATH ../tests',
                    # Move coverage file to a new name
                    # 'mv .coverage "../.coverage.$WORKSPACE_DNAME"',
                    'cd ..',
                ]
            },
            Actions.upload_artifact({
                'name': 'Upload sdist artifact',
                'with': {
                    'name': 'sdist_wheels',
                    'path': build_parts['artifact']
                }
            })
        ]
    }
    return Yaml.Dict(job)


def build_binpy_wheels_job(self):
    """
    Builds the action for binary python packages that creates the wheels.

    Returns:
        Dict: yaml structure

    cat ~/code/xcookie/xcookie/rc/test_binaries.yml.in | yq  .jobs.build_and_test_wheels

    Notes:
        Supported Action platforms:
            https://raw.githubusercontent.com/actions/python-versions/main/versions-manifest.json
    """
    supported_platform_info = common_ci.get_supported_platform_info(self)
    os_list = supported_platform_info['os_list']
    main_python_version = supported_platform_info['main_python_version']

    pyproj_config = self.config._load_pyproject_config()
    cibw_skip = pyproj_config.get('tool', {}).get('cibuildwheel', {}).get('skip', '')
    if isinstance(cibw_skip, list):
        cibw_skip = ' '.join(cibw_skip)
    explicit_skips = ' ' + cibw_skip
    print(f'explicit_skips={explicit_skips}')

    # Fixme: how to get this working again?
    WITH_WIN_32BIT = False

    if 'win' in self.config['os']:
        if WITH_WIN_32BIT:
            included_runs = [
                {'os': 'windows-latest', 'arch': 'auto', 'cibw_skip': ("*-win_amd64" + explicit_skips).strip()},
            ]
        else:
            included_runs = []
    else:
        included_runs = []

    matrix = Yaml.Dict({})
    matrix.yaml_set_start_comment(ub.codeblock(
        '''
        Normally, xcookie generates explicit lists of platforms to build / test
        on, but in this case cibuildwheel does that for us, so we need to just
        set the environment variables for cibuildwheel. These are parsed out of
        the standard [tool.cibuildwheel] section in pyproject.toml and set
        explicitly here.
        '''), indent=8)

    # Seems like we dont need explicit macos-13
    # and it could produce issues:
    # https://github.com/pypa/gh-action-pypi-publish/issues/215
    # if 'osx' in self.config['os']:
    #     # os_list.append('macos-14')
    #     os_list.append('macos-13')

    matrix['os'] = os_list

    if 'win' in self.config['os']:
        matrix['cibw_skip'] = [('*-win32' + explicit_skips).strip()]
    else:
        matrix['cibw_skip'] = [explicit_skips.strip()]
    matrix['arch'] = ['auto']
    if included_runs:
        matrix['include'] = included_runs

    conditional_actions = []
    if 'win' in self.config['os']:
        conditional_actions += [
            Actions.msvc_dev_cmd(bits=64, osvar='matrix.os', test_condition="${{ contains(matrix.cibw_skip, '*-win32') }}"),
        ]

        if WITH_WIN_32BIT:
            conditional_actions += [
                Actions.msvc_dev_cmd(bits=32, osvar='matrix.os', test_condition="${{ contains(matrix.cibw_skip, '*-win_amd64') }}"),
            ]

    job = Yaml.Dict({
        'name': '${{ matrix.os }}, arch=${{ matrix.arch }}',
        'runs-on': '${{ matrix.os }}',
        'strategy': {
            'fail-fast': False,
            'matrix': matrix,
        },
        'steps': None,
    })

    job_steps = []
    #job_steps += [Actions.setup_xcode(sensible=True)]

    # Emulate aarch64 ppc64le s390x under linux
    job_steps += [Actions.checkout()]
    job_steps += conditional_actions

    USE_ABI3 = True
    if USE_ABI3:
        # Hack in abi3 support, todo: clean up later.
        abi3_action = Actions.cibuildwheel(sensible=True)
        # TODO: use min python
        abi3_action['env']['CIBW_CONFIG_SETTINGS'] = '--build-option=--py-limited-api=cp38'
        abi3_action['env']['CIBW_BUILD'] = 'cp38-*'

    job_steps += [
        Actions.setup_qemu(sensible=True),
        abi3_action,
        Actions.cibuildwheel(sensible=True),
    ]
    job_steps += [
        {
            "name": "Show built files",
            "shell": "bash",
            "run": "ls -la wheelhouse"
        },

        Actions.setup_python({
            'name': f'Set up Python {main_python_version} to combine coverage',
            'if': "runner.os == 'Linux'",
            'with': {
                'python-version': main_python_version
            }
        }),
        Actions.combine_coverage(),
        # https://github.com/github/docs/issues/6861
        Actions.codecov_action(Yaml.coerce(
            '''
            name: Codecov Upload
            env:
              HAVE_CODECOV_TOKEN: ${{ secrets.CODECOV_TOKEN != '' }}
            # Only upload coverage if we have the token
            if: ${{ env.HAVE_PERSONAL_TOKEN == 'true' }}
            with:
              file: ./coverage.xml
              token: ${{ secrets.CODECOV_TOKEN }}
            ''')),

        Actions.codecov_action({
            'name': 'Codecov Upload',
            'with': {
                'file': './coverage.xml',
                'token': '${{ secrets.CODECOV_TOKEN }}',
            }
        }),
        Actions.upload_artifact({
            'name': 'Upload wheels artifact',
            'with': {
                'name': 'wheels-${{ matrix.os }}-${{ matrix.arch }}',
                'path': f"./wheelhouse/{self.mod_name}*.whl"
            }
        })
    ]
    job['steps'] = job_steps
    return job


def build_purewheel_job(self):
    wheelhouse_dpath = 'wheelhouse'
    supported_platform_info = common_ci.get_supported_platform_info(self)
    # os_list = supported_platform_info['os_list']
    main_python_version = supported_platform_info['main_python_version']
    # pypy_versions = supported_platform_info['pypy_versions']
    # min_python_version = supported_platform_info['min_python_version']
    # max_python_version = supported_platform_info['max_python_version']
    job = {
        'name': '${{ matrix.python-version }} on ${{ matrix.os }}, arch=${{ matrix.arch }} with ${{ matrix.install-extras }}',
        'runs-on': '${{ matrix.os }}',
        'strategy': {
            'fail-fast': False,
            'matrix': {
                # Build on one of the platforms with the newest python version
                # (it does not really matter)
                'os': ['ubuntu-latest'],  # os_list[0:1],
                'python-version': [main_python_version],
                'arch': ['auto'],
            }
        },
        'steps': None,
    }
    build_parts = common_ci.make_build_wheel_parts(self, wheelhouse_dpath)
    job['steps'] = [
        Actions.checkout(),
        Actions.setup_qemu(sensible=True),
        Actions.setup_python({
            'with': {'python-version': '${{ matrix.python-version }}'}
        }),
        {
            'name': 'Build pure wheel',
            'shell': 'bash',
            'run': build_parts['commands'],
        },
        {
            'name': 'Show built files',
            'shell': 'bash',
            'run': f'ls -la {wheelhouse_dpath}'
        },
        Actions.upload_artifact({
            'name': 'Upload wheels artifact',
            'with': {
                # 'name': 'wheels',
                'name': 'wheels-${{ matrix.os }}-${{ matrix.arch }}',
                'path': build_parts['artifact'],
            }
        })
    ]
    return job


def test_wheels_job(self, needs=None):
    wheelhouse_dpath = 'wheelhouse'
    supported_platform_info = common_ci.get_supported_platform_info(self)

    os_list = supported_platform_info['os_list']

    install_extra_versions = supported_platform_info['install_extra_versions']

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

    special_strict_test_env = {}
    special_loose_test_env = {}
    if 'gdal' in self.tags:
        special_loose_test_env['gdal-requirement-txt'] = 'requirements/gdal.txt'
        # TODO: need to have better logic for gdal strict that doesn't require
        # separate tracked files.
        # special_strict_test_env['gdal-requirement-txt'] = 'requirements-strict/gdal.txt'
        special_strict_test_env['gdal-requirement-txt'] = 'requirements/gdal-strict.txt'

    platform_basis = [
        {'os': osname, 'arch': 'auto'}
        for osname in os_list
    ]

    # Reduce the CI load, don't specify the entire product space
    # arch = 'auto'
    include = []
    for platkw in platform_basis:
        for extra in install_extras.take(['minimal-strict']):
            for pyver in install_extra_versions['minimal-strict']:
                include.append({
                    'python-version': pyver, 'install-extras': extra,
                    **platkw, **special_strict_test_env})

    for platkw in platform_basis:
        for extra in install_extras.take(['full-strict']):
            for pyver in install_extra_versions['full-strict']:
                include.append({
                    'python-version': pyver, 'install-extras': extra,
                    **platkw, **special_strict_test_env})

    for platkw in platform_basis[1:]:
        for extra in install_extras.take(['minimal-loose']):
            for pyver in install_extra_versions['minimal-loose']:
                include.append({
                    'python-version': pyver, 'install-extras': extra,
                    **platkw, **special_loose_test_env})

    for platkw in platform_basis:
        for extra in install_extras.take(['full-loose']):
            for pyver in install_extra_versions['full-loose']:
                include.append({
                    'python-version': pyver, 'install-extras': extra,
                    **platkw, **special_loose_test_env})

    # TODO: implement pypy support
    # pypy_versions = supported_platform_info['pypy_versions']
    # for platkw in platform_basis:
    #     for extra in install_extras.take(['full-loose']):
    #         for pyver in pypy_versions:
    #             include.append({
    #                 'python-version': pyver, 'install-extras': extra,
    #                 **platkw, **special_loose_test_env})

    assert not ub.find_duplicates(map(ub.hash_data, include))

    for item in include:
        # Available os names:
        # https://docs.github.com/en/actions/using-github-hosted-runners/about-github-hosted-runners/about-github-hosted-runners#standard-github-hosted-runners-for-public-repositories
        if item['python-version'] == '3.6' and item['os'] == 'ubuntu-latest':
            # This image is no longer supported, and does not work apparently
            item['os'] = 'ubuntu-20.04'
            # item['os'] = 'ubuntu-18.04'
        if item['python-version'] == '3.7' and item['os'] == 'ubuntu-latest':
            item['os'] = 'ubuntu-22.04'
        if item['python-version'] == '3.6' and item['os'] == 'macOS-latest':
            item['os'] = 'macos-13'
        if item['python-version'] == '3.7' and item['os'] == 'macOS-latest':
            item['os'] = 'macos-13'

    if True:
        # hack, todo better specific disable for rc versions
        # if self.config.mod_name == 'xcookie':
        #     filtered_include = []
        #     for item in include:
        #         flag = True
        #         if 'rc' in item['python-version']:
        #             if 'windows' in item['os']:
        #                 flag = False
        #         if flag:
        #             filtered_include.append(item)
        #     include = filtered_include
        from fnmatch import translate as glob_to_re
        import re

        def compile_rules(rules):
            return [
                {k: re.compile(glob_to_re(str(pat))) for k, pat in rule.items()}
                for rule in (rules or ())
            ]

        def is_blocked_compiled(item, compiled_rules):
            for crule in compiled_rules:
                if all(regex.fullmatch(str(item.get(k, ""))) for k, regex in crule.items()):
                    return True
            return False

        ci_blocklist = Yaml.coerce(self.config.ci_blocklist)
        compiled = compile_rules(ci_blocklist)
        include = [it for it in include if not is_blocked_compiled(it, compiled)]

    condition = "! startsWith(github.event.ref, 'refs/heads/release')"
    job = Yaml.Dict({
        'name': '${{ matrix.python-version }} on ${{ matrix.os }}, arch=${{ matrix.arch }} with ${{ matrix.install-extras }}',
        'if': condition,
        'runs-on': '${{ matrix.os }}',
        'needs': sorted(needs),
        'strategy': {
            'fail-fast': False,
            'matrix': Yaml.Dict({
                # 'os': os_list,
                # 'python-version': python_versions_non34,
                # 'install-extras': list(install_extras.take(['minimal-loose', 'full-loose'])),
                # 'arch': [
                #     'auto'
                # ],
                'include': include,
            })
        },
        'steps': None,
    })

    job['strategy']['matrix'].yaml_set_start_comment(ub.codeblock(
        '''
        Xcookie generates an explicit list of environments that will be used
        for testing instead of using the more concise matrix notation.
        '''), indent=8)

    # if 1:
    #     # get_modname_python = "import tomli; print(tomli.load(open('pyproject.toml', 'rb'))['tool']['xcookie']['mod_name'])"
    #     # get_modname_bash = f'python -c "{get_modname_python}"'

    #     # get_wheel_fpath_python = f"import pathlib; print(str(sorted(pathlib.Path('{wheelhouse_dpath}').glob('$MOD_NAME*.whl'))[-1]).replace(chr(92), chr(47)))"
    #     # get_wheel_fpath_bash = f'python -c "{get_wheel_fpath_python}"'

    #     # get_mod_version_python = "from pkginfo import Wheel; print(Wheel('$WHEEL_FPATH').version)"
    #     # get_mod_version_bash = f'python -c "{get_mod_version_python}"'

    #     # # get_modpath_python = "import ubelt; print(ubelt.modname_to_modpath('${MOD_NAME}'))"
    #     # get_modpath_python = f"import {self.mod_name}, os; print(os.path.dirname({self.mod_name}.__file__))"
    #     # get_modpath_bash = f'python -c "{get_modpath_python}"'

    install_env = {'INSTALL_EXTRAS': '${{ matrix.install-extras }}'}

    special_install_lines = []
    if 'gdal' in self.tags:
        install_env['GDAL_REQUIREMENT_TXT'] = '${{ matrix.gdal-requirement-txt }}'
        special_install_lines.append(f'{self.PIP_INSTALL} -r "$GDAL_REQUIREMENT_TXT"')

    if 'ibeis' == self.mod_name:
        custom_before_test_lines = [
            'mkdir -p "ci_ibeis_workdir"',
            'echo "About to reset workdirs"',
            'python -m ibeis --set-workdir="$(readlink -f ci_ibeis_workdir)" --nogui',
            'python -m ibeis --resetdbs',
        ]
    else:
        custom_before_test_lines = []

    action_steps = []
    action_steps += [
        Actions.checkout(),
    ]
    if 'win' in self.config['os']:
        action_steps += [
            Actions.msvc_dev_cmd(bits=64, osvar='matrix.os'),
            # Actions.msvc_dev_cmd(bits=32, osvar='matrix.os'),  # need a test condition if we are going to have both.
        ]

    if 'ipfs' in self.config['tags']:
        action_steps += [
            Actions.setup_ipfs(),
        ]
    action_steps += [
        Actions.setup_qemu(sensible=True),
        Actions.setup_python({'with': {'python-version': '${{ matrix.python-version }}'}}),
        Actions.download_artifact({
            'name': 'Download wheels',
            'with': {
                # 'name': 'wheels',
                'pattern': 'wheels-*',
                'merge-multiple': True,
                'path': 'wheelhouse'
            }}),
    ]

    workspace_dname = 'testdir_${CI_PYTHON_VERSION}_${GITHUB_RUN_ID}_${RUNNER_OS}'

    # HACK
    WITH_COVERAGE = ('ibeis' != self.mod_name)
    if WITH_COVERAGE:
        custom_after_test_commands = [
            'ls -al',
            '# Move coverage file to a new name',
            'mv .coverage "../.coverage.$WORKSPACE_DNAME"',
            'echo "changing directory back to th repo root"',
            'cd ..',
            'ls -al',
        ]
    else:
        custom_after_test_commands = [
        ]
    install_and_test_wheel_parts = common_ci.make_install_and_test_wheel_parts(
        self, wheelhouse_dpath, special_install_lines, workspace_dname,
        custom_before_test_lines=custom_before_test_lines,
        custom_after_test_commands=custom_after_test_commands,
    )

    action_steps.append(Actions.action({
        'name': 'Install wheel ${{ matrix.install-extras }}',
        'shell': 'bash',
        'env': install_env,
        'run': install_and_test_wheel_parts['install_wheel_commands'],
    }))

    action_steps.append(Actions.action({
        'name': 'Test wheel ${{ matrix.install-extras }}',
        'shell': 'bash',
        'env': {
            'CI_PYTHON_VERSION': 'py${{ matrix.python-version }}',
            'COVERAGE_CORE': 'ctrace',
        },
        'run': install_and_test_wheel_parts['test_wheel_commands'],
    }))
    if WITH_COVERAGE:
        action_steps += [
            Actions.combine_coverage(),
            Actions.codecov_action({
                'name': 'Codecov Upload',
                'with': {
                    'file': './coverage.xml',
                    'token': '${{ secrets.CODECOV_TOKEN }}',
                }
            }),
        ]
    job['steps'] = action_steps
    return job


def build_deploy(self, mode='live', needs=None):
    """
    CommandLine:
        xdoctest -m /home/joncrall/code/xcookie/xcookie/builders/github_actions.py build_deploy
        xdoctest -m xcookie.builders.github_actions build_deploy

    Example:
        >>> from xcookie.builders.github_actions import *  # NOQA
        >>> from xcookie.main import XCookieConfig
        >>> from xcookie.main import TemplateApplier
        >>> config = XCookieConfig(tags=['purepy'], remote_group='Org', repo_name='Repo')
        >>> self = TemplateApplier(config)
        >>> self._presetup()
        >>> text = Yaml.dumps(build_deploy(self))
        >>> print(text)
    """

    enable_gpg = self.config['enable_gpg']

    live_pass_varname = self.config['ci_pypi_live_password_varname']
    test_pass_varname = self.config['ci_pypi_test_password_varname']

    assert mode in {'live', 'test'}
    if mode == 'live':
        env = {
            'TWINE_REPOSITORY_URL': 'https://upload.pypi.org/legacy/',
            # 'TWINE_USERNAME': '${{ secrets.TWINE_USERNAME }}',
            'TWINE_USERNAME': '__token__',
            'TWINE_PASSWORD': '${{ secrets.' + live_pass_varname + ' }}',
        }
        if enable_gpg:
            # TODO: make this not me-specific
            env['CI_SECRET'] = '${{ secrets.CI_SECRET }}'

        condition = "github.event_name == 'push' && (startsWith(github.event.ref, 'refs/tags') || startsWith(github.event.ref, 'refs/heads/release'))"
    elif mode == 'test':
        env = {
            'TWINE_REPOSITORY_URL': 'https://test.pypi.org/legacy/',
            # 'TWINE_USERNAME': '${{ secrets.TEST_TWINE_USERNAME }}',
            'TWINE_USERNAME': '__token__',
            'TWINE_PASSWORD': '${{ secrets.' + test_pass_varname + ' }}',
        }
        if enable_gpg:
            # TODO: make this not me-specific
            env['CI_SECRET'] = '${{ secrets.CI_SECRET }}'

        condition = "github.event_name == 'push' && ! startsWith(github.event.ref, 'refs/tags') && ! startsWith(github.event.ref, 'refs/heads/release')"
    else:
        raise KeyError(mode)

    if 'group' in self.remote_info and 'repo_name' in self.remote_info:
        group = self.remote_info['group']
        repo_name = self.remote_info['repo_name']
        repo_suffix = f'{group}/{repo_name}'  # NOQA
        # https://github.com/orgs/community/discussions/25217
        is_not_fork_condition = "github.event.pull_request.head.repo.full_name == '" + repo_suffix + "'"
        # Note: disabling because this does not seem to work?
        is_not_fork_condition = None
    else:
        is_not_fork_condition = None

    if is_not_fork_condition is not None:
        condition = condition + ' && ' + is_not_fork_condition

    if needs is None:
        needs = []

    # TODO: this is probably configured earlier, update it to point to the
    # single source of truth.
    wheelhouse_dpath = 'wheelhouse'

    artifact_globs = [
        f'{wheelhouse_dpath}/*.whl',
        f'{wheelhouse_dpath}/*.zip',
        f'{wheelhouse_dpath}/*.tar.gz',
    ]

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
            f'{self.UPDATE_PIP}',
            f'{self.SYSTEM_PIP_INSTALL} packaging twine -U',
            f'{self.SYSTEM_PIP_INSTALL} urllib3 requests[security]',
            'GPG_KEYID=$(cat dev/public_gpg_key)',
            '''echo "GPG_KEYID = '$GPG_KEYID'"''',
            'GPG_SIGN_CMD="$GPG_EXECUTABLE --batch --yes --detach-sign --armor --local-user $GPG_KEYID"',
        ]
        run += ub.codeblock(
            '''
            WHEEL_PATHS=(''' + wheelhouse_dpath + '''/*.whl ''' + wheelhouse_dpath + '''/*.tar.gz)
            WHEEL_PATHS_STR=$(printf '"%s" ' "${WHEEL_PATHS[@]}")
            echo "$WHEEL_PATHS_STR"
            for WHEEL_PATH in "${WHEEL_PATHS[@]}"
            do
                echo "------"
                echo "WHEEL_PATH = $WHEEL_PATH"
                $GPG_SIGN_CMD --output $WHEEL_PATH.asc $WHEEL_PATH
                $GPG_EXECUTABLE --verify $WHEEL_PATH.asc $WHEEL_PATH  || echo "hack, the first run of gpg very fails"
                $GPG_EXECUTABLE --verify $WHEEL_PATH.asc $WHEEL_PATH
            done
            ls -la wheelhouse
            ''').strip().split('\n')

        artifact_globs.append(
            f'{wheelhouse_dpath}/*.asc'
        )

        enable_otc = True
        if enable_otc:
            run += [
                f'{self.SYSTEM_PIP_INSTALL} opentimestamps-client',
                f'ots stamp {wheelhouse_dpath}/*.whl {wheelhouse_dpath}/*.tar.gz {wheelhouse_dpath}/*.asc',
                'ls -la wheelhouse'
            ]
            artifact_globs.append(
                f'{wheelhouse_dpath}/*.ots'
            )

        if self.config['deploy_pypi']:
            run += [
                f'twine upload --username __token__ --password "$TWINE_PASSWORD" --repository-url "$TWINE_REPOSITORY_URL" {wheelhouse_dpath}/*.whl {wheelhouse_dpath}/*.tar.gz --skip-existing --verbose || {{ echo "failed to twine upload" ; exit 1; }}',
            ]
        # pypi doesn't care about GPG keys anymore, but we can keep them as artifacts.
        # run += [
        #     ('DO_GPG=True GPG_KEYID=$GPG_KEYID TWINE_REPOSITORY_URL=${TWINE_REPOSITORY_URL} '
        #      'TWINE_PASSWORD=$TWINE_PASSWORD TWINE_USERNAME=$TWINE_USERNAME '
        #      'GPG_EXECUTABLE=$GPG_EXECUTABLE DO_UPLOAD=True DO_TAG=False '
        #      './publish.sh'),
        # ]
    else:
        if self.config['deploy_pypi']:
            run = [
                f'{self.SYSTEM_PIP_INSTALL} urllib3 requests[security] twine -U',
                f'twine upload --username __token__ --password "$TWINE_PASSWORD" --repository-url "$TWINE_REPOSITORY_URL" {wheelhouse_dpath}/*.whl {wheelhouse_dpath}/*.tar.gz --skip-existing --verbose || {{ echo "failed to twine upload" ; exit 1; }}',
            ]

    if 'nosrcdist' not in self.tags:
        sdist_wheel_steps = [
            Actions.download_artifact({
                'name': 'Download sdist',
                'with': {
                    'name': 'sdist_wheels',
                    'path': wheelhouse_dpath
                }})
        ]
    else:
        sdist_wheel_steps = []

    deploy_steps = [
        Actions.checkout(name='Checkout source'),
        Actions.download_artifact({
            'name': 'Download wheels',
            'with': {
                # 'name': 'wheels',
                'pattern': 'wheels-*',
                'merge-multiple': True,
                'path': wheelhouse_dpath
            }}),
    ]
    deploy_steps += sdist_wheel_steps
    deploy_steps += [
        {
            'name': 'Show files to upload',
            'shell': 'bash',
            'run': f'ls -la {wheelhouse_dpath}'
        },
        # TODO: it might make sense to make this a script that is invoked
        {
            'name': 'Sign and Publish' if self.config['enable_gpg'] else 'Publish',
            'env': env,
            'run': run,
        },
        Actions.upload_artifact({
            'name': 'Upload deploy artifacts',
            'with': {
                'name': 'deploy_artifacts',
                'path': chr(10).join(artifact_globs)
            }
        })
    ]

    job = {
        'name': f"Deploy {mode.capitalize()}",
        'runs-on': 'ubuntu-latest',
        'if': condition,
        'needs': sorted(needs),
        'steps': deploy_steps,
    }
    return job


# def build_github_tag_release(self, needs=None):
#     """
#     References:
#         https://github.com/softprops/action-gh-release/issues/20#issuecomment-572245945
#     """
#     condition = "github.event_name == 'push' && (startsWith(github.event.ref, 'refs/heads/release'))"
#     job = {
#         'name': "Tag Release Commit",
#         'if': condition,
#         'runs-on': 'ubuntu-latest',
#         'permissions': {'contents': 'write'},
#         'needs': sorted(needs),
#         'steps': [
#             Actions.checkout(name='Checkout source'),
#             Actions.download_artifact({'name': 'Download artifacts', 'with': {'name': 'deploy_artifacts', 'path': 'wheelhouse'}}),
#             {'name': 'Show files to release', 'shell': 'bash', 'run': 'ls -la wheelhouse'},
#             write_release_notes_action,
#             release_action,
#         ]
#     }
#     return job


def build_github_release(self, needs=None):
    """
    References:
        https://github.com/marketplace/actions/create-a-release-in-a-github-action
        https://github.com/softprops/action-gh-release
        https://github.com/softprops/action-gh-release/issues/20#issuecomment-572245945
    """
    condition = "github.event_name == 'push' && (startsWith(github.event.ref, 'refs/tags') || startsWith(github.event.ref, 'refs/heads/release'))"
    env = {
        'GITHUB_TOKEN': '${{ secrets.GITHUB_TOKEN }}',
    }

    write_release_notes_action = {
        'run': 'echo "Automatic Release Notes. TODO: improve" > ${{ github.workspace }}-CHANGELOG.txt'
    }

    wheelhouse_dpath = 'wheelhouse'
    artifact_globs = [
        f'{wheelhouse_dpath}/*.whl',
        f'{wheelhouse_dpath}/*.asc',
        f'{wheelhouse_dpath}/*.ots',
        f'{wheelhouse_dpath}/*.zip',
        f'{wheelhouse_dpath}/*.tar.gz',
    ]

    needs_tag_condition = "(startsWith(github.event.ref, 'refs/heads/release'))"
    tag_action = {
        'name': 'Tag Release Commit',
        'if': needs_tag_condition,
        'run': ub.codeblock(
            '''
            export VERSION=$(python -c "import setup; print(setup.VERSION)")
            git tag "v$VERSION"
            git push origin "v$VERSION"
            ''')
    }

    # 'release_name', valid inputs are ['body', 'body_path', 'name',
    # 'tag_name', 'draft', 'prerelease', 'files', 'fail_on_unmatched_files',
    # 'repository', 'token', 'target_commitish', 'discussion_category_name',
    # 'generate_release_notes', 'append_body']

    release_action = {
        'uses': 'softprops/action-gh-release@v1',
        'name': 'Create Release',
        'id': 'create_release',
        'env': env,
        'with': {
            'body_path': '${{ github.workspace }}-CHANGELOG.txt',
            'tag_name': '${{ github.ref }}',
            # 'release_name': 'Release ${{ github.ref }}',
            'name': 'Release ${{ github.ref }}',
            'body': 'Automatic Release',
            'generate_release_notes': True,
            'draft': True,  # Maybe keep as a draft until we determine this is ok?
            'prerelease': False,
            'files': chr(10).join(artifact_globs),
        }
    }

    job = {
        'name': "Create Github Release",
        'if': condition,
        'runs-on': 'ubuntu-latest',
        'permissions': {'contents': 'write'},
        'needs': sorted(needs),
        'steps': [
            Actions.checkout(name='Checkout source'),
            Actions.download_artifact({'name': 'Download artifacts', 'with': {
                'name': 'deploy_artifacts',
                'path': 'wheelhouse'
            }}),
            {'name': 'Show files to release', 'shell': 'bash', 'run': 'ls -la wheelhouse'},
            write_release_notes_action,
            tag_action,
            release_action,
        ]
    }
    return job
