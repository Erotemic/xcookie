from __future__ import annotations

from pathlib import Path


class _FakeConfig(dict):
    def __init__(self, repodir: Path, pyproject_data=None, **kwargs):
        defaults = {
            'repodir': repodir,
            'use_pyproject_requirements': True,
            'test_variants': [
                'minimal-loose',
                'full-loose',
                'minimal-strict',
                'full-strict',
            ],
            'ci_extras': None,
        }
        defaults.update(kwargs)
        super().__init__(defaults)
        self._pyproject_data = pyproject_data or {}

    def _load_pyproject_config(self):
        return self._pyproject_data

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)


class _FakeApplier:
    def __init__(self, config, tags=None):
        self.config = config
        self.tags = tags or ['github', 'purepy']


def test_ci_plan_filters_static_pyproject_extras(tmp_path) -> None:
    from xcookie.builders.ci_plan import make_ci_plan

    (tmp_path / 'pyproject.toml').write_text('[project]\nname = "demo"\n')
    pyproject_data = {
        'project': {
            'optional-dependencies': {
                'tests': [],
            }
        }
    }
    config = _FakeConfig(tmp_path, pyproject_data=pyproject_data)
    plan = make_ci_plan(_FakeApplier(config))

    assert plan.optional_dependency_keys == {'tests'}
    assert plan.typecheck_extras == ('tests',)
    assert plan.sdist_test_extras == ('tests',)
    assert plan.active_install_extras() == {
        'minimal-loose': 'tests',
        'full-loose': 'tests',
        'minimal-strict': 'tests',
        'full-strict': 'tests',
    }


def test_ci_plan_sees_dynamic_setuptools_extras(tmp_path) -> None:
    from xcookie.builders.ci_plan import make_ci_plan

    (tmp_path / 'pyproject.toml').write_text('[project]\nname = "demo"\n')
    pyproject_data = {
        'project': {},
        'tool': {
            'setuptools': {
                'dynamic': {
                    'optional-dependencies': {
                        'tests': {'file': ['requirements/tests.txt']},
                        'optional': {'file': ['requirements/optional.txt']},
                    }
                }
            }
        },
    }
    config = _FakeConfig(tmp_path, pyproject_data=pyproject_data)
    plan = make_ci_plan(_FakeApplier(config))

    assert {'tests', 'optional'} <= plan.optional_dependency_keys
    assert plan.active_install_extras()['full-loose'] == 'tests,optional'
    assert plan.active_install_extras()['full-strict'] == 'tests,optional'


def test_ci_plan_applies_ci_extras_by_group_and_variant(tmp_path) -> None:
    from xcookie.builders.ci_plan import make_ci_plan

    # No pyproject.toml exists, so the scaffold/new-repo path keeps desired
    # extras without filtering against disk metadata.
    config = _FakeConfig(
        tmp_path,
        pyproject_data={},
        ci_extras={
            'loose': ['loose-extra'],
            'full-strict': ['strict-extra'],
        },
    )
    plan = make_ci_plan(_FakeApplier(config))

    extras = plan.active_install_extras()
    assert extras['minimal-loose'] == 'tests,loose-extra'
    assert extras['full-loose'] == 'tests,optional,loose-extra'
    assert extras['minimal-strict'] == 'tests'
    assert extras['full-strict'] == 'tests,optional,strict-extra'


def test_ci_plan_legacy_requirements_mode_uses_strict_extra_names(tmp_path) -> None:
    from xcookie.builders.ci_plan import make_ci_plan

    config = _FakeConfig(
        tmp_path,
        use_pyproject_requirements=False,
        pyproject_data={},
    )
    plan = make_ci_plan(_FakeApplier(config, tags=['github', 'purepy', 'cv2']))

    extras = plan.active_install_extras()
    assert extras['minimal-loose'] == 'tests,headless'
    assert extras['full-loose'] == 'tests,optional,headless'
    assert extras['minimal-strict'] == 'tests-strict,runtime-strict,headless-strict'
    assert extras['full-strict'] == (
        'tests-strict,runtime-strict,optional-strict,headless-strict'
    )


def test_format_pyproject_install_target_omits_empty_brackets() -> None:
    from xcookie.builders.ci_plan import format_pyproject_install_target

    assert format_pyproject_install_target([], editable=True) == '-e "."'
    assert format_pyproject_install_target(['tests']) == '".[tests]"'
