"""
Wrappers around :mod:`pyyaml` or :mod:`ruamel.yaml`.


The important functions to know are:

* :func:`Yaml.loads`

* :func:`Yaml.dumps`

* :func:`Yaml.coerce`

Loads and Dumps are strightforward. Loads takes a block of text and passes it
through the ruamel.yaml or pyyaml to parse the string. Dumps takes a data
structure and turns it into a YAML string. Roundtripping is supported with the
ruamel.yaml backend.

Coerce will accept input as a non-string data structure, and simply return it,
a path to a file, or a string which it assumes is YAML text (note: there is a
small ambiguity introduced here). If coerce encounters a string that looks like
an existing path it reads it. This does not happen by default in longer YAML
text inputs, but the parser does respect a !include constructor, which does let
you make nested configs by pointing to other configs.
"""
import io
import os
import ubelt as ub


NEW_RUAMEL = 1


class _YamlRepresenter:

    @staticmethod
    def str_presenter(dumper, data):
        # https://stackoverflow.com/questions/8640959/how-can-i-control-what-scalar-form-pyyaml-uses-for-my-data
        if len(data.splitlines()) > 1 or '\n' in data:
            text_list = [line.rstrip() for line in data.splitlines()]
            fixed_data = '\n'.join(text_list)
            return dumper.represent_scalar('tag:yaml.org,2002:str', fixed_data, style='|')
        return dumper.represent_scalar('tag:yaml.org,2002:str', data)


@ub.memoize
def _custom_ruaml_loader():
    """
    old method

    References:
        https://stackoverflow.com/questions/59635900/ruamel-yaml-custom-commentedmapping-for-custom-tags
        https://stackoverflow.com/questions/528281/how-can-i-include-a-yaml-file-inside-another
        https://stackoverflow.com/questions/76870413/using-a-custom-loader-with-ruamel-yaml-0-15-0
    """
    import ruamel.yaml
    Loader = ruamel.yaml.RoundTripLoader

    def _construct_include_tag(self, node):
        # print(f'node={node}')
        if isinstance(node.value, list):
            return [Yaml.coerce(v.value) for v in node.value]
        else:
            external_fpath = ub.Path(node.value)
            if not external_fpath.exists():
                raise IOError(f'Included external yaml file {external_fpath} '
                              'does not exist')
            return Yaml.load(node.value)
    Loader.add_constructor("!include", _construct_include_tag)
    return Loader


@ub.memoize
def _custom_ruaml_dumper():
    """
    References:
        https://stackoverflow.com/questions/59635900/ruamel-yaml-custom-commentedmapping-for-custom-tags
    """
    import ruamel.yaml
    Dumper = ruamel.yaml.RoundTripDumper
    Dumper.add_representer(str, _YamlRepresenter.str_presenter)
    Dumper.add_representer(ub.udict, Dumper.represent_dict)
    return Dumper


@ub.memoize
def _custom_pyaml_dumper():
    import yaml

    class Dumper(yaml.Dumper):
        pass
    # dumper = yaml.dumper.Dumper
    # dumper = yaml.SafeDumper(sort_keys=False)
    # yaml.dump(data, s, Dumper=yaml.SafeDumper, sort_keys=False, width=float("inf"))
    # yaml.dump(data, s, sort_keys=False)
    Dumper.add_representer(str, _YamlRepresenter.str_presenter)
    Dumper.add_representer(ub.udict, Dumper.represent_dict)
    return Dumper


