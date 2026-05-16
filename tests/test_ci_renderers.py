from __future__ import annotations

from types import SimpleNamespace


class _Config(dict):
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)


def test_github_renderer_threads_plan_into_test_jobs(monkeypatch) -> None:
    from xcookie.builders import github_actions

    plan = object()
    applier = SimpleNamespace(
        config=_Config(defaultbranch='main', deploy=False),
        tags=['github', 'purepy'],
    )
    seen = {}

    def fake_collect(arg_applier, arg_plan):
        seen['applier'] = arg_applier
        seen['plan'] = arg_plan
        return 'DemoCI', {}

    def fake_render_workflow_text(name, on_lines, jobs, footer):
        seen['render'] = (name, on_lines, jobs, footer)
        return 'rendered-tests'

    monkeypatch.setattr(github_actions, '_collect_test_jobs', fake_collect)
    monkeypatch.setattr(
        github_actions, '_render_workflow_text', fake_render_workflow_text
    )

    text = github_actions.GitHubActionsRenderer(applier, plan=plan).render_tests()

    assert text == 'rendered-tests'
    assert seen['applier'] is applier
    assert seen['plan'] is plan


def test_github_renderer_threads_plan_into_release_jobs(monkeypatch) -> None:
    from xcookie.builders import github_actions

    plan = object()
    applier = SimpleNamespace(
        config=_Config(deploy=False),
        tags=['github', 'purepy'],
    )
    seen = {}

    def fake_collect(arg_applier, arg_plan):
        seen['applier'] = arg_applier
        seen['plan'] = arg_plan
        return 'DemoRelease', {}, []

    def fake_render_workflow_text(name, on_lines, jobs, footer):
        seen['render'] = (name, on_lines, jobs, footer)
        return 'rendered-release'

    monkeypatch.setattr(github_actions, '_collect_release_jobs', fake_collect)
    monkeypatch.setattr(github_actions, '_build_github_footer', lambda arg: '')
    monkeypatch.setattr(
        github_actions, '_render_workflow_text', fake_render_workflow_text
    )

    text = github_actions.GitHubActionsRenderer(applier, plan=plan).render_release()

    assert text == 'rendered-release'
    assert seen['applier'] is applier
    assert seen['plan'] is plan


def test_gitlab_renderer_threads_plan_into_provider_jobs(monkeypatch) -> None:
    from xcookie.builders import gitlab_ci

    plan = object()
    applier = SimpleNamespace(tags=['gitlab', 'purepy'])
    seen = {}

    def fake_make_purepy(arg_applier, plan=None):
        seen['applier'] = arg_applier
        seen['plan'] = plan
        return 'rendered-gitlab'

    monkeypatch.setattr(gitlab_ci, 'make_purepy_ci_jobs', fake_make_purepy)

    text = gitlab_ci.GitLabCIRenderer(applier, plan=plan).render()

    assert text == 'rendered-gitlab'
    assert seen['applier'] is applier
    assert seen['plan'] is plan
