def build_docs_conf(self):
    import ubelt as ub
    import datetime

    author = self.config['author']
    if isinstance(author, list):
        author_str = ' '.join(author)
    else:
        author_str = author

    fmtkw = {
        'repo_name': self.config['repo_name'],
        'repo_dashname': self.config['repo_name'].replace('_', '-'),
        'mod_name': self.config['mod_name'],
        'rel_mod_dpath': str(self.rel_mod_dpath),
        'repo_url': self.remote_info['url'],
        'author': author_str,
        'year': datetime.datetime.now().year,
        'repodir_wrt_home': self.repodir.shrinkuser()
    }

    text = ub.codeblock(
        r'''
        """
        Notes:
            Based on template code in:
                ~/code/xcookie/xcookie/builders/docs_conf.py
                ~/code/xcookie/xcookie/rc/conf_ext.py

            http://docs.readthedocs.io/en/latest/getting_started.html

            pip install sphinx sphinx-autobuild sphinx_rtd_theme sphinxcontrib-napoleon

            cd {repodir_wrt_home}
            mkdir -p docs
            cd docs

            sphinx-quickstart

            # need to edit the conf.py

            cd {repodir_wrt_home}/docs
            sphinx-apidoc --private -f -o {repodir_wrt_home}/docs/source {repodir_wrt_home}/{rel_mod_dpath} --separate
            make html

            git add source/*.rst

            Also:
                To turn on PR checks

                https://docs.readthedocs.io/en/stable/guides/autobuild-docs-for-pull-requests.html

                https://readthedocs.org/dashboard/{repo_dashname}/advanced/

                ensure your github account is connected to readthedocs
                https://readthedocs.org/accounts/social/connections/

                ### For gitlab

                The user will need to enable the repo on their readthedocs account:
                https://readthedocs.org/dashboard/import/manual/?

                To enable the read-the-docs go to https://readthedocs.org/dashboard/ and login

                Make sure you have a .readthedocs.yml file

                Click import project: (for github you can select, but gitlab you need to import manually)
                    Set the Repository NAME: {repo_name}
                    Set the Repository URL: {repo_url}

                For gitlab you also need to setup an integrations and add gitlab
                incoming webhook

                    https://readthedocs.org/dashboard/{repo_dashname}/integrations/create/

                Then go to

                    {repo_url}/hooks

                and add the URL

                select push, tag, and merge request

                See Docs for more details https://docs.readthedocs.io/en/stable/integrations.html

                Will also need to activate the main branch:
                    https://readthedocs.org/projects/{repo_dashname}/versions/
        """
        #
        # Configuration file for the Sphinx documentation builder.
        #
        # This file does only contain a selection of the most common options. For a
        # full list see the documentation:
        # http://www.sphinx-doc.org/en/stable/config

        # -- Path setup --------------------------------------------------------------

        # If extensions (or modules to document with autodoc) are in another directory,
        # add these directories to sys.path here. If the directory is relative to the
        # documentation root, use os.path.abspath to make it absolute, like shown here.
        #
        # import os
        # import sys
        # sys.path.insert(0, os.path.abspath('.'))


        # -- Project information -----------------------------------------------------
        import sphinx_rtd_theme
        from os.path import exists
        from os.path import dirname
        from os.path import join


        def parse_version(fpath):
            """
            Statically parse the version number from a python file
            """
            import ast
            if not exists(fpath):
                raise ValueError('fpath={{!r}} does not exist'.format(fpath))
            with open(fpath, 'r') as file_:
                sourcecode = file_.read()
            pt = ast.parse(sourcecode)
            class VersionVisitor(ast.NodeVisitor):
                def visit_Assign(self, node):
                    for target in node.targets:
                        if getattr(target, 'id', None) == '__version__':
                            self.version = node.value.s
            visitor = VersionVisitor()
            visitor.visit(pt)
            return visitor.version

        project = '{repo_name}'
        copyright = '{year}, {author}'
        author = '{author}'
        modname = '{mod_name}'

        modpath = join(dirname(dirname(dirname(__file__))), modname, '__init__.py')
        release = parse_version(modpath)
        version = '.'.join(release.split('.')[0:2])


        # -- General configuration ---------------------------------------------------

        # If your documentation needs a minimal Sphinx version, state it here.
        #
        # needs_sphinx = '1.0'

        # Add any Sphinx extension module names here, as strings. They can be
        # extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
        # ones.
        extensions = [
            'sphinx.ext.autodoc',
            'sphinx.ext.autosummary',
            'sphinx.ext.intersphinx',
            'sphinx.ext.napoleon',
            'sphinx.ext.todo',
            'sphinx.ext.viewcode',
            # 'myst_parser',  # TODO
        ]

        todo_include_todos = True
        napoleon_google_docstring = True
        napoleon_use_param = False
        napoleon_use_ivar = True

        autodoc_inherit_docstrings = False

        autodoc_member_order = 'bysource'
        autoclass_content = 'both'
        # autodoc_mock_imports = ['torch', 'torchvision', 'visdom']

        intersphinx_mapping = {{
            # 'pytorch': ('http://pytorch.org/docs/master/', None),
            'python': ('https://docs.python.org/3', None),
            'click': ('https://click.palletsprojects.com/', None),
            # 'xxhash': ('https://pypi.org/project/xxhash/', None),
            # 'pygments': ('https://pygments.org/docs/', None),
            # 'tqdm': ('https://tqdm.github.io/', None),
            # Requries that the repo have objects.inv
            'kwarray': ('https://kwarray.readthedocs.io/en/latest/', None),
            'kwimage': ('https://kwimage.readthedocs.io/en/latest/', None),
            # 'kwplot': ('https://kwplot.readthedocs.io/en/latest/', None),
            'ndsampler': ('https://ndsampler.readthedocs.io/en/latest/', None),
            'ubelt': ('https://ubelt.readthedocs.io/en/latest/', None),
            'xdoctest': ('https://xdoctest.readthedocs.io/en/latest/', None),
            'networkx': ('https://networkx.org/documentation/stable/', None),
            'scriptconfig': ('https://scriptconfig.readthedocs.io/en/latest/', None),

        }}
        __dev_note__ = """
        python -m sphinx.ext.intersphinx https://docs.python.org/3/objects.inv
        python -m sphinx.ext.intersphinx https://kwcoco.readthedocs.io/en/latest/objects.inv
        python -m sphinx.ext.intersphinx https://networkx.org/documentation/stable/objects.inv
        python -m sphinx.ext.intersphinx https://kwarray.readthedocs.io/en/latest/objects.inv
        python -m sphinx.ext.intersphinx https://kwimage.readthedocs.io/en/latest/objects.inv
        python -m sphinx.ext.intersphinx https://ubelt.readthedocs.io/en/latest/objects.inv
        python -m sphinx.ext.intersphinx https://networkx.org/documentation/stable/objects.inv
        """


        # Add any paths that contain templates here, relative to this directory.
        templates_path = ['_templates']

        # The suffix(es) of source filenames.
        # You can specify multiple suffix as a list of string:
        #
        source_suffix = ['.rst', '.md']

        # The master toctree document.
        master_doc = 'index'

        # The language for content autogenerated by Sphinx. Refer to documentation
        # for a list of supported languages.
        #
        # This is also used if you do content translation via gettext catalogs.
        # Usually you set "language" from the command line for these cases.
        language = 'en'

        # List of patterns, relative to source directory, that match files and
        # directories to ignore when looking for source files.
        # This pattern also affects html_static_path and html_extra_path .
        exclude_patterns = []

        # The name of the Pygments (syntax highlighting) style to use.
        pygments_style = 'sphinx'


        # -- Options for HTML output -------------------------------------------------

        # The theme to use for HTML and HTML Help pages.  See the documentation for
        # a list of builtin themes.
        #
        html_theme = 'sphinx_rtd_theme'
        html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]

        # Theme options are theme-specific and customize the look and feel of a theme
        # further.  For a list of options available for each theme, see the
        # documentation.
        #
        html_theme_options = {{
            'collapse_navigation': False,
            'display_version': True,
            # 'logo_only': True,
        }}
        # html_logo = '.static/{repo_name}.svg'
        # html_favicon = '.static/{repo_name}.ico'

        # Add any paths that contain custom static files (such as style sheets) here,
        # relative to this directory. They are copied after the builtin static files,
        # so a file named "default.css" will overwrite the builtin "default.css".
        html_static_path = ['_static']

        # Custom sidebar templates, must be a dictionary that maps document names
        # to template names.
        #
        # The default sidebars (for documents that don't match any pattern) are
        # defined by theme itself.  Builtin themes are using these templates by
        # default: ``['localtoc.html', 'relations.html', 'sourcelink.html',
        # 'searchbox.html']``.
        #
        # html_sidebars = {{}}


        # -- Options for HTMLHelp output ---------------------------------------------

        # Output file base name for HTML help builder.
        htmlhelp_basename = '{repo_name}doc'


        # -- Options for LaTeX output ------------------------------------------------

        latex_elements = {{
            # The paper size ('letterpaper' or 'a4paper').
            #
            # 'papersize': 'letterpaper',

            # The font size ('10pt', '11pt' or '12pt').
            #
            # 'pointsize': '10pt',

            # Additional stuff for the LaTeX preamble.
            #
            # 'preamble': '',

            # Latex figure (float) alignment
            #
            # 'figure_align': 'htbp',
        }}

        # Grouping the document tree into LaTeX files. List of tuples
        # (source start file, target name, title,
        #  author, documentclass [howto, manual, or own class]).
        latex_documents = [
            (master_doc, '{repo_name}.tex', '{repo_name} Documentation',
             '{author}', 'manual'),
        ]


        # -- Options for manual page output ------------------------------------------

        # One entry per manual page. List of tuples
        # (source start file, name, description, authors, manual section).
        man_pages = [
            (master_doc, '{repo_name}', '{repo_name} Documentation',
             [author], 1)
        ]


        # -- Options for Texinfo output ----------------------------------------------

        # Grouping the document tree into Texinfo files. List of tuples
        # (source start file, target name, title, author,
        #  dir menu entry, description, category)
        texinfo_documents = [
            (master_doc, '{repo_name}', '{repo_name} Documentation',
             author, '{repo_name}', 'One line description of project.',
             'Miscellaneous'),
        ]


        # -- Extension configuration -------------------------------------------------
        ''').format(**fmtkw)

    from xcookie import rc

    util_text = rc.resource_fpath('conf_ext.py').read_text()
    if 1:
        util_text = util_text.replace('RENDER_IMAGES = 0', 'RENDER_IMAGES = 1')

    if self.config['repo_name'] == 'kwcoco':
        util_text = util_text.replace('HACK_FOR_KWCOCO = 0', 'HACK_FOR_KWCOCO = 1')

    text = text + '\n' + util_text
    return text
