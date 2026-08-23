from xcookie.builders import ci_model
from xcookie.main import TemplateApplier, XCookieConfig


def _make_applier(
    tmp_path,
    *,
    tags,
    enable_gpg=False,
    deploy=False,
    trusted=False,
    direct_gpg=False,
    gpg_transport=None,
    min_python=None,
    ci_artifacts=None,
):
    kwargs = dict(
        repodir=tmp_path,
        repo_name='demo_pkg',
        mod_name='demo_pkg',
        tags=tags,
        interactive=False,
        test_variants=['minimal-strict', 'full-loose'],
    )
    if min_python is not None:
        kwargs['min_python'] = min_python
    if ci_artifacts is not None:
        kwargs['ci_artifacts'] = ci_artifacts
    cfg = XCookieConfig(**kwargs)
    cfg['enable_gpg'] = enable_gpg
    cfg['deploy'] = deploy
    cfg['deploy_pypi'] = deploy
    cfg['linter'] = False
    cfg['ci_pypi_trusted_publishing'] = trusted
    cfg['ci_cpython_versions'] = cfg['ci_cpython_versions'][-2:]
    if gpg_transport is not None:
        cfg['ci_gpg_secret_transport'] = gpg_transport
    elif direct_gpg:
        cfg['ci_gpg_secret_transport'] = 'direct_ci'
    self = TemplateApplier(cfg)
    self._presetup()
    return self


def test_github_release_plan_describes_trusted_publishing(tmp_path):
    self = _make_applier(
        tmp_path,
        tags=['github', 'purepy', 'erotemic'],
        deploy=True,
        trusted=True,
    )
    plan = ci_model.make_release_plan(self, provider='github')

    assert plan.provider == 'github'
    assert plan.package_kind == 'purepy'
    assert plan.build_job_keys == ('build_sdist', 'build_purepy_wheels')
    assert plan.deploy_job_keys == ('test_deploy', 'live_deploy', 'release')
    assert [target.name for target in plan.publish_targets] == [
        'testpypi',
        'pypi',
        'github-release',
    ]
    package_targets = [
        target
        for target in plan.publish_targets
        if target.name in {'testpypi', 'pypi'}
    ]
    assert all(target.trusted_publishing for target in package_targets)
    assert all(target.requires_oidc for target in package_targets)
    assert {target.environment for target in package_targets} == {
        'testpypi',
        'pypi',
    }
    release_targets = [
        target
        for target in plan.publish_targets
        if target.name == 'github-release'
    ]
    assert len(release_targets) == 1
    assert not release_targets[0].trusted_publishing
    assert not release_targets[0].requires_oidc


def test_release_plan_distribution_and_artifact_globs_track_gpg(tmp_path):
    self = _make_applier(
        tmp_path,
        tags=['github', 'binpy'],
        min_python='3.9',
        enable_gpg=True,
        deploy=True,
        gpg_transport='encrypted_repo',
    )
    plan = ci_model.make_release_plan(self, provider='github')

    assert plan.package_kind == 'binpy'
    assert plan.signing_transport == 'encrypted_repo'
    assert plan.distribution_globs == (
        'wheelhouse/*.whl',
        'wheelhouse/*.tar.gz',
    )
    assert 'wheelhouse/*.zip' in plan.artifact_globs
    assert 'wheelhouse/*.asc' in plan.artifact_globs
    assert 'wheelhouse/*.ots' in plan.artifact_globs


def test_gitlab_release_plan_describes_current_gpg_and_deploy_jobs(tmp_path):
    self = _make_applier(
        tmp_path,
        tags=['gitlab', 'purepy'],
        enable_gpg=True,
        deploy=True,
        gpg_transport='encrypted_repo',
    )
    plan = ci_model.make_release_plan(
        self, provider='gitlab', wheelhouse_dpath='dist'
    )

    assert plan.provider == 'gitlab'
    assert plan.package_kind == 'purepy'
    assert plan.build_job_keys == ('build/sdist', 'build/wheel')
    assert plan.deploy_job_keys == ('gpgsign/wheels', 'deploy/wheels')
    assert plan.signing_transport == 'encrypted_repo'
    assert plan.distribution_globs == ('dist/*.whl', 'dist/*.tar.gz')
    assert 'dist/*.asc' in plan.artifact_globs
    assert 'dist/*.ots' in plan.artifact_globs


def test_github_release_workflow_current_trusted_behavior_is_pinned(tmp_path):
    self = _make_applier(
        tmp_path,
        tags=['github', 'purepy', 'erotemic'],
        deploy=True,
        trusted=True,
    )
    text = self.build_github_actions_release()

    assert 'test_deploy:' in text
    assert 'live_deploy:' in text
    assert 'release:' in text
    assert 'build_purepy_wheels:' in text
    assert 'test_purepy_wheels:' not in text
    assert 'pypa/gh-action-pypi-publish@release/v1' in text
    assert 'id-token: write' in text
    assert 'environment: testpypi' in text
    assert 'environment: pypi' in text
    assert 'Trusted publishing setup checklist' in text