# @ub.memoize
def _custom_new_ruaml_yaml_obj():
    """
    new method

    References:
        https://stackoverflow.com/questions/59635900/ruamel-yaml-custom-commentedmapping-for-custom-tags
        https://stackoverflow.com/questions/528281/how-can-i-include-a-yaml-file-inside-another
        https://stackoverflow.com/questions/76870413/using-a-custom-loader-with-ruamel-yaml-0-15-0

    Example:
        >>> # xdoctest: +REQUIRES(module:ruamel.yaml)
        >>> # Test new load
        >>> import io
        >>> file = io.StringIO('[a, b, c]')
        >>> yaml_obj = _custom_new_ruaml_yaml_obj()
        >>> data = yaml_obj.load(file)
        >>> print(data)
        >>> # Test round trip tump
        >>> file = io.StringIO()
        >>> yaml_obj.dump(data, file)
        >>> print(file.getvalue())
        >>> #
        >>> # Test new dump
        >>> data2 = ub.udict(a=1, b=2)
        >>> file = io.StringIO()
        >>> yaml_obj.dump(data2, file)
        >>> print(file.getvalue())
    """
    import ruamel.yaml
    from collections import Counter, OrderedDict, defaultdict

    # make a new instance, although you could get the YAML
    # instance from the constructor argument
    class CustomConstructor(ruamel.yaml.constructor.RoundTripConstructor):
        ...

    class CustomRepresenter(ruamel.yaml.representer.RoundTripRepresenter):
        ...

    CustomRepresenter.add_representer(str, _YamlRepresenter.str_presenter)
    CustomRepresenter.add_representer(ub.udict, CustomRepresenter.represent_dict)
    CustomRepresenter.add_representer(Counter, CustomRepresenter.represent_dict)
    CustomRepresenter.add_representer(OrderedDict, CustomRepresenter.represent_dict)
    CustomRepresenter.add_representer(defaultdict, CustomRepresenter.represent_dict)

    def _construct_include_tag(self, node):
        print(f'node={node}')
        value = node.value
        print(f'value={value}')
        if isinstance(value, list):
            return [Yaml.coerce(v.value) for v in value]
        else:
            external_fpath = ub.Path(value)
            if not external_fpath.exists():
                raise IOError(f'Included external yaml file {external_fpath} '
                              'does not exist')
            # Not sure why we can't recurse here...
            # yaml_obj
            # print(f'yaml_obj={yaml_obj}')
            # import xdev
            # xdev.embed()
            return Yaml.load(value)
    # Loader = ruamel.yaml.RoundTripLoader
    # Loader.add_constructor("!include", _construct_include_tag)

    CustomConstructor.add_constructor('!include', _construct_include_tag)
    # yaml_obj = ruamel.yaml.YAML(typ='unsafe', pure=True)
    yaml_obj = ruamel.yaml.YAML()
    yaml_obj.Constructor = CustomConstructor
    yaml_obj.Representer = CustomRepresenter
    yaml_obj.preserve_quotes = True
    yaml_obj.width = float('inf')
    return yaml_obj


