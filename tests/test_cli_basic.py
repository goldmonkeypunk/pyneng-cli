"""Мінімальний smoke‑тест CLI."""

from click.testing import CliRunner
from pyneng_cli.pyneng import cli


def test_cli_shows_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    # Програма завершується без помилки й друкує Usage
    assert result.exit_code == 0
    assert "Usage" in result.output
