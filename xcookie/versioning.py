"""Package-version discovery and maintenance for xcookie."""

from __future__ import annotations

import ast
import dataclasses
import datetime as datetime_mod
import re
from typing import Literal

import toml
import ubelt as ub
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version


_RELATIVE_BUMPS = {'major', 'minor', 'patch', 'micro'}


@dataclasses.dataclass(frozen=True)
class VersionSource:
    """A statically editable package-version source."""

    path: ub.Path
    kind: Literal['python', 'pyproject', 'version-file']
    version: str
    variable: str | None = None

    def updated_text(self, new_version: str) -> str:
        """Return this source with only its authoritative version changed."""
        text = self.path.read_text()
        if self.kind == 'python':
            assert self.variable is not None
            pattern = re.compile(
                rf"(?m)^(?P<prefix>\s*{re.escape(self.variable)}"
                r"(?:\s*:\s*[^=]+)?\s*=\s*)"
                rf"(?P<quote>['\"]){re.escape(self.version)}(?P=quote)"
                r"(?P<suffix>\s*(?:#.*)?)$"
            )
            matches = list(pattern.finditer(text))
            if len(matches) != 1:
                raise RuntimeError(
                    f'Expected exactly one assignment to {self.variable!r} '
                    f'in {self.path}, found {len(matches)}'
                )
            match = matches[0]
            quote = match.group('quote')
            replacement = (
                match.group('prefix')
                + quote
                + new_version
                + quote
                + match.group('suffix')
            )
            return text[: match.start()] + replacement + text[match.end() :]

        if self.kind == 'pyproject':
            lines = text.splitlines(keepends=True)
            section = None
            replaced = 0
            pattern = re.compile(
                rf"^(?P<prefix>\s*version\s*=\s*)"
                rf"(?P<quote>['\"]){re.escape(self.version)}(?P=quote)"
                r"(?P<suffix>\s*(?:#.*)?(?:\r?\n)?)$"
            )
            for index, line in enumerate(lines):
                section_match = re.match(r'^\s*\[([^]]+)\]\s*$', line.strip())
                if section_match:
                    section = section_match.group(1)
                    continue
                if section == 'project':
                    match = pattern.match(line)
                    if match:
                        quote = match.group('quote')
                        lines[index] = (
                            match.group('prefix')
                            + quote
                            + new_version
                            + quote
                            + match.group('suffix')
                        )
                        replaced += 1
            if replaced != 1:
                raise RuntimeError(
                    'Expected exactly one [project] version assignment in '
                    f'{self.path}, found {replaced}'
                )
            return ''.join(lines)

        if self.kind == 'version-file':
            stripped = text.strip()
            if stripped != self.version:
                raise RuntimeError(
                    f'Expected {self.path} to contain only version '
                    f'{self.version!r}, found {stripped!r}'
                )
            prefix_len = len(text) - len(text.lstrip())
            suffix_len = len(text) - len(text.rstrip())
            prefix = text[:prefix_len]
            suffix = text[len(text) - suffix_len :] if suffix_len else ''
            return prefix + new_version + suffix

        raise AssertionError(f'Unknown version source kind={self.kind!r}')


@dataclasses.dataclass(frozen=True)
class VersionTextEdit:
    """One additional file edit coupled to a root version bump."""

    path: ub.Path
    text: str


@dataclasses.dataclass(frozen=True)
class VersionBumpPlan:
    """Resolved edits for one package-version bump."""

    current_version: str
    next_version: str
    version_source: VersionSource
    changelog_path: ub.Path
    version_text: str
    changelog_text: str
    additional_edits: tuple[VersionTextEdit, ...] = ()

    def apply(self) -> None:
        """Write the validated version and changelog edits."""
        self.version_source.path.write_text(self.version_text)
        for edit in self.additional_edits:
            edit.path.write_text(edit.text)
        self.changelog_path.write_text(self.changelog_text)


