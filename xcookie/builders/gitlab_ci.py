import ubelt as ub
from xcookie.builders import common_ci


def build_gitlab_ci(self):
    """
    Example:
        >>> from xcookie.builders.gitlab_ci import *  # NOQA
        >>> from xcookie.main import XCookieConfig
        >>> from xcookie.main import TemplateApplier
        >>> config = XCookieConfig(tags=['purepy'])
        >>> self = TemplateApplier(config)
        >>> text = build_gitlab_ci(self)
        >>> print(text)
    """
    if 'purepy' in self.tags:
        return make_purepy_ci_jobs(self)
    else:
        raise NotImplementedError


def build_gitlab_rules(self):
    group = self.remote_info['group']
    repo_name = self.remote_info['repo_name']
    text = ub.codeblock(
        f'''
        # Rules for where jobs can run
        # Derived from: https://gitlab.kitware.com/cmake/cmake/-/blob/v3.25.1/.gitlab/rules.yml
        # For an overview of gitlab rules see:
        # https://docs.gitlab.com/ee/ci/yaml/#workflowrules

        .run_manually:
            rules:
                - if: '$CI_MERGE_REQUEST_ID'
                  when: manual
                - if: '$CI_COMMIT_REF_PROTECTED == true'
                  when: on_success
                - if: '$CI_PROJECT_PATH == "{group}/{repo_name}" && $CI_PIPELINE_SOURCE == "schedule"'
                  when: on_success
                - if: '$CI_PROJECT_PATH == "{group}/{repo_name}"'
                  when: manual
                - when: never

        .run_automatically:
            rules:
                - if: '$CI_MERGE_REQUEST_ID'
                  when: on_success
                - if: '$CI_PROJECT_PATH == "{group}/{repo_name}" && $CI_PIPELINE_SOURCE == "schedule"'
                  when: on_success
                - if: '$CI_PROJECT_PATH == "{group}/{repo_name}"'
                  when: delayed
                  start_in: 5 minutes
                - when: never

        .run_dependent:
            rules:
                - if: '$CI_MERGE_REQUEST_ID'
                  when: on_success
                - if: '$CI_PROJECT_PATH == "{group}/{repo_name}"'
                  when: on_success
                - when: never
        ''')
    return text


# class YamlBuilder:
#     def __init__(self, data):
#         pass


