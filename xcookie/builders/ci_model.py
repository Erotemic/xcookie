"""
Provider-neutral CI workflow and artifact-test planning helpers.

This module deliberately stops short of rendering GitHub Actions or GitLab CI
YAML.  It models the shared job/test-case decisions that both providers need,
and leaves provider-specific syntax to the provider renderers.
"""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import translate as glob_to_re
import re
from typing import Any, Literal, Mapping

import ubelt as ub

from xcookie.builders import common_ci
from xcookie.builders.ci_plan import CIPlan, TestVariant, VariantKey
from xcookie.util_yaml import Yaml

ProviderName = Literal['github', 'gitlab']
WorkflowKind = Literal['tests', 'release']
PackageKind = Literal['purepy', 'binpy']


@dataclass(frozen=True)
class CIPlatform:
    """A logical CI platform plus provider-specific render labels."""

    logical_os: str
    arch: str = 'auto'
    github_os: str | None = None
    gitlab_os: str = 'linux'
    gitlab_arch: str = 'x86_64'

    @property
    def gitlab_swenv_key(self) -> str:
        return f'{self.gitlab_os}-{self.gitlab_arch}'


@dataclass(frozen=True)
class ArtifactTestCase:
    """One provider-neutral artifact-install/test case."""

    variant: TestVariant
    python_version: str
    platform: CIPlatform
    install_extras: str
    uv_resolution: str | None = None
    gdal_requirement_txt: str | None = None

    @property
    def key(self) -> tuple[str, str, str, str, str, str | None, str | None]:
        return (
            self.variant.key,
            self.python_version,
            self.platform.logical_os,
            self.platform.arch,
            self.install_extras,
            self.uv_resolution,
            self.gdal_requirement_txt,
        )

    @property
    def gitlab_cpver(self) -> str:
        return 'cp' + self.python_version.replace('.', '')

    @property
    def gitlab_swenv_key(self) -> str:
        return f'{self.gitlab_cpver}-{self.platform.gitlab_swenv_key}'

    def github_matrix_item(self) -> dict[str, str]:
        github_os = self.platform.github_os
        if github_os is None:
            raise ValueError('github matrix item requires github_os')
        item = {
            'python-version': self.python_version,
            'install-extras': self.install_extras,
            'os': github_os,
            'arch': self.platform.arch,
        }
        if self.uv_resolution is not None:
            item['uv-resolution'] = self.uv_resolution
        if self.gdal_requirement_txt is not None:
            item['gdal-requirement-txt'] = self.gdal_requirement_txt
        return item

    def gitlab_special_install_lines(self, pip_install: str) -> list[str]:
        if self.gdal_requirement_txt is None:
            return []
        if self.variant.is_strict:
            return [
                "sed 's/>=/==/' \"requirements/gdal.txt\" > \"requirements/gdal-strict.txt\"",
                f'{pip_install} -r requirements/gdal-strict.txt',
            ]
        return [f'{pip_install} -r requirements/gdal.txt']


@dataclass(frozen=True)
class CIWorkflowPlan:
    """Provider-neutral workflow topology used before provider rendering."""

    kind: WorkflowKind
    package_kind: PackageKind
    provider: ProviderName
    sdist_job_key: str | None
    wheel_build_job_key: str
    artifact_test_job_key: str
    artifact_test_cases: tuple[ArtifactTestCase, ...]


def _logical_os_from_github_runner(runner: str) -> str:
    runner_lower = runner.lower()
    if runner_lower.startswith('ubuntu'):
        return 'linux'
    if runner_lower.startswith('macos'):
        return 'osx'
    if runner_lower.startswith('windows'):
        return 'win'
    return runner_lower


def _cibw_windows_arches(self: Any) -> list[str]:
    pyproj_config = self.config._load_pyproject_config()
    arches = (
        pyproj_config.get('tool', {})
        .get('cibuildwheel', {})
        .get('windows', {})
        .get('archs', None)
    )
    if arches is None:
        return []
    if isinstance(arches, str):
        return [arches.lower()]
    return [str(arch).lower() for arch in arches]


def make_ci_platforms(
    self: Any,
    provider: ProviderName = 'github',
    supported_platform_info: Mapping[str, Any] | None = None,
) -> list[CIPlatform]:
    """Return provider-renderable platforms from xcookie OS settings."""
    if supported_platform_info is None:
        supported_platform_info = common_ci.get_supported_platform_info(self)

    if provider == 'gitlab':
        # The current GitLab renderer only builds/tests Linux Docker images.
        return [
            CIPlatform(
                logical_os='linux',
                arch='x86_64',
                github_os='ubuntu-latest',
                gitlab_os='linux',
                gitlab_arch='x86_64',
            )
        ]

    platforms = []
    for github_os in supported_platform_info['os_list']:
        platforms.append(
            CIPlatform(
                logical_os=_logical_os_from_github_runner(str(github_os)),
                arch='auto',
                github_os=str(github_os),
                gitlab_os='linux',
                gitlab_arch='x86_64',
            )
        )

    if 'arm64' in _cibw_windows_arches(self):
        platforms.append(
            CIPlatform(
                logical_os='win',
                arch='auto',
                github_os='windows-11-arm',
                gitlab_os='linux',
                gitlab_arch='x86_64',
            )
        )
    return platforms


