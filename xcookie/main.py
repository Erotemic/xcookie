"""
This is a Python script to apply the xcookie template to either create a new repo
or update an existing one with the latest standards.

TODO:
    Port logic from ~/misc/make_new_python_package_repo.sh

ComamndLine:
    ~/code/xcookie/xcookie/main.py

    python -m xcookie.main

ExampleUsage:
    # Update my repos
    python -m xcookie.main --repodir=$HOME/code/pyflann_ibeis --tags="erotemic,github,binpy"

    # Create this repo
    python -m xcookie.main --repo_name=xcookie --repodir=$HOME/code/xcookie --tags="erotemic,github,purepy"

    # Create a new python repo
    python -m xcookie.main --repo_name=cookiecutter_purepy --repodir=$HOME/code/cookiecutter_purepy --tags="github,purepy"

    # Create a new binary repo
    python -m xcookie.main --repo_name=cookiecutter_binpy --repodir=$HOME/code/cookiecutter_binpy --tags="github,binpy,gdal"

    # Create a new binary gitlab kitware repo
    python -m xcookie.main --repo_name=kwimage_ext --repodir=$HOME/code/kwimage_ext --tags="kitware,gitlab,binpy"
"""
import toml
import shutil
import ubelt as ub
import tempfile
import scriptconfig as scfg
import xdev
import os


class SkipFile(Exception):
    pass