def test_github_release_workflow_direct_gpg_uses_environment_secrets(tmp_path):
    self = _make_applier(
        tmp_path,
        tags=['github', 'purepy', 'erotemic'],
        enable_gpg=True,
        deploy=True,
        trusted=False,
        direct_gpg=True,
    )
    text = self.build_github_actions_release()

    assert 'GPG_SECRET_SIGNING_SUBKEY_B64' in text
    assert 'GPG_PUBLIC_KEY_B64' in text
    assert 'GPG_OWNER_TRUST_B64' in text
    assert 'environment: testpypi' in text
    assert 'environment: pypi' in text
    assert 'dev/ci_secret_gpg_subkeys.pgp.enc' not in text


def test_gitlab_gpg_and_deploy_render_current_behavior_is_pinned(tmp_path):
    from xcookie.util_yaml import Yaml

    self = _make_applier(
        tmp_path,
        tags=['gitlab', 'purepy'],
        enable_gpg=True,
        deploy=True,
        gpg_transport='encrypted_repo',
    )
    text = self.build_gitlab_ci()

    assert 'gpgsign/wheels:' in text
    assert 'deploy/wheels:' in text
    assert 'stage: gpgsign' in text
    assert 'stage: deploy' in text
    assert 'needs:' in text
    assert 'dev/ci_secret_gpg_subkeys.pgp.enc' in text
    assert 'opentimestamps-client' in text
    assert 'twine upload' in text

    body = Yaml.loads(text)
    assert body['gpgsign/wheels']['needs'] == [
        {'job': 'build/sdist', 'artifacts': True},
        {'job': 'build/wheel', 'artifacts': True},
    ]


def test_gitlab_direct_gpg_render_uses_ci_variables_not_encrypted_repo(
    tmp_path,
):
    self = _make_applier(
        tmp_path,
        tags=['gitlab', 'purepy'],
        enable_gpg=True,
        direct_gpg=True,
    )
    text = self.build_gitlab_ci()

    assert 'gpgsign/wheels:' in text
    assert 'GPG_SECRET_SIGNING_SUBKEY_B64' in text
    assert 'GPG_PUBLIC_KEY_B64' in text
    assert 'GPG_OWNER_TRUST_B64' in text
    assert 'dev/ci_secret_gpg_subkeys.pgp.enc' not in text
    assert 'CI_SECRET=${!VARNAME_CI_SECRET}' not in text


def test_github_project_artifact_survives_ci_and_release_generation(tmp_path):
    from xcookie.util_yaml import Yaml

    ci_artifacts = {
        'windows_installer': {
            'name': 'Windows installer',
            'runner': 'windows-latest',
            'shell': 'pwsh',
            'python_version': '3.13',
            'setup_commands': [
                'python -m pip install -U pip',
                'python -m pip install -U uv',
            ],
            'build_command': '.\\dev\\_installers\\build_installer.ps1 -Checks',
            'post_build_commands': [
                'Get-ChildItem -Recurse dist | Format-Table FullName, Length'
            ],
            'artifact_paths': [
                'dist\\installer\\*',
                'dist\\diagnostics\\*',
            ],
            'release': True,
            'release_paths': ['dist\\installer\\*.exe'],
        }
    }
    self = _make_applier(
        tmp_path,
        tags=['github', 'purepy', 'erotemic', 'nosrcdist'],
        enable_gpg=True,
        deploy=True,
        trusted=True,
        direct_gpg=True,
        ci_artifacts=ci_artifacts,
    )

    test_body = Yaml.loads(self.build_github_actions())
    assert 'build_windows_installer' in test_body['jobs']
    test_job = test_body['jobs']['build_windows_installer']
    assert test_job['runs-on'] == 'windows-latest'
    assert test_job['steps'][-1]['with']['name'] == 'windows-installer'
    assert 'dist\\diagnostics\\*' in test_job['steps'][-1]['with']['path']

    release_text = self.build_github_actions_release()
    release_body = Yaml.loads(release_text)
    release_job = release_body['jobs']['build_windows_installer']
    assert release_job['steps'][-1]['with']['name'] == 'windows-installer-release'
    assert release_job['steps'][-1]['with']['path'] == 'dist\\installer\\*.exe'

    for deploy_key in ['test_deploy', 'live_deploy']:
        deploy_job = release_body['jobs'][deploy_key]
        assert 'build_windows_installer' in deploy_job['needs']
        download_steps = [
            step
            for step in deploy_job['steps']
            if step.get('name') == 'Download Windows installer'
        ]
        assert len(download_steps) == 1
        assert download_steps[0]['with']['name'] == 'windows-installer-release'
        assert any(
            step.get('with', {}).get('name') == 'deploy_extra_artifacts'
            for step in deploy_job['steps']
        )

    final_release = release_body['jobs']['release']
    assert any(
        step.get('with', {}).get('name') == 'deploy_extra_artifacts'
        for step in final_release['steps']
    )
    create_release = next(
        step for step in final_release['steps'] if step.get('name') == 'Create Release'
    )
    assert 'release_artifacts/**/*' in create_release['with']['files']

    plan = ci_model.make_release_plan(self, provider='github')
    assert 'build_windows_installer' in plan.build_job_keys
    assert 'release_artifacts/**/*' in plan.artifact_globs
