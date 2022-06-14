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
"""
import toml
import shutil
import ubelt as ub
import tempfile
import scriptconfig as scfg
from rich.prompt import Confirm
import xdev
import os


class XCookieConfig(scfg.Config):
    default = {
        'repodir': scfg.Value('.', help='path to the new or existing repo'),

        'repo_name': scfg.Value(None, help='defaults to ``repodir.name``'),
        'mod_name': scfg.Value(None, help='The name of the importable Python module. defaults to ``repo_name``'),
        'pkg_name': scfg.Value(None, help='The name of the installable Python package. defaults to ``mod_name``'),

        'rotate_secrets': scfg.Value('auto'),

        'is_new': scfg.Value('auto'),

        'interative': scfg.Value(True),

        'tags': scfg.Value('auto', nargs='*', help=ub.paragraph(
            '''
            Tags modify what parts of the template are used.
            Valid tags are:
                "binpy" - do we build binpy wheels?
                "graphics" - do we need opencv / opencv-headless?
                "erotemic" - this is an erotemic repo
                "kitware" - this is an kitware repo
                "pyutils" - this is an pyutils repo
                "purepy" - this is a pure python repo
            ''')),
    }

    def normalize(self):

        if self['repodir'] is None:
            self['repodir'] = ub.Path.cwd()
        else:
            self['repodir'] = ub.Path(self['repodir']).absolute()
        pyproject_fpath = self['repodir'] / 'pyproject.toml'
        if pyproject_fpath.exists():
            try:
                disk_config = toml.loads(pyproject_fpath.read_text())
            except Exception as ex:
                print(f'ex={ex}')
            if self['tags'] == 'auto':
                try:
                    self['tags'] = disk_config['tool']['xcookie']['tags']
                except KeyError:
                    pass

        if self['tags'] == 'auto':
            self['tags'] = []

        if self['tags']:
            if isinstance(self['tags'], str):
                self['tags'] = [self['tags']]
            new = []
            for t in self['tags']:
                new.extend([p.strip() for p in t.split(',')])
            self['tags'] = new

        if self['repo_name'] is None:
            self['repo_name'] = self['repodir'].name
        if self['mod_name'] is None:
            self['mod_name'] = self['repo_name']
        if self['is_new'] == 'auto':
            self['is_new'] = not (self['repodir'] / '.git').exists()
        if self['rotate_secrets'] == 'auto':
            self['rotate_secrets'] = self['is_new']

    def confirm(self, msg, default=True):
        """
        Args:
            msg (str): display to the user
            default (bool): default value if non-interactive

        Returns:
            bool:
        """
        if self['interative']:
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
        config = XCookieConfig(cmdline=cmdline, data=kwargs)
        config.normalize()
        print('config = {}'.format(ub.repr2(dict(config), nl=1)))
        repodir = ub.Path(config['repodir']).absolute()
        repodir.ensuredir()

        self = TemplateApplier(config)
        self.setup().apply()


class TemplateApplier:

    def _build_template_registry(self):
        """
        Take stock of the files in the template repo and ensure they all have
        appropriate properties.
        """

        rel_mod_dpath = ub.Path(self.config['mod_name'])
        # mod_dpath = self.config['repodir'] / rel_mod_dpath

        self.template_infos = [
            # {'template': 1, 'overwrite': False, 'fname': '.circleci/config.yml'},
            # {'template': 1, 'overwrite': False, 'fname': '.travis.yml'},

            {'template': 0, 'overwrite': 1, 'fname': 'dev/setup_secrets.sh'},

            {'template': 0, 'overwrite': 0, 'fname': '.gitignore'},
            # {'template': 1, 'overwrite': 1, 'fname': '.coveragerc'},
            {'template': 0, 'overwrite': 1, 'fname': '.readthedocs.yml'},
            # {'template': 0, 'overwrite': 1, 'fname': 'pytest.ini'},
            {'template': 0, 'overwrite': 0, 'fname': 'pyproject.toml', 'dynamic': 'build_pyproject'},

            {'template': 0, 'overwrite': 1, 'fname': '.github/dependabot.yml', 'tags': 'github'},
            {'template': 0, 'overwrite': 1, 'fname': '.github/workflows/test_binaries.yml', 'tags': 'binpy,github', 'input_fname': '.github/workflows/test_binaries.yml.in'},
            {'template': 1, 'overwrite': 1, 'fname': '.github/workflows/tests.yml', 'tags': 'purepy,github', 'input_fname': '.github/workflows/tests.yml.in'},

            {'template': 1, 'overwrite': 1, 'fname': '.gitlab-ci.yml', 'tags': 'gitlab'},
            # {'template': 1, 'overwrite': False, 'fname': 'appveyor.yml'},
            {'template': 1, 'overwrite': 0, 'fname': 'CMakeLists.txt', 'tags': 'binpy', 'input_fname': 'CMakeLists.txt.in'},

            {'template': 0, 'overwrite': 1, 'fname': 'dev/make_strict_req.sh', 'perms': 'x'},
            {'template': 0, 'overwrite': 1, 'fname': 'requirements.txt'},  # 'dynamic': 'build_requirements'},
            {'template': 0, 'overwrite': 0, 'fname': 'requirements/graphics.txt', 'tags': 'graphics'},
            {'template': 0, 'overwrite': 0, 'fname': 'requirements/headless.txt', 'tags': 'graphics'},
            {'template': 0, 'overwrite': 0, 'fname': 'requirements/optional.txt'},
            {'template': 0, 'overwrite': 0, 'fname': 'requirements/runtime.txt'},
            {'template': 0, 'overwrite': 0, 'fname': 'requirements/tests.txt'},
            {'template': 0, 'overwrite': 0, 'fname': 'requirements/docs.txt'},
            {'template': 1, 'overwrite': 0, 'fname': 'docs/source/conf.py'},

            {'template': 0, 'overwrite': 0, 'fname': 'docs/source/_static', 'path_type': 'dir'},
            {'template': 0, 'overwrite': 0, 'fname': 'docs/source/_templates', 'path_type': 'dir'},

            {'template': 0, 'overwrite': 1, 'fname': 'publish.sh', 'perms': 'x'},
            {'template': 1, 'overwrite': 1, 'fname': 'run_doctests.sh', 'perms': 'x'},
            {'template': 1, 'overwrite': 1, 'fname': 'build_wheels.sh', 'perms': 'x', 'tags': 'binpy'},
            {'template': 1, 'overwrite': 1, 'fname': 'run_tests.py', 'perms': 'x', 'tags': 'binpy', 'input_fname': 'run_tests.binpy.py.in'},
            {'template': 1, 'overwrite': 1, 'fname': 'run_tests.py', 'perms': 'x', 'tags': 'purepy', 'input_fname': 'run_tests.purepy.py.in'},
            {'template': 1, 'overwrite': 0, 'fname': 'setup.py', 'input_fname': 'setup.py.in', 'perms': 'x'},

            {'template': 1, 'overwrite': 0, 'fname': 'README.rst'},
            {'source': 'dynamic', 'overwrite': 0, 'fname': 'CHANGELOG.md'},
            {'source': 'dynamic', 'overwrite': 0, 'fname': rel_mod_dpath / '__init__.py'},
            # {'source': 'dynamic', 'overwrite': 0, 'fname': rel_mod_dpath / '__main__.py'},
            {'source': 'dynamic', 'overwrite': 0, 'fname': 'tests/test_import.py'},
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

    def setup(self):
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
                # TODO:
                # At least instructions on how to create a new repo, or maybe an
                # API call
                # https://github.com/new

                git init

                gh repo create {self.repo_name} --public

                # https://cli.github.com/manual/gh_repo_create
                ''')
            print(create_new_repo_info)
            git_dpath = self.repodir / '.git'
            if not git_dpath.exists():
                if self.config.confirm('Do git init?'):
                    print('todo: not implemented')
            # if self.config.confirm('Make initial files?'):
            #     print('todo: not implemented')

    def apply(self):
        self.vcs_checks()
        self.copy_staged_files()
        if self.config['rotate_secrets']:
            self.rotate_secrets()

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
                __version__ = '0.0.1'

                __mkinit__ = """
                mkinit {info['repo_fpath']}
                """
                ''')
        else:
            raise KeyError(fname)

    def stage_files(self):
        self.staging_infos = []
        for info in ub.ProgIter(self.template_infos, desc='staging'):
            print('info = {!r}'.format(info))
            tags = info.get('tags', None)
            if tags:
                tags = set(tags.split(','))
                if not set(self.config['tags']).issuperset(tags):
                    continue

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
                    stage_fpath.write_text(text)
                else:
                    in_fname = info.get('input_fname', path_name)
                    raw_fpath = self.template_dpath / in_fname
                    if not raw_fpath.exists():
                        raise IOError(f'Template file: {raw_fpath=} does not exist')
                    shutil.copy2(raw_fpath, stage_fpath)
                    if info['template']:
                        xdev.sedfile(stage_fpath, 'xcookie', self.repo_name, verbose=0)
                        author = ub.cmd('git config --global user.name')['out'].strip()
                        author_email = ub.cmd('git config --global user.email')['out'].strip()
                        xdev.sedfile(stage_fpath, '<AUTHOR>', author, verbose=0)
                        xdev.sedfile(stage_fpath, '<AUTHOR_EMAIL>', author_email, verbose=0)
            self.staging_infos.append(info)

        if 1:
            import pandas as pd
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
                    difftext = xdev.difftext('', stage_text[:10000], colored=1)
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
                    if info['overwrite']:
                        tasks['copy'].append((stage_fpath, repo_fpath))
                        stats['dirty'].append(repo_fpath)
                        print(f'<DIFF FOR repo_fpath={repo_fpath}>')
                        print(difftext[:10000])
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

        print('stats = {}'.format(ub.repr2(stats, nl=2)))
        return stats, tasks

    # def build_requirements(self):
    #     pass

    def build_pyproject(self):
        """
        Returns:
            str: templated code
        """
        # data = toml.loads((self.template_dpath / 'pyproject.toml').read_text())
        # print('data = {}'.format(ub.repr2(data, nl=5)))
        pyproj_config = ub.AutoDict()
        # {'tool': {}}
        if 'binpy' in self.config['tags']:
            pyproj_config['build-system']['requires'] = [
                "setuptools>=41.0.1",
                # setuptools_scm[toml]
                "wheel",
                "scikit-build>=0.9.0",
                "numpy",
                "ninja"
            ]
            pyproj_config['tool']['cibuildwheel'].update({
                'build': "cp37-* cp38-* cp39-* cp310-*",
                'build-frontend': "build",
                'skip': "pp* cp27-* cp34-* cp35-* cp36-* *-musllinux_*",
                'build-verbosity': 1,
                'test-requires': ["-r requirements/tests.txt"],
                'test-command': "python {project}/run_tests.py"
            })

            if True:
                cibw = pyproj_config['tool']['cibuildwheel']
                req_commands = {
                    'linux': [
                        'yum install epel-release lz4 lz4-devel -y',
                    ],
                    'windows': [
                        'choco install lz4 -y',
                    ],
                    'macos': [
                        'brew install lz4',
                    ]
                }
                for plat in req_commands.keys():
                    cmd = ' && '.join(req_commands[plat])
                    cibw[plat]['before-all'] = cmd

        WITH_PYTEST_INI = 1
        if WITH_PYTEST_INI:
            pytest_ini_opts = pyproj_config['tool']['pytest']['ini_options']
            pytest_ini_opts['addopts'] = "-p no:doctest --xdoctest --xdoctest-style=google --ignore-glob=setup.py"
            pytest_ini_opts['norecursedirs'] = ".git ignore build __pycache__ dev _skbuild"
            pytest_ini_opts['filterwarnings'] = [
                "default",
                "ignore:.*No cfgstr given in Cacher constructor or call.*:Warning",
                "ignore:.*Define the __nice__ method for.*:Warning",
                "ignore:.*private pytest class or function.*:Warning",
            ]

        WITH_COVERAGE = 1
        if WITH_COVERAGE:
            pyproj_config['tool']['coverage'].update(toml.loads(ub.codeblock(
                '''
                [run]
                branch = true

                [report]
                exclude_lines =[
                    "pragma: no cover",
                    ".*  # pragma: no cover",
                    ".*  # nocover",
                    "def __repr__",
                    "raise AssertionError",
                    "raise NotImplementedError",
                    "if 0:",
                    "if trace is not None",
                    "verbose = .*",
                    "^ *raise",
                    "^ *pass *$",
                    "if _debug:",
                    "if __name__ == .__main__.:",
                    ".*if six.PY2:"
                ]

                omit=[
                    "{REPO_NAME}/__main__.py",
                    "*/setup.py"
                ]
                ''').format(REPO_NAME=self.repo_name)))

        WITH_XCOOKIE = 1
        if WITH_XCOOKIE:
            pyproj_config['tool']['xcookie'].update(toml.loads(ub.codeblock(
                f'''
                tags = {self.config['tags']}
                mod_name = "{self.config['mod_name']}"
                repo_name = "{self.config['repo_name']}"
                ''')))

        text = toml.dumps(pyproj_config)
        return text

    def rotate_secrets(self):
        setup_secrets_fpath = self.repodir / 'dev/setup_secrets.sh'
        # dev/public_gpg_key
        if self.config.confirm('Ready to rotate secrets?'):
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
            script = cmd_queue.Queue.create()
            script.submit(ub.codeblock(
                f'''
                cd {self.repodir}
                source {setup_secrets_fpath}
                {environ_export}
                load_secrets
                export_encrypted_code_signing_keys
                git commit -am "Updated secrets"
                {upload_secret_cmd}
                '''))

            script.rprint()
            print('FIXME: for now, you need to manually execute this')

    def _docs_quickstart():
        # Probably just need to copy/paste the conf.py
        r"""
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