def _github_case_for_python(case: ArtifactTestCase) -> ArtifactTestCase | None:
    """Apply GitHub runner compatibility post-processing."""
    github_os = case.platform.github_os
    if github_os is None:
        return case
    python_version = case.python_version
    if python_version == '3.6' and github_os == 'ubuntu-latest':
        github_os = 'ubuntu-20.04'
    if python_version == '3.7' and github_os == 'ubuntu-latest':
        github_os = 'ubuntu-22.04'
    if python_version == '3.6' and github_os == 'macOS-latest':
        github_os = 'macos-13'
    if python_version == '3.7' and github_os == 'macOS-latest':
        github_os = 'macos-13'
    if github_os == 'windows-11-arm' and python_version in {
        '3.6',
        '3.7',
        '3.8',
        '3.9',
        '3.10',
    }:
        return None
    if github_os != case.platform.github_os:
        platform = CIPlatform(
            logical_os=case.platform.logical_os,
            arch=case.platform.arch,
            github_os=github_os,
            gitlab_os=case.platform.gitlab_os,
            gitlab_arch=case.platform.gitlab_arch,
        )
        case = ArtifactTestCase(
            variant=case.variant,
            python_version=case.python_version,
            platform=platform,
            install_extras=case.install_extras,
            uv_resolution=case.uv_resolution,
            gdal_requirement_txt=case.gdal_requirement_txt,
        )
    return case


def _variant_gdal_requirement(self: Any, variant: TestVariant) -> str | None:
    if 'gdal' not in self.tags:
        return None
    if variant.is_strict:
        return 'requirements/gdal-strict.txt'
    return 'requirements/gdal.txt'


def _compile_ci_blocklist(rules: Any):
    return [
        {k: re.compile(glob_to_re(str(pat))) for k, pat in rule.items()}
        for rule in (rules or ())
    ]


def _is_blocked(item: Mapping[str, Any], compiled_rules: Any) -> bool:
    for crule in compiled_rules:
        if all(
            regex.fullmatch(str(item.get(k, '')))
            for k, regex in crule.items()
        ):
            return True
    return False


def _dedupe_cases(cases: list[ArtifactTestCase]) -> list[ArtifactTestCase]:
    seen: set[str] = set()
    deduped = []
    for case in cases:
        h = ub.hash_data(case.key)
        if h in seen:
            continue
        seen.add(h)
        deduped.append(case)
    return deduped


def make_artifact_test_cases(
    self: Any,
    plan: CIPlan | None = None,
    provider: ProviderName = 'github',
) -> list[ArtifactTestCase]:
    """Build shared artifact install/test cases for provider renderers."""
    if plan is None:
        plan = common_ci.make_ci_plan(self)

    supported_platform_info = common_ci.get_supported_platform_info(self)
    platforms = make_ci_platforms(self, provider, supported_platform_info)
    install_extra_versions = supported_platform_info['install_extra_versions']

    if provider == 'github':
        variant_groups = [
            (tuple(plan.iter_active_variants(['minimal-strict'])), platforms),
            (tuple(plan.iter_active_variants(['full-strict'])), platforms),
            # Preserve historical behavior where minimal-loose skips the first
            # platform basis entry, usually Linux, to reduce CI load.
            (tuple(plan.iter_active_variants(['minimal-loose'])), platforms[1:]),
            (tuple(plan.iter_active_variants(['full-loose'])), platforms),
        ]
    else:
        # GitLab has historically tested every active variant across each
        # configured CPython Docker image on Linux.
        variant_groups = [(tuple(plan.iter_active_variants()), platforms)]

    cases: list[ArtifactTestCase] = []
    for variants, variant_platforms in variant_groups:
        for platform in variant_platforms:
            for variant in variants:
                if provider == 'gitlab':
                    python_versions = list(self.config['ci_cpython_versions'])
                else:
                    python_versions = install_extra_versions[variant.key]
                for pyver in python_versions:
                    uv_resolution = None
                    if common_ci.ci_plan.uses_lockfile_ci(self):
                        uv_resolution = variant.uv_resolution
                    base_case = ArtifactTestCase(
                        variant=variant,
                        python_version=str(pyver),
                        platform=platform,
                        install_extras=variant.install_extras,
                        uv_resolution=uv_resolution,
                        gdal_requirement_txt=_variant_gdal_requirement(
                            self, variant
                        ),
                    )
                    if provider == 'github':
                        github_case = _github_case_for_python(base_case)
                        if github_case is None:
                            continue
                        cases.append(github_case)
                    else:
                        cases.append(base_case)

    if self.config['use_pyproject_requirements']:
        cases = _dedupe_cases(cases)
    else:
        duplicates = ub.find_duplicates(map(lambda c: c.key, cases))
        assert not duplicates, duplicates

    if provider == 'github':
        ci_blocklist = Yaml.coerce(self.config.ci_blocklist)
        compiled = _compile_ci_blocklist(ci_blocklist)
        cases = [
            case
            for case in cases
            if not _is_blocked(case.github_matrix_item(), compiled)
        ]

    return cases


