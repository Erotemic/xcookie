from xcookie.builders import ci_model, ci_plan
from xcookie.main import TemplateApplier, XCookieConfig


def _make_applier(
    tmp_path, *, tags=None, use_pyproject_requirements=False, min_python=None
):
    if tags is None:
        tags = ['github', 'purepy']
    kwargs = dict(
        repodir=tmp_path,
        repo_name='demo_pkg',
        mod_name='demo_pkg',
        tags=tags,
        interactive=False,
        rotate_secrets=False,
        refresh_docs=False,
        test_variants=[
            'minimal-loose',
            'full-loose',
            'minimal-strict',
            'full-strict',
        ],
    )
    if min_python is not None:
        kwargs['min_python'] = min_python
    cfg = XCookieConfig(**kwargs)
    cfg['enable_gpg'] = False
    cfg['deploy'] = False
    cfg['use_pyproject_requirements'] = use_pyproject_requirements
    self = TemplateApplier(cfg)
    self._presetup()
    return self


def test_format_pyproject_install_target_omits_empty_brackets():
    assert ci_plan.format_pyproject_install_target([], editable=True) == '-e "."'
    assert (
        ci_plan.format_pyproject_install_target(['tests', 'optional'], editable=True)
        == '-e ".[tests,optional]"'
    )


def test_ci_plan_filters_pyproject_extras(tmp_path):
    (tmp_path / 'pyproject.toml').write_text(
        '''
[project]
name = "demo-pkg"
version = "0.0.0"

[project.optional-dependencies]
tests = []
optional = []
headless = []
'''
    )
    self = _make_applier(
        tmp_path,
        tags=['github', 'purepy', 'cv2'],
        use_pyproject_requirements=True,
    )
    plan = ci_plan.make_ci_plan(self)
    assert plan.optional_dependency_keys == frozenset({'tests', 'optional', 'headless'})
    assert plan.typecheck_extras == ('tests',)
    variants = plan.active_variants_by_key()
    assert variants['full-strict'].extras == ('tests', 'optional', 'headless')
    assert variants['full-strict'].uv_resolution == 'lowest-direct'


def test_artifact_test_cases_preserve_github_minimal_loose_platform_reduction(tmp_path):
    self = _make_applier(tmp_path, tags=['github', 'purepy'])
    plan = ci_plan.make_ci_plan(self)
    cases = ci_model.make_artifact_test_cases(self, plan=plan, provider='github')
    minimal_loose = [case for case in cases if case.variant.key == 'minimal-loose']
    full_loose = [case for case in cases if case.variant.key == 'full-loose']
    assert len(full_loose) >= len(minimal_loose)
    assert all(case.platform.github_os != 'ubuntu-latest' for case in minimal_loose)


def test_ci_platform_mapping_adds_gitlab_linux_platform(tmp_path):
    self = _make_applier(tmp_path, tags=['gitlab', 'purepy'])
    platforms = ci_model.make_ci_platforms(self, provider='gitlab')
    assert len(platforms) == 1
    assert platforms[0].logical_os == 'linux'
    assert platforms[0].gitlab_arch == 'x86_64'


def test_binpy_workflow_plan_uses_shared_topology(tmp_path):
    self = _make_applier(
        tmp_path, tags=['github', 'binpy'], min_python='3.9'
    )
    plan = ci_plan.make_ci_plan(self)
    workflow_plan = ci_model.make_test_workflow_plan(
        self, plan=plan, provider='github'
    )
    assert workflow_plan.package_kind == 'binpy'
    assert workflow_plan.sdist_job_key == 'build_and_test_sdist'
    assert workflow_plan.wheel_build_job_key == 'build_binpy_wheels'
    assert workflow_plan.artifact_test_job_key == 'test_binpy_wheels'
    assert workflow_plan.artifact_test_cases


def test_gitlab_binpy_workflow_plan_has_template_job_keys(tmp_path):
    self = _make_applier(
        tmp_path, tags=['gitlab', 'binpy'], min_python='3.9'
    )
    plan = ci_plan.make_ci_plan(self)
    workflow_plan = ci_model.make_test_workflow_plan(
        self, plan=plan, provider='gitlab'
    )
    assert workflow_plan.package_kind == 'binpy'
    assert workflow_plan.sdist_job_key is None
    assert workflow_plan.wheel_build_job_key == 'build/{swenv_key}'
    assert workflow_plan.artifact_test_job_key == 'test/{variant_key}/{swenv_key}'
    assert workflow_plan.artifact_test_cases