def _parse_python_assignment(path: ub.Path, variable: str) -> str | None:
    try:
        tree = ast.parse(path.read_text())
    except (OSError, SyntaxError):
        return None
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and target.id == variable:
                    value_node = node.value
                    if value_node is None:
                        continue
                    try:
                        value = ast.literal_eval(value_node)
                    except (TypeError, ValueError):
                        return None
                    return value if isinstance(value, str) else None
    return None


def _candidate_module_paths(
    repodir: ub.Path, data: dict, module_name: str
) -> list[ub.Path]:
    tool = data.get('tool', {})
    xcookie_config = tool.get('xcookie', {})
    setuptools = tool.get('setuptools', {})
    roots = [ub.Path(xcookie_config.get('rel_mod_parent_dpath', '.'))]

    packages = setuptools.get('packages', {})
    if isinstance(packages, dict):
        find_config = packages.get('find', {})
        if isinstance(find_config, dict):
            where = find_config.get('where', []) or []
            roots.extend(ub.Path(item) for item in where)

    roots.append(ub.Path('.'))
    rel_module = ub.Path(*module_name.split('.'))
    candidates = []
    for root in ub.oset(roots):
        candidates.extend(
            [
                repodir / root / rel_module / '__init__.py',
                repodir / root / f'{rel_module}.py',
            ]
        )
    return list(ub.oset(candidates))


def find_version_source(
    repodir: str | ub.Path,
    data: dict | None = None,
    *,
    required: bool = True,
) -> VersionSource | None:
    """Locate the authoritative package version without importing package code."""
    repodir = ub.Path(repodir).absolute()
    pyproject_path = repodir / 'pyproject.toml'
    if data is None:
        if not pyproject_path.exists():
            if required:
                raise RuntimeError(
                    f'Cannot find version: {pyproject_path} does not exist'
                )
            return None
        data = toml.loads(pyproject_path.read_text())

    project = data.get('project', {})
    static_version = project.get('version')
    if isinstance(static_version, str):
        return VersionSource(
            path=pyproject_path,
            kind='pyproject',
            version=static_version,
        )

    tool = data.get('tool', {})
    setuptools = tool.get('setuptools', {})
    dynamic = setuptools.get('dynamic', {})
    version_spec = dynamic.get('version', {})
    if not isinstance(version_spec, dict):
        version_spec = {}

    attr = version_spec.get('attr')
    if isinstance(attr, str):
        module_name, sep, variable = attr.rpartition('.')
        if not sep:
            if required:
                raise RuntimeError(
                    f'Invalid tool.setuptools.dynamic.version.attr={attr!r}'
                )
            return None
        matches = []
        for path in _candidate_module_paths(repodir, data, module_name):
            version = _parse_python_assignment(path, variable)
            if version is not None:
                matches.append((path, version))
        if len(matches) == 1:
            path, version = matches[0]
            return VersionSource(
                path=path,
                kind='python',
                version=version,
                variable=variable,
            )
        if matches:
            if required:
                raise RuntimeError(
                    f'Version attr {attr!r} resolved to multiple files: '
                    + ', '.join(str(path) for path, _ in matches)
                )
            return None
        if required:
            raise RuntimeError(
                f'Could not resolve version attr {attr!r} to a Python file'
            )
        return None

    version_files = version_spec.get('file')
    if isinstance(version_files, str):
        version_files = [version_files]
    if isinstance(version_files, (list, tuple)):
        matches = []
        for relpath in version_files:
            path = repodir / relpath
            if path.exists():
                version = path.read_text().strip()
                if version:
                    matches.append((path, version))
        if len(matches) == 1:
            path, version = matches[0]
            return VersionSource(
                path=path, kind='version-file', version=version
            )
        if matches:
            if required:
                raise RuntimeError(
                    'Dynamic version file resolved to multiple candidates: '
                    + ', '.join(str(path) for path, _ in matches)
                )
            return None

    if required:
        raise RuntimeError(
            'Could not find an editable package version. Expected '
            '[project].version or [tool.setuptools.dynamic].version.attr/file.'
        )
    return None


