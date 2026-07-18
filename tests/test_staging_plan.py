from __future__ import annotations

import os
import stat

from xcookie.main import TemplateApplier
from xcookie.patch_plan import PatchPlan
from xcookie.template_registry import TemplateInfo


class MinimalConfig(dict):
    pass


def _make_applier(staging_infos, *, regen=None, only_generate=None):
    applier = TemplateApplier.__new__(TemplateApplier)
    applier.config = MinimalConfig(
        regen=regen,
        only_generate=only_generate,
        verbose=0,
    )
    applier.staging_infos = staging_infos
    return applier


def _info(fname, stage_fpath, repo_fpath, **kwargs):
    data = {
        'fname': fname,
        'stage_fpath': stage_fpath,
        'repo_fpath': repo_fpath,
    }
    data.update(kwargs)
    return TemplateInfo.coerce(data)


def test_gather_tasks_classifies_missing_dirty_modified_and_clean(tmp_path, capsys):
    stage = tmp_path / 'stage'
    repo = tmp_path / 'repo'
    stage.mkdir()
    repo.mkdir()

    missing_stage = stage / 'missing.txt'
    missing_repo = repo / 'missing.txt'
    missing_stage.write_text('new file')

    dirty_stage = stage / 'dirty.txt'
    dirty_repo = repo / 'dirty.txt'
    dirty_stage.write_text('new dirty')
    dirty_repo.write_text('old dirty')

    modified_stage = stage / 'modified.txt'
    modified_repo = repo / 'modified.txt'
    modified_stage.write_text('new modified')
    modified_repo.write_text('old modified')

    clean_stage = stage / 'clean.txt'
    clean_repo = repo / 'clean.txt'
    clean_stage.write_text('same\n')
    clean_repo.write_text('same')

    infos = [
        _info('missing.txt', missing_stage, missing_repo),
        _info('dirty.txt', dirty_stage, dirty_repo, overwrite=True),
        _info('modified.txt', modified_stage, modified_repo, overwrite=False),
        _info('clean.txt', clean_stage, clean_repo),
    ]
    applier = _make_applier(infos)

    plan = applier.gather_tasks()
    captured = capsys.readouterr()
    assert captured.out == ''
    applier.render_patch_plan(plan)
    captured = capsys.readouterr()

    assert isinstance(plan, PatchPlan)
    assert missing_repo in plan.missing
    assert dirty_repo in plan.dirty
    assert modified_repo in plan.modified
    assert clean_repo in plan.clean
    assert [task.dst for task in plan.copy] == [missing_repo, dirty_repo]
    assert '<NEW FPATH=' in captured.out
    assert '<DIFF FOR repo_fpath=' in captured.out


def test_gather_tasks_regen_allows_rewrite_without_overwrite(tmp_path):
    stage = tmp_path / 'stage'
    repo = tmp_path / 'repo'
    stage.mkdir()
    repo.mkdir()

    stage_fpath = stage / 'pyproject.toml'
    repo_fpath = repo / 'pyproject.toml'
    stage_fpath.write_text('new')
    repo_fpath.write_text('old')

    applier = _make_applier(
        [_info('pyproject.toml', stage_fpath, repo_fpath, overwrite=False)],
        regen='pyproject',
    )

    plan = applier.gather_tasks()

    assert repo_fpath in plan.dirty
    assert [task.dst for task in plan.copy] == [repo_fpath]


def test_gather_tasks_honors_only_generate(tmp_path):
    stage = tmp_path / 'stage'
    repo = tmp_path / 'repo'
    stage.mkdir()
    repo.mkdir()

    keep_stage = stage / 'keep.txt'
    skip_stage = stage / 'skip.txt'
    keep_repo = repo / 'keep.txt'
    skip_repo = repo / 'skip.txt'
    keep_stage.write_text('keep')
    skip_stage.write_text('skip')

    infos = [
        _info('keep.txt', keep_stage, keep_repo),
        _info('skip.txt', skip_stage, skip_repo),
    ]
    applier = _make_applier(infos, only_generate='keep')

    plan = applier.gather_tasks()

    assert [task.dst for task in plan.copy] == [keep_repo]


def test_gather_tasks_records_missing_dirs_and_permissions(tmp_path):
    stage = tmp_path / 'stage'
    repo = tmp_path / 'repo'
    stage.mkdir()
    repo.mkdir()

    stage_dir = stage / 'pkg'
    repo_dir = repo / 'pkg'
    stage_dir.mkdir()

    stage_script = stage / 'script.sh'
    repo_script = repo / 'script.sh'
    stage_script.write_text('#!/bin/sh\necho hi\n')
    repo_script.write_text('#!/bin/sh\necho hi\n')
    os.chmod(repo_script, 0o644)

    infos = [
        _info('pkg', stage_dir, repo_dir, path_type='dir'),
        _info('script.sh', stage_script, repo_script, perms='x'),
    ]
    applier = _make_applier(infos)

    plan = applier.gather_tasks()

    assert [task.path for task in plan.mkdir] == [repo_dir]
    assert repo_dir in plan.missing_dir
    assert [task.path for task in plan.perms] == [repo_script]
    # Preserve the historical behavior from TemplateApplier: adding ``x``
    # means owner-executable, not necessarily executable for every class.
    assert plan.perms[0].mode & stat.S_IXUSR
