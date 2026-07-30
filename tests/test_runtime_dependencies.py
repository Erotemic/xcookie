from pathlib import Path

from packaging.requirements import Requirement


def test_runtime_requirements_avoid_heavy_data_stack():
    runtime_fpath = Path(__file__).parents[1] / 'requirements/runtime.txt'
    requirement_names = set()
    for line in runtime_fpath.read_text().splitlines():
        line = line.split('#', 1)[0].strip()
        if not line:
            continue
        requirement_names.add(Requirement(line).name.lower())

    assert requirement_names.isdisjoint(
        {'numpy', 'pandas', 'xdev', 'cmd-queue'}
    )


def test_exported_locks_avoid_heavy_data_stack():
    lock_dpath = Path(__file__).parents[1] / 'requirements/locks'
    forbidden = {'numpy', 'pandas', 'xdev', 'cmd-queue', 'scriptconfig'}
    lock_names = [
        'runtime.txt',
        'docs.txt',
        'optional.txt',
        'tests.txt',
        'tests-optional.txt',
    ]
    for lock_name in lock_names:
        resolved_names = set()
        for line in (lock_dpath / lock_name).read_text().splitlines():
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('-'):
                continue
            requirement_text = line.split('  #', 1)[0]
            try:
                resolved_names.add(Requirement(requirement_text).name.lower())
            except Exception:
                # Continuation/comment lines are not requirement entries.
                continue
        assert resolved_names.isdisjoint(forbidden), lock_name