def build_initial_changelog(version: str) -> str:
    """Build the changelog scaffold used for a newly generated project."""
    return ub.codeblock(
        f"""
        # Changelog
        We [keep a changelog](https://keepachangelog.com/en/1.0.0/).
        We aim to adhere to [semantic versioning](https://semver.org/spec/v2.0.0.html).

        ## Version {version} - Unreleased

        ### Added
        * Initial version
        """
    )


def update_changelog_for_bump(
    text: str,
    current_version: str,
    next_version: str,
    release_date: datetime_mod.date,
) -> str:
    """Close the current changelog entry and prepend the next version.

    Older xcookie repositories do not all use the current changelog heading
    convention. In particular, some released versions use headings such as
    ``## [Version 2.2.0] -`` or omit the current package version entirely.
    Treat an older leading version as stale history and start the new cycle
    above it instead of requiring a manual changelog rewrite first.
    """
    heading_pattern = re.compile(
        r'^##\s+\[?Version\s+'
        r'(?P<version>[^\]\s]+)'
        r'\]?'
        r'(?P<tail>.*)$'
    )
    lines = text.splitlines(keepends=True)
    headings = []
    for index, line in enumerate(lines):
        match = heading_pattern.match(line.rstrip('\r\n'))
        if match:
            tail = match.group('tail').strip()
            status = tail.lstrip('-').strip() if tail.startswith('-') else tail
            headings.append((index, match, status))

    if not headings:
        raise RuntimeError('Could not find any version headings in CHANGELOG.md')

    current_matches = [
        item for item in headings if item[1].group('version') == current_version
    ]
    if len(current_matches) > 1:
        raise RuntimeError(
            f'Expected at most one changelog heading for version '
            f'{current_version}, found {len(current_matches)}'
        )
    if any(m.group('version') == next_version for _, m, _ in headings):
        raise RuntimeError(f'CHANGELOG.md already contains version {next_version}')

    if current_matches:
        current_index, _, status = current_matches[0]
        if headings[0][1].group('version') != current_version:
            raise RuntimeError(
                'The current package version appears in CHANGELOG.md but is '
                'not the first version heading; '
                f'package={current_version}, changelog='
                f'{headings[0][1].group("version")}'
            )
    else:
        first_index, first_match, _ = headings[0]
        try:
            first_version = Version(first_match.group('version'))
        except ValueError as ex:
            raise RuntimeError(
                'Cannot compare the package version against the first '
                f'changelog version {first_match.group("version")!r}'
            ) from ex
        if first_version >= Version(current_version):
            raise RuntimeError(
                'The package version is missing from the changelog and the '
                'first changelog version is not older; '
                f'package={current_version}, changelog={first_version}'
            )
        current_index = first_index
        status = None

    if status in {'Unreleased', ''}:
        newline = '\n' if lines[current_index].endswith('\n') else ''
        if lines[current_index].endswith('\r\n'):
            newline = '\r\n'
        lines[current_index] = (
            f'## Version {current_version} - '
            f'Released {release_date.isoformat()}{newline}'
        )
    elif status is not None and not re.fullmatch(
        r'Released\s+\d{4}-\d{2}-\d{2}', status
    ):
        raise RuntimeError(
            f'Expected version {current_version} changelog status to be '
            f'Unreleased, blank, or Released YYYY-MM-DD, found {status!r}'
        )

    new_heading = f'## Version {next_version} - Unreleased\n\n\n'
    lines.insert(current_index, new_heading)
    return ''.join(lines)


def _load_workspace_sync_config(repodir: ub.Path) -> tuple[bool, list[str], dict]:
    pyproject_path = repodir / 'pyproject.toml'
    if not pyproject_path.exists():
        return False, [], {}
    data = toml.loads(pyproject_path.read_text())
    xcookie = data.get('tool', {}).get('xcookie', {}) or {}
    sync = bool(xcookie.get('workspace_sync_versions', False))
    members = xcookie.get('workspace_members', []) or []
    if isinstance(members, str):
        members = [members]
    return sync, [str(item) for item in members], data


