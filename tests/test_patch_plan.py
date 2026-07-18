from xcookie.patch_plan import (
    PatchPlan,
    SearchPattern,
    coerce_legacy_patch_plan,
    render_patch_plan,
)


def test_patch_plan_apply_all(tmp_path):
    stage = tmp_path / 'stage'
    repo = tmp_path / 'repo'
    src = stage / 'pkg' / 'file.txt'
    dst = repo / 'pkg' / 'file.txt'
    src.parent.mkdir(parents=True)
    src.write_text('new text')

    plan = PatchPlan()
    plan.add_copy(src, dst)
    plan.add_mkdir(repo / 'empty')

    assert plan.has_tasks()
    assert plan.task_summary == {'copy': 1, 'perms': 0, 'mkdir': 1}

    plan.apply_all()

    assert dst.read_text() == 'new text'
    assert (repo / 'empty').is_dir()


def test_patch_plan_apply_some_filters_copy_tasks(tmp_path):
    stage = tmp_path / 'stage'
    repo = tmp_path / 'repo'
    src1 = stage / 'one.txt'
    src2 = stage / 'two.txt'
    dst1 = repo / 'one.txt'
    dst2 = repo / 'two.txt'
    stage.mkdir()
    src1.write_text('one')
    src2.write_text('two')

    plan = PatchPlan()
    plan.add_copy(src1, dst1)
    plan.add_copy(src2, dst2)

    plan.apply_some([dst2])

    assert not dst1.exists()
    assert dst2.read_text() == 'two'


def test_patch_plan_legacy_shape_roundtrip(tmp_path):
    src = tmp_path / 'stage.txt'
    dst = tmp_path / 'repo.txt'
    stats = {
        'missing': [dst],
        'modified': [],
        'dirty': [],
        'clean': [],
        'missing_dir': [],
    }
    tasks = {
        'copy': [(src, dst)],
        'perms': [(dst, 0o755)],
        'mkdir': [tmp_path / 'pkg'],
    }

    plan = coerce_legacy_patch_plan(stats, tasks)

    assert plan.stats['missing'] == [dst]
    assert plan.tasks['copy'] == [(src, dst)]
    assert plan.tasks['perms'] == [(dst, 0o755)]
    assert plan.tasks['mkdir'] == [tmp_path / 'pkg']


def test_search_pattern_preserves_search_style_strings():
    matcher = SearchPattern.coerce('keep')

    assert matcher is not None
    assert matcher.matches('keep.txt')
    assert matcher.matches('pkg/keep/__init__.py')
    assert not matcher.matches('skip.txt')


def test_search_pattern_supports_globs_and_regex_lists():
    matcher = SearchPattern.coerce(['*.toml', r'docs/.+\.md$'])

    assert matcher is not None
    assert matcher.matches('pyproject.toml')
    assert matcher.matches('docs/index.md')
    assert not matcher.matches('docs/index.rst')


def test_search_pattern_none_disables_matcher():
    assert SearchPattern.coerce(None) is None


def test_render_patch_plan_is_separate_from_gathering(tmp_path, capsys):
    missing = tmp_path / 'new.txt'
    dirty = tmp_path / 'dirty.txt'
    plan = PatchPlan(missing=[missing], dirty=[dirty])
    plan.diff_texts[missing] = 'new diff'
    plan.diff_texts[dirty] = 'dirty diff'

    render_patch_plan(plan)

    captured = capsys.readouterr()
    assert '<NEW FPATH=' in captured.out
    assert '<DIFF FOR repo_fpath=' in captured.out
    assert 'stats = ' in captured.out
