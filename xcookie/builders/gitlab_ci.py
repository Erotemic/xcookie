from __future__ import annotations

from typing import Any

import ubelt as ub

from xcookie.builders import ci_model
from xcookie.builders import common_ci
from xcookie.builders.ci_plan import CIPlan


class GitLabCIRenderer:
    """Render GitLab CI YAML from a provider-neutral CI plan."""

    def __init__(self, applier, plan: CIPlan | None = None):
        self.applier = applier
        self.plan = plan if plan is not None else common_ci.make_ci_plan(applier)

    def render(self) -> str:
        if 'purepy' in self.applier.tags:
            return make_purepy_ci_jobs(self.applier, plan=self.plan)
        elif 'binpy' in self.applier.tags:
            return make_binpy_ci_jobs(self.applier, plan=self.plan)
        else:
            raise NotImplementedError



def _add_yaml_merge(target, referent):
    """Attach a YAML merge key across ruamel.yaml versions.

    Older xcookie code used ``add_yaml_merge([(0, referent)])``.  Newer
    ruamel.yaml releases expect a ``MergeValue`` object; plain lists can be
    accepted by ``add_yaml_merge`` but fail later while dumping because they do
    not provide ``sequence`` / ``merge_pos`` attributes.
    """
    try:
        from ruamel.yaml.mergevalue import MergeValue
    except Exception:  # pragma: no cover - old ruamel fallback
        target.add_yaml_merge([(0, referent)])
    else:
        merge_value = MergeValue()
        merge_value.merge_pos = 0
        merge_value.append(referent)
        target.add_yaml_merge(merge_value)