# TODO: split up into a configuration that is saved to pyproject.toml and one
# that is on only used when executing
class XCookieConfig(scfg.Config):
    default = {
        'repodir': scfg.Value('.', help='path to the new or existing repo', position=1),

        'repo_name': scfg.Value(None, help='defaults to ``repodir.name``'),
        'mod_name': scfg.Value(None, help='The name of the importable Python module. defaults to ``repo_name``'),
        'pkg_name': scfg.Value(None, help='The name of the installable Python package. defaults to ``mod_name``'),
        'rel_mod_parent_dpath': scfg.Value('.', help=ub.paragraph(
            '''
            The location of the module directory relative to the repository
            root.  This defaults to simply placing the module in ".", but
            another common pattern is to specify this as "./src".
            '''
        )),

        'rotate_secrets': scfg.Value('auto', help='If True will execute secret rotation'),

        'os': scfg.Value('all', help='all or any of win,osx,linux'),

        'is_new': scfg.Value('auto', help=ub.paragraph(
            '''
            If the repo is detected or specified as being new, then steps to
            create a project for the repo on github/gitlab and other
            initialization procedures will be executed. Otherwise we assume
            that we are updating an existing repo.
            '''
        )),

        'min_python': scfg.Value('3.7'),

        'autostage': scfg.Value(False, help='if true, automatically add changes to version control'),

        'interactive': scfg.Value(True),

        'version': scfg.Value(None, help='repo metadata: url for the project'),
        'url': scfg.Value(None, help='repo metadata: url for the project'),
        'author': scfg.Value(None, help='repo metadata: author for the project'),
        'author_email': scfg.Value(None, help='repo metadata'),
        'description': scfg.Value(None, help='repo metadata'),
        'license': scfg.Value(None, help='repo metadata'),
        'dev_status': scfg.Value('planning'),

        'regen': scfg.Value(None, help=ub.paragraph(
            '''
            if specified, any modified template file that matches this pattern
            will be considered for re-write
            ''')),

        'tags': scfg.Value('auto', nargs='*', help=ub.paragraph(
            '''
            Tags modify what parts of the template are used.
            Valid tags are:
                "binpy" - do we build binpy wheels?
                "erotemic" - this is an erotemic repo
                "kitware" - this is an kitware repo
                "pyutils" - this is an pyutils repo
                "purepy" - this is a pure python repo
                "gdal" - add in our gdal hack # TODO
                "cv2" - enable the headless hack
            ''')),

        'yes': scfg.Value(False, help=ub.paragraph('Say yes to everything'))
    }

    def normalize(self):
        if self['repodir'] is None:
            self['repodir'] = ub.Path.cwd()
        else:
            self['repodir'] = ub.Path(self['repodir']).absolute()

        if self['tags']:
            if isinstance(self['tags'], str):
                self['tags'] = [self['tags']]
            new = []
            for t in self['tags']:
                new.extend([p.strip() for p in t.split(',')])
            self['tags'] = new

        if self['os']:
            if isinstance(self['os'], str):
                self['os'] = [self['os']]
            new = []
            for t in self['os']:
                new.extend([p.strip() for p in t.split(',')])
            self['os'] = set(new)
            if 'all' in self['os']:
                self['os'].add('win')
                self['os'].add('osx')
                self['os'].add('linux')

        if self['repo_name'] is None:
            self['repo_name'] = self['repodir'].name
        if self['mod_name'] is None:
            self['mod_name'] = self['repo_name']
        if self['is_new'] == 'auto':
            self['is_new'] = not (self['repodir'] / '.git').exists()
        if self['rotate_secrets'] == 'auto':
            self['rotate_secrets'] = self['is_new']
        if self['author'] is None:
            self['author'] = ub.cmd('git config --global user.name')['out'].strip()
        if self['license'] is None:
            self['license'] = 'Apache 2'
        if self['author_email'] is None:
            self['author_email'] = ub.cmd('git config --global user.email')['out'].strip()
        if self['version'] is None:
            # TODO: read from __init__.py
            self['version'] = '0.0.1'
        if self['description'] is None:
            self['description'] = 'A module cut from xcookie'

    def _load_pyproject_settings(self):
        pyproject_fpath = self['repodir'] / 'pyproject.toml'
        if pyproject_fpath.exists():
            try:
                disk_config = toml.loads(pyproject_fpath.read_text())
            except Exception:
                raise
                # print(f'ex={ex}')
            else:
                settings = disk_config.get('tool', {}).get('xcookie', {})
                return settings

    def confirm(self, msg, default=True):
        """
        Args:
            msg (str): display to the user
            default (bool): default value if non-interactive

        Returns:
            bool:
        """
        if self['interactive']:
            from rich.prompt import Confirm
            flag = Confirm.ask(msg)
        else:
            flag = default
        return flag

    @classmethod
    def main(cls, cmdline=0, **kwargs):
        """
        Ignore:
            repodir = ub.Path('~/code/pyflann_ibeis').expand()
            kwargs = {
                'repodir': repodir,
                'tags': ['binpy', 'erotemic', 'github'],
            }
            cmdline = 0

        Example:
            repodir = ub.Path.appdir('pypkg/demo/my_new_repo')
            import sys, ubelt
            sys.path.append(ubelt.expandpath('~/code/xcookie'))
            from xcookie.main import *  # NOQA
            kwargs = {
                'repodir': repodir,
            }
            cmdline = 0
        """
        # We load the config multiple times to get the right defaults.
        config = XCookieConfig(cmdline=cmdline, data=kwargs)
        config.normalize()
        settings = config._load_pyproject_settings()
        if settings:
            print(f'settings={settings}')
            config = XCookieConfig(cmdline=cmdline, data=kwargs, default=ub.dict_isect(settings, config))
        config.normalize()

        # import xdev
        # xdev.embed()

        print('config = {}'.format(ub.repr2(dict(config), nl=1)))
        repodir = ub.Path(config['repodir']).absolute()
        repodir.ensuredir()

        self = TemplateApplier(config)
        self.setup().apply()


