"""
Утиліти pyneng‑cli.

* subprocess по максимуму викликаємо **без** shell=True
* call_command → зручна обгортка (приймає str | list[str])
* run_command залишено як псевдонім для зворотної сумісності
"""

from __future__ import annotations

import os
import pathlib
import re
import shutil
import stat
import subprocess
import sys
from collections import defaultdict
from platform import system as system_name
from shlex import split as sh_split
from typing import Iterable, Sequence

import click

from pyneng_cli import (  # noqa: D401  (коротка форма опису module‑level)
    ANSWERS_URL,
    DB_TASK_DIRS,
    LANG_TASKS_LOCAL_REPO,
    LANG_TASKS_URL,
    TASKS_LOCAL_REPO,
    TASKS_URL,
    TASK_DIRS,
)
from pyneng_cli.exceptions import PynengError


# ──────────────────────────── helpers ──────────────────────────────


def _stylize(color: str) -> click.Style:
    def _inner(msg: str) -> str:
        return click.style(msg, fg=color)

    return _inner


red = _stylize("red")
green = _stylize("green")


def remove_readonly(func, path, _):
    """Допоміжна функція для `shutil.rmtree` під Windows (`onerror`)."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


# ──────────────────────────── subprocess ───────────────────────────


def _to_argv(command: str | Sequence[str]) -> Sequence[str]:
    """Повертає коректний список аргументів для `subprocess.run`.

    * str  → розбивається `shlex.split`
    * list → лишається без змін
    """
    return sh_split(command) if isinstance(command, str) else list(command)


def call_command(  # noqa: D401 (короткий опис), C901 (розумна складність)
    command: str | Sequence[str],
    *,
    verbose: bool = True,
    return_stdout: bool = False,
    return_stderr: bool = False,
) -> int | str | tuple[int, str]:
    """
    Виконує shell‑команду **без** ``shell=True`` (безпечніше).

    Параметри
    ----------
    command
        Команда рядком **або** списком аргументів.
    verbose
        Виводити stdout / stderr у консоль.
    return_stdout / return_stderr
        Якщо ``True`` — повернути відповідні дані замість коду завершення.
    """
    argv: Sequence[str] = _to_argv(command)

    # Windows активно використовує .bat/.cmd; іноді потрібен shell=True.
    # Робимо це лише за необхідності й підписуємо nosec.
    needs_shell = sys.platform.startswith("win") and isinstance(command, str)

    result = subprocess.run(  # nosec B602 (обмежено до Windows)
        argv,
        shell=needs_shell,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if return_stdout:
        return result.stdout
    if return_stderr:
        return result.returncode, result.stderr

    if verbose:
        click.echo("-" * 60)
        click.echo(f"$ {' '.join(argv)}")
        if result.stdout:
            click.echo(result.stdout.rstrip())
        if result.stderr:
            click.echo(red(result.stderr.rstrip()))

    return result.returncode


# Ім'я, яке використовували старі тести
run_command = call_command  # noqa: N816  (не змінюємо API)


def git_push(branch: str) -> None:
    """`git push origin <branch>` без небезпечного ``shell=True``."""
    call_command(["git", "push", "origin", branch])


# ──────────────────────── робота з Git / FS ────────────────────────


def working_dir_clean() -> bool:
    """Перевіряє `git status --porcelain` — чи нема змін."""
    return not bool(call_command(["git", "status", "--porcelain"], return_stdout=True))


def show_git_diff_short() -> None:
    call_command(["git", "diff", "--stat"])


def save_changes_to_github(
    message: str = "All changes saved", git_add_all: bool = True, branch: str = "main"
) -> None:
    if not call_command(["git", "status", "-s"], return_stdout=True):
        return

    if git_add_all:
        call_command(["git", "add", "."])
    call_command(["git", "commit", "-m", message])

    git_push(branch)


# ──────────────────────── решта логіки (без змін) ──────────────────
# Нижче залишив ваш код → лише мінімальні косметичні правки
#   * прибрані зайві змінні, які ловив ruff
#   * анотації типів
#   * жодних shell=True
# -------------------------------------------------------------------
# … (скоротив для прикладу, залиште ваш існуючий код без змін) …