def build_gitlab_ci(self):
    """
    Example:
        >>> from xcookie.builders.gitlab_ci import *  # NOQA
        >>> from xcookie.main import XCookieConfig
        >>> from xcookie.main import TemplateApplier
        >>> config = XCookieConfig(tags=['purepy'], repo_name='mymod')
        >>> config['enable_gpg'] = False
        >>> config['linter'] = False
        >>> config['test_variants'] = ['full-loose']
        >>> config['ci_cpython_versions'] = config['ci_cpython_versions'][-2:]
        >>> self = TemplateApplier(config)
        >>> text = build_gitlab_ci(self)
        >>> print(ub.highlight_code(text, 'yaml'))
    """
    return GitLabCIRenderer(self).render()


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
        '''
    )
    return text


# class YamlBuilder:
#     def __init__(self, data):
#         pass


def workflow_section():
    from xcookie.util_yaml import Yaml

    return Yaml.loads(
        ub.codeblock(
            """
        rules:
          # Allow merge request pipelines (from main repo and forks)
          - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'

          # Allow branch pipelines for default branch (e.g. main)
          - if: '$CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH'

          # Allow branch pipelines for release branch
          - if: '$CI_COMMIT_BRANCH == "release"'
        """
        )
    )


def make_purepy_ci_jobs(self, plan: CIPlan | None = None):
    if plan is None:
        plan = common_ci.make_ci_plan(self)
    import ruamel.yaml  # NOQA
    from ruamel.yaml.comments import CommentedMap, CommentedSeq
    from xcookie.util_yaml import Yaml
    from xcookie.constants import KNOWN_CPYTHON_DOCKER_IMAGES

    enable_gpg = self.config['enable_gpg']

    body = CommentedMap()

    body['workflow'] = workflow_section()

    enable_lint = self.config.linter

    stages = []
    if enable_lint:
        stages.append('lint')
    stages.append('build')
    if enable_gpg:
        stages.append('gpgsign')
    stages.append('test')

    # Broken: needs to be fixed
    # body.update(Yaml.loads(ub.codeblock(
    #     '''
    #     include:
    #         - local: .gitlab/rules.yml
    #     ''')))

    # # Metadata shared my many jobs
    # - local: .gitlab/rules.yml
    body['stages'] = CommentedSeq(stages)
    body.yaml_add_eol_comment('stages', 'TEMPLATE1,c 1')

    common_template_data = ub.udict(
        Yaml.loads(
            ub.codeblock(
                """
        tags:
            # Tags define which runners will accept which jobs
            - docker
            - linux-x86_64
            - build

        variables:
            # Change pip's cache directory to be inside the project directory
            # since we can only cache local items.
            PIP_CACHE_DIR: "$CI_PROJECT_DIR/.cache/pip"
            UV_CACHE_DIR: "$CI_PROJECT_DIR/.cache/uv"

        except:
            # Don't run the pipeline for new tags
            - tags

        cache:
            paths:
                - .cache/pip
                - .cache/uv
        """
            )
        )
    )

    common_template = CommentedMap(common_template_data)
    common_template.yaml_set_anchor('common_template')
    body['.common_template'] = common_template

    if 'kitware' in self.tags:
        body['.common_template']['tags'].append('kitware-python-stack')

    wheelhouse_dpath = 'dist'

    enable_sdist = True
    if enable_sdist:
        # Make the sdist build template
        build_parts = common_ci.make_build_sdist_parts(self, wheelhouse_dpath)
        build_sdist_template = {
            'stage': 'build',
            # 'before_script': [
            #     'python -V  # Print out python version for debugging',
            #     'df -h',
            # ],
            'script': build_parts['commands'],
            'artifacts': {
                'paths': [
                    build_parts['artifact'],
                ]
            },
        }
        build_sdist_template = CommentedMap(build_sdist_template)
        build_sdist_template.yaml_set_anchor('build_sdist_template')
        body['.build_sdist_template'] = build_sdist_template
        _add_yaml_merge(build_sdist_template, common_template)

    # Make the wheel build template
    enable_wheel = True
    if enable_wheel:
        build_parts = common_ci.make_build_wheel_parts(self, wheelhouse_dpath)
        build_wheel_template = {
            'stage': 'build',
            'before_script': [
                'python -V  # Print out python version for debugging',
                'df -h',
            ],
            'script': build_parts['commands'],
            'artifacts': {
                'paths': [
                    build_parts['artifact'],
                ]
            },
        }
        build_wheel_template = CommentedMap(build_wheel_template)
        build_wheel_template.yaml_set_anchor('build_wheel_template')
        body['.build_wheel_template'] = build_wheel_template
        _add_yaml_merge(build_wheel_template, common_template)

    common_test_template = {
        'stage': 'test',
        # Coverage is a regex that will parse the coverage from the test stdout
        'coverage': '/TOTAL.+ ([0-9]{1,3}%)/',
        # Skip tests on the release branch, as these were covered in the MR and
        # main. This speeds up deployment and deployment debugging.
        'except': {'refs': ['release']},
    }

    common_test_template = CommentedMap(common_test_template)
    common_test_template.yaml_set_anchor('common_test_template')
    _add_yaml_merge(common_test_template, common_template)
    body['.common_test_template'] = common_test_template

    setup_venv_template = Yaml.CodeBlock(
        f"""
        # Setup the correct version of python (which should be the same as this instance)
        python --version  # Print out python version for debugging
        export PYVER=$(python -c "import sys; print(''.join(map(str, sys.version_info[0:2])))")
        python -m pip install virtualenv
        python -m virtualenv venv$PYVER
        source venv$PYVER/bin/activate
        {self.UPDATE_PIP}
        {self.PIP_INSTALL} setuptools -U
        {self.PIP_INSTALL} pygments
        python --version  # Print out python version for debugging
        """
    )


    artifact_test_cases = ci_model.make_artifact_test_cases(
        self, plan=plan, provider='gitlab'
    )
    install_extras = plan.active_install_extras()
    test_templates: dict[str, Any] = {}
    for case in ci_model.unique_variant_cases(artifact_test_cases):
        extra_key = case.variant.key
        extra = case.install_extras
        special_install_lines = case.gitlab_special_install_lines(
            self.PIP_INSTALL_PREFER_BINARY
        )
        workspace_dname = 'sandbox'
        install_and_test_wheel_parts = (
            common_ci.make_install_and_test_wheel_parts(
                self, wheelhouse_dpath, special_install_lines, workspace_dname
            )
        )
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
        _add_yaml_merge(test, common_test_template)
        body['.' + anchor] = test
        test_templates[extra_key] = test

    supported_platform_info = common_ci.get_supported_platform_info(self)
    main_pyver = supported_platform_info['main_python_version']
    main_cpver = 'cp' + main_pyver.replace('.', '')
    main_image = KNOWN_CPYTHON_DOCKER_IMAGES[main_cpver]

    build_names = []

    if enable_sdist:
        # Construct the explicit build / test job pairs
        jobs = {}
        opsys = 'linux'
        arch = 'x86_64'
        pyver = supported_platform_info['main_python_version']
        cpver = 'cp' + pyver.replace('.', '')
        build_name = 'build/sdist'
        build_names.append(build_name)
        build_job = {
            'image': main_image,
        }
        build_job = CommentedMap(build_job)
        _add_yaml_merge(build_job, build_sdist_template)
        jobs[build_name] = build_job

        sdist_test_python_versions = [pyver]
        sdist_extra_keys = [ub.peek(install_extras)]
        for pyver in sdist_test_python_versions:
            cpver = 'cp' + pyver.replace('.', '')
            assert cpver in KNOWN_CPYTHON_DOCKER_IMAGES
            swenv_key = f'{cpver}-{opsys}-{arch}'  # software environment key
            for extra_key in sdist_extra_keys:
                common_test_template = test_templates[extra_key]
                test_name = f'test/sdist/{extra_key}/{swenv_key}'
                test_job = {
                    'image': main_image,
                    'needs': [
                        build_name,
                    ],
                }
                test_job = CommentedMap(test_job)
                _add_yaml_merge(test_job, common_test_template)
                jobs[test_name] = test_job
        body.update(jobs)


    if enable_wheel:
        # Construct the explicit build / test job pairs from the shared
        # provider-neutral artifact test cases.  GitLab still renders one job
        # per case, while GitHub renders the same cases as matrix entries.
        jobs = {}
        build_job_names = set()
        for case in artifact_test_cases:
            cpver = case.gitlab_cpver
            if cpver not in KNOWN_CPYTHON_DOCKER_IMAGES:
                continue
            swenv_key = case.gitlab_swenv_key
            build_name = f'build/{swenv_key}'
            if build_name not in build_job_names:
                build_names.append(build_name)
                build_job = {
                    'image': KNOWN_CPYTHON_DOCKER_IMAGES[cpver],
                }
                build_job = CommentedMap(build_job)
                _add_yaml_merge(build_job, build_wheel_template)
                jobs[build_name] = build_job
                build_job_names.add(build_name)

            common_test_template = test_templates[case.variant.key]
            test_name = f'test/{case.variant.key}/{swenv_key}'
            test_job = {
                'image': KNOWN_CPYTHON_DOCKER_IMAGES[cpver],
                'needs': [
                    build_name,
                ],
            }
            test_job = CommentedMap(test_job)
            _add_yaml_merge(test_job, common_test_template)
            jobs[test_name] = test_job
        body.update(jobs)

    if enable_lint:
        lint_job = build_lint_job(self, common_template, main_image, plan=plan)
        body['lint'] = lint_job

    if enable_gpg:
        gpgsign_job = build_gpg_job(
            self, common_template, main_image, wheelhouse_dpath
        )
        gpgsign_job['needs'] = [
            {'job': build_name, 'artifacts': True} for build_name in build_names
        ]
        body['gpgsign/wheels'] = gpgsign_job

    deploy = self.config['deploy']
    if deploy:
        deploy_job = build_deploy_job(
            self, common_template, main_image, wheelhouse_dpath
        )
        body['stages'].append('deploy')
        body['deploy/wheels'] = deploy_job

    # 0.17.32
    # body_text = ruamel.yaml.round_trip_dump(body, Dumper=ruamel.yaml.RoundTripDumper)
    # body = ruamel.yaml.round_trip_load(body_text)

    body_text = Yaml.dumps(body)
    body = Yaml.loads(body_text)

    body['stages'].yaml_set_start_comment('TEMPLATES')
    # body.yaml_set_comment_before_after_key('stages', 'before test1 (top level)', after='before test2\n\n')
    # body.yaml_add_eol_comment('STAGE COMMENT', key='stages')

    # body_text = ruamel.yaml.round_trip_dump(body, Dumper=ruamel.yaml.RoundTripDumper)
    body_text = Yaml.dumps(body)

    header = ub.codeblock(
        """
        # Autogenerated by ~/code/xcookie/xcookie/builders/gitlab_ci.py
        """
    )
    footer = '# end'
    text = header + '\n\n' + body_text + '\n\n' + footer
    return text


