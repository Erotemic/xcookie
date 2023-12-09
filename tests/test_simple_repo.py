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

    main.XCookieConfig.main(
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
