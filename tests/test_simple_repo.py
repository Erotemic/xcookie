def test_simple_repo():
    """
    This performs a simple run of xcookie, adds a few dummy files, and builds
    the docs.

    TODO:
        - [ ] Add checks. There are no checks other than that things run
              without errors.

    """
    import ubelt as ub

    if ub.WIN32:
        import pytest
        pytest.skip('requires bash')

    dpath = ub.Path.appdir('xcookie/tests/test-init/simple_repo')
    dpath.delete().ensuredir()

    # Create a demo repo
    from xcookie import main
    # import rich

    kwargs = dict(
        repodir=dpath,
        mod_name='simple_mod',
        remote_group='demo_group',
        rotate_secrets=False,
        init_new_remotes=False,
        tags=['github', 'purepy'],
        interactive=False
    )
    # config = main.XCookieConfig(**kwargs)
    # config['repodir'] = 'fds'
    # rich.print(f'config = {ub.urepr(config, nl=1)}')

    self = main.XCookieConfig.main(
        cmdline=0,
        **kwargs
    )
    import xdev
    xdev.tree_repr(dpath)
    # from xdev.cli.dirstats import DirectoryWalker
    # walker = DirectoryWalker(dpath, show_nfiles=0,
    #                          show_types=0,
    #                          block_dnames=['.git'])
    # walker.build()
    # walker.write_network_text()

    # ---
    # Write some simple content into the module
    mymod1_fpath = self.mod_dpath / 'mymod1.py'
    mymod1_fpath.write_text(ub.codeblock(
        '''
        """
        A simple demo module.
        """


        def add3(x, y, z):
            """
            Args:
                x (int): a number
                y (int): a number
                z (int): a number

            Returns:
                int:

            Example:
                >>> # xdoctest: +REQUIRES(--show)
                >>> import kwplot
                >>> kwplot.autompl()
                >>> kwplot.plt.plot([1, 2, 3], [1, 2, 3])
                >>> kwplot.show_if_requested()
            """
            return x + y + z
        '''))

    mymod1_init_fpath = self.mod_dpath / '__init__.py'
    text = mymod1_init_fpath.read_text()
    text = text.replace('Basic', ub.paragraph(
        '''
        Hello world. This is an example documentation written to the module
        dunder init. It should be rendered in the main sphinx apidoc page.
        ''')) + '\n\n# foobar\n\n'
    mymod1_init_fpath.write_text(text)

    # We could do mkinit if we wanted.
    # ub.cmd(f'mkinit {mymod1_init_fpath} -w', verbose=3)

    self = main.XCookieConfig.main(
        cmdline=0,
        **kwargs,
        refresh_docs=True,
        render_doc_images=True,
    )
    docs_dpath = self.repodir / 'docs'

    # hack to ensure module is importable before make html
    import os
    env = os.environ
    PYTHONPATH = env.get('PYTHONPATH', '').split(os.pathsep)
    PYTHONPATH.insert(0, str(self.mod_dpath.parent.absolute()))
    env['PYTHONPATH'] = os.pathsep.join(PYTHONPATH)
    ub.cmd('make html', cwd=docs_dpath, verbose=3, env=env)

    if 0:
        # For Debugging
        import xdev
        index_html_fpath = (docs_dpath / 'build/html/index.html')
        xdev.startfile(index_html_fpath)