def make_binpy_ci_jobs(self, plan: CIPlan | None = None):
    if plan is None:
        plan = common_ci.make_ci_plan(self)
    import ruamel.yaml  # NOQA
    from ruamel.yaml.comments import CommentedMap, CommentedSeq
    from xcookie.util_yaml import Yaml
    from xcookie.constants import KNOWN_CPYTHON_DOCKER_IMAGES

    enable_gpg = self.config['enable_gpg']

    body = CommentedMap()

    body['workflow'] = workflow_section()

    stages = ['build', 'test']
    if enable_gpg:
        stages.append('gpgsign')
    body['stages'] = CommentedSeq(stages)

    common_template_data = ub.udict(
        Yaml.loads(
            ub.codeblock(
                """
        tags:
            - docker
            - linux-x86_64
            - build

        variables:
            PIP_CACHE_DIR: "$CI_PROJECT_DIR/.cache/pip"
            UV_CACHE_DIR: "$CI_PROJECT_DIR/.cache/uv"

        cache:
            paths:
                - .cache/pip
                - .cache/uv
        """
            )
        )
    )

    common_template = CommentedMap(common_template_data)
    common_template.yaml_set_anchor('common_template')
    body['.common_template'] = common_template

    if 'kitware' in self.tags:
        body['.common_template']['tags'].append('kitware-python-stack')

    wheelhouse_dpath = 'wheelhouse'

    # TODO: We may want to bake in a lot of the configuration vfs stuff into
    # the podman image that we are using. Not sure if that matters, or if there
    # is a more efficient way to use podman here.
    podman_image = 'gitlab.kitware.com:4567/computer-vision/ci-docker/podman:v4.9.0-uv0.8.8-python3.12-cuda12.4.1-cudnn-devel-ubuntu22.04'

    cibuildwheel_template = Yaml.loads(
        ub.codeblock(
            rf"""
        stage: build
        tags:
            - linux-x86_64
            - docker
            - privileged
        image: {podman_image}
        script:
            - podman --version
            - podman info --debug
            - python3 -m pip install cibuildwheel>=2.8.0
            - pwd
            - ls -al
            - mkdir -p ".cache/containers/vfs-storage/"
            - |
              codeblock()
              {{
                  PYEXE=python3
                  echo "$1" | $PYEXE -c "import sys; from textwrap import dedent; print(dedent(sys.stdin.read()).strip(chr(10)))"
              }}
              export CONTAINERS_CONF=$(realpath "temp_containers.conf")
              export CONTAINERS_STORAGE_CONF=$(realpath "temp_storage.conf")
              codeblock "
              [storage]
              driver=\"vfs\"
              graphroot=\"$HOME/.local/share/containers/vfs-storage\"
              runroot=\"$HOME/.local/share/containers/vfs-runroot\"
              [storage.options.aufs]
              mountopt=\"rw\"
              " > $CONTAINERS_STORAGE_CONF
              codeblock "
              [containers]
              default_capabilities = [
                \"CHOWN\",
                \"DAC_OVERRIDE\",
                \"FOWNER\",
                \"FSETID\",
                \"KILL\",
                \"NET_BIND_SERVICE\",
                \"SETFCAP\",
                \"SETGID\",
                \"SETPCAP\",
                \"SETUID\",
                \"SYS_CHROOT\"
              ]
              [engine]
              cgroup_manager=\"cgroupfs\"
              events_logger=\"file\"
              [machine]
              " > $CONTAINERS_CONF
              cat $CONTAINERS_CONF
              cat $CONTAINERS_STORAGE_CONF
            - podman info --debug
            - export CIBW_CONTAINER_ENGINE="podman"
            - cibuildwheel --config-file pyproject.toml --platform linux --print-build-identifiers
            - cibuildwheel --config-file pyproject.toml --output-dir wheelhouse --platform linux
            - ls $CIBW_OCI_ROOT
            - ls wheelhouse
        artifacts:
            paths:
                - wheelhouse/
        """
        )
    )

    cibuildwheel_template = CommentedMap(cibuildwheel_template)
    cibuildwheel_template.yaml_set_anchor('cibuildwheel_template')
    body['.cibuildwheel_template'] = cibuildwheel_template

    common_test_template = {
        'stage': 'test',
        'coverage': '/TOTAL.+ ([0-9]{1,3}%)/',
        'except': {'refs': ['release']},
    }
    common_test_template = CommentedMap(common_test_template)
    common_test_template.yaml_set_anchor('common_test_template')
    _add_yaml_merge(common_test_template, common_template)
    body['.common_test_template'] = common_test_template

    setup_venv_template = Yaml.CodeBlock(
        f"""
        # Setup the correct version of python (which should be the same as this instance)
        python --version  # Print out python version for debugging
        export PYVER=$(python -c "import sys; print(''.join(map(str, sys.version_info[0:2])))")
        python -m pip install virtualenv
        python -m virtualenv venv$PYVER
        source venv$PYVER/bin/activate
        {self.UPDATE_PIP}
        {self.PIP_INSTALL} setuptools -U
        {self.PIP_INSTALL} pygments
        python --version  # Print out python version for debugging
        """
    )

    workflow_plan = ci_model.make_binpy_workflow_plan(
        self, plan=plan, provider='gitlab'
    )
    artifact_test_cases = list(workflow_plan.artifact_test_cases)
    test_templates: dict[str, Any] = {}
    for case in ci_model.unique_variant_cases(artifact_test_cases):
        extra_key = case.variant.key
        extra = case.install_extras
        special_install_lines = case.gitlab_special_install_lines(
            self.PIP_INSTALL_PREFER_BINARY
        )
        workspace_dname = 'sandbox'
        install_and_test_wheel_parts = (
            common_ci.make_install_and_test_wheel_parts(
                self, wheelhouse_dpath, special_install_lines, workspace_dname
            )
        )
        test_steps = [f'export INSTALL_EXTRAS="{extra}"']
        test_steps += install_and_test_wheel_parts['install_wheel_commands']
        test_steps += install_and_test_wheel_parts['test_wheel_commands']
        test = {
            'before_script': [setup_venv_template],
            'script': test_steps,
        }
        anchor = f'test_{extra_key}_template'
        test = CommentedMap(test)
        test.yaml_set_anchor(anchor)
        _add_yaml_merge(test, common_test_template)
        body['.' + anchor] = test
        test_templates[extra_key] = test

    supported_platform_info = common_ci.get_supported_platform_info(self)
    main_pyver = supported_platform_info['main_python_version']
    main_cpver = 'cp' + main_pyver.replace('.', '')
    main_image = KNOWN_CPYTHON_DOCKER_IMAGES[main_cpver]

    build_names: list[str] = []
    jobs: dict[str, Any] = {}
    build_job_names: set[str] = set()
    for case in artifact_test_cases:
        cpver = case.gitlab_cpver
        if cpver not in KNOWN_CPYTHON_DOCKER_IMAGES:
            continue
        image = KNOWN_CPYTHON_DOCKER_IMAGES[cpver]

        # TODO: handle this case in other variants
        extra_environs: dict[str, str] = {}

        # fixme: might not be a robust check, e.g. python could release, but
        # packages might not have official wheels yet.
        needs_prerelease = '-rc' in image
        if needs_prerelease:
            if self.config['use_uv']:
                # TODO: determine if we need torch prereleases or what else
                extra_environs.update(
                    {
                        'UV_PRERELEASE': 'allow',
                        'UV_INDEX_STRATEGY': 'unsafe-best-match',
                        'UV_INDEX': ' '.join(
                            [
                                'https://pypi.org/simple',
                                'https://download.pytorch.org/whl/nightly/cpu',
                                # 'https://download.pytorch.org/whl/nightly/cu126',
                            ]
                        ),
                    }
                )

        swenv_key = case.gitlab_swenv_key
        build_name = workflow_plan.wheel_build_job_key.format(
            swenv_key=swenv_key
        )
        if build_name not in build_job_names:
            build_job = {
                'variables': {
                    'CIBW_BUILD': f'{cpver}-*',
                }
            }
            build_job = CommentedMap(build_job)
            _add_yaml_merge(build_job, cibuildwheel_template)
            jobs[build_name] = build_job
            build_names.append(build_name)
            build_job_names.add(build_name)

        common_test_template = test_templates[case.variant.key]
        test_name = workflow_plan.artifact_test_job_key.format(
            variant_key=case.variant.key,
            swenv_key=swenv_key,
        )
        test_job = {
            'image': image,
            'needs': [build_name],
        }
        test_job = CommentedMap(test_job)
        _add_yaml_merge(test_job, common_test_template)
        if extra_environs:
            test_job['variables'] = extra_environs.copy()
        jobs[test_name] = test_job

    body.update(jobs)

    if enable_gpg:
        gpgsign_job = build_gpg_job(
            self, common_template, main_image, wheelhouse_dpath
        )
        gpgsign_job['needs'] = [
            {'job': build_name, 'artifacts': True} for build_name in build_names
        ]
        body['gpgsign/wheels'] = gpgsign_job

    deploy = self.config['deploy']
    if deploy:
        body['stages'].append('deploy')
        deploy_job = build_deploy_job(
            self, common_template, main_image, wheelhouse_dpath
        )
        body['deploy/wheels'] = deploy_job

    body_text = Yaml.dumps(body)
    body = Yaml.loads(body_text)

    header = ub.codeblock(
        """
        # Autogenerated by ~/code/xcookie/xcookie/builders/gitlab_ci.py
        """
    )
    footer = '# end'
    text = header + '\n\n' + body_text + '\n\n' + footer
    return text


