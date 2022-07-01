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
        return action

    @classmethod
    def checkout(cls, *args, **kwargs):
        return cls._generic_action({
            'uses': 'actions/checkout@v3'
        }, *args, **kwargs)

    @classmethod
    def setup_python(cls, *args, **kwargs):
        return cls._generic_action({
            'uses': 'actions/setup-python@v4'
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
    def msvc_dev_cmd(cls, *args, **kwargs):
        return cls._generic_action({
            'name': 'Enable MSVC',
            'uses': 'ilammy/msvc-dev-cmd@v1',
        }, *args, **kwargs)

    @classmethod
    def setup_qemu(cls, *args, **kwargs):
        return cls._generic_action({
            'name': 'Set up QEMU',
            'uses': 'docker/setup-qemu-action@v2',
        }, *args, **kwargs)


def build_github_actions(self):
    """
    cat ~/code/xcookie/xcookie/rc/tests.yml.in | yq  .jobs.lint
    cat ~/code/xcookie/xcookie/rc/tests.yml.in | yq  .jobs.build_and_test_wheels
    cat ~/code/xcookie/xcookie/rc/tests.yml.in | yq  .jobs.build_and_test_sdist
    cat ~/code/xcookie/xcookie/rc/tests.yml.in | yq  .jobs.deploy
    cat ~/code/xcookie/xcookie/rc/tests.yml.in | yq  .
    build_and_test_wheels
    """

    jobs = {
        'lint_job': lint_job(self),
        'build_and_test_sdist': build_and_test_sdist(self),
        'build_and_test_wheels': build_and_test_wheels(self),
        'test_deploy': build_deploy(self, 'test'),
        'live_deploy': build_deploy(self, 'live'),
    }

    # For some reason, it doesn't like the on block
    header = ub.codeblock(
        '''
        # This workflow will install Python dependencies, run tests and lint with a variety of Python versions
        # For more information see: https://help.github.com/actions/language-and-framework-guides/using-python-with-github-actions
        # Based on ~/code/xcookie/xcookie/rc/tests.yml.in
        # Now based on ~/code/xcookie/xcookie/builders/github_actions.py

        name: Tests

        on:
          push:
          pull_request:
            branches: [ main ]

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

    text = header + '\n\n' + yaml_dumps(body) + '\n\n' + footer
    # print(text)
    return text


def yaml_dumps(data):
    import yaml
    import io
    # https://stackoverflow.com/questions/8640959/how-can-i-control-what-scalar-form-pyyaml-uses-for-my-data
    def str_presenter(dumper, data):
        if len(data.splitlines()) > 1 or '\n' in data:
            text_list = [line.rstrip() for line in data.splitlines()]
            fixed_data = '\n'.join(text_list)
            return dumper.represent_scalar('tag:yaml.org,2002:str', fixed_data, style='|')
        return dumper.represent_scalar('tag:yaml.org,2002:str', data)

    yaml.add_representer(str, str_presenter)
    # dumper = yaml.dumper.Dumper
    # dumper = yaml.SafeDumper(sort_keys=False)
    # yaml.dump(data, s, Dumper=yaml.SafeDumper, sort_keys=False, width=float("inf"))
    s = io.StringIO()
    # yaml.dump(data, s, sort_keys=False)
    yaml.dump(data, s, Dumper=yaml.Dumper, sort_keys=False, width=float("inf"))
    s.seek(0)
    text = s.read()
    print(text)
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
                'run': [
                    'python -m pip install --upgrade pip',
                    'python -m pip install -r requirements/tests.txt',
                    'python -m pip install -r requirements/runtime.txt',
                    'python -m pip install -r requirements/headless.txt' if 'cv2' in self.tags else 'true',
                ]
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
                    f'MOD_DPATH=$(python -c "import {self.mod_name}, os; print(os.path.dirname({self.mod_name}.__file__))")',
                    'echo "MOD_DPATH = $MOD_DPATH"',
                    f'python -m pytest -p pytester -p no:doctest --xdoctest --cov={self.mod_name} $MOD_DPATH ./tests',
                ]
            },
            {
                'name': 'Test full loose sdist',
                'run': [
                    'pwd',
                    'ls -al',
                    'python -m pip install -r requirements/optional.txt',
                    'python -m pip install -r requirements/headless.txt' if 'cv2' in self.tags else 'true',
                    f'MOD_DPATH=$(python -c "import {self.mod_name}, os; print(os.path.dirname({self.mod_name}.__file__))")',
                    'echo "MOD_DPATH = $MOD_DPATH"',
                    '# Run in a sandboxed directory',
                    'WORKSPACE_DNAME="testsrcdir_${CI_PYTHON_VERSION}_${GITHUB_RUN_ID}_${RUNNER_OS}"',
                    'mkdir -p $WORKSPACE_DNAME',
                    'cd $WORKSPACE_DNAME',
                    '# Run the tests',
                    '# Get path to installed package',
                    f'MOD_DPATH=$(python -c "import {self.mod_name}, os; print(os.path.dirname({self.mod_name}.__file__))")',
                    'echo "MOD_DPATH = $MOD_DPATH"',
                    'python -m pytest -p pytester -p no:doctest --xdoctest $MOD_DPATH ../tests',
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


def build_and_test_wheels(self):
    os_list = []
    if 'win' in self.config['os']:
        os_list.append('windows-latest')
    if 'linux' in self.config['os']:
        os_list.append('ubuntu-latest')
    if 'osx' in self.config['os']:
        os_list.append('macOS-latest')

    # TODO: use min ersions
    min_python = str(self.config['min_python'])
    from packaging.version import parse as Version

    # python_versions = ["3.7", "3.8", "3.9", "3.10"]
    supported_python_versions = [
        '2.7', '3.4', '3.5', '3.6', '3.7', '3.8', '3.9', '3.10'
    ]

    python_versions = [v for v in supported_python_versions if Version(v) >= Version(min_python)]

    # TODO:
    python_versions += [
        # '3.11-dev',
        'pypy-3.7',
    ]

    install_extras = [
        'tests',
        'tests,optional',
        'tests-strict,runtime-strict',
        'tests-strict,runtime-strict,optional-strict',
    ]

    latest_python = supported_python_versions[-1]

    job = {
        'name': '${{ matrix.python-version }} on ${{ matrix.os }}, arch=${{ matrix.arch }} with ${{ matrix.install-extras }}',
        'runs-on': '${{ matrix.os }}',
        'strategy': {
            'matrix': {
                'os': os_list,
                'python-version': python_versions,
                'install-extras': install_extras[0:2],
                'arch': [
                    'auto'
                ],
                'include': [
                    {'python-version': pyver, 'os': osname, 'install-extras': extra}
                    for osname in os_list
                    for extra in install_extras[2:]
                    for pyver in [python_versions[0], supported_python_versions[-1]]
                ]
            }
        },
        'steps': [
            Actions.checkout(),
            Actions.msvc_dev_cmd({
                'name': 'Enable MSVC 64bit',
                'if': "matrix.os == 'windows-latest' && matrix.cibw_build != 'cp3*-win32'",
            }),
            Actions.msvc_dev_cmd({
                'name': 'Enable MSVC 32bit',
                'if': "matrix.os == 'windows-latest' && matrix.cibw_build == 'cp3*-win32'",
                'with': {
                    'arch': 'x86'
                }
            }),
            Actions.setup_qemu({
                'if': "runner.os == 'Linux' && matrix.arch != 'auto'",
                'with': {
                    'platforms': 'all'
                }
            }),
            Actions.setup_python({
                'with': {'python-version': '${{ matrix.python-version }}'}
            }),
            {
                'name': 'Build pure wheel',
                'shell': 'bash',
                'run': [
                    'python -m pip install pip -U',
                    # "python -m pip install setuptools>=0.8 wheel",
                    # "python -m pip wheel --wheel-dir wheelhouse .",
                    'python -m pip install setuptools>=0.8 wheel build',
                    'python -m build --wheel --outdir wheelhouse',
                ]
            },
            # {
            #     'name': 'Test minimal loose pure wheel',
            #     'shell': 'bash',
            #     'env': {
            #         'CI_PYTHON_VERSION': 'py${{ matrix.python-version }}'
            #     },
            #     'run': [
            #         # '# Install the wheel',
            #         # f'python -m pip install wheelhouse/{self.mod_name}*.whl',
            #         # 'python -m pip install -r requirements/tests.txt',
            #         # 'python -m pip install -r requirements/headless.txt' if 'cv2' in self.tags else 'true',
            #         '# Find the path to the wheel',
            #         f'WHEEL_FPATH=$(ls wheelhouse/{self.mod_name}*.whl)',
            #         '# Install the wheel',
            #         'python -m pip install --user --force-reinstall ${WHEEL_FPATH}[tests,headless]' if 'cv2' in self.tags else
            #         'python -m pip install --user --force-reinstall ${WHEEL_FPATH}[tests]',
            #         '# Create a sandboxed directory',
            #         'WORKSPACE_DNAME="testdir_${CI_PYTHON_VERSION}_${GITHUB_RUN_ID}_${RUNNER_OS}"',
            #         'mkdir -p $WORKSPACE_DNAME',
            #         'cd $WORKSPACE_DNAME',
            #         '# Get the path to the installed package and run the tests',
            #         f'MOD_DPATH=$(python -c "import {self.mod_name}, os; print(os.path.dirname({self.mod_name}.__file__))")',
            #         'echo "MOD_DPATH = $MOD_DPATH"',
            #         f'python -m pytest -p pytester -p no:doctest --xdoctest --cov-config ../pyproject.toml --cov-report term --cov={self.mod_name} $MOD_DPATH ../tests',
            #         '# Move coverage file to a new name',
            #         'mv .coverage "../.coverage.$WORKSPACE_DNAME"',
            #         'cd ..',
            #     ]
            # },
            # {
            #     'name': 'Test minimal strict pure wheel',
            #     'shell': 'bash',
            #     'env': {
            #         'CI_PYTHON_VERSION': 'py${{ matrix.python-version }}'
            #     },
            #     'run': [
            #         '# Find the path to the wheel',
            #         f'WHEEL_FPATH=$(ls wheelhouse/{self.mod_name}*.whl)',
            #         '# Install the wheel',
            #         'python -m pip install --user --force-reinstall ${WHEEL_FPATH}[tests-strict,runtime-strict,headless-strict]' if 'cv2' in self.tags else
            #         'python -m pip install --user --force-reinstall ${WHEEL_FPATH}[tests-strict,runtime-strict]',
            #         '# Create a sandboxed directory',
            #         'WORKSPACE_DNAME="testdir_${CI_PYTHON_VERSION}_${GITHUB_RUN_ID}_${RUNNER_OS}"',
            #         'mkdir -p $WORKSPACE_DNAME',
            #         'cd $WORKSPACE_DNAME',
            #         '# Get the path to the installed package and run the tests',
            #         f'MOD_DPATH=$(python -c "import {self.mod_name}, os; print(os.path.dirname({self.mod_name}.__file__))")',
            #         'echo "MOD_DPATH = $MOD_DPATH"',
            #         f'python -m pytest -p pytester -p no:doctest --xdoctest --cov-config ../pyproject.toml --cov-report term --cov={self.mod_name} $MOD_DPATH ../tests',
            #         '# Move coverage file to a new name',
            #         'mv .coverage "../.coverage.$WORKSPACE_DNAME"',
            #         'cd ..',
            #     ]
            # },
            {
                'name': 'Test wheel with ${{ matrix.install-extras }}',
                'shell': 'bash',
                'env': {
                    'INSTALL_EXTRAS': '${{ matrix.install-extras }}',
                    'CI_PYTHON_VERSION': 'py${{ matrix.python-version }}'
                },
                'run': [
                    '# Find the path to the wheel',
                    f'WHEEL_FPATH=$(ls wheelhouse/{self.mod_name}*.whl)',
                    '# Install the wheel',
                    'python -m pip install ${WHEEL_FPATH}[${INSTALL_EXTRAS}]',
                    '# Create a sandboxed directory',
                    'WORKSPACE_DNAME="testdir_${CI_PYTHON_VERSION}_${GITHUB_RUN_ID}_${RUNNER_OS}"',
                    'mkdir -p $WORKSPACE_DNAME',
                    'cd $WORKSPACE_DNAME',
                    '# Get the path to the installed package and run the tests',
                    f'MOD_DPATH=$(python -c "import {self.mod_name}, os; print(os.path.dirname({self.mod_name}.__file__))")',
                    'echo "MOD_DPATH = $MOD_DPATH"',
                    f'python -m pytest -p pytester -p no:doctest --xdoctest --cov-config ../pyproject.toml --cov-report term --cov={self.mod_name} $MOD_DPATH ../tests',
                    '# Move coverage file to a new name',
                    'mv .coverage "../.coverage.$WORKSPACE_DNAME"',
                    'cd ..',
                ]
            },
            # {
            #     'name': 'Test full loose pure wheel',
            #     'shell': 'bash',
            #     'env': {
            #         'CI_PYTHON_VERSION': 'py${{ matrix.python-version }}'
            #     },
            #     'run': [
            #         '# Find the path to the wheel',
            #         f'WHEEL_FPATH=$(ls wheelhouse/{self.mod_name}*.whl)',
            #         '# Install the wheel',
            #         'python -m pip install --user --force-reinstall ${WHEEL_FPATH}[tests,all,headless]' if 'cv2' in self.tags else
            #         'python -m pip install --user --force-reinstall ${WHEEL_FPATH}[tests,all]',
            #         '# Create a sandboxed directory',
            #         'WORKSPACE_DNAME="testdir_${CI_PYTHON_VERSION}_${GITHUB_RUN_ID}_${RUNNER_OS}"',
            #         'mkdir -p $WORKSPACE_DNAME',
            #         'cd $WORKSPACE_DNAME',
            #         '# Get the path to the installed package and run the tests',
            #         f'MOD_DPATH=$(python -c "import {self.mod_name}, os; print(os.path.dirname({self.mod_name}.__file__))")',
            #         'echo "MOD_DPATH = $MOD_DPATH"',
            #         f'python -m pytest -p pytester -p no:doctest --xdoctest --cov-config ../pyproject.toml --cov-report term --cov={self.mod_name} $MOD_DPATH ../tests',
            #         '# Move coverage file to a new name',
            #         'mv .coverage "../.coverage.$WORKSPACE_DNAME"',
            #         'cd ..',
            #     ]
            # },
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
    }
    return job


def build_deploy(self, mode='live'):
    assert mode in {'live', 'test'}
    if mode == 'live':
        env = {
            'TWINE_REPOSITORY_URL': 'https://upload.pypi.org/legacy/',
            'TWINE_USERNAME': '${{ secrets.TWINE_USERNAME }}',
            'TWINE_PASSWORD': '${{ secrets.TWINE_PASSWORD }}',
            # TODO: make this not me-specific
            'CI_SECRET': '${{ secrets.EROTEMIC_CI_SECRET }}'
        }
        condition = "github.event_name == 'push' && (startsWith(github.event.ref, 'refs/tags') || startsWith(github.event.ref, 'refs/heads/release'))"
    elif mode == 'test':
        env = {
            'TWINE_REPOSITORY_URL': 'https://test.pypi.org/legacy/',
            'TWINE_USERNAME': '${{ secrets.TEST_TWINE_USERNAME }}',
            'TWINE_PASSWORD': '${{ secrets.TEST_TWINE_PASSWORD }}',
            # TODO: make this not me-specific
            'CI_SECRET': '${{ secrets.EROTEMIC_CI_SECRET }}'
        }
        condition = "github.event_name == 'push' && ! startsWith(github.event.ref, 'refs/tags') && ! startsWith(github.event.ref, 'refs/heads/release')"
    else:
        raise KeyError(mode)

    job = {
        'name': f"Uploading {mode.capitalize()} to PyPi",
        'runs-on': 'ubuntu-latest',
        'if': condition,
        'needs': [
            'build_and_test_wheels',
            'build_and_test_sdist'
        ],
        'steps': [
            Actions.checkout(name='Checkout source'),
            Actions.download_artifact({'name': 'Download wheels and sdist', 'with': {'name': 'wheels', 'path': 'wheelhouse'}}),
            {'name': 'Show files to upload', 'shell': 'bash', 'run': 'ls -la wheelhouse'},
            {
                'name': 'Sign and Publish',
                'env': env,
                'run': [
                    # 'ls -al',
                    'GPG_EXECUTABLE=gpg',
                    '$GPG_EXECUTABLE --version',
                    'openssl version',
                    '$GPG_EXECUTABLE --list-keys',
                    'echo "Decrypting Keys"',
                    'CIS=$CI_SECRET openssl enc -aes-256-cbc -pbkdf2 -md SHA512 -pass env:CIS -d -a -in dev/ci_public_gpg_key.pgp.enc | $GPG_EXECUTABLE --import',
                    'CIS=$CI_SECRET openssl enc -aes-256-cbc -pbkdf2 -md SHA512 -pass env:CIS -d -a -in dev/gpg_owner_trust.enc | $GPG_EXECUTABLE --import-ownertrust',
                    'CIS=$CI_SECRET openssl enc -aes-256-cbc -pbkdf2 -md SHA512 -pass env:CIS -d -a -in dev/ci_secret_gpg_subkeys.pgp.enc | $GPG_EXECUTABLE --import',
                    'echo "Finish Decrypt Keys"',
                    '$GPG_EXECUTABLE --list-keys || true',
                    '$GPG_EXECUTABLE --list-keys  || echo "first invocation of gpg creates directories and returns 1"',
                    '$GPG_EXECUTABLE --list-keys',
                    'VERSION=$(python -c "import setup; print(setup.VERSION)")',
                    'pip install twine',
                    'pip install six pyopenssl ndg-httpsclient pyasn1 -U --user',
                    'pip install requests[security] twine --user',
                    'GPG_KEYID=$(cat dev/public_gpg_key)',
                    '''echo "GPG_KEYID = '$GPG_KEYID'"''',
                    ('DO_GPG=True GPG_KEYID=$GPG_KEYID TWINE_REPOSITORY_URL=${TWINE_REPOSITORY_URL} '
                     'TWINE_PASSWORD=$TWINE_PASSWORD TWINE_USERNAME=$TWINE_USERNAME '
                     'GPG_EXECUTABLE=$GPG_EXECUTABLE DO_UPLOAD=True DO_TAG=False '
                     './publish.sh'),
                ]
            }
        ]
    }
    return job
