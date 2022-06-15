"""
Port and extension of xdoctest directives.
"""
import sys
import os
import re
import warnings
import operator
from xdoctest import utils
from xdoctest import static_analysis as static
from collections import namedtuple
# from xdoctest import exceptions


def named(key, pattern):
    """ helper for regex """
    return '(?P<{}>{})'.format(key, pattern)


Effect = namedtuple('Effect', ('action', 'key', 'value'))


def extract_directive_comment(source):
    """
    Different than the xdoctest version. Finds the last comment part of a line

    source = '# acommend  # b comment'
    list(extract_directive_comment(source))

    # TODO: lark grammar?
    """
    for comment in static.extract_comments(source):
        current = comment
        stripped = current[1:]
        while True:
            n = list(static.extract_comments(stripped))
            if len(n) == 0:
                yield current
                break
            else:
                current = n[0]
                stripped = current[1:]


class Directive(utils.NiceRepr):
    """
    Directives modify the runtime state.
    """
    def __init__(self, name, positive=True, args=[], inline=None):
        self.name = name
        self.args = args
        self.inline = inline
        self.positive = positive

    @classmethod
    def extract(cls, text, directive_re, commands):
        """
        Parses directives from a line or repl line

        Args:
            text (str):
                must correspond to exactly one PS1 line and its PS2 followups.

            prefix (str | None):
                The directive "namespace". If None, this uses the xdoctest
                defaults of ``DIRECTIVE_RE``. This will always be the case for
                xdoctest, but we are extending this class for use elsewhere.

        Yields:
            Directive: directive: the parsed directives
        """
        # Flag extracted directives as inline iff the text is only comments
        inline = not all(line.strip().startswith('#')
                         for line in text.splitlines())
        #
        for comment in extract_directive_comment(text):
            # remove the first comment character and see if the comment matches
            # the directive pattern
            m = directive_re.match(comment[1:].strip())
            if m:
                for key, optstr in m.groupdict().items():
                    if optstr:
                        optparts = _split_opstr(optstr)
                        # optparts = optstr.split(',')
                        for optpart in optparts:
                            directive = parse_directive_optstr(optpart, commands, inline)
                            if directive:
                                yield directive

    def __nice__(self):
        prefix = ['-', '+'][int(self.positive)]
        if self.args:
            argstr = ', '.join(self.args)
            return '{}{}({})'.format(prefix, self.name, argstr)
        else:
            return '{}{}'.format(prefix, self.name)

    def _unpack_args(self, num):
        from xdoctest.utils import util_deprecation
        util_deprecation.schedule_deprecation3(
            modname='xdoctest',
            name='Directive._unpack_args', type='method',
            migration='there is no need to use this',
            deprecate='1.0.0', error='1.1.0', remove='1.2.0'
        )
        nargs = self.args
        if len(nargs) != 1:
            raise TypeError(
                '{} directive expected exactly {} argument(s), '
                'got {}'.format(self.name, num, nargs))
        return self.args

    def effect(self, argv=None, environ=None):
        from xdoctest.utils import util_deprecation
        util_deprecation.schedule_deprecation3(
            modname='xdoctest',
            name='Directive.effect', type='method',
            migration='Use Directive.effects instead',
            deprecate='1.0.0', error='1.1.0', remove='1.2.0'
        )
        effects = self.effects(argv=argv, environ=environ)
        if len(effects) > 1:
            raise Exception('Old method cannot handle multiple effects')
        return effects[0]

    def effects(self, argv=None, environ=None):
        """
        Returns how this directive modifies a RuntimeState object

        This is called by :func:`RuntimeState.update` to update itself

        Args:
            argv (List[str], default=None):
                if specified, overwrite sys.argv
            environ (Dict[str, str], default=None):
                if specified, overwrite os.environ

        Returns:
            List[Effect]: list of named tuples containing:
                action (str): code indicating how to update
                key (str): name of runtime state item to modify
                value (object): value to modify with
        """
        key = self.name
        value = None

        effects = []
        if self.name == 'REQUIRES':
            # Special handling of REQUIRES
            for arg in self.args:
                value = arg
                if _is_requires_satisfied(arg, argv=argv, environ=environ):
                    # If the requirement is met, then do nothing,
                    action = 'noop'
                else:
                    # otherwise, add or remove the condition from REQUIREMENTS,
                    # depending on if the directive is positive or negative.
                    if self.positive:
                        action = 'set.add'
                    else:
                        action = 'set.remove'
                effects.append(Effect(action, key, value))
        elif key.startswith('REPORT_'):
            # Special handling of report style
            if self.positive:
                action = 'noop'
            else:
                action = 'set_report_style'
            effects.append(Effect(action, key, value))
        else:
            # The action overwrites state[key] using value
            action = 'assign'
            value = self.positive
            effects.append(Effect(action, key, value))
        return effects