def build_lint_job(self, common_template, deploy_image, plan: CIPlan | None = None):
    from ruamel.yaml.comments import CommentedMap

    from xcookie.util_yaml import Yaml

    lint_job: dict[str, Any] = {}
    lint_job.update(
        ub.udict(
            Yaml.loads(
                ub.codeblock(
                    f"""
        image:
            {deploy_image}

        stage:
            lint
        """
                )
            )
        )
    )

    # TODO: only install linting requirements if the file exists.
    lint_job.update(
        Yaml.loads(
            ub.codeblock(
                f"""
        before_script:
            - df -h
        script:
            - {self.UPDATE_PIP}
            - {self.PIP_INSTALL} -r requirements/linting.txt
            - ./run_linter.sh
        """
            )
        )
    )

    # Add typechecking commands (mypy + ty by default) unless disabled
    if 'notypes' not in self.tags:
        typecheck_cmds = common_ci.make_typecheck_parts(self, plan=plan)
        # Ensure the script key exists and is a list
        script_list = lint_job.get('script') or []
        # Extend script with typecheck commands
        script_list = list(script_list) + typecheck_cmds
        lint_job['script'] = script_list

    lint_job = CommentedMap(lint_job)
    _add_yaml_merge(lint_job, common_template)

    lint_job['allow_failure'] = True
    return lint_job