def _replace_exact_dependency_pin(
    text: str,
    project_data: dict,
    pkg_name: str,
    current_version: str,
    next_version: str,
) -> str:
    dependencies = project_data.get('project', {}).get('dependencies', []) or []
    target_name = canonicalize_name(pkg_name)
    matching_entries = []
    for entry in dependencies:
        if not isinstance(entry, str):
            continue
        try:
            req = Requirement(entry)
        except Exception:
            continue
        if canonicalize_name(req.name) != target_name:
            continue
        if str(req.specifier) == f'=={current_version}' and not req.marker:
            matching_entries.append(entry)
    if len(matching_entries) != 1:
        raise RuntimeError(
            f'workspace_sync_versions requires exactly one root dependency '
            f'pin {pkg_name}=={current_version}; found {matching_entries!r}'
        )
    old_entry = matching_entries[0]
    new_entry = re.sub(
        rf'=={re.escape(current_version)}$',
        f'=={next_version}',
        old_entry,
    )
    pattern = re.compile(
        r'(?P<quote>[\"\'])' + re.escape(old_entry) + r'(?P=quote)'
    )
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise RuntimeError(
            f'Expected exactly one textual dependency {old_entry!r} in '
            f'pyproject.toml, found {len(matches)}'
        )
    match = matches[0]
    quote = match.group('quote')
    return text[: match.start()] + quote + new_entry + quote + text[match.end() :]


def _plan_workspace_version_edits(
    repodir: ub.Path,
    source: VersionSource,
    next_version: str,
    version_text: str,
) -> tuple[str, tuple[VersionTextEdit, ...]]:
    sync, member_paths, root_data = _load_workspace_sync_config(repodir)
    if not sync:
        return version_text, tuple()
    if not member_paths:
        raise RuntimeError(
            'workspace_sync_versions=true requires at least one workspace member'
        )

    root_pyproject_path = repodir / 'pyproject.toml'
    root_pyproject_text = (
        version_text
        if source.path.resolve() == root_pyproject_path.resolve()
        else root_pyproject_path.read_text()
    )
    additional: list[VersionTextEdit] = []
    seen_paths: set[ub.Path] = set()
    for relpath in member_paths:
        member_dpath = (repodir / relpath).resolve()
        member_pyproject = member_dpath / 'pyproject.toml'
        if not member_pyproject.exists():
            raise RuntimeError(
                f'workspace member {relpath!r} has no pyproject.toml'
            )
        member_data = toml.loads(member_pyproject.read_text())
        member_project = member_data.get('project', {}) or {}
        member_pkg_name = member_project.get('name')
        if not isinstance(member_pkg_name, str):
            raise RuntimeError(
                f'workspace member {relpath!r} requires [project].name'
            )
        member_source = find_version_source(
            member_dpath, data=member_data, required=True
        )
        assert member_source is not None
        if member_source.version != source.version:
            raise RuntimeError(
                f'workspace member {member_pkg_name!r} version '
                f'{member_source.version} does not match root version '
                f'{source.version}'
            )
        member_edit = VersionTextEdit(
            path=member_source.path,
            text=member_source.updated_text(next_version),
        )
        if member_edit.path.resolve() in seen_paths:
            raise RuntimeError(
                f'duplicate workspace version source: {member_edit.path}'
            )
        seen_paths.add(member_edit.path.resolve())
        additional.append(member_edit)
        root_pyproject_text = _replace_exact_dependency_pin(
            root_pyproject_text,
            root_data,
            member_pkg_name,
            source.version,
            next_version,
        )

    if source.path.resolve() == root_pyproject_path.resolve():
        version_text = root_pyproject_text
    else:
        additional.append(
            VersionTextEdit(
                path=root_pyproject_path,
                text=root_pyproject_text,
            )
        )
    return version_text, tuple(additional)


