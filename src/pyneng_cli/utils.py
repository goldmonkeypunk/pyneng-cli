from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import sys
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path
from platform import system as system_name
from shlex import split as sh_split
from typing import Literal, overload

import click

from pyneng_cli import (
    ANSWERS_URL,
    DB_TASK_DIRS,
    LANG_TASKS_LOCAL_REPO,
    LANG_TASKS_URL,
    TASK_DIRS,
    TASKS_LOCAL_REPO,
    TASKS_URL,
)
from pyneng_cli.exceptions import PynengError

# --------------------------------------------------------------------------- #
#  Цветовые «прикраси»
# --------------------------------------------------------------------------- #


def red(msg: str) -> str:
    """Вернуть строку, окрашенную в **красный**."""
    return click.style(msg, fg="red")


def green(msg: str) -> str:
    """Вернуть строку, окрашенную в **зелёный**."""
    return click.style(msg, fg="green")


# --------------------------------------------------------------------------- #
#  Вспомогательные утилиты
# --------------------------------------------------------------------------- #


def remove_readonly(func, path, _):
    """
    Windows-хак: позволяет ``shutil.rmtree`` удалять read-only файлы
    (например, внутри .git).
    """
    os.chmod(path, stat.S_IWRITE)
    func(path)


def _to_argv(command: str | Sequence[str]) -> list[str]:
    """
    Гарантировать, что в ``subprocess`` пойдёт *list[str]*.

    * str  → ``shlex.split``
    * list/tuple → оставить как есть
    """
    return sh_split(command) if isinstance(command, str) else list(command)


# ======== перегрузки для mypy =================================================


@overload
def call_command(
    command: str | Sequence[str],
    *,
    verbose: bool = ...,
    return_stdout: Literal[True],
    return_stderr: Literal[False] = ...,
) -> str:  # только stdout
    ...


@overload
def call_command(
    command: str | Sequence[str],
    *,
    verbose: bool = ...,
    return_stdout: Literal[False] = ...,
    return_stderr: Literal[True],
) -> tuple[int, str]:  # returncode + stderr
    ...


@overload
def call_command(
    command: str | Sequence[str],
    *,
    verbose: bool = ...,
    return_stdout: Literal[False] = ...,
    return_stderr: Literal[False] = ...,
) -> int:  # только код возврата
    ...


# ======== реализация =========================================================