def _split_opstr(optstr):
    """
    Simplified balanced paren logic to only split commas outside of parens

    Example:
        >>> optstr = '+FOO, REQUIRES(foo,bar), +ELLIPSIS'
        >>> _split_opstr(optstr)
        ['+FOO', 'REQUIRES(foo,bar)', '+ELLIPSIS']
    """
    import re
    stack = []
    split_pos = []
    for match in re.finditer(r',|\(|\)', optstr):
        token = match.group()
        if token == ',' and not stack:
            # Only split when there are no parens
            split_pos.append(match.start())
        elif token == '(':
            stack.append(token)
        elif token == ')':
            stack.pop()
    assert len(stack) == 0, 'parens not balanced'

    parts = []
    prev = 0
    for curr in split_pos:
        parts.append(optstr[prev:curr].strip())
        prev = curr + 1
    curr = None
    parts.append(optstr[prev:curr].strip())
    return parts


def _is_requires_satisfied(arg, argv=None, environ=None):
    """
    Determines if the argument to a REQUIRES directive is satisfied

    Args:
        arg (str): condition code
        argv (List[str]): cmdline if arg is cmd code usually ``sys.argv``
        environ (Dict[str, str]): environment variables usually ``os.environ``

    Returns:
        bool: flag - True if the requirement is met
    """
    # TODO: add python version options
    SYS_PLATFORM_TAGS = ['win32', 'linux', 'darwin', 'cywgin']
    OS_NAME_TAGS = ['posix', 'nt', 'java']
    PY_IMPL_TAGS = ['cpython', 'ironpython', 'jython', 'pypy']
    # TODO: tox tags: https://tox.readthedocs.io/en/latest/example/basic.html
    PY_VER_TAGS = ['py2', 'py3']

    arg_lower = arg.lower()

    if arg.startswith('-'):
        if argv is None:
            argv = sys.argv
        flag = arg in argv
    elif arg.startswith('module:'):
        parts = arg.split(':')
        if len(parts) != 2:
            raise ValueError('xdoctest module REQUIRES directive has too many parts')
        # set flag to False (aka SKIP) if the module does not exist
        modname = parts[1]
        flag = _module_exists(modname)
    elif arg.startswith('env:'):
        if environ is None:
            environ = os.environ
        parts = arg.split(':')
        if len(parts) != 2:
            raise ValueError('xdoctest env REQUIRES directive has too many parts')
        envexpr = parts[1]
        expr_parts = re.split('(==|!=|>=)', envexpr)
        if len(expr_parts) == 1:
            # Test if the environment variable is truthy
            env_key = expr_parts[0]
            flag = bool(environ.get(env_key, None))
        elif len(expr_parts) == 3:
            # Test if the environment variable is equal to an expression
            env_key, op_code, value = expr_parts
            env_val = environ.get(env_key, None)
            if op_code == '==':
                op = operator.eq
            elif op_code == '!=':
                op = operator.ne
            else:
                raise KeyError(op_code)
            flag = op(env_val, value)
        else:
            raise ValueError('Too many expr_parts={}'.format(expr_parts))
    elif arg_lower in SYS_PLATFORM_TAGS:
        flag = sys.platform.lower().startswith(arg_lower)
    elif arg_lower in OS_NAME_TAGS:
        flag = os.name.startswith(arg_lower)
    elif arg_lower in PY_IMPL_TAGS:
        import platform
        flag = platform.python_implementation().lower().startswith(arg_lower)
    elif arg_lower in PY_VER_TAGS:
        if sys.version_info[0] == 2:  # nocover
            flag = arg_lower == 'py2'
        elif sys.version_info[0] == 3:  # pragma: nobranch
            flag = arg_lower == 'py3'
        else:  # nocover
            flag = False
    else:
        msg = utils.codeblock(
            '''
            Argument to REQUIRES directive must be either
            (1) a PLATFORM or OS tag (e.g. win32, darwin, linux),
            (2) a command line flag prefixed with '--', or
            (3) a module prefixed with 'module:'.
            (4) an environment variable prefixed with 'env:'.
            Got arg={!r}
            ''').replace('\n', ' ').strip().format(arg)
        raise ValueError(msg)
    return flag


