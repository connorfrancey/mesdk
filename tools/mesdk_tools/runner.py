"""Runs CMake/CTest with a progress bar, a full log on disk and a readable error summary."""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console
from rich.markup import escape
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

console = Console(highlight=False)

NINJA_PROGRESS = re.compile(r"^\[(\d+)/(\d+)\]\s*(.*)")
MAKE_PROGRESS = re.compile(r"^\[\s*(\d+)%\]\s*(.*)")
DIAGNOSTIC = re.compile(r"(\berror\b|\bwarning\b|FAILED:|CMake Error|CMake Warning|fatal)", re.IGNORECASE)
ERROR = re.compile(r"(\berror\b|FAILED:|CMake Error|fatal)", re.IGNORECASE)
# GCC/Clang "file:line:col: error:" and MSVC "file(line): error C1234:"
COMPILER_ERROR = re.compile(r"(:\d+(:\d+)?: (fatal )?error:|\(\d+\): (fatal )?error [A-Z]+\d+)")
# Lines that mention "error" without being one (file names, option names...)
NOT_AN_ERROR = re.compile(r"(-Werror|error_|_error|errors?\.(cpp|h|hpp|txt)|0 errors?)", re.IGNORECASE)


@dataclass
class Result:
    returncode: int
    lines: list[str] = field(default_factory=list)
    seconds: float = 0.0

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    def error_excerpt(self, limit: int = 40) -> list[str]:
        """The lines worth showing when the step failed: the first errors plus a little context."""
        # Compiler diagnostics (with the source line and caret below them) beat everything else,
        # including the long compiler command lines Ninja prints after FAILED:
        indices = [i for i, line in enumerate(self.lines) if COMPILER_ERROR.search(line)]
        before, after = 0, 4
        if not indices:
            indices = [i for i, line in enumerate(self.lines) if ERROR.search(line) and not NOT_AN_ERROR.search(line)]
            before, after = 2, 6
        if not indices:
            return self.lines[-limit:]

        keep: list[int] = []
        for i in indices:
            for j in range(max(0, i - before), min(len(self.lines), i + after)):
                if j not in keep:
                    keep.append(j)
            if len(keep) >= limit:
                break

        excerpt: list[str] = []
        previous = None
        for j in keep[:limit]:
            if previous is not None and j != previous + 1:
                excerpt.append("...")
            excerpt.append(self.lines[j])
            previous = j
        return excerpt


def short_description(text: str) -> str:
    """'Building CXX object CMakeFiles/x.dir/long/path/ME_Core_functions.cpp.obj' -> 'Building ME_Core_functions.cpp'"""
    words = text.split()
    if not words:
        return ""
    last = Path(words[-1]).name
    for suffix in (".obj", ".o"):
        last = last.removesuffix(suffix)
    verb = words[0]
    return f"{verb} {last}" if len(words) > 1 else verb


def run(title: str, command: list[str], log: Path, *, verbose: bool = False, env: dict[str, str] | None = None,
        cwd: Path | None = None) -> Result:
    """Runs a command, streaming it to `log`. Shows a progress bar, or the raw output with `verbose`."""
    log.parent.mkdir(parents=True, exist_ok=True)
    full_env = {**os.environ, **(env or {})}
    full_env.setdefault("CLICOLOR_FORCE", "0")
    started = time.monotonic()
    result = Result(returncode=1)

    console.print(f"[bold cyan]==>[/] [bold]{escape(title)}[/]")
    # Paths under the current directory are shown relative, to keep the line short
    shown = shlex.join(command).replace(str(Path.cwd()) + os.sep, "")
    console.print(f"    [dim]$ {escape(shown)}[/]", soft_wrap=True)

    with open(log, "w", encoding="utf-8") as log_file:
        log_file.write(f"$ {shlex.join(command)}\n")
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                       encoding="utf-8", errors="replace", env=full_env, cwd=cwd, bufsize=1)
        except OSError as error:
            result.lines = [f"could not start {command[0]}: {error}"]
            return result

        progress = Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                            BarColumn(bar_width=30), MofNCompleteColumn(), TimeElapsedColumn(),
                            console=console, transient=True, disable=verbose)
        try:
            with progress:
                task = progress.add_task(title, total=None)
                assert process.stdout is not None
                for raw in process.stdout:
                    line = raw.rstrip("\r\n")
                    log_file.write(line + "\n")
                    result.lines.append(line)

                    if verbose:
                        console.print(escape(line))
                        continue

                    if match := NINJA_PROGRESS.match(line):
                        done, total, what = int(match[1]), int(match[2]), match[3]
                        progress.update(task, completed=done, total=total, description=short_description(what) or title)
                    elif match := MAKE_PROGRESS.match(line):
                        progress.update(task, completed=int(match[1]), total=100,
                                        description=short_description(match[2]) or title)
                    elif DIAGNOSTIC.search(line) and not NOT_AN_ERROR.search(line):
                        # Diagnostics are printed above the bar as they happen
                        style = "red" if ERROR.search(line) else "yellow"
                        progress.console.print(f"    [{style}]{escape(line)}[/]")
                result.returncode = process.wait()
        except KeyboardInterrupt:
            process.kill()
            process.wait()
            result.returncode = 130
            raise
        finally:
            result.seconds = time.monotonic() - started

    return result