def call_command(
    command: str | Sequence[str],
    *,
    verbose: bool = True,
    return_stdout: bool = False,
    return_stderr: bool = False,
) -> int | str | tuple[int, str]:
    """
    Выполнить *command* через :pyfunc:`subprocess.run`.

    На Windows бат/cmd-файлы требуют ``shell=True`` (ловим это вручную),
    на остальных ОС работаем без оболочки (избегаем Bandit B602).
    """
    argv: list[str] = _to_argv(command)
    needs_shell = sys.platform.startswith("win") and isinstance(command, str)

    completed: subprocess.CompletedProcess[str] = subprocess.run(  # nosec B603
        argv if not needs_shell else command,  # type: ignore[arg-type]
        shell=needs_shell,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if return_stdout:
        return completed.stdout
    if return_stderr:
        return completed.returncode, completed.stderr

    if verbose:
        print("#" * 20, command)
        if completed.stdout:
            print(completed.stdout)
        if completed.stderr:
            print(completed.stderr)

    return completed.returncode


# обратная совместимость
run_command = call_command  # type: ignore[assignment]

# --------------------------------------------------------------------------- #
#  Git-хелперы
# --------------------------------------------------------------------------- #


def working_dir_clean() -> bool:
    """True, если «чистый» ``git status --porcelain``."""
    return not call_command("git status --porcelain", return_stdout=True)


def show_git_diff_short() -> None:
    call_command("git diff --stat")


def git_push(branch: str) -> None:
    """Упрощённая обёртка над ``git push origin <branch>``."""
    command = f"git push origin {branch}"
    print("#" * 20, command)
    subprocess.run(_to_argv(command))


def save_changes_to_github(
    message: str = "All changes saved",
    *,
    git_add_all: bool = True,
    branch: str = "main",
) -> None:
    """Сделать ``git add/commit/push`` одним вызовом."""
    status = call_command("git status -s", return_stdout=True)
    if not status:
        return

    if git_add_all:
        call_command("git add .")
    call_command(f'git commit -m "{message}"')

    if system_name().lower() == "windows":
        git_push(branch)
    else:
        call_command(f"git push origin {branch}")


# --------------------------------------------------------------------------- #
#  Главо-/путь-утилиты
# --------------------------------------------------------------------------- #


def current_dir_name() -> str:
    return Path().absolute().name


def current_chapter_id() -> int:
    """Номер текущей главы-директории (exercises/XX_name)."""
    chapter = current_dir_name()
    if chapter in DB_TASK_DIRS:
        chapter = TASK_DIRS[-1]
    return int(chapter.split("_")[0])


# --------------------------------------------------------------------------- #
#  PyTest JSON-report
# --------------------------------------------------------------------------- #


def parse_json_report(report):  # type: ignore[override]
    """
    Преобразовать dict от ``pytest-json-report`` → список успешно пройденных тестов.
    """
    if report and report["summary"]["total"]:
        grouped: defaultdict[str, list[bool]] = defaultdict(list)
        for test in report["tests"]:
            fname = test["nodeid"].split("::")[0]
            grouped[fname].append(test["outcome"] == "passed")
        return [name for name, ok in grouped.items() if all(ok)]
    return []


# --------------------------------------------------------------------------- #
#  Работа с удалёнными репо / копирование файлов
# --------------------------------------------------------------------------- #


def git_clone_repo(repo_url: str, dst_dir: str) -> None:
    rc, err = call_command(
        ["git", "clone", repo_url, dst_dir],
        verbose=False,
        return_stderr=True,
    )
    if rc != 0:
        if "could not resolve host" in err.lower():
            raise PynengError(red("Failed to clone the repository. No internet?"))
        raise PynengError(red(f"Failed to copy files. {err}"))


def copy_answer_files(passed_tests: Sequence[str], dst_dir: Path) -> None:
    for test_file in passed_tests:
        task_match = re.search(r"task_\w+\.py", test_file)
        ans_match = re.search(
            r"answer_task_\w+\.py", test_file.replace("test_", "answer_")
        )
        if not (task_match and ans_match):
            continue
        task = task_match.group()
        answer = ans_match.group()
        if not (dst_dir / answer).exists():
            shutil.copy2(task, dst_dir / answer)


def copy_answers(passed_tests: Sequence[str]) -> None:
    """
    Скопировать ответы для *успешных* тестов в текущую директорию.
    """
    cwd = Path().absolute()
    chapter = cwd.name
    answers_repo = Path.home() / "pyneng-answers"
    answers_repo.parent.mkdir(exist_ok=True)

    if answers_repo.exists():
        shutil.rmtree(answers_repo, onerror=remove_readonly)
    git_clone_repo(ANSWERS_URL, str(answers_repo))

    os.chdir(answers_repo / "answers" / chapter)
    copy_answer_files(passed_tests, cwd)
    print(green("\nAnswers copied to answer_task_x.py\n"))
    os.chdir(Path.home())
    shutil.rmtree(answers_repo, onerror=remove_readonly)
    os.chdir(cwd)


# --------------------------------------------------------------------------- #
#  Обновление репо заданий
# --------------------------------------------------------------------------- #


def clone_or_pull_task_repo() -> None:
    cwd = Path().absolute()
    home = Path.home()
    repo_path = home / TASKS_LOCAL_REPO

    os.chdir(home)
    if repo_path.exists():
        os.chdir(repo_path)
        call_command(["git", "pull"])
    else:
        git_clone_repo(TASKS_URL, TASKS_LOCAL_REPO)
    os.chdir(cwd)


def copy_task_test_files(
    dst: Path,
    tasks: Sequence[str] | None = None,
    tests: Sequence[str] | None = None,
) -> None:
    for fname in list(tasks or []) + list(tests or []):
        shutil.copy2(fname, dst / fname)


def copy_tasks_tests_from_repo(tasks: Sequence[str], tests: Sequence[str]) -> None:
    cwd = Path().absolute()
    chapter = cwd.name
    clone_or_pull_task_repo()

    src = Path.home() / TASKS_LOCAL_REPO / "exercises" / chapter
    os.chdir(src)
    copy_task_test_files(cwd, tasks, tests)
    print(green("\nUpdated tasks and tests copied"))
    os.chdir(cwd)


# --------------------------------------------------------------------------- #
#  Пакетные обновления / сохранение рабочего каталога
# --------------------------------------------------------------------------- #


def save_working_dir(branch: str = "main") -> None:
    if working_dir_clean():
        return
    print(red("Unsaved changes detected!"))
    if input(red("Save them? [y/N]: ")).strip().lower() in ("y", "yes"):
        save_changes_to_github("Auto-save before update", branch=branch)


def working_dir_changed_diff(branch: str = "main") -> None:
    print(red("The following files have been updated:"))
    show_git_diff_short()
    if input(red("\nCommit & push these changes? [y/N]: ")).strip().lower() in (
        "y",
        "yes",
    ):
        save_changes_to_github("Update tasks/tests", branch=branch)


def change_tasks_lang(lang: str) -> None:
    global TASKS_URL, TASKS_LOCAL_REPO
    TASKS_URL = LANG_TASKS_URL.get(lang, TASKS_URL)
    TASKS_LOCAL_REPO = LANG_TASKS_LOCAL_REPO.get(lang, TASKS_LOCAL_REPO)


def update_tasks_and_tests(
    tasks: Sequence[str],
    tests: Sequence[str],
    lang: str,
    branch: str = "main",
) -> bool:
    change_tasks_lang(lang)
    save_working_dir(branch)
    copy_tasks_tests_from_repo(tasks, tests)
    if working_dir_clean():
        print(green("Tasks and tests already up-to-date"))
        return False
    working_dir_changed_diff(branch)
    return True


# --------------------------------------------------------------------------- #
#  Обновление целых глав
# --------------------------------------------------------------------------- #


def copy_chapters(dst_root: Path, chapters: Sequence[str]) -> None:
    for chapter in chapters:
        dst = dst_root / chapter
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(chapter, dst)


def copy_chapters_from_repo(chapters: Sequence[str]) -> None:
    cwd = Path().absolute()
    clone_or_pull_task_repo()

    src = Path.home() / TASKS_LOCAL_REPO / "exercises"
    os.chdir(src)
    copy_chapters(cwd, chapters)
    print(green("\nUpdated chapters copied"))
    os.chdir(cwd)


def update_chapters_tasks_and_tests(
    chapters: Sequence[str],
    lang: str,
    branch: str = "main",
) -> bool:
    change_tasks_lang(lang)
    save_working_dir(branch)
    copy_chapters_from_repo(chapters)
    if working_dir_clean():
        print(green("All chapters are up-to-date"))
        return False
    working_dir_changed_diff(branch)
    return True