class DirectiveExtractor:
    """
    Example:
        >>> from xcookie.directive import *  # NOQA
        >>> namespace = 'xcookie'
        >>> commands = ['UNCOMMENT_IF', 'COMMENT_IF']
        >>> self = DirectiveExtractor(namespace, commands)
        >>> text = '- this line is not python # xcookie: +COMMENT_IF(cv2)'
        >>> text = '# commented line # xcookie: +UNCOMMENT_IF(cv2)'
        >>> extracted = self.extract(text)
        >>> assert len(extracted) == 1
        >>> directive = extracted[0]
    """
    def __init__(self, namespace, commands):
        self.commands = commands
        self.namesapce = namespace
        directive_patterns = [
            namespace + r':\s*' + named('style2', '.*'),
        ]
        directive_re = re.compile('|'.join(directive_patterns), flags=re.IGNORECASE)
        self.directive_re = directive_re

    def extract(self, text):
        extracted = list(Directive.extract(text, self.directive_re, self.commands))
        return extracted


_MODNAME_EXISTS_CACHE = {}


def _module_exists(modname):
    if modname not in _MODNAME_EXISTS_CACHE:
        from xdoctest import static_analysis as static
        modpath = static.modname_to_modpath(modname)
        exists_flag = modpath is not None
        _MODNAME_EXISTS_CACHE[modname] = exists_flag
    exists_flag = _MODNAME_EXISTS_CACHE[modname]
    return exists_flag


def parse_directive_optstr(optpart, commands, inline=None):
    """
    Parses the information in the directive from the "optpart"

    optstrs are:
        optionally prefixed with ``+`` (default) or ``-``
        comma separated
        may contain one paren enclosed argument (experimental)
        all spaces are ignored

    Returns:
        Directive: the parsed directive
    """
    optpart = optpart.strip()
    # all spaces are ignored
    optpart = optpart.replace(' ', '')

    paren_pos = optpart.find('(')
    if paren_pos > -1:
        # handle simple paren case.
        body = optpart[paren_pos + 1:optpart.find(')')]
        args = [a.strip() for a in body.split(',')]
        # args = [optpart[paren_pos + 1:optpart.find(')')]]
        optpart = optpart[:paren_pos]
    else:
        args = []

    # Determine if the option starts with + or - (we assume + by default)
    if optpart.startswith(('+', '-')):
        positive = not optpart.startswith('-')
        name = optpart[1:]
    else:
        positive = True
        name = optpart

    name = name.upper()
    if name not in commands:
        msg = 'Unknown directive: {!r}'.format(optpart)
        warnings.warn(msg)
    else:
        directive = Directive(name, positive, args, inline)
        return directive