class Yaml:
    """
    Namespace for yaml functions

    Example:
        >>> # xdoctest: +REQUIRES(module:ruamel.yaml)
        >>> import ubelt as ub
        >>> data = {
        >>>     'a': 'hello world',
        >>>     'b': ub.udict({'a': 3})
        >>> }
        >>> text1 = Yaml.dumps(data, backend='ruamel')
        >>> # Coerce is idempotent and resolves the input to nested Python
        >>> # structures.
        >>> resolved1 = Yaml.coerce(data)
        >>> resolved2 = Yaml.coerce(text1)
        >>> resolved3 = Yaml.coerce(resolved2)
        >>> assert resolved1 == resolved2 == resolved3 == data
        >>> # with ruamel
        >>> data2 = Yaml.loads(text1)
        >>> assert data2 == data
        >>> # with pyyaml
        >>> data2 = Yaml.loads(text1, backend='pyyaml')
        >>> assert data2 == data
    """

    @staticmethod
    def dumps(data, backend='ruamel'):
        """
        Dump yaml to a string representation
        (and account for some of our use-cases)

        Args:
            data (Any): yaml representable data
            backend (str): either ruamel or pyyaml

        Returns:
            str: yaml text

        Example:
            >>> # xdoctest: +REQUIRES(module:pyyaml)
            >>> # xdoctest: +REQUIRES(module:ruamel.yaml)
            >>> import ubelt as ub
            >>> data = {
            >>>     'a': 'hello world',
            >>>     'b': ub.udict({'a': 3})
            >>> }
            >>> text2 = Yaml.dumps(data, backend='pyyaml')
            >>> print(text2)
            >>> text1 = Yaml.dumps(data, backend='ruamel')
            >>> print(text1)
            >>> assert text1 == text2
        """
        file = io.StringIO()
        if backend == 'ruamel':
            if NEW_RUAMEL:
                yaml_obj = _custom_new_ruaml_yaml_obj()
                yaml_obj.dump(data, file)
            else:
                import ruamel.yaml
                Dumper = _custom_ruaml_dumper()
                ruamel.yaml.round_trip_dump(data, file, Dumper=Dumper, width=float("inf"))
        elif backend == 'pyyaml':
            import yaml
            Dumper = _custom_pyaml_dumper()
            yaml.dump(data, file, Dumper=Dumper, sort_keys=False, width=float("inf"))
        else:
            raise KeyError(backend)
        text = file.getvalue()
        return text

    @staticmethod
    def load(file, backend='ruamel'):
        """
        Load yaml from a file

        Args:
            file (io.TextIOBase | PathLike | str): yaml file path or file object
            backend (str): either ruamel or pyyaml

        Returns:
            object

        Example:
            >>> # xdoctest: +REQUIRES(module:pyyaml)
            >>> # xdoctest: +REQUIRES(module:ruamel.yaml)
            >>> import ubelt as ub
            >>> data = {
            >>>     'a': 'hello world',
            >>>     'b': ub.udict({'a': 3})
            >>> }
            >>> text1 = Yaml.dumps(data, backend='ruamel')
            >>> import io
            >>> # with ruamel
            >>> file = io.StringIO(text1)
            >>> data2 = Yaml.load(file)
            >>> assert data2 == data
            >>> # with pyyaml
            >>> file = io.StringIO(text1)
            >>> data2 = Yaml.load(file, backend='pyyaml')
            >>> assert data2 == data
        """
        if isinstance(file, (str, os.PathLike)):
            fpath = file
            with open(fpath, 'r') as fp:
                return Yaml.load(fp, backend=backend)
        else:
            if backend == 'ruamel':
                import ruamel.yaml  # NOQA
                # TODO: seems like there will be a deprecation
                # from ruamel.yaml import YAML
                if NEW_RUAMEL:
                    yaml_obj = _custom_new_ruaml_yaml_obj()
                    data = yaml_obj.load(file)
                else:
                    # yaml = YAML(typ='unsafe', pure=True)
                    # data = yaml.load(file, Loader=Loader, preserve_quotes=True)
                    Loader = _custom_ruaml_loader()
                    data = ruamel.yaml.load(file, Loader=Loader, preserve_quotes=True)
                    # data = ruamel.yaml.load(file, Loader=ruamel.yaml.RoundTripLoader, preserve_quotes=True)
            elif backend == 'pyyaml':
                import yaml
                # data = yaml.load(file, Loader=yaml.SafeLoader)
                data = yaml.load(file, Loader=yaml.Loader)
            else:
                raise KeyError(backend)
            return data

    @staticmethod
    def loads(text, backend='ruamel'):
        """
        Load yaml from a text

        Args:
            text (str): yaml text
            backend (str): either ruamel or pyyaml

        Returns:
            object

        Example:
            >>> # xdoctest: +REQUIRES(module:pyyaml)
            >>> # xdoctest: +REQUIRES(module:ruamel.yaml)
            >>> import ubelt as ub
            >>> data = {
            >>>     'a': 'hello world',
            >>>     'b': ub.udict({'a': 3})
            >>> }
            >>> print('data = {}'.format(ub.urepr(data, nl=1)))
            >>> print('---')
            >>> text = Yaml.dumps(data)
            >>> print(ub.highlight_code(text, 'yaml'))
            >>> print('---')
            >>> data2 = Yaml.loads(text)
            >>> assert data == data2
            >>> data3 = Yaml.loads(text, backend='pyyaml')
            >>> print('data2 = {}'.format(ub.urepr(data2, nl=1)))
            >>> print('data3 = {}'.format(ub.urepr(data3, nl=1)))
            >>> assert data == data3
        """
        # TODO: add debugging helpers when a loads fails
        file = io.StringIO(text)
        if backend == 'ruamel':
            import ruamel.yaml  # NOQA
            try:
                data = Yaml.load(file, backend=backend)
            except ruamel.yaml.parser.ParserError as ex_:
                ex = ex_
                print(f'YAML ERROR: {ex!r}')
                try:
                    from xdoctest.utils import add_line_numbers, highlight_code
                    lines = text.split('\n')
                    error_line = ex.context_mark.line
                    context_before = 3
                    context_after = 3
                    start_line = error_line - context_before
                    stop_line = error_line + context_after
                    show_lines = lines[start_line:stop_line]
                    show_lines = highlight_code('\n'.join(show_lines), 'YAML').split('\n')
                    lines = add_line_numbers(show_lines, start=start_line + 1)
                    print(f'ex.context_mark.line={ex.context_mark.line + 1}')
                    print(f'ex.context_mark.column={ex.context_mark.column}')
                    print('\n'.join(lines))
                except Exception:
                    ...
                raise
        else:
            data = Yaml.load(file, backend=backend)
        return data

    @staticmethod
    def coerce(data, backend='ruamel', path_policy='existing_file_with_extension'):
        """
        Attempt to convert input into a parsed yaml / json data structure.
        If the data looks like a path, it tries to load and parse file contents.
        If the data looks like a yaml/json string it tries to parse it.
        If the data looks like parsed data, then it returns it as-is.

        Args:
            data (str | PathLike | dict | list):
            backend (str): either ruamel or pyyaml
            path_policy (str):
                Determines how we determine if something looks like a path.
                Pre 0.3.2 behavior is from path_policy='existing_file'.
                Default is 'existing_file_with_extension'.
                Can also be 'never' to disable the path feature and decrease
                ambiguity.

        Returns:
            object: parsed yaml data

        Note:
            The input to the function cannot distinguish a string that should be
            loaded and a string that should be parsed. If it looks like a file that
            exists it will read it. To avoid this coerner case use this only for
            data where you expect the output is a List or Dict.

        References:
            https://stackoverflow.com/questions/528281/how-can-i-include-a-yaml-file-inside-another

        Example:
            >>> # xdoctest: +REQUIRES(module:pyyaml)
            >>> # xdoctest: +REQUIRES(module:ruamel.yaml)
            >>> text = ub.codeblock(
                '''
                - !!float nan
                - !!float inf
                - nan
                - inf
                # Seems to break older ruamel.yaml 0.17.21
                # - .nan
                # - .inf
                - null
                ''')
            >>> Yaml.coerce(text, backend='pyyaml')
            >>> Yaml.coerce(text, backend='ruamel')

        Example:
            >>> # xdoctest: +REQUIRES(module:pyyaml)
            >>> # xdoctest: +REQUIRES(module:ruamel.yaml)
            >>> Yaml.coerce('"[1, 2, 3]"')
            [1, 2, 3]
            >>> fpath = ub.Path.appdir('cmd_queue/tests/util_yaml').ensuredir() / 'file.yaml'
            >>> fpath.write_text(Yaml.dumps([4, 5, 6]))
            >>> Yaml.coerce(fpath)
            [4, 5, 6]
            >>> Yaml.coerce(str(fpath))
            [4, 5, 6]
            >>> dict(Yaml.coerce('{a: b, c: d}'))
            {'a': 'b', 'c': 'd'}
            >>> Yaml.coerce(None)
            None

        Example:
            >>> # xdoctest: +REQUIRES(module:pyyaml)
            >>> # xdoctest: +REQUIRES(module:ruamel.yaml)
            >>> assert Yaml.coerce('') is None

        Example:
            >>> # xdoctest: +REQUIRES(module:pyyaml)
            >>> # xdoctest: +REQUIRES(module:ruamel.yaml)
            >>> dpath = ub.Path.appdir('cmd_queue/tests/util_yaml').ensuredir()
            >>> fpath = dpath / 'external.yaml'
            >>> fpath.write_text(Yaml.dumps({'foo': 'bar'}))
            >>> text = ub.codeblock(
            >>>    f'''
            >>>    items:
            >>>        - !include {dpath}/external.yaml
            >>>    ''')
            >>> data = Yaml.coerce(text, backend='ruamel')
            >>> print(Yaml.dumps(data, backend='ruamel'))
            items:
            - foo: bar

            >>> text = ub.codeblock(
            >>>    f'''
            >>>    items:
            >>>        !include [{dpath}/external.yaml, blah, 1, 2, 3]
            >>>    ''')
            >>> data = Yaml.coerce(text, backend='ruamel')
            >>> print('data = {}'.format(ub.urepr(data, nl=1)))
            >>> print(Yaml.dumps(data, backend='ruamel'))
        """
        if isinstance(data, os.PathLike):
            result = Yaml.load(data, backend=backend)
        elif isinstance(data, str):
            maybe_path = None

            if path_policy == 'never':
                ...
            else:
                if path_policy == 'existing_file':
                    path_requires_extension = False
                elif path_policy == 'existing_file_with_extension':
                    path_requires_extension = True
                else:
                    raise KeyError(path_policy)

                if '\n' not in data and len(data.strip()) > 0:
                    # Ambiguous case: might this be path-like?
                    maybe_path = ub.Path(data)
                    try:
                        if not maybe_path.is_file():
                            maybe_path = None
                    except OSError:
                        maybe_path = None

                if maybe_path and path_requires_extension:
                    # If the input looks like a path, try to load it.  This was
                    # added because I tried to coerce "auto" as a string, but
                    # for some reason there was a file "auto" in my cwd and
                    # that was confusing.
                    if '.' not in maybe_path.name:
                        maybe_path = None

            if maybe_path is not None:
                result = Yaml.coerce(maybe_path, backend=backend)
            else:
                result = Yaml.loads(data, backend=backend)
        elif hasattr(data, 'read'):
            # assume file
            result = Yaml.load(data, backend=backend)
        else:
            # Probably already parsed. Return the input
            result = data
        return result

    @staticmethod
    def InlineList(items):
        """
        References:
            .. [SO56937691] https://stackoverflow.com/questions/56937691/making-yaml-ruamel-yaml-always-dump-lists-inline
        """
        import ruamel.yaml
        ret = ruamel.yaml.comments.CommentedSeq(items)
        ret.fa.set_flow_style()
        return ret

    @staticmethod
    def Dict(data):
        """
        Get a ruamel-enhanced dictionary

        Example:
            >>> # xdoctest: +REQUIRES(module:pyyaml)
            >>> # xdoctest: +REQUIRES(module:ruamel.yaml)
            >>> data = {'a': 'avalue', 'b': 'bvalue'}
            >>> data = Yaml.Dict(data)
            >>> data.yaml_set_start_comment('hello')
            >>> # Note: not working https://sourceforge.net/p/ruamel-yaml/tickets/400/
            >>> data.yaml_set_comment_before_after_key('a', before='a comment', indent=2)
            >>> data.yaml_set_comment_before_after_key('b', 'b comment')
            >>> print(Yaml.dumps(data))
        """
        import ruamel.yaml
        ret = ruamel.yaml.comments.CommentedMap(data)
        return ret

    @staticmethod
    def CodeBlock(text):
        import ruamel.yaml
        return ruamel.yaml.scalarstring.LiteralScalarString(ub.codeblock(text))


def _dev():
    # import yaml
    # yaml
    # https://stackoverflow.com/questions/18065427/generating-anchors-with-pyyaml-dump/36295979#36295979
    from xcookie import rc
    import ubelt as ub
    import yaml
    fpath = rc.resource_fpath('gitlab-ci.purepy.yml.in')
    data = yaml.load(open(fpath, 'r'), yaml.SafeLoader)
    print('data = {}'.format(ub.urepr(data, nl=-1)))
    from xcookie.util_yaml import Yaml
    print(Yaml.dumps(data))

    import ruamel.yaml
    data = ruamel.yaml.load(open(fpath, 'r'), Loader=ruamel.yaml.RoundTripLoader, preserve_quotes=True)
    print(ruamel.yaml.round_trip_dump(data, Dumper=ruamel.yaml.RoundTripDumper))