class TemplateApplier:

    def __init__(self, config):
        self.config = config
        self.repodir = ub.Path(self.config['repodir'])
        if self.config['repo_name'] is None:
            self.config['repo_name'] = self.repodir.name
        self.repo_name = self.config['repo_name']
        self._tmpdir = tempfile.TemporaryDirectory(prefix=self.repo_name)

        self.template_infos = None
        try:
            xcookie_dpath = ub.Path(__file__).parent.parent
        except NameError:
            xcookie_dpath = ub.Path('~/misc/templates/xcookie').expand()
        self.template_dpath = xcookie_dpath
        self.staging_dpath = ub.Path(self._tmpdir.name)
        self.remote_info = {
            'type': 'unknown'
        }

    def apply(self):
        self.vcs_checks()
        self.copy_staged_files()
        if self.config['rotate_secrets']:
            self.rotate_secrets()
        self.print_help_tips()

        if self.config['autostage']:
            self.autostage()

    def autostage(self):
        import git
        repo = git.Repo(self.repodir)

        # Find untracked files
        untracked = []
        for info in self.staging_infos:
            fpath = info['repo_fpath']
            if not repo.git.ls_files(fpath):
                untracked.append(fpath)

        repo.git.add(untracked)

    @property
    def rel_mod_dpath(self):
        return ub.Path(self.config['rel_mod_parent_dpath']) / self.config['mod_name']

    @property
    def mod_dpath(self):
        return self.repodir / self.rel_mod_dpath

    @property
    def mod_name(self):
        return self.config['mod_name']

    def _build_template_registry(self):
        """
        Take stock of the files in the template repo and ensure they all have
        appropriate properties.
        """
        from xcookie import rc

        rel_mod_dpath = self.rel_mod_dpath

        self.template_infos = [
            # {'template': 1, 'overwrite': False, 'fname': '.circleci/config.yml'},
            # {'template': 1, 'overwrite': False, 'fname': '.travis.yml'},

            {'template': 0, 'overwrite': 1, 'fname': 'dev/setup_secrets.sh'},

            {'template': 0, 'overwrite': 0, 'fname': '.gitignore'},
            # {'template': 1, 'overwrite': 1, 'fname': '.coveragerc'},
            {'template': 1, 'overwrite': 1, 'fname': '.readthedocs.yml'},
            # {'template': 0, 'overwrite': 1, 'fname': 'pytest.ini'},

            {'template': 0, 'overwrite': 0, 'fname': 'pyproject.toml',
             'dynamic': 'build_pyproject'},

            {'template': 1, 'overwrite': 0, 'fname': 'setup.py',
             # 'input_fname': rc.resource_fpath('setup.py.in'),
             'dynamic': 'build_setup',
             'perms': 'x'},

            {'template': 0, 'overwrite': 0, 'fname': 'docs/source/index.rst',
             'dynamic': 'build_docs_index'},
            {'template': 0, 'overwrite': 0, 'fname': 'README.rst',
             'dynamic': 'build_readme'},
            #
            {'source': 'dynamic', 'overwrite': 0, 'fname': 'CHANGELOG.md'},
            {'source': 'dynamic', 'overwrite': 0, 'fname': rel_mod_dpath / '__init__.py'},
            # {'source': 'dynamic', 'overwrite': 0, 'fname': rel_mod_dpath / '__main__.py'},
            {'source': 'dynamic', 'overwrite': 0, 'fname': 'tests/test_import.py'},

            {'template': 0, 'overwrite': 1, 'fname': '.github/dependabot.yml', 'tags': 'github'},

            {'template': 0, 'overwrite': 1,
             'tags': 'binpy,github',
             'fname': '.github/workflows/test_binaries.yml',
             'input_fname': rc.resource_fpath('test_binaries.yml.in')},

            {'template': 1, 'overwrite': 1,
             'tags': 'purepy,github',
             'fname': '.github/workflows/tests.yml',
             'dynamic': 'build_github_actions',
             # 'input_fname': rc.resource_fpath('tests.yml.in')
             },

            {'template': 0, 'overwrite': 1, 'fname': '.gitlab-ci.yml', 'tags': 'gitlab,purepy'},

            {'template': 0, 'overwrite': 1, 'fname': '.gitlab-ci.yml', 'tags': 'gitlab,binpy',
             'input_fname': rc.resource_fpath('gitlab-ci.binpy.yml.in')},
            # {'template': 1, 'overwrite': False, 'fname': 'appveyor.yml'},

            {'template': 1, 'overwrite': 0, 'fname': 'CMakeLists.txt',
             'tags': 'binpy',
             'input_fname': rc.resource_fpath('CMakeLists.txt.in')},

            # {'template': 0, 'overwrite': 1, 'fname': 'dev/make_strict_req.sh', 'perms': 'x'},

            {'template': 0, 'overwrite': 1, 'fname': 'requirements.txt'},  # 'dynamic': 'build_requirements'},
            {'template': 0, 'overwrite': 0, 'fname': 'requirements/graphics.txt', 'tags': 'cv2'},
            {'template': 0, 'overwrite': 0, 'fname': 'requirements/headless.txt', 'tags': 'cv2'},
            {'template': 0, 'overwrite': 0, 'fname': 'requirements/optional.txt'},
            {'template': 0, 'overwrite': 0, 'fname': 'requirements/runtime.txt'},
            {'template': 0, 'overwrite': 0, 'fname': 'requirements/tests.txt'},
            {'template': 0, 'overwrite': 0, 'fname': 'requirements/docs.txt'},
            {'template': 1, 'overwrite': 0, 'fname': 'docs/source/conf.py'},

            # {'template': 0, 'overwrite': 0, 'fname': 'docs/source/_static', 'path_type': 'dir'},
            # {'template': 0, 'overwrite': 0, 'fname': 'docs/source/_templates', 'path_type': 'dir'},

            {'template': 0, 'overwrite': 1, 'fname': 'publish.sh', 'perms': 'x'},
            {'template': 1, 'overwrite': 1, 'fname': 'build_wheels.sh', 'perms': 'x', 'tags': 'binpy'},
            {'template': 1, 'overwrite': 1, 'fname': 'run_doctests.sh', 'perms': 'x'},
            {'template': 1, 'overwrite': 1, 'fname': 'run_linter.sh', 'perms': 'x'},
            {'template': 1, 'overwrite': 1, 'fname': 'run_tests.py',
             'perms': 'x', 'tags': 'binpy',
             'input_fname': rc.resource_fpath('run_tests.binpy.py.in')},

            {'template': 1, 'overwrite': 1, 'fname': 'run_tests.py',
             'perms': 'x', 'tags': 'purepy',
             'input_fname': rc.resource_fpath('run_tests.purepy.py.in')},

        ]
        if 0:
            # Checker and help autopopulate
            template_contents = []
            dname_blocklist = {
                '__pycache__',
                'old',
                '.circleci',
                'xcookie',
                '.git',
            }
            fname_blocklist = set()
            for root, ds, fs in self.template_dpath.walk():
                for d in set(ds) & dname_blocklist:
                    ds.remove(d)
                fs = set(fs) - fname_blocklist
                if fs:
                    rel_root = root.relative_to(self.template_dpath)
                    for fname in fs:
                        abs_fpath = root / fname
                        if abs_fpath.name.endswith('.in'):
                            is_template = 1
                        else:
                            try:
                                is_template = int('xcookie' in abs_fpath.read_text())
                            except Exception:
                                is_template = 0
                            # is_template = 0
                        rel_fpath = rel_root / fname
                        # overwrite indicates if we dont expect the user to
                        # make modifications
                        template_contents.append({
                            'template': is_template,
                            'overwrite': False,
                            'fname': os.fspath(rel_fpath),
                        })
            print('template_contents = {}'.format(ub.repr2(sorted(template_contents, key=lambda x: x['fname']), nl=1, sort=0)))
            known_fpaths = {d['fname'] for d in self.template_infos}
            exist_fpaths = {d['fname'] for d in template_contents}
            unexpected_fpaths = exist_fpaths - known_fpaths
            if unexpected_fpaths:
                print(f'WARNING UNREGISTERED unexpected_fpaths={unexpected_fpaths}')

    @property
    def tags(self):
        return set(self.config['tags'])

    def setup(self):
        tags = set(self.config['tags'])
        self.remote_info = {
            'type': 'unknown'
        }
        if 'gitlab' in tags:
            self.remote_info['type'] = 'gitlab'

        if 'github' in tags:
            self.remote_info['type'] = 'github'
        if self.remote_info['type'] == 'gitlab':
            if 'kitware' in tags:
                self.remote_info['host'] = 'https://gitlab.kitware.com'
                self.remote_info['group'] = 'computer-vision'  # hack
        if self.remote_info['type'] == 'github':
            if 'erotemic' in tags:
                self.remote_info['host'] = 'https://github.com'
                self.remote_info['group'] = 'Erotemic'  # hack
        print(f'tags={tags}')
        print('self.remote_info = {}'.format(ub.repr2(self.remote_info, nl=1)))
        assert self.remote_info['type'] != 'unknown'
        self.remote_info['repo_name'] = self.config['repo_name']
        self.remote_info['url'] = '/'.join([self.remote_info['host'], self.remote_info['group'], self.config['repo_name']])
        self.remote_info['git_url'] = '/'.join([self.remote_info['host'], self.remote_info['group'], self.config['repo_name'] + '.git'])

        self._build_template_registry()
        self.stage_files()
        return self

    def copy_staged_files(self):
        stats, tasks = self.gather_tasks()
        copy_tasks = tasks['copy']
        perm_tasks = tasks['perms']
        mkdir_tasks = tasks['mkdir']
        task_summary = ub.map_vals(len, tasks)
        if any(task_summary.values()):
            print('task_summary = {}'.format(ub.repr2(task_summary, nl=1)))
            if self.config.confirm('Do you want to apply this patch?'):
                dirs = {d.parent for s, d in copy_tasks}
                for d in dirs:
                    d.ensuredir()
                for d in mkdir_tasks:
                    d.ensuredir()
                for src, dst in copy_tasks:
                    shutil.copy2(src, dst)
                for fname, mode in perm_tasks:
                    os.chmod(fname, mode)

    def vcs_checks(self):
        # repodir = self.config['repodir']
        # mod_dpath = None
        # if mod_dpath is None:
        #     mod_name = self.config['mod_name']
        #     mod_dpath = repodir / mod_name

        # package_structure = [
        #     repodir / 'CHANGELOG.md',
        #     mod_dpath / '__init__.py',
        #     mod_dpath / '__main__.py',
        # ]
        # missing = []
        # for fpath in package_structure:
        #     if not fpath.exists():
        #         missing.append(fpath)
        # if missing:
        #     print('missing = {}'.format(ub.repr2(missing, nl=1)))
        if self.config['is_new']:
            create_new_repo_info = ub.codeblock(
                f'''
                TODO: call the APIS
                git init
                gh repo create {self.repo_name} --public
                # https://cli.github.com/manual/gh_repo_create
                ''')
            print(create_new_repo_info)
            import cmd_queue
            queue = cmd_queue.Queue.create(cwd=self.repodir)
            git_dpath = self.repodir / '.git'
            if not git_dpath.exists():
                queue.submit('git init')
                queue.sync().submit(f'git remote add origin {self.remote_info["url"]}')

            if queue.jobs:
                queue.rprint()
                if self.config.confirm('Do git init?'):
                    queue.run()

    def _stage_file(self, info):
        """
        Example:
            >>> from xcookie.main import *  # NOQA
            >>> dpath = ub.Path.appdir('xcookie/tests/test-stage').delete().ensuredir()
            >>> kwargs = {
            >>>     'repodir': dpath / 'testrepo',
            >>>     'tags': ['gitlab', 'kitware', 'purepy', 'cv2'],
            >>>     'rotate_secrets': False,
            >>>     'is_new': False,
            >>>     'interactive': False,
            >>> }
            >>> config = XCookieConfig(cmdline=0, data=kwargs)
            >>> config.normalize()
            >>> print('config = {}'.format(ub.repr2(dict(config), nl=1)))
            >>> self = TemplateApplier(config)
            >>> self._build_template_registry()
            >>> info = [d for d in self.template_infos if d['fname'] == 'setup.py'][0]
            >>> info = [d for d in self.template_infos if d['fname'] == '.gitlab-ci.yml'][0]
            >>> self._stage_file(info)
        """
        # print('info = {!r}'.format(info))
        tags = info.get('tags', None)
        if tags:
            tags = set(tags.split(','))
            if not set(self.config['tags']).issuperset(tags):
                raise SkipFile

        path_name = info['fname']
        path_type = info.get('path_type', 'file')

        stage_fpath = self.staging_dpath / path_name
        info['stage_fpath'] = stage_fpath
        info['repo_fpath'] = self.repodir / path_name
        info['path_type'] = path_type
        if path_type == 'dir':
            stage_fpath.ensuredir()
        else:
            stage_fpath.parent.ensuredir()
            dynamic = info.get('dynamic', '') or info.get('source', '') == 'dynamic'
            if dynamic:
                dynamic_var = info.get('dynamic', '')
                if dynamic_var == '':
                    text = self.lut(info)
                else:
                    text = getattr(self, dynamic_var)()
                try:
                    stage_fpath.write_text(text)
                except Exception:
                    print(f'text={text}')
                    raise
                    pass
            else:
                in_fname = info.get('input_fname', path_name)
                raw_fpath = self.template_dpath / in_fname
                if not raw_fpath.exists():
                    raise IOError(f'Template file: {raw_fpath=} does not exist')
                shutil.copy2(raw_fpath, stage_fpath)

                self._apply_xcookie_directives(stage_fpath)

                if info['template']:
                    xdev.sedfile(stage_fpath, 'xcookie', self.repo_name, verbose=0)
                    author = ub.cmd('git config --global user.name')['out'].strip()
                    author_email = ub.cmd('git config --global user.email')['out'].strip()
                    xdev.sedfile(stage_fpath, '<AUTHOR>', author, verbose=0)
                    xdev.sedfile(stage_fpath, '<AUTHOR_EMAIL>', author_email, verbose=0)
        return info

    def _apply_xcookie_directives(self, stage_fpath):
        text = stage_fpath.read_text()
        from xcookie.directive import DirectiveExtractor
        namespace = 'xcookie'
        commands = ['UNCOMMENT_IF', 'COMMENT_IF']
        extractor = DirectiveExtractor(namespace, commands)

        import re
        def comment_line(line):
            """

            line = '       #- pip install .[tests-strict,headless-strict]  # testrepo: +UNCOMMENT_IF(cv2)'
            uncomment_line(line)

            cases = [
                '   foobar',
                'foobar',
                '   def fds(): # hello',
            ]
            for line in cases:
                cline = comment_line(line)
                uline = uncomment_line(cline)
                print(f'line={line}')
                print(f'cline={cline}')
                print(f'uline={uline}')
                assert uline == line
            cases = [
                '#   foobar',
                '   #  foobar',
                '   #foobar',
                '#foobar',
                '#  foobar',
                '# foobar',
                '#   def fds(): # hello',
                '   #def fds(): # hello',
            ]
            for line in cases:
                uline = uncomment_line(cline)
                cline = comment_line(line)
                print(f'line={line}')
                print(f'cline={cline}')
                print(f'uline={uline}')
            """
            return re.sub(r'^(\s*)([^\s])', r'\g<1># \g<2>', line)

        def uncomment_line(line):
            return re.sub(r'^(\s*)#\s*', r'\g<1>', line, count=1)

        def tags_satisfied(directive, tags):
            value = tags.issuperset(set(directive.args))
            return value

        tags = set(self.config['tags'])
        new_lines = []
        did_work = 0
        for line in text.split('\n'):
            extracted = list(extractor.extract(line))
            # if 'COMMENT' in line:
            #     print(f'line={line}')
            #     print(f'extracted={extracted}')
            if extracted:
                for directive in extracted:
                    action = None
                    if directive.name == 'COMMENT_IF':
                        value = tags_satisfied(directive, tags)
                        if value:
                            action = comment_line
                            # print(f'action={action}')
                            did_work = 1
                    if directive.name == 'UNCOMMENT_IF':
                        value = tags_satisfied(directive, tags)
                        if value:
                            action = uncomment_line
                            print(f'action={action}')
                            did_work = 1
                    if action is not None:
                        # print(f'directive.name={directive.name}')
                        # print(f'action={action}')
                        # print(f'old line={line}')
                        line = action(line)
                        # print(f'new line={line}')
            new_lines.append(line)

        if did_work:
            stage_fpath.write_text('\n'.join(new_lines))

    def stage_files(self):
        self.staging_infos = []
        for info in ub.ProgIter(self.template_infos, desc='staging'):
            try:
                info = self._stage_file(info)
            except SkipFile:
                continue
            else:
                self.staging_infos.append(info)

        if 1:
            import pandas as pd
            # print('self.staging_infos = {}'.format(ub.repr2(self.staging_infos, nl=1)))
            df = pd.DataFrame(self.staging_infos)
            print(df)

    def gather_tasks(self):
        tasks = {
            'copy': [],
            'perms': [],
            'mkdir': [],
        }
        stats = {
            'missing': [],
            'modified': [],
            'dirty': [],
            'clean': [],
            'missing_dir': [],
        }

        if self.config['regen'] is not None:
            regen_pat = xdev.Pattern.coerce(self.config['regen'])
        else:
            regen_pat = None

        for info in self.staging_infos:
            stage_fpath = info['stage_fpath']
            repo_fpath = info['repo_fpath']
            if not repo_fpath.exists():
                if stage_fpath.is_dir():
                    tasks['mkdir'].append(repo_fpath)
                    stats['missing_dir'].append(repo_fpath)
                else:
                    stats['missing'].append(repo_fpath)
                    tasks['copy'].append((stage_fpath, repo_fpath))
                    stage_text = stage_fpath.read_text()
                    difftext = xdev.difftext('', stage_text[:1000], colored=1)
                    print(f'<NEW FPATH={repo_fpath}>')
                    print(difftext)
                    print(f'<END FPATH={repo_fpath}>')
            else:
                assert stage_fpath.exists()
                if stage_fpath.is_dir():
                    continue
                repo_text = repo_fpath.read_text()
                stage_text = stage_fpath.read_text()
                if stage_text.strip() == repo_text.strip():
                    difftext = None
                else:
                    difftext = xdev.difftext(repo_text, stage_text, colored=1)
                if difftext:
                    want_rewrite = info['overwrite']
                    if not want_rewrite:
                        if regen_pat is not None:
                            if regen_pat.search(info['fname']):
                                want_rewrite = True

                    if want_rewrite:
                        tasks['copy'].append((stage_fpath, repo_fpath))
                        stats['dirty'].append(repo_fpath)
                        print(f'<DIFF FOR repo_fpath={repo_fpath}>')
                        print(difftext)
                        print(f'<END DIFF repo_fpath={repo_fpath}>')
                    else:
                        stats['modified'].append(repo_fpath)
                else:
                    stats['clean'].append(repo_fpath)

            if 'x' in info.get('perms', ''):
                import stat
                if info['repo_fpath'].exists():
                    st = ub.Path(info['repo_fpath']).stat()
                    mode_want = st.st_mode | stat.S_IEXEC
                    if mode_want != st.st_mode:
                        tasks['perms'].append((info['repo_fpath'], mode_want))
                else:
                    tasks['perms'].append((info['repo_fpath'], mode_want))

        print('stats = {}'.format(ub.repr2(stats, nl=2)))
        return stats, tasks

    # def build_requirements(self):
    #     pass

    def rotate_secrets(self):
        setup_secrets_fpath = self.repodir / 'dev/setup_secrets.sh'
        # dev/public_gpg_key
        # if self.config.confirm('Ready to rotate secrets?'):
        if 'erotemic' in self.config['tags']:
            environ_export = 'setup_package_environs_github_erotemic'
            upload_secret_cmd = 'upload_github_secrets'
        elif 'pyutils' in self.config['tags']:
            environ_export = 'setup_package_environs_github_pyutils'
            upload_secret_cmd = 'upload_github_secrets'
        elif 'kitware' in self.config['tags']:
            environ_export = 'setup_package_environs_gitlab_kitware'
            upload_secret_cmd = 'upload_gitlab_repo_secrets'
        else:
            raise Exception

        import cmd_queue
        script = cmd_queue.Queue.create(cwd=self.repodir)
        script.submit(f'source {setup_secrets_fpath}')
        script.sync().submit(f'{environ_export}')
        # script.sync().submit('load_secrets')
        script.sync().submit('export_encrypted_code_signing_keys')
        script.sync().submit('git commit -am "Updated secrets"')
        script.sync().submit(f'{upload_secret_cmd}')
        # script.submit(ub.codeblock(
        #     f'''
        #     cd {self.repodir}
        #     source {setup_secrets_fpath}
        #     {environ_export}
        #     load_secrets
        #     export_encrypted_code_signing_keys
        #     git commit -am "Updated secrets"
        #     {upload_secret_cmd}
        #     '''))
        script.rprint()
        # print('FIXME: for now, you need to manually execute this')
        # print('Note: need to load_secrets before running this')
        if self.config.confirm('Ready to rotate secrets?'):
            script.run()

    def print_help_tips(self):
        text = ub.codeblock(
            f'''
            Things that xcookie might eventually do that you should do for
            yourself for now:

            * Add typing to the module

                # Generate stubs and check them
                xdev doctypes {self.repo_name} && mypy {self.repo_name}

                # Make sure you add the following to setup.py
                package_data={{
                    '{self.repo_name}': ['py.typed', '*.pyi'],
                }},


            ''')
        print(text)

    def build_setup(self):
        """
        Returns:
            str: templated code
        """
        from xcookie.builders import setup
        return setup.build_setup(self)

    def build_pyproject(self):
        """
        Returns:
            str: templated code
        """
        from xcookie.builders import pyproject
        return pyproject.build_pyproject(self)

    def build_github_actions(self):
        from xcookie.builders import github_actions
        return github_actions.build_github_actions(self)

    def build_readme(self):
        from xcookie.builders import readme
        return readme.build_readme(self)

    def build_docs_index(self):
        from xcookie.builders import docs
        return docs.build_docs_index(self)

    def lut(self, info):
        """
        Returns:
            str: templated code
        """
        fname = ub.Path(info['fname']).name
        if fname == 'CHANGELOG.md':
            return ub.codeblock(
                '''
                # Changelog

                We are currently working on porting this changelog to the specifications in
                [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
                This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

                ## [Version 0.0.1] -

                ### Added
                * Initial version
                ''')
        elif fname == 'test_import.py':
            return ub.codeblock(
                f'''
                def test_import():
                    import {self.config['mod_name']}
                ''')
        elif fname == '__main__.py':
            return ub.codeblock(
                '''
                #!/usr/bin/env python
                ''')
        elif fname == '__init__.py':
            return ub.codeblock(
                f'''
                """
                Basic
                """
                __version__ = '{self.config['version']}'
                __author__ = '{self.config['author']}'
                __author_email__ = '{self.config['author_email']}'
                __url__ = '{self.config['url']}'

                __mkinit__ = """
                mkinit {info['repo_fpath']}
                """
                ''')
        else:
            raise KeyError(fname)

    def _docs_quickstart():
        # Probably just need to copy/paste the conf.py
        r"""

        TODO:
            - [ ] Auto-edit the index.py to include the magic reference to `__init__`
            - [ ] If this is a utility library, populate the "usefulness section"
            - [ ] Try and find out how to auto-expand the toc tree
            - [ ] Auto-run the sphinx-apidoc for the user

        REPO_NAME=xcookie
        REPO_DPATH=$HOME/code/$REPO_NAME
        AUTHOR=$(git config --global user.name)
        cd $REPO_DPATH/docs
        sphinx-quickstart -q --sep \
            --project="$REPO_NAME" \
            --author="$AUTHOR" \
            --ext-autodoc \
            --ext-viewcode \
            --ext-intersphinx \
            --ext-todo \
            --extensions=sphinx.ext.autodoc,sphinx.ext.viewcode,sphinx.ext.napoleon,sphinx.ext.intersphinx,sphinx.ext.todo,sphinx.ext.autosummary \
            "$REPO_DPATH/docs"

        # THEN NEED TO:
        REPO_NAME=kwarray
        REPO_DPATH=$HOME/code/$REPO_NAME
        MOD_DPATH=$REPO_DPATH/$REPO_NAME
        sphinx-apidoc -f -o "$REPO_DPATH/docs/source"  "$MOD_DPATH" --separate
        cd "$REPO_DPATH/docs"
        make html

        The user will need to enable the repo on their readthedocs account:
        https://readthedocs.org/dashboard/import/manual/?

        To enable the read-the-docs go to https://readthedocs.org/dashboard/ and login

        Make sure you have a .readthedocs.yml file

        Click import project: (for github you can select, but gitlab you need to import manually)
            Set the Repository NAME: $REPO_NAME
            Set the Repository URL: $REPO_URL

        For gitlab you also need to setup an integrations and add gitlab
        incoming webhook Then go to $REPO_URL/hooks and add the URL

        Will also need to activate the main branch:
            https://readthedocs.org/projects/xcookie/versions/
        """
        pass


def main():
    XCookieConfig.main(cmdline={
        'strict': True,
        'autocomplete': True,
    })

if __name__ == '__main__':
    """
    CommandLine:
        python ~/misc/templates/xcookie/apply_template.py --help
    """
    main()
