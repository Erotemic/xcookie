import shutil

import pytest

from xcookie.util_command import SerialCommandQueue


def test_serial_command_queue_renders_one_shell_script(tmp_path):
    queue = SerialCommandQueue.create(
        backend='serial', cwd=tmp_path, log=False
    )
    queue.submit('export XCOOKIE_QUEUE_TEST=works')
    queue.sync().submit(
        'printf "%s" "$XCOOKIE_QUEUE_TEST" > queue-result.txt'
    )

    text = queue.finalize_text(with_gaurds=False)
    assert text.startswith('set -e\n')
    assert 'export XCOOKIE_QUEUE_TEST=works\n' in text
    assert 'printf "%s" "$XCOOKIE_QUEUE_TEST"' in text


@pytest.mark.skipif(shutil.which('bash') is None, reason='requires bash')
def test_serial_command_queue_preserves_shell_state(tmp_path):
    queue = SerialCommandQueue.create(
        backend='serial', cwd=tmp_path, log=False
    )
    queue.submit('export XCOOKIE_QUEUE_TEST=works')
    queue.sync().submit(
        'printf "%s" "$XCOOKIE_QUEUE_TEST" > queue-result.txt'
    )

    queue.run()
    assert (tmp_path / 'queue-result.txt').read_text() == 'works'
