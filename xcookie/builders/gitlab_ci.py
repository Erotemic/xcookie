import ubelt as ub


def _dev():
    # import yaml
    # yaml
    # https://stackoverflow.com/questions/18065427/generating-anchors-with-pyyaml-dump/36295979#36295979
    from xcookie import rc
    import yaml
    fpath = rc.resource_fpath('gitlab-ci.purepy.yml.in')
    data = yaml.load(open(fpath, 'r'))
    print('data = {}'.format(ub.repr2(data, nl=-1)))
    from xcookie import util_yaml
    print(util_yaml.yaml_dumps(data))

    import ruamel.yaml
    data = ruamel.yaml.load(open(fpath, 'r'), Loader=ruamel.yaml.RoundTripLoader, preserve_quotes=True)
    print(ruamel.yaml.round_trip_dump(data, Dumper=ruamel.yaml.RoundTripDumper))


def build_gitlab_ci(self):
    if 'purepy' in self.tags:
        return make_purepy_ci_jobs(self)
    else:
        raise NotImplementedError


# class YamlBuilder:
#     def __init__(self, data):
#         pass


def make_purepy_ci_jobs(self):
    from xcookie import util_yaml

    enable_gpg = self.config['enable_gpg']

    RUAMEL = 1
    if RUAMEL:
        import ruamel.yaml
        from ruamel.yaml.comments import CommentedMap, CommentedSeq

    def CodeBlock(text):
        if RUAMEL:
            return ruamel.yaml.scalarstring.LiteralScalarString(ub.codeblock(text))
        else:
            return ub.codeblock(text)

    stages = [
        'build',
        'test',
    ]
    if enable_gpg:
        stages.append('gpgsign')

    stages.append('deploy')
    body = {
        'stages': stages,
    }
    if RUAMEL:
        body = CommentedMap(**body)
        body['stages'] = CommentedSeq(body['stages'])
        body.yaml_add_eol_comment('stages', 'TEMPLATE1,c 1')

    common_template = ub.udict(util_yaml.yaml_loads(ub.codeblock(
        '''
        tags:
            # Tags define which runners will accept which jobs
            - docker
            - linux
            - build

        variables:
            # Change pip's cache directory to be inside the project directory
            # since we can only cache local items.
            PIP_CACHE_DIR: "$CI_PROJECT_DIR/.cache/pip"

        except:
            # Don't run the pipeline for new tags
            - tags

        cache:
            paths:
                - .cache/pip
        ''')))

    RUAMEL = 1
    if RUAMEL:
        common_template = CommentedMap(common_template)
        common_template.yaml_set_anchor('common_template')
        body['.common_template'] = common_template

    build_template = {
        'stage': 'build',

        'before_script': [
            'python -V  # Print out python version for debugging',
        ],

        'script': [
            'python -m pip install pip -U',
            'python -m pip install setuptools>=0.8 wheel build',
            'python -m build --wheel --outdir wheelhouse',
        ],

        'artifacts': {
            'paths': [
                'wheelhouse/*.whl'
            ]
        },
    }
    if RUAMEL:
        build_template = CommentedMap(build_template)
        build_template.yaml_set_anchor('build_template')
        body['.build_template'] = build_template
        build_template.add_yaml_merge([(0, common_template)])
    else:
        build_template = common_template | build_template

    test_template = {
        'stage': 'test',

        # Coverage is a regex that will parse the coverage from the test stdout
        'coverage': '/TOTAL.+ ([0-9]{1,3}%)/',
    }

    if RUAMEL:
        test_template = CommentedMap(test_template)
        test_template.yaml_set_anchor('test_template')
        test_template.add_yaml_merge([(0, common_template)])
        body['.test_template'] = test_template
    else:
        test_template = common_template | test_template

    setup_venv_template = CodeBlock(
        '''
        # Setup the correct version of python (which should be the same as this instance)
        python --version  # Print out python version for debugging
        export PYVER=$(python -c "import sys; print('{}{}'.format(*sys.version_info[0:2]))")
        python -m pip install virtualenv
        python -m virtualenv venv$PYVER
        source venv$PYVER/bin/activate
        pip install pip -U
        pip install pip setuptools -U
        pip install pygments
        python --version  # Print out python version for debugging
        ''')

    get_modname_python = "import tomli; print(tomli.load(open('pyproject.toml', 'rb'))['tool']['xcookie']['mod_name'])"
    get_modname_bash = f'python -c "{get_modname_python}"'

    get_modpath_python = "import ubelt; print(ubelt.modname_to_modpath('${MOD_NAME}'))"
    get_modpath_bash = f'python -c "{get_modpath_python}"'

    test_templates = {}
    install_extras = ub.udict({
        'test-minimal-loose'  : 'tests',
        'test-full-loose'     : 'tests,optional',
        'test-minimal-strict' : 'tests-strict,runtime-strict',
        'test-full-strict'    : 'tests-strict,runtime-strict,optional-strict',
    })
    for key, extra in install_extras.items():
        test_steps = [
            'ls wheelhouse || echo "wheelhouse does not exist"',
            'pip install tomli ubelt',
            f'MOD_NAME=$({get_modname_bash})',
            'echo "MOD_NAME=$MOD_NAME"',
        ]
        if 'gdal' in self.tags:
            test_steps += [
                # TODO: handle strict
                'pip install -r requirements/gdal.txt',
            ]
        test_steps += [
            f'pip install "$MOD_NAME"[{extra}] -f wheelhouse'
        ]
        test_steps += [
            CodeBlock(f'mkdir -p sandbox && cd sandbox && pytest --xdoctest-verbose=3 -s --cov-config ../pyproject.toml --cov-report html --cov-report term --cov="$MOD_NAME" --xdoc "$({get_modpath_bash})" ../tests && cd ..'),
        ]
        test = {
            'before_script': [setup_venv_template],
            'script': test_steps,
        }
        if RUAMEL:
            test = CommentedMap(test)
            test.yaml_set_anchor(key)
            test.add_yaml_merge([(0, test_template)])
            body['.' + key] = test
        else:
            test = test_template | test
        test_templates[key] = test

    python_images = {
        'cp311': 'python:3.11.0rc2',
        'cp310': 'python:3.10',
        'cp39': 'python:3.9',
        'cp38': 'python:3.8',
        'cp37': 'python:3.7',
        'cp36': 'python:3.6',
    }

    jobs = {}
    opsys = 'linux'
    for pyver in self.config['ci_cpython_versions']:
        cpver = 'cp' + pyver.replace('.', '')
        if cpver in python_images:
            swenv_key = f'{cpver}_{opsys}'  # software environment key
            build_name = f'build/{swenv_key}'

            build_job = {
                'image': python_images[cpver],
            }
            if RUAMEL:
                build_job = CommentedMap(build_job)
                build_job.add_yaml_merge([(0, build_template)])
            else:
                build_job = build_template | build_job
            jobs[build_name] = build_job

            for test_key, test_template in test_templates.items():
                test_name = f'test/{test_key}/{swenv_key}'
                test_job = {
                    'image': python_images[cpver],
                    'needs': [
                        build_name,
                    ]
                }
                if RUAMEL:
                    test_job = CommentedMap(test_job)
                    test_job.add_yaml_merge([(0, test_template)])
                else:
                    test_job = test_template | test_job
                jobs[test_name] = test_job

    body.update(jobs)

    if enable_gpg:
        gpgsign_job = {}
        gpgsign_job.update(ub.udict(util_yaml.yaml_loads(ub.codeblock(
            '''
            image:
                python:3.8

            stage:
                gpgsign

            artifacts:
                paths:
                    - wheelhouse/*.asc

            only:
                refs:
                    # Gitlab will only expose protected variables on protected branches
                    # (which I've set to be main and release), so only run this stage
                    # there.
                    - master
                    - main
                    - release
            '''))))

        gpgsign_job.update(util_yaml.yaml_loads(ub.codeblock(
            '''
            script:
                - ls wheelhouse
                - export GPG_EXECUTABLE=gpg
                - export GPG_KEYID=$(cat dev/public_gpg_key)
                - echo "GPG_KEYID = $GPG_KEYID"
                # Decrypt and import GPG Keys / trust
                # note the variable pointed to by VARNAME_CI_SECRET is a protected variables only available on main and release branch
                - source dev/secrets_configuration.sh
                - CI_SECRET=${!VARNAME_CI_SECRET}
                - $GPG_EXECUTABLE --version
                - openssl version
                - $GPG_EXECUTABLE --list-keys
                # note CI_KITWARE_SECRET is a protected variables only available on main and release branch
                - CIS=$CI_SECRET openssl enc -aes-256-cbc -pbkdf2 -md SHA512 -pass env:CIS -d -a -in dev/ci_public_gpg_key.pgp.enc | $GPG_EXECUTABLE --import
                - CIS=$CI_SECRET openssl enc -aes-256-cbc -pbkdf2 -md SHA512 -pass env:CIS -d -a -in dev/gpg_owner_trust.enc | $GPG_EXECUTABLE --import-ownertrust
                - CIS=$CI_SECRET openssl enc -aes-256-cbc -pbkdf2 -md SHA512 -pass env:CIS -d -a -in dev/ci_secret_gpg_subkeys.pgp.enc | $GPG_EXECUTABLE --import
                - GPG_SIGN_CMD="$GPG_EXECUTABLE --batch --yes --detach-sign --armor --local-user $GPG_KEYID"
            ''')))
        gpgsign_job['script'].append(
            CodeBlock(
                '''
                WHEEL_PATHS=(wheelhouse/*.whl)
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
                '''
            )
        )
        gpgsign_job['script'].append('ls wheelhouse')

        if RUAMEL:
            gpgsign_job = CommentedMap(gpgsign_job)
            gpgsign_job.add_yaml_merge([(0, common_template)])
        else:
            gpgsign_job = common_template | gpgsign_job
        body['gpgsign/wheels'] = gpgsign_job

    deploy = True
    if deploy:
        deploy_job = {}
        deploy_job.update(ub.udict(util_yaml.yaml_loads(ub.codeblock(
            '''
            image:
                python:3.8

            stage:
                deploy

            '''))))
        deploy_script = [
            'pip install pyopenssl ndg-httpsclient pyasn1 requests[security] twine -U',
            'ls wheelhouse',
        ]
        deploy_script += [
            CodeBlock(
                '''
                WHEEL_PATHS=(wheelhouse/*.whl)
                WHEEL_PATHS_STR=$(printf '"%s" ' "${WHEEL_PATHS[@]}")
                source dev/secrets_configuration.sh
                TWINE_PASSWORD=${!VARNAME_TWINE_PASSWORD}
                TWINE_USERNAME=${!VARNAME_TWINE_USERNAME}
                echo "$WHEEL_PATHS_STR"
                for WHEEL_PATH in "${WHEEL_PATHS[@]}"
                do
                    twine check $WHEEL_PATH.asc $WHEEL_PATH
                    twine upload --username $TWINE_USERNAME --password $TWINE_PASSWORD $WHEEL_PATH.asc $WHEEL_PATH || echo "upload already exists"
                done
                ''')
        ]
        deploy_script += [
            CodeBlock(
                r'''
                # Have the server git-tag the release and push the tags
                export VERSION=$(python -c "import setup; print(setup.VERSION)")
                # do sed twice to handle the case of https clone with and without a read token
                URL_HOST=$(git remote get-url origin | sed -e 's|https\?://.*@||g' | sed -e 's|https\?://||g' | sed -e 's|git@||g' | sed -e 's|:|/|g')
                source dev/secrets_configuration.sh
                CI_SECRET=${!VARNAME_CI_SECRET}
                PUSH_TOKEN=${!VARNAME_PUSH_TOKEN}
                echo "URL_HOST = $URL_HOST"
                # A git config user name and email is required. Set if needed.
                if [[ "$(git config user.email)" == "" ]]; then
                    git config user.email "ci@gitlab.org.com"
                    git config user.name "Gitlab-CI"
                fi
                TAG_NAME="v${VERSION}"
                echo "TAG_NAME = $TAG_NAME"
                if [ $(git tag -l "$TAG_NAME") ]; then
                    echo "Tag already exists"
                else
                    # if we messed up we can delete the tag
                    # git push origin :refs/tags/$TAG_NAME
                    # and then tag with -f
                    git tag $TAG_NAME -m "tarball tag $VERSION"
                    git push --tags "https://git-push-token:${PUSH_TOKEN}@${URL_HOST}"
                fi
                ''')
        ]
        deploy_job['script'] = deploy_script
        if RUAMEL:
            deploy_job = CommentedMap(deploy_job)
            deploy_job.add_yaml_merge([(0, common_template)])
        else:
            deploy_job = common_template | deploy_job
        body['deploy/wheels'] = deploy_job

    if RUAMEL:
        body_text = ruamel.yaml.round_trip_dump(body, Dumper=ruamel.yaml.RoundTripDumper)

        # if RUAMEL:
        body = ruamel.yaml.round_trip_load(body_text)
        body['stages'].yaml_set_start_comment('TEMPLATES')
        # body.yaml_set_comment_before_after_key('stages', 'before test1 (top level)', after='before test2\n\n')
        # body.yaml_add_eol_comment('STAGE COMMENT', key='stages')
        body_text = ruamel.yaml.round_trip_dump(body, Dumper=ruamel.yaml.RoundTripDumper)
    else:
        from xcookie import util_yaml
        body_text = util_yaml.yaml_dumps(body)

    header = ub.codeblock(
        '''
        # Autogenerated by ~/code/xcookie/xcookie/builders/gitlab_ci.py
        '''
    )
    footer = '# end'
    text = header + '\n\n' + body_text + '\n\n' + footer
    return text