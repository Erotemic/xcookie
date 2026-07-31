import pytest

from xcookie import util_command
from xcookie.util_command import SerialCommandQueue
from xcookie.util_command import find_bash_executable


def test_serial_command_queue_renders_one_shell_script(tmp_path):
    queue = SerialCommandQueue.create(backend='serial', cwd=tmp_path, log=False)
    queue.submit('export XCOOKIE_QUEUE_TEST=works')
    queue.sync().submit('printf "%s" "$XCOOKIE_QUEUE_TEST" > queue-result.txt')

    text = queue.finalize_text(with_gaurds=False)
    assert text.startswith('set -e\n')
    assert 'export XCOOKIE_QUEUE_TEST=works\n' in text
    assert 'printf "%s" "$XCOOKIE_QUEUE_TEST"' in text


@pytest.mark.skipif(find_bash_executable() is None, reason='requires bash')
def test_serial_command_queue_preserves_shell_state(tmp_path):
    queue = SerialCommandQueue.create(backend='serial', cwd=tmp_path, log=False)
    queue.submit('export XCOOKIE_QUEUE_TEST=works')
    queue.sync().submit('printf "%s" "$XCOOKIE_QUEUE_TEST" > queue-result.txt')

    queue.run()
    assert (tmp_path / 'queue-result.txt').read_text() == 'works'


def test_windows_bash_resolution_prefers_git_bash(monkeypatch):
    git_executable = r'C:\Program Files\Git\cmd\git.exe'
    git_bash = r'C:\Program Files\Git\bin\bash.exe'
    wsl_bash = r'C:\Windows\System32\bash.exe'

    def fake_which(name: str) -> str | None:
        return {'git': git_executable, 'bash': wsl_bash}.get(name)

    monkeypatch.setattr(util_command.sys, 'platform', 'win32')
    monkeypatch.setattr(util_command.shutil, 'which', fake_which)
    monkeypatch.setattr(
        util_command.os.path,
        'isfile',
        lambda path: path == git_bash,
    )
    monkeypatch.delenv('ProgramFiles', raising=False)
    monkeypatch.delenv('ProgramFiles(x86)', raising=False)
    monkeypatch.delenv('LocalAppData', raising=False)

    assert find_bash_executable() == git_bash


def test_windows_bash_resolution_rejects_unconfigured_wsl(monkeypatch):
    wsl_bash = r'C:\Windows\System32\bash.exe'

    def fake_which(name: str) -> str | None:
        return wsl_bash if name == 'bash' else None

    monkeypatch.setattr(util_command.sys, 'platform', 'win32')
    monkeypatch.setattr(util_command.shutil, 'which', fake_which)
    monkeypatch.setattr(util_command.os.path, 'isfile', lambda path: True)
    monkeypatch.delenv('ProgramFiles', raising=False)
    monkeypatch.delenv('ProgramFiles(x86)', raising=False)
    monkeypatch.delenv('LocalAppData', raising=False)

    assert find_bash_executable() is None
