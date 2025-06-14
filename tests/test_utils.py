from pyneng_cli.utils import run_command


def test_run_command_echo():
    """run_command має повернути stdout shell-команди."""
    out = run_command("echo 123", return_stdout=True)
    assert "123" in out