def unique_variant_cases(
    cases: list[ArtifactTestCase] | tuple[ArtifactTestCase, ...]
) -> list[ArtifactTestCase]:
    """Return the first test case for each variant key, preserving order."""
    seen: set[VariantKey] = set()
    result = []
    for case in cases:
        if case.variant.key in seen:
            continue
        seen.add(case.variant.key)
        result.append(case)
    return result


def any_test_case_needs_qemu(
    cases: list[ArtifactTestCase] | tuple[ArtifactTestCase, ...]
) -> bool:
    return any(case.platform.arch != 'auto' for case in cases)


def make_purepy_workflow_plan(
    self: Any,
    plan: CIPlan | None = None,
    provider: ProviderName = 'github',
) -> CIWorkflowPlan:
    """Build the provider-neutral test workflow topology for purepy repos."""
    if plan is None:
        plan = common_ci.make_ci_plan(self)
    sdist_job_key = None
    if 'nosrcdist' not in self.tags:
        if provider == 'github':
            sdist_job_key = 'build_and_test_sdist'
        else:
            sdist_job_key = 'build/sdist'
    return CIWorkflowPlan(
        kind='tests',
        package_kind='purepy',
        provider=provider,
        sdist_job_key=sdist_job_key,
        wheel_build_job_key='build_purepy_wheels'
        if provider == 'github'
        else 'build/{swenv_key}',
        artifact_test_job_key='test_purepy_wheels'
        if provider == 'github'
        else 'test/{variant_key}/{swenv_key}',
        artifact_test_cases=tuple(
            make_artifact_test_cases(self, plan=plan, provider=provider)
        ),
    )


def make_binpy_workflow_plan(
    self: Any,
    plan: CIPlan | None = None,
    provider: ProviderName = 'github',
) -> CIWorkflowPlan:
    """Build the provider-neutral test workflow topology for binpy repos."""
    if plan is None:
        plan = common_ci.make_ci_plan(self)
    sdist_job_key = None
    if provider == 'github' and 'nosrcdist' not in self.tags:
        sdist_job_key = 'build_and_test_sdist'
    return CIWorkflowPlan(
        kind='tests',
        package_kind='binpy',
        provider=provider,
        sdist_job_key=sdist_job_key,
        wheel_build_job_key='build_binpy_wheels'
        if provider == 'github'
        else 'build/{swenv_key}',
        artifact_test_job_key='test_binpy_wheels'
        if provider == 'github'
        else 'test/{variant_key}/{swenv_key}',
        artifact_test_cases=tuple(
            make_artifact_test_cases(self, plan=plan, provider=provider)
        ),
    )


def make_test_workflow_plan(
    self: Any,
    plan: CIPlan | None = None,
    provider: ProviderName = 'github',
) -> CIWorkflowPlan:
    """Dispatch to the provider-neutral test workflow plan for this repo."""
    if plan is None:
        plan = common_ci.make_ci_plan(self)
    if 'purepy' in self.tags:
        return make_purepy_workflow_plan(self, plan=plan, provider=provider)
    if 'binpy' in self.tags:
        return make_binpy_workflow_plan(self, plan=plan, provider=provider)
    raise NotImplementedError('Need to specify binpy or purepy in tags')


@dataclass(frozen=True)
class PublishTarget:
    """One publishing/deploy target described before provider rendering."""

    name: str
    repository_url: str | None = None
    environment: str | None = None
    trusted_publishing: bool = False
    requires_oidc: bool = False
    upload_artifacts: bool = True


@dataclass(frozen=True)
class ReleasePlan:
    """Provider-neutral release/deploy description used before rendering."""

    provider: ProviderName
    package_kind: PackageKind
    build_job_keys: tuple[str, ...]
    deploy_job_keys: tuple[str, ...]
    publish_targets: tuple[PublishTarget, ...]
    signing_transport: str | None
    distribution_globs: tuple[str, ...]
    artifact_globs: tuple[str, ...]


