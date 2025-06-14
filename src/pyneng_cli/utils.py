from __future__ import annotations

# ────────────── стандартная библиотека ──────────────────────────────────────
import os
import re
import shutil
import stat
import subprocess
import sys
from collections import defaultdict
from collections.abc import Sequence
from itertools import chain
from pathlib import Path
from platform import system as system_name
from shlex import split as sh_split
from typing import Any, Final, Literal, overload  # <-- добавили

# ────────────── сторонние пакеты ────────────────────────────────────────────
import click

# ────────────── внутренние импорты ──────────────────────────────────────────
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

# ────────────── константы ───────────────────────────────────────────────────
ENC: Final[str] = "utf-8"

# ════════════════════════════════════════════════════════════════════════════
#  ЦВЕТНЫЕ ХЕЛПЕРЫ
# ════════════════════════════════════════════════════════════════════════════


def red(text: str) -> str:
    """Вернуть *text* окрашенный в **красный**."""
    return click.style(text, fg="red")


def green(text: str) -> str:
    """Вернуть *text* окрашенный в **зелёный**."""
    return click.style(text, fg="green")


# ════════════════════════════════════════════════════════════════════════════
#  ОБЩИЕ ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ════════════════════════════════════════════════════════════════════════════


def remove_readonly(func: Any, path: str | bytes | os.PathLike, _exc: Any) -> None:
    """Callback для `shutil.rmtree` — снимает readonly-бит и повторяет `func`."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def _to_argv(cmd: str | Sequence[str]) -> list[str]:
    """Преобразовать *cmd* к `list[str]` для `subprocess.run`."""
    return sh_split(cmd) if isinstance(cmd, str) else list(cmd)


# ---------- overload’ы для корректных типов возврата -----------------------


@overload
def call_command(
    command: str | Sequence[str],
    *,
    verbose: bool = True,
    return_output: Literal[True],
    **kwargs: Any,
) -> subprocess.CompletedProcess[str]:
    ...


@overload
def call_command(
    command: str | Sequence[str],
    *,
    verbose: bool = True,
    return_output: Literal[False] = False,
    **kwargs: Any,
) -> int:
    ...


def call_command(  # noqa: D401 (краткое описание)
    command: str | Sequence[str],
    *,
    verbose: bool = True,
    return_output: bool = False,
    **kwargs: Any,
) -> int | subprocess.CompletedProcess[str]:
    """
    Выполнить *command*.

    * Если *verbose* — печатает команду и STDOUT/STDERR.
    * При `return_output=True` возвращается `CompletedProcess`,
      иначе — числовой код возврата.
    """
    argv = _to_argv(command)
    needs_shell = sys.platform.startswith("win") and isinstance(command, str)

    if verbose:
        click.echo("#" * 20 + " " + " ".join(argv))

    result = subprocess.run(  # nosec B603 – аргументы контролируемые
        argv if not needs_shell else command,  # type: ignore[arg-type]
        shell=needs_shell,
        encoding=ENC,
        capture_output=True,
        **kwargs,
    )

    if verbose and result.stdout:
        click.echo(result.stdout.strip())
    if verbose and result.stderr:
        click.echo(red(result.stderr.strip()))

    return result if return_output else result.returncode


# alias для обратной совместимости
run_command = call_command

# ════════════════════════════════════════════════════════════════════════════
#  GIT-ХЕЛПЕРЫ
# ════════════════════════════════════════════════════════════════════════════


def working_dir_clean() -> bool:
    """True, если `git status --porcelain` ничего не выводит."""
    res = call_command(["git", "status", "--porcelain"], return_output=True, verbose=False)
    return not res.stdout


def show_git_diff_short() -> None:
    """Показать краткий diff (`git diff --stat`)."""
    call_command(["git", "diff", "--stat"])


def git_push(branch: str) -> None:
    """`git push origin <branch>`."""
    call_command(["git", "push", "origin", branch])


def save_changes_to_github(
    message: str = "Auto-save",
    *,
    git_add_all: bool = True,
    branch: str = "main",
) -> None:
    """Сохранить изменения `git add/commit/push`."""
    res = call_command(["git", "status", "-s"], return_output=True, verbose=False)
    if not res.stdout:
        return

    if git_add_all:
        call_command(["git", "add", "."])
    call_command(["git", "commit", "-m", message])

    if system_name().lower() == "windows":
        git_push(branch)
    else:
        call_command(["git", "push", "origin", branch])


# ════════════════════════════════════════════════════════════════════════════
#  УТИЛИТЫ ДЛЯ ПУТЕЙ / ГЛАВ
# ════════════════════════════════════════════════════════════════════════════


def current_dir_name() -> str:
    """Имя текущей директории."""
    return Path.cwd().name


def current_chapter_id() -> int:
    """Извлечь номер главы из имени директории (exercises/XX_name)."""
    chapter = current_dir_name()
    chapter = TASK_DIRS[-1] if chapter in DB_TASK_DIRS else chapter
    return int(chapter.split("_")[0])


# ════════════════════════════════════════════════════════════════════════════
#  PARSE PYTEST JSON REPORT
# ════════════════════════════════════════════════════════════════════════════


def parse_json_report(report: dict[str, Any] | None) -> list[str]:
    """Вернуть список тест-файлов, где все тесты прошли."""
    if not (report and report["summary"]["total"]):
        return []

    grouped: defaultdict[str, list[bool]] = defaultdict(list)
    for test in report["tests"]:
        fname = test["nodeid"].split("::")[0]
        grouped[fname].append(test["outcome"] == "passed")

    return [name for name, passed in grouped.items() if all(passed)]


# ════════════════════════════════════════════════════════════════════════════
#  РАБОТА С ОТДАЛЁННЫМИ РЕПО / КОПИРОВАНИЕ ФАЙЛОВ
# ════════════════════════════════════════════════════════════════════════════


def git_clone_repo(repo_url: str, dst_dir: str) -> None:
    """Клонировать *repo_url* в *dst_dir* (depth=1)."""
    res = call_command(
        ["git", "clone", "--depth", "1", repo_url, dst_dir],
        return_output=True,
        verbose=False,
    )
    if res.returncode != 0:
        msg = res.stderr.lower()
        if "could not resolve host" in msg:
            raise PynengError(red("Cannot clone repo: no internet?"))
        raise PynengError(red(f"Git clone failed:\n{res.stderr}"))


# ————— Ответы ————————————————————————————————————————————————


def _copy_answer_files(passed_tests: Sequence[str], dst_dir: Path) -> None:
    """Скопировать `answer_task_X.py` для успешно прошедших тестов."""
    for test_file in passed_tests:
        task_match = re.search(r"task_\w+\.py", test_file)
        ans_name = re.sub(r"^test_", "answer_", test_file)
        ans_match = re.search(r"answer_task_\w+\.py", ans_name)
        if not (task_match and ans_match):
            continue

        task, answer = task_match.group(), ans_match.group()
        if not (dst_dir / answer).exists():
            shutil.copy2(task, dst_dir / answer)


def copy_answers(passed_tests: Sequence[str]) -> None:
    """Скачать и скопировать ответы в текущую папку."""
    cwd = Path.cwd()
    chapter = cwd.name
    answers_repo = Path.home() / "pyneng-answers"
    answers_repo.mkdir(exist_ok=True, parents=True)

    if answers_repo.exists():
        shutil.rmtree(answers_repo, onerror=remove_readonly)
    git_clone_repo(ANSWERS_URL, answers_repo.as_posix())

    os.chdir(answers_repo / "answers" / chapter)
    _copy_answer_files(passed_tests, cwd)
    click.echo(green("Answers copied → answer_task_x.py"))
    os.chdir(Path.home())
    shutil.rmtree(answers_repo, onerror=remove_readonly)
    os.chdir(cwd)


# ————— Обновление основного репозитория задач ————————————————


def _clone_or_pull_task_repo() -> None:
    repo_path = Path.home() / TASKS_LOCAL_REPO
    if repo_path.exists():
        call_command(["git", "-C", repo_path.as_posix(), "pull"], verbose=False)
    else:
        git_clone_repo(TASKS_URL, repo_path.as_posix())


def _copy_task_test_files(
    dst: Path,
    tasks: Sequence[str] | None = None,
    tests: Sequence[str] | None = None,
) -> None:
    """Скопировать указанные файлы задач/тестов в *dst*."""
    for fname in chain(tasks or [], tests or []):
        shutil.copy2(fname, dst / fname)


def copy_tasks_tests_from_repo(tasks: Sequence[str], tests: Sequence[str]) -> None:
    """Высокоуровневый фасад для CLI."""
    cwd = Path.cwd()
    chapter = cwd.name

    _clone_or_pull_task_repo()
    src = Path.home() / TASKS_LOCAL_REPO / "exercises" / chapter
    os.chdir(src)

    _copy_task_test_files(cwd, tasks, tests)
    click.echo(green("Tasks/tests updated"))
    os.chdir(cwd)


# ════════════════════════════════════════════════════════════════════════════
#  ПАКЕТНЫЕ ОПЕРАЦИИ (UPDATE / SAVE)
# ════════════════════════════════════════════════════════════════════════════


def save_working_dir(branch: str = "main") -> None:
    """Сохранить изменения, если есть, перед обновлением."""
    if working_dir_clean():
        return
    click.echo(red("Unsaved changes detected!"))
    if input(red("Save them? [y/N]: ")).strip().lower() in {"y", "yes"}:
        save_changes_to_github(branch=branch)


def working_dir_changed_diff(branch: str = "main") -> None:
    """Показать diff и предложить сохранить после обновления."""
    click.echo(red("Following files changed:"))
    show_git_diff_short()
    if input(red("Commit & push? [y/N]: ")).strip().lower() in {"y", "yes"}:
        save_changes_to_github("Update tasks/tests", branch=branch)


# ————— Переключение языка репозитория задач ————————————————


def _change_tasks_lang(lang: str) -> None:
    global TASKS_URL, TASKS_LOCAL_REPO
    TASKS_URL = LANG_TASKS_URL.get(lang, TASKS_URL)
    TASKS_LOCAL_REPO = LANG_TASKS_LOCAL_REPO.get(lang, TASKS_LOCAL_REPO)


def update_tasks_and_tests(
    tasks: Sequence[str],
    tests: Sequence[str],
    lang: str,
    branch: str = "main",
) -> bool:
    """Обновить выбранные задачи/тесты; вернуть True, если что-то изменилось."""
    _change_tasks_lang(lang)
    save_working_dir(branch)
    copy_tasks_tests_from_repo(tasks, tests)
    if working_dir_clean():
        click.echo(green("Tasks/tests already up-to-date"))
        return False
    working_dir_changed_diff(branch)
    return True


# ————— Обновление целых глав ————————————————————————————————


def _copy_chapters(dst_root: Path, chapters: Sequence[str]) -> None:
    for chapter in chapters:
        dst = dst_root / chapter
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(chapter, dst)


def copy_chapters_from_repo(chapters: Sequence[str]) -> None:
    cwd = Path.cwd()
    _clone_or_pull_task_repo()

    src = Path.home() / TASKS_LOCAL_REPO / "exercises"
    os.chdir(src)
    _copy_chapters(cwd, chapters)
    click.echo(green("Chapters updated"))
    os.chdir(cwd)


def update_chapters_tasks_and_tests(
    chapters: Sequence[str],
    lang: str,
    branch: str = "main",
) -> bool:
    """Обновить указанные главы полностью."""
    _change_tasks_lang(lang)
    save_working_dir(branch)
    copy_chapters_from_repo(chapters)
    if working_dir_clean():
        click.echo(green("Chapters already up-to-date"))
        return False
    working_dir_changed_diff(branch)
    return True
