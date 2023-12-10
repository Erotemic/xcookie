def test_simple_repo():
    import ubelt as ub
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
            """
            return x + y + z
        '''))

    self = main.XCookieConfig.main(
        cmdline=0,
        **kwargs,
        refresh_docs=True,
    )
    docs_dpath = self.repodir / 'docs'
    ub.cmd('make html', cwd=docs_dpath, verbose=3)

    if 0:
        # For Debugging
        import xdev
        index_html_fpath = (docs_dpath / 'build/html/index.html')
        xdev.startfile(index_html_fpath)
