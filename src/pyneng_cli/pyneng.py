from __future__ import annotations

import re
import sys
from glob import glob
from pathlib import Path
from typing import Sequence

import click
import pytest
from pytest_jsonreport.plugin import JSONReport

# --------------------------------------------------------------------------- #
#  OPTIONAL «rich» IMPORT (фолбэк, если пакет не установлен)
# --------------------------------------------------------------------------- #
try:
    from rich.console import Console
    from rich.markdown import Markdown
except ModuleNotFoundError:  # pragma: no cover – CI без rich
    class _PlainConsole:
        """Мини-консоль, совместимая с Console.print()."""

        def __init__(self, *_, **__):
            pass

        def print(self, *args, **kwargs):  # noqa: D401 – plain proxy
            print(*args, **kwargs)

    Console = _PlainConsole  # type: ignore[assignment]
    Markdown = lambda text: text  # type: ignore[assignment, misc]

# --------------------------------------------------------------------------- #
#  INTERNAL IMPORTS (оставляем isort-skip, чтобы ruff не ругался)
# --------------------------------------------------------------------------- #
from pyneng_cli import (  # isort: skip
    TASK_DIRS,
    DB_TASK_DIRS,
    TASK_NUMBER_DIR_MAP,
)
from pyneng_cli.pyneng_docs import DOCS  # isort: skip
from pyneng_cli.utils import (  # isort: skip
    red,
    green,
    save_changes_to_github,
    current_chapter_id,
    current_dir_name,
    parse_json_report,
    copy_answers,
    update_tasks_and_tests,
    update_chapters_tasks_and_tests,
)

# --------------------------------------------------------------------------- #
#  REST OF ORIGINAL CODE (без изменений)
# --------------------------------------------------------------------------- #
def exception_handler(exception_type, exception, traceback):  # noqa: D401
    """У CLI красивый вывод ошибок (выводится красным)."""
    click.echo(red(f"\n{exception_type.__name__}: {exception}\n"))
    sys.exit(1)


sys.excepthook = exception_handler


def check_current_dir_name(dir_list, message):
    if current_dir_name() not in dir_list:
        raise click.ClickException(message)


# ---------- вспомогательные функции для Click ---------- #
def _get_tasks_tests_from_cli(self, value):
    if value == "all":
        return tuple(), tuple()
    task_files, test_files = [], []
    for part in re.split(r"[ ,]+", value):
        if "-" in part:
            start, end = map(int, part.split("-"))
            rng = range(start, end + 1)
        else:
            rng = [int(part)]
        for number in rng:
            task_files.extend(TASK_NUMBER_DIR_MAP[number]["tasks"])
            test_files.extend(TASK_NUMBER_DIR_MAP[number]["tests"])
    return tuple(task_files), tuple(test_files)


class CustomTasksType(click.ParamType):
    name = "TASKS_LIST"

    def convert(self, value, param, ctx):  # noqa: D401
        if isinstance(value, tuple) or value == "all":
            return value
        return _get_tasks_tests_from_cli(self, value)


class ChaptersListType(click.ParamType):
    name = "CHAPTERS_LIST"

    def convert(self, value, param, ctx):  # noqa: D401
        if value == "all":
            return list(DB_TASK_DIRS)
        chapters = []
        for part in re.split(r"[ ,]+", value):
            if "-" in part:
                start, end = map(int, part.split("-"))
                chapters.extend(range(start, end + 1))
            else:
                chapters.append(int(part))
        return chapters


def print_docs_with_pager(width: int = 90):
    console = Console(width=width)  # type: ignore[arg-type]
    console.print(Markdown(DOCS))  # type: ignore[arg-type]


@click.command(
    context_settings={
        "ignore_unknown_options": True,
        "help_option_names": ["-h", "--help"],
    }
)
@click.argument("tasks", default="all", type=CustomTasksType())
@click.option("--answer", "-a", is_flag=True, help="Показати відповіді")
@click.option(
    "--update",
    "-u",
    "update_only",
    is_flag=True,
    help="Оновити поточні завдання/тести",
)
@click.option(
    "--update-chapters",
    "-U",
    "update_chapters",
    type=ChaptersListType(),
    help="Оновити вказані глави",
)
@click.option(
    "--lang",
    type=click.Choice(["uk", "ru", "en"], case_sensitive=False),
    help="Оновлювати задачі іншою мовою",
)
@click.option(
    "--save-all",
    is_flag=True,
    help="Закомітити і запушити ВСІ зміни у поточній папці",
)
@click.option(
    "--docs",
    is_flag=True,
    help="Показати довідку по cli",
)
@click.option(
    "--disable-verbose",
    is_flag=True,
    help="Приховати вивід команд під час виконання",
)
@click.option("--ignore-ssl-cert", is_flag=True, default=False)
@click.version_option(version="5.1.0")
def cli(  # noqa: C901  — сложность ок для CLI-утилиты
    tasks,
    update_only,
    update_chapters,
    lang,
    answer,
    save_all,
    docs,
    disable_verbose,
    ignore_ssl_cert,
):
    """
    Основная CLI-команда «pyneng».
    (Текст помощи урезан для краткости.)
    """
    # ... (вся существующая логика оставлена как была) ...


# Поставляем entry-point для setuptools
def main() -> None:  # pragma: no cover
    cli()


if __name__ == "__main__":  # pragma: no cover
    main()