def _package_kind_from_tags(self: Any) -> PackageKind:
    if 'purepy' in self.tags:
        return 'purepy'
    if 'binpy' in self.tags:
        return 'binpy'
    raise NotImplementedError('Need to specify binpy or purepy in tags')


def make_distribution_globs(
    self: Any,
    wheelhouse_dpath: str = 'wheelhouse',
) -> tuple[str, ...]:
    """Return distribution globs that publish/sign steps operate on."""
    globs = [f'{wheelhouse_dpath}/*.whl']
    if 'nosrcdist' not in self.tags:
        globs.append(f'{wheelhouse_dpath}/*.tar.gz')
    return tuple(globs)


def make_release_artifact_globs(
    self: Any,
    wheelhouse_dpath: str = 'wheelhouse',
) -> tuple[str, ...]:
    """Return artifact globs preserved by release/signing jobs."""
    globs = list(make_distribution_globs(self, wheelhouse_dpath))
    globs.append(f'{wheelhouse_dpath}/*.zip')
    if self.config.get('enable_gpg', False):
        globs.append(f'{wheelhouse_dpath}/*.asc')
        globs.append(f'{wheelhouse_dpath}/*.ots')
    return tuple(globs)


def make_publish_targets(
    self: Any,
    provider: ProviderName = 'github',
) -> tuple[PublishTarget, ...]:
    """Describe the configured publishing targets without rendering YAML."""
    targets: list[PublishTarget] = []
    deploy_pypi = bool(self.config.get('deploy_pypi', False))
    deploy_tags = bool(self.config.get('deploy_tags', False))
    deploy_artifacts = bool(self.config.get('deploy_artifacts', False))

    if provider == 'github':
        trusted = bool(self.config.get('ci_pypi_trusted_publishing', False))
        if deploy_pypi:
            targets.extend(
                [
                    PublishTarget(
                        name='testpypi',
                        repository_url='https://test.pypi.org/legacy/',
                        environment='testpypi',
                        trusted_publishing=trusted,
                        requires_oidc=trusted,
                    ),
                    PublishTarget(
                        name='pypi',
                        repository_url='https://upload.pypi.org/legacy/',
                        environment='pypi',
                        trusted_publishing=trusted,
                        requires_oidc=trusted,
                    ),
                ]
            )
        if deploy_tags:
            targets.append(
                PublishTarget(name='github-release', upload_artifacts=True)
            )
    else:
        if deploy_pypi:
            targets.append(
                PublishTarget(
                    name='pypi',
                    repository_url='https://upload.pypi.org/legacy/',
                )
            )
        if deploy_tags:
            targets.append(
                PublishTarget(name='git-tags', upload_artifacts=False)
            )
        if deploy_artifacts:
            targets.append(PublishTarget(name='gitlab-package-registry'))

    return tuple(targets)


def make_release_plan(
    self: Any,
    provider: ProviderName = 'github',
    wheelhouse_dpath: str = 'wheelhouse',
) -> ReleasePlan:
    """Build a provider-neutral description of release/deploy behavior."""
    package_kind = _package_kind_from_tags(self)
    enable_gpg = bool(self.config.get('enable_gpg', False))
    deploy = bool(self.config.get('deploy', False))

    if provider == 'github':
        build_job_keys = []
        if 'nosrcdist' not in self.tags:
            build_job_keys.append('build_sdist')
        if package_kind == 'purepy':
            build_job_keys.append('build_purepy_wheels')
        else:
            build_job_keys.append('build_binpy_wheels')

        deploy_job_keys = []
        if deploy:
            deploy_job_keys.extend(['test_deploy', 'live_deploy', 'release'])
    else:
        build_job_keys = []
        if package_kind == 'purepy':
            if 'nosrcdist' not in self.tags:
                build_job_keys.append('build/sdist')
            build_job_keys.append('build/{swenv_key}')
        else:
            build_job_keys.append('build/{swenv_key}')

        deploy_job_keys = []
        if enable_gpg:
            deploy_job_keys.append('gpgsign/wheels')
        if deploy:
            deploy_job_keys.append('deploy/wheels')

    signing_transport = None
    if enable_gpg:
        signing_transport = str(
            self.config.get('ci_gpg_secret_transport', 'direct_ci')
        )

    return ReleasePlan(
        provider=provider,
        package_kind=package_kind,
        build_job_keys=tuple(build_job_keys),
        deploy_job_keys=tuple(deploy_job_keys),
        publish_targets=make_publish_targets(self, provider=provider),
        signing_transport=signing_transport,
        distribution_globs=make_distribution_globs(self, wheelhouse_dpath),
        artifact_globs=make_release_artifact_globs(self, wheelhouse_dpath),
    )

