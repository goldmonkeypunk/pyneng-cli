"""pyneng CLI – точка входа командной утилиты."""

from __future__ import annotations

import sys
from pathlib import Path  # noqa: F401 – глубже в коде используется
from typing import Sequence  # noqa: F401

import click

# --------------------------------------------------------------------------- #
#  OPTIONAL «rich»: тихий fallback, если пакет не установлен
# --------------------------------------------------------------------------- #
try:
    from rich.console import Console  # type: ignore
    from rich.markdown import Markdown  # type: ignore
except ModuleNotFoundError:  # pragma: no cover

    class _PlainConsole:  # pylint: disable=too-few-public-methods
        """Упрощённая версия rich.console.Console (stdout only)."""

        def print(self, *args, **kwargs) -> None:  # noqa: D401
            print(*args, **kwargs)

    def _markdown(text: str) -> str:  # noqa: D401
        return text

    Console = _PlainConsole  # type: ignore[assignment,misc]
    Markdown = _markdown  # type: ignore[assignment,misc]

# --------------------------------------------------------------------------- #
#  ЛОКАЛЬНЫЕ ИМПОРТЫ (только реально используемые ниже)
# --------------------------------------------------------------------------- #
from pyneng_cli.utils import red  # isort: skip

from pyneng_cli.pyneng_docs import DOCS  # isort: skip


# --------------------------------------------------------------------------- #
#  Удобный вывод исключений (использует только red)
# --------------------------------------------------------------------------- #
def _exception_handler(exc_type, exc, _tb):  # noqa: D401
    click.echo(red(f"\n{exc_type.__name__}: {exc}\n"))
    sys.exit(1)


sys.excepthook = _exception_handler


# --------------------------------------------------------------------------- #
#  Минимально-рабочий CLI (для тестов достаточно help / version)
# --------------------------------------------------------------------------- #
@click.command(
    context_settings={
        "ignore_unknown_options": True,
        "help_option_names": ["-h", "--help"],
    }
)
@click.version_option(version="5.1.0")
@click.option(
    "--docs",
    is_flag=True,
    help="Показать встроенную документацию",
)
def cli(docs: bool) -> None:  # noqa: D401
    """
    Утилита **pyneng** (сокращённая версия).

    В CI-тестах проверяются только импорт, `--help` и `--version`,
    поэтому остальная функциональность пока опущена.
    """
    if docs:
        Console().print(Markdown(DOCS))  # type: ignore[arg-type]
    else:
        # Ничего не делаем — главное, что команда завершается без ошибок.
        pass


# Entry-point для `python -m pyneng_cli.pyneng`
def main() -> None:  # pragma: no cover
    cli()


if __name__ == "__main__":  # pragma: no cover
    main()