class VersionBumper:
    """Bump a package version and roll its changelog to the next cycle."""

    def __init__(self, repodir: str | ub.Path = '.') -> None:
        self.repodir = ub.Path(repodir).absolute()

    def find_version_source(self) -> VersionSource:
        """Locate the authoritative version without importing package code."""
        source = find_version_source(self.repodir, required=True)
        assert source is not None
        return source

    def create_branch(self, branch_name: str) -> None:
        """Create and switch to the requested branch before editing files."""
        info = ub.cmd(
            ['git', 'switch', '-c', branch_name],
            cwd=self.repodir,
            verbose=2,
        )
        if info['ret'] != 0:
            detail = (info.get('err') or info.get('out') or '').strip()
            suffix = f': {detail}' if detail else ''
            raise RuntimeError(f'Could not create branch {branch_name!r}{suffix}')

    @staticmethod
    def resolve_next_version(current: str, target: str) -> str:
        """Resolve ``patch``/``minor``/``major`` or an explicit version."""
        current_version = Version(current)
        target = target.lower() if target.lower() in _RELATIVE_BUMPS else target
        if target in _RELATIVE_BUMPS:
            if any(
                [
                    current_version.epoch,
                    current_version.pre,
                    current_version.post,
                    current_version.dev,
                    current_version.local,
                ]
            ):
                raise ValueError(
                    'Relative bumps require a plain release version; use an '
                    f'explicit target for current version {current!r}'
                )
            major = current_version.major
            minor = current_version.minor
            patch = current_version.micro
            if target == 'major':
                next_version = Version(f'{major + 1}.0.0')
            elif target == 'minor':
                next_version = Version(f'{major}.{minor + 1}.0')
            else:
                next_version = Version(f'{major}.{minor}.{patch + 1}')
        else:
            next_version = Version(target)

        if next_version <= current_version:
            raise ValueError(
                f'Next version {next_version} must be greater than current '
                f'version {current_version}'
            )
        return str(next_version)

    def plan(
        self,
        target: str = 'patch',
        *,
        release_date: datetime_mod.date | None = None,
    ) -> VersionBumpPlan:
        """Validate and construct the two-file bump before writing either."""
        source = self.find_version_source()
        next_version = self.resolve_next_version(source.version, target)
        changelog_path = self.repodir / 'CHANGELOG.md'
        if not changelog_path.exists():
            raise RuntimeError(
                f'Cannot bump version: {changelog_path} does not exist'
            )
        if release_date is None:
            release_date = datetime_mod.date.today()
        version_text = source.updated_text(next_version)
        version_text, additional_edits = _plan_workspace_version_edits(
            self.repodir, source, next_version, version_text
        )
        changelog_text = update_changelog_for_bump(
            changelog_path.read_text(),
            source.version,
            next_version,
            release_date,
        )
        return VersionBumpPlan(
            current_version=source.version,
            next_version=next_version,
            version_source=source,
            changelog_path=changelog_path,
            version_text=version_text,
            changelog_text=changelog_text,
            additional_edits=additional_edits,
        )

    def bump(
        self,
        target: str = 'patch',
        *,
        release_date: datetime_mod.date | None = None,
        branch: bool = False,
    ) -> VersionBumpPlan:
        """Apply a validated package/changelog bump and report the transition."""
        plan = self.plan(target, release_date=release_date)
        if branch:
            branch_name = f'dev/{plan.next_version}'
            self.create_branch(branch_name)
            print(f'Created branch {branch_name}')
        plan.apply()
        print(f'Bumped version {plan.current_version} -> {plan.next_version}')
        print(f'Updated {plan.version_source.path}')
        for edit in plan.additional_edits:
            print(f'Updated {edit.path}')
        print(f'Updated {plan.changelog_path}')
        return plan
