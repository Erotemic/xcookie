import re

import pytest

from xcookie._vendor.xdev import difftext


ANSI_ESCAPE = re.compile(r'\x1b\[[0-9;]*m')


def test_vendored_difftext_matches_xdev_shape():
    result = difftext('one\ntwo\nthree', 'one\ntwo\nfive')
    assert result == '- three\n+ five'


def test_vendored_difftext_retains_requested_context():
    result = difftext(
        'zero\none\ntwo\nthree\nfour',
        'zero\none\nTWO\nthree\nfour',
        context_lines=1,
    )
    assert result.splitlines() == [
        '  one',
        '- two',
        '+ TWO',
        '  three',
    ]


def test_vendored_difftext_restores_colored_output():
    plain = difftext('old', 'new', colored=False)
    colored = difftext('old', 'new', colored=True)

    assert '\x1b[' not in plain
    assert '\x1b[' in colored
    assert ANSI_ESCAPE.sub('', colored) == plain


def test_vendored_difftext_can_ignore_trailing_whitespace():
    result = difftext('same  \n', 'same\n', ignore_whitespace=True)
    assert result == ''


def test_vendored_difftext_rejects_negative_context():
    with pytest.raises(ValueError):
        difftext('old', 'new', context_lines=-1)