def build_gpg_job(self, common_template, deploy_image, wheelhouse_dpath):
    # import ruamel.yaml
    from ruamel.yaml.comments import CommentedMap

    from xcookie.util_yaml import Yaml

    ci_gpg_transport = self.config.get(
        'ci_gpg_secret_transport', 'encrypted_repo'
    )
    use_direct_gpg = ci_gpg_transport == 'direct_ci'

    _dist_patterns = []
    _dist_patterns.append(wheelhouse_dpath + '/*.whl')
    if 'nosrcdist' not in self.tags:
        _dist_patterns.append(wheelhouse_dpath + '/*.tar.gz')
    dist_pattern = ' '.join(_dist_patterns)

    _artifact_patterns = []
    _artifact_patterns.append(wheelhouse_dpath + '/*.whl')
    _artifact_patterns.append(wheelhouse_dpath + '/*.asc')
    if 'nosrcartifact' not in self.tags and 'nosrcdist' not in self.tags:
        _artifact_patterns.append(wheelhouse_dpath + '/*.tar.gz')
    artifact_pattern = ' '.join(_artifact_patterns)

    gpgsign_job = {}
    gpgsign_job.update(
        ub.udict(
            Yaml.loads(
                ub.codeblock(
                    f"""
        image:
            {deploy_image}

        stage:
            gpgsign

        artifacts:
            paths:
                - {wheelhouse_dpath}/*.asc
                - {wheelhouse_dpath}/*.tar.gz
                - {wheelhouse_dpath}/*.whl
        only:
            refs:
                # Gitlab will only expose protected variables on protected branches
                # (which I've set to be main and release), so only run this stage
                # there.
                - master
                - main
                - release
        """
                )
            )
        )
    )

    if use_direct_gpg:
        # direct_ci mode: GPG material comes from protected+masked CI
        # variables; no .enc files, no CI_SECRET, no indirect expansion.
        # Public signer identity is pinned in dev/public_gpg_key (full
        # fingerprint) and verified after import.
        preamble_script = [
            f'ls {wheelhouse_dpath}',
            'export GPG_EXECUTABLE=gpg',
            # Read pinned primary fingerprint from repo anchor file
            'export GPG_KEYID=$(cat dev/public_gpg_key)',
            'echo "GPG_KEYID = $GPG_KEYID"',
            '$GPG_EXECUTABLE --version',
            'openssl version',
            '$GPG_EXECUTABLE --list-keys',
            'echo "Importing GPG keys from CI secrets"',
            # Import public key first so the primary fingerprint is visible
            # before the secret subkey is imported
            'printf \'%s\' "$GPG_PUBLIC_KEY_B64" | base64 -d | $GPG_EXECUTABLE --import',
            'printf \'%s\' "$GPG_OWNER_TRUST_B64" | base64 -d | $GPG_EXECUTABLE --import-ownertrust',
            'printf \'%s\' "$GPG_SECRET_SIGNING_SUBKEY_B64" | base64 -d | $GPG_EXECUTABLE --import',
            # Verify imported key matches the repo-pinned fingerprint
            'IMPORTED_FPR=$($GPG_EXECUTABLE --list-keys --with-colons "$GPG_KEYID" | awk -F: \'/^fpr/ { print $10; exit }\')',
            '[[ "$IMPORTED_FPR" == "$GPG_KEYID" ]] || { echo "ERROR: fingerprint mismatch: $IMPORTED_FPR != $GPG_KEYID"; exit 1; }',
            'echo "GPG fingerprint verified: $IMPORTED_FPR"',
            'GPG_SIGN_CMD="$GPG_EXECUTABLE --batch --yes --detach-sign --armor --local-user $GPG_KEYID"',
        ]
    else:
        # encrypted_repo mode (default): decrypt .enc files using CI_SECRET.
        # VARNAME_CI_SECRET indirection lets each org name the secret
        # differently without changing the CI template.
        preamble_script = [
            f'ls {wheelhouse_dpath}',
            'export GPG_EXECUTABLE=gpg',
            'export GPG_KEYID=$(cat dev/public_gpg_key)',
            'echo "GPG_KEYID = $GPG_KEYID"',
            '# Decrypt and import GPG Keys / trust',
            '# note the variable pointed to by VARNAME_CI_SECRET is a protected variable only available on main and release branch',
            'source dev/secrets_configuration.sh',
            'CI_SECRET=${!VARNAME_CI_SECRET}',
            '$GPG_EXECUTABLE --version',
            'openssl version',
            '$GPG_EXECUTABLE --list-keys',
            '# note CI_KITWARE_SECRET is a protected variable only available on main and release branch',
            'CIS=$CI_SECRET openssl enc -aes-256-cbc -pbkdf2 -md SHA512 -pass env:CIS -d -a -in dev/ci_public_gpg_key.pgp.enc | $GPG_EXECUTABLE --import',
            'CIS=$CI_SECRET openssl enc -aes-256-cbc -pbkdf2 -md SHA512 -pass env:CIS -d -a -in dev/gpg_owner_trust.enc | $GPG_EXECUTABLE --import-ownertrust',
            'CIS=$CI_SECRET openssl enc -aes-256-cbc -pbkdf2 -md SHA512 -pass env:CIS -d -a -in dev/ci_secret_gpg_subkeys.pgp.enc | $GPG_EXECUTABLE --import',
            'GPG_SIGN_CMD="$GPG_EXECUTABLE --batch --yes --detach-sign --armor --local-user $GPG_KEYID"',
        ]

    gpgsign_job['script'] = preamble_script
    gpgsign_job['script'].append(
        Yaml.CodeBlock(
            """
            WHEEL_PATHS=("""
            + dist_pattern
            + """)
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
            """
        )
    )
    gpgsign_job['script'].append(f'ls {wheelhouse_dpath}')

    gpgsign_job = CommentedMap(gpgsign_job)
    _add_yaml_merge(gpgsign_job, common_template)

    enable_otc = True
    if enable_otc:
        # Use an open timestamp to tag when the signature and wheels were
        # created
        gpgsign_job['artifacts']['paths'].append(f'{wheelhouse_dpath}/*.ots')
        gpgsign_job['script'].append(f'{self.UPDATE_PIP}')
        gpgsign_job['script'].append(
            f'{self.PIP_INSTALL} opentimestamps-client'
        )
        gpgsign_job['script'].append(f'ots stamp {artifact_pattern}')
    return gpgsign_job


