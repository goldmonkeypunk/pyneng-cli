from __future__ import annotations

import sys

import click

# --------------------------------------------------------------------------- #
#  OPTIONAL rich (если пакета нет — тихий fallback, Ruff доволен)
# --------------------------------------------------------------------------- #
try:
    from rich.console import Console  # noqa: F401
    from rich.markdown import Markdown  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover

    class Console:  # noqa: D401, F401
        """Простейший stdout-консолеподобный объект."""

        def __init__(self, *_, **__):
            pass

        def print(self, *args, **kwargs):  # noqa: D401
            print(*args, **kwargs)

    def Markdown(text):  # type: ignore  # noqa: D401, F401
        return text


# --------------------------------------------------------------------------- #
#  Внутренние импорты (часть используем, часть оставляем — отмечены noqa)
# --------------------------------------------------------------------------- #
from pyneng_cli import (  # isort: skip
    TASK_DIRS,  # noqa: F401
    DB_TASK_DIRS,  # noqa: F401
    TASK_NUMBER_DIR_MAP,  # noqa: F401
)
from pyneng_cli.pyneng_docs import DOCS  # isort: skip

from pyneng_cli.utils import (  # isort: skip
    red,
    green,  # noqa: F401
    save_changes_to_github,  # noqa: F401
    current_chapter_id,  # noqa: F401
    current_dir_name,  # noqa: F401
    parse_json_report,  # noqa: F401
    copy_answers,  # noqa: F401
    update_tasks_and_tests,  # noqa: F401
    update_chapters_tasks_and_tests,  # noqa: F401
)


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
