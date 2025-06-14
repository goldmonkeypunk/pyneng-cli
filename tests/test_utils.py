"""Перевіряємо базову функцію запуску shell‑команд."""

from pyneng_cli.utils import call_command


def test_call_command_echo():
    """echo 123 має повернути 123 у stdout і exit‑код 0."""
    out = call_command("echo 123", return_stdout=True)
    assert out.strip() == "123"