def build_deploy_job(self, common_template, deploy_image, wheelhouse_dpath):
    # import ruamel.yaml
    from ruamel.yaml.comments import CommentedMap

    from xcookie.util_yaml import Yaml

    deploy_job = {}
    deploy_job.update(
        ub.udict(
            Yaml.loads(
                ub.codeblock(
                    f"""
        image:
            {deploy_image}

        stage:
            deploy

        only:
            refs:
                - release
        """
                )
            )
        )
    )
    deploy_script = [
        f'{self.UPDATE_PIP}',
        f'{self.PIP_INSTALL} pyopenssl ndg-httpsclient pyasn1 requests[security] setuptools twine -U',
        f'ls {wheelhouse_dpath}',
    ]

    _dist_patterns = []
    _dist_patterns.append(wheelhouse_dpath + '/*.whl')
    if 'nosrcdist' not in self.tags:
        _dist_patterns.append(wheelhouse_dpath + '/*.tar.gz')
    dist_pattern = ' '.join(_dist_patterns)

    if self.config['deploy_pypi']:
        deploy_script += [
            Yaml.CodeBlock(
                """
                set -e
                WHEEL_PATHS=("""
                + dist_pattern
                + """)
                WHEEL_PATHS_STR=$(printf '"%s" ' "${WHEEL_PATHS[@]}")
                source dev/secrets_configuration.sh
                TWINE_PASSWORD=${!VARNAME_TWINE_PASSWORD}
                TWINE_USERNAME=${!VARNAME_TWINE_USERNAME}
                echo "$WHEEL_PATHS_STR"
                for WHEEL_PATH in "${WHEEL_PATHS[@]}"
                do
                    twine check $WHEEL_PATH
                    twine upload --username $TWINE_USERNAME --password $TWINE_PASSWORD $WHEEL_PATH || echo "upload already exists"
                done
                """
            )
        ]

    if self.config['deploy_tags']:
        deploy_script += [
            Yaml.CodeBlock(
                'set -e\n'
                + common_ci.make_project_version_assignment(
                    self, 'PROJECT_VERSION', export=True
                )
                + '\n'
                + r"""
                # Have the server git-tag the release and push the tags
                # do sed twice to handle the case of https clone with and without a read token
                URL_HOST=$(git remote get-url origin | sed -e 's|https\?://.*@||g' | sed -e 's|https\?://||g' | sed -e 's|git@||g' | sed -e 's|:|/|g')
                source dev/secrets_configuration.sh
                PUSH_TOKEN=${!VARNAME_PUSH_TOKEN}
                echo "URL_HOST = $URL_HOST"
                # A git config user name and email is required. Set if needed.
                if [[ "$(git config user.email)" == "" ]]; then
                    git config user.email "ci@gitlab.org.com"
                    git config user.name "Gitlab-CI"
                fi
                TAG_NAME="v${PROJECT_VERSION}"
                echo "TAG_NAME = $TAG_NAME"
                if [ $(git tag -l "$TAG_NAME") ]; then
                    echo "Tag already exists"
                else
                    # if we messed up we can delete the tag
                    # git push origin :refs/tags/$TAG_NAME
                    # and then tag with -f
                    git tag $TAG_NAME -m "tarball tag $PROJECT_VERSION"
                    git push --tags "https://git-push-token:${PUSH_TOKEN}@${URL_HOST}"
                fi
                """
            )
        ]

    if self.config['deploy_artifacts']:
        # Add artifacts to the package registry
        deploy_script += [
            Yaml.CodeBlock(
                rf'''
                set -e
                # https://docs.gitlab.com/ee/ci/variables/predefined_variables.html
                echo "CI_PROJECT_ID=$CI_PROJECT_ID"
                echo "CI_PROJECT_NAME=$CI_PROJECT_NAME"
                echo "CI_API_V4_URL=$CI_API_V4_URL"

                {common_ci.make_project_version_assignment(self, 'PROJECT_VERSION', export=True)}
                echo "PROJECT_VERSION=$PROJECT_VERSION"

                # If running on CI use CI authentication, otherwise
                # assume we developer authentication available.
                if [[ -z "$CI_JOB_TOKEN" ]]; then
                    AUTH_HEADER="PRIVATE-TOKEN: $PRIVATE_GITLAB_TOKEN"
                else
                    AUTH_HEADER="JOB-TOKEN: $CI_JOB_TOKEN"
                fi

                # Loop over all of the assets in the wheelhouse (i.e.  dist)
                # and upload them to a package registry. We also store the
                # links to the artifacts so we can attach them to a release
                # page.
                PACKAGE_ARTIFACT_ARRAY=()
                for FPATH in "{wheelhouse_dpath}"/*; do
                    FNAME=$(basename $FPATH)
                    echo "Upload artifact: $FNAME"
                    PACKAGE_URL="$CI_API_V4_URL/projects/$CI_PROJECT_ID/packages/generic/$CI_PROJECT_NAME/$PROJECT_VERSION/$FNAME"
                    curl \
                        --header "$AUTH_HEADER" \
                        --upload-file $FPATH \
                        "$PACKAGE_URL"
                    PACKAGE_ARTIFACT_ARRAY+=("$PACKAGE_URL")
                done

                '''
            )
        ]

        # Create a gitlab release, but only if deploy artifacts AND tags are
        # also on.
        # https://docs.gitlab.com/ee/api/releases/#create-a-release
        if self.config['deploy_tags']:
            if 0:
                __note__ = r"""
                    To populate the CI variables and test locally
                    This logic is quick and dirty, could be cleaned up

                    load_secrets
                    export PRIVATE_GITLAB_TOKEN=$(git_token_for https://gitlab.kitware.com)
                    echo "PRIVATE_GITLAB_TOKEN=$PRIVATE_GITLAB_TOKEN"
                    DEPLOY_REMOTE=origin
                    GROUP_NAME=$(git remote get-url "$DEPLOY_REMOTE" | cut -d ":" -f 2 | cut -d "/" -f 1)
                    HOST=https://$(git remote get-url "$DEPLOY_REMOTE" | cut -d "/" -f 1 | cut -d "@" -f 2 | cut -d ":" -f 1)

                    CI_PROJECT_NAME=$(git remote get-url "$DEPLOY_REMOTE" | cut -d "/" -f 2 | cut -d "." -f 1)
                    CI_API_V4_URL=$HOST/api/v4

                    # TODO: better use of gitlab python api
                    TMP_DIR=$(mktemp -d -t ci-XXXXXXXXXX)
                    curl --header "PRIVATE-TOKEN: $PRIVATE_GITLAB_TOKEN" "$HOST/api/v4/groups" > "$TMP_DIR/all_group_info"
                    GROUP_ID=$(cat "$TMP_DIR/all_group_info" | jq ". | map(select(.name==\"$GROUP_NAME\")) | .[0].id")
                    curl --header "PRIVATE-TOKEN: $PRIVATE_GITLAB_TOKEN" "$HOST/api/v4/groups/$GROUP_ID" > "$TMP_DIR/group_info"
                    CI_PROJECT_ID=$(cat "$TMP_DIR/group_info" | jq ".projects | map(select(.name==\"$CI_PROJECT_NAME\")) | .[0].id")
                    echo "CI_PROJECT_ID=$CI_PROJECT_ID"
                    echo "CI_PROJECT_NAME=$CI_PROJECT_NAME"
                    echo "CI_API_V4_URL=$CI_API_V4_URL"

                    {common_ci.make_project_version_assignment(self, 'PROJECT_VERSION', export=True)}

                    # Building this dummy variable requires some wheels built
                    # in the local dir, the next step wont use them directly
                    # it will just use their names, and only point to the ones
                    # in the package registry.
                    DO_UPLOAD=0 DO_TAG=0 ./publish.sh

                    export PACKAGE_ARTIFACT_ARRAY=()
                    for FPATH in "dist"/*; do
                        FNAME=$(basename $FPATH)
                        PACKAGE_URL="$CI_API_V4_URL/projects/$CI_PROJECT_ID/packages/generic/$CI_PROJECT_NAME/$PROJECT_VERSION/$FNAME"
                        PACKAGE_ARTIFACT_ARRAY+=("$PACKAGE_URL")
                    done
                    echo "PACKAGE_ARTIFACT_ARRAY=${PACKAGE_ARTIFACT_ARRAY[@]}"
                """
                __note__
            deploy_script += [
                Yaml.CodeBlock(
                    common_ci.make_project_version_assignment(
                        self, 'PROJECT_VERSION', export=True
                    )
                    + '\n'
                    + r"""
                    echo "PROJECT_VERSION=$PROJECT_VERSION"
                    TAG_NAME="v$PROJECT_VERSION"

                    # Construct the JSON for assets to attach to the release
                    RELEASE_ASSET_JSON_LINKS=()
                    for ASSET_URL in "${PACKAGE_ARTIFACT_ARRAY[@]}"; do
                        ASSET_FNAME=$(basename $ASSET_URL)
                        RELEASE_ASSET_JSON_LINKS+=("{\"name\": \"$ASSET_FNAME\", \"url\": \"$ASSET_URL\"},")
                    done
                    _ASSET_LINK_JSON="${RELEASE_ASSET_JSON_LINKS[@]}"
                    # remove the trailing comma
                    ASSET_LINK_JSON=${_ASSET_LINK_JSON::-1}
                    echo "ASSET_LINK_JSON=$ASSET_LINK_JSON"

                    # Build json describing the release
                    RELEASE_DATA_JSON="{
                        \"name\": \"Version $PROJECT_VERSION\",
                        \"description\": \"Automated release of $CI_PROJECT_NAME version $PROJECT_VERSION\",
                        \"tag_name\": \"$TAG_NAME\",
                        \"assets\": {\"links\": [$ASSET_LINK_JSON]}
                    }"
                    echo "$RELEASE_DATA_JSON"

                    # If running on CI use CI authentication, otherwise
                    # assume we developer authentication available.
                    if [[ -z "${CI_JOB_TOKEN}" ]]; then
                        AUTH_HEADER="PRIVATE-TOKEN: $PRIVATE_GITLAB_TOKEN"
                    else
                        AUTH_HEADER="JOB-TOKEN: $CI_JOB_TOKEN"
                    fi

                    curl \
                        --header 'Content-Type: application/json' \
                        --header "$AUTH_HEADER" \
                        --data "$RELEASE_DATA_JSON" \
                        --request POST \
                        "$CI_API_V4_URL/projects/$CI_PROJECT_ID/releases"
                    """
                )
            ]

    deploy_job['script'] = deploy_script
    deploy_job = CommentedMap(deploy_job)
    _add_yaml_merge(deploy_job, common_template)
    return deploy_job