def make_purepy_ci_jobs(self):
    import ruamel.yaml
    from ruamel.yaml.comments import CommentedMap, CommentedSeq
    from xcookie.util_yaml import Yaml

    enable_gpg = self.config['enable_gpg']

    body = CommentedMap()
    body['stages'] = CommentedSeq([
        'build',
        'test',
    ])
    body.yaml_add_eol_comment('stages', 'TEMPLATE1,c 1')

    common_template = ub.udict(Yaml.loads(ub.codeblock(
        '''
        tags:
            # Tags define which runners will accept which jobs
            - docker
            - linux-x86_64
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

    common_template = CommentedMap(common_template)
    common_template.yaml_set_anchor('common_template')
    body['.common_template'] = common_template

    if 'kitware' in self.tags:
        body['.common_template']['tags'].append('kitware-python-stack')

    wheelhouse_dpath = 'dist'
    build_wheel_parts = common_ci.make_build_wheel_parts(self, wheelhouse_dpath)
    build_template = {
        'stage': 'build',
        'before_script': [
            'python -V  # Print out python version for debugging',
        ],
        'script': build_wheel_parts['commands'],
        'artifacts': {
            'paths': [
                build_wheel_parts['artifact'],
            ]
        },
    }
    build_template = CommentedMap(build_template)
    build_template.yaml_set_anchor('build_template')
    body['.build_template'] = build_template
    build_template.add_yaml_merge([(0, common_template)])

    common_test_template = {
        'stage': 'test',

        # Coverage is a regex that will parse the coverage from the test stdout
        'coverage': '/TOTAL.+ ([0-9]{1,3}%)/',
    }

    common_test_template = CommentedMap(common_test_template)
    common_test_template.yaml_set_anchor('common_test_template')
    common_test_template.add_yaml_merge([(0, common_template)])
    body['.common_test_template'] = common_test_template

    setup_venv_template = Yaml.CodeBlock(
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

    test_templates = {}
    loose_cv2 = ''
    strict_cv2 = ''
    if 'cv2' in self.tags:
        loose_cv2 = ',headless'
        strict_cv2 = ',headless-strict'
    install_extras = ub.udict({
        'minimal-loose'  : 'tests' + loose_cv2,
        'full-loose'     : 'tests,optional' + loose_cv2,
        'minimal-strict' : 'tests-strict,runtime-strict' + strict_cv2,
        'full-strict'    : 'tests-strict,runtime-strict,optional-strict' + strict_cv2,
    })
    for extra_key, extra in install_extras.items():
        if 'gdal' in self.tags:
            special_install_lines = [
                # TODO: handle strict
                'pip install -r requirements/gdal.txt',
            ]
        else:
            special_install_lines = []
        workspace_dname = 'sandbox'
        install_and_test_wheel_parts = common_ci.make_install_and_test_wheel_parts(
            self, wheelhouse_dpath, special_install_lines, workspace_dname)
        test_steps = [
            f'export INSTALL_EXTRAS="{extra}"',
        ]
        test_steps += install_and_test_wheel_parts['install_wheel_commands']
        test_steps += install_and_test_wheel_parts['test_wheel_commands']
        test = {
            'before_script': [setup_venv_template],
            'script': test_steps,
        }
        anchor = f'test_{extra_key}_template'
        test = CommentedMap(test)
        test.yaml_set_anchor(anchor)
        test.add_yaml_merge([(0, common_test_template)])
        body['.' + anchor] = test
        test_templates[extra_key] = test

    python_images = {
        'cp311': 'python:3.11',
        'cp310': 'python:3.10',
        'cp39': 'python:3.9',
        'cp38': 'python:3.8',
        'cp37': 'python:3.7',
        'cp36': 'python:3.6',
    }

    build_names = []

    jobs = {}
    opsys = 'linux'
    arch = 'x86_64'
    for pyver in self.config['ci_cpython_versions']:
        cpver = 'cp' + pyver.replace('.', '')
        if cpver in python_images:
            swenv_key = f'{cpver}-{opsys}-{arch}'  # software environment key
            build_name = f'build/{swenv_key}'
            build_names.append(build_name)

            build_job = {
                'image': python_images[cpver],
            }
            build_job = CommentedMap(build_job)
            build_job.add_yaml_merge([(0, build_template)])
            jobs[build_name] = build_job

            for extra_key, common_test_template in test_templates.items():
                test_name = f'test/{extra_key}/{swenv_key}'
                test_job = {
                    'image': python_images[cpver],
                    'needs': [
                        build_name,
                    ]
                }
                test_job = CommentedMap(test_job)
                test_job.add_yaml_merge([(0, common_test_template)])
                jobs[test_name] = test_job

    body.update(jobs)

    deploy_image = python_images['cp38']

    if enable_gpg:
        gpgsign_job = {}
        gpgsign_job.update(ub.udict(Yaml.loads(ub.codeblock(
            f'''
            image:
                {deploy_image}

            stage:
                gpgsign

            artifacts:
                paths:
                    - {wheelhouse_dpath}/*.asc

            only:
                refs:
                    # Gitlab will only expose protected variables on protected branches
                    # (which I've set to be main and release), so only run this stage
                    # there.
                    - master
                    - main
                    - release
            '''))))

        gpgsign_job['needs'] = [{'job': build_name, 'artifacts': True} for build_name in build_names]

        gpgsign_job.update(Yaml.loads(ub.codeblock(
            '''
            script:
                - ls ''' + wheelhouse_dpath + '''
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
            Yaml.CodeBlock(
                '''
                WHEEL_PATHS=(''' + wheelhouse_dpath + '''/*.whl)
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
        gpgsign_job['script'].append(f'ls {wheelhouse_dpath}')

        gpgsign_job = CommentedMap(gpgsign_job)
        gpgsign_job.add_yaml_merge([(0, common_template)])
        body['stages'].append('gpgsign')
        body['gpgsign/wheels'] = gpgsign_job

    deploy = True
    if deploy:
        deploy_job = {}
        deploy_job.update(ub.udict(Yaml.loads(ub.codeblock(
            f'''
            image:
                {deploy_image}

            stage:
                deploy

            only:
                refs:
                    - release
            '''))))
        deploy_script = [
            'pip install pyopenssl ndg-httpsclient pyasn1 requests[security] twine -U',
            f'ls {wheelhouse_dpath}',
        ]
        deploy_script += [
            Yaml.CodeBlock(
                '''
                WHEEL_PATHS=(''' + wheelhouse_dpath + '''/*.whl)
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
            Yaml.CodeBlock(
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
        deploy_job = CommentedMap(deploy_job)
        deploy_job.add_yaml_merge([(0, common_template)])
        body['stages'].append('deploy')
        body['deploy/wheels'] = deploy_job

    body_text = ruamel.yaml.round_trip_dump(body, Dumper=ruamel.yaml.RoundTripDumper)

    body = ruamel.yaml.round_trip_load(body_text)
    body['stages'].yaml_set_start_comment('TEMPLATES')
    # body.yaml_set_comment_before_after_key('stages', 'before test1 (top level)', after='before test2\n\n')
    # body.yaml_add_eol_comment('STAGE COMMENT', key='stages')
    body_text = ruamel.yaml.round_trip_dump(body, Dumper=ruamel.yaml.RoundTripDumper)

    header = ub.codeblock(
        '''
        # Autogenerated by ~/code/xcookie/xcookie/builders/gitlab_ci.py
        '''
    )
    footer = '# end'
    text = header + '\n\n' + body_text + '\n\n' + footer
    return text
