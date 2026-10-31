"""mesdk command line: `uv run mesdk build | test | clean | install | doctor`."""

from __future__ import annotations

import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import click
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from mesdk_tools import __version__
from mesdk_tools.project import (
    BUILD_ROOT,
    IS_WINDOWS,
    ROOT,
    Check,
    Target,
    all_checks,
    build_checks,
    check_wine,
)
from mesdk_tools.runner import Result, console, run


class StepFailed(Exception):
    def __init__(self, message: str, result: Result | None = None, log: Path | None = None):
        super().__init__(message)
        self.result = result
        self.log = log


def finish_ok(title: str, details: list[str] | None = None) -> None:
    body = "\n".join(details or [])
    console.print(Panel(body or "Done.", title=f"[bold green]{title}[/]", border_style="green", expand=False))


def report_failure(banner: str, error: StepFailed) -> None:
    lines = [f"[bold]{escape(str(error))}[/]"]
    if error.result and error.result.lines:
        lines += ["", *(f"[red]{escape(line)}[/]" for line in error.result.error_excerpt())]
    if error.log:
        lines += ["", f"[dim]Full log: {escape(str(error.log))}[/]"]
    console.print(Panel("\n".join(lines), title=f"[bold red]{banner}[/]", border_style="red", expand=False))


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def require(checks: list[Check]) -> None:
    missing = [check for check in checks if check.required and not check.found]
    if missing:
        names = ", ".join(check.name for check in missing)
        hints = "; ".join(f"{check.name}: {check.hint}" for check in missing if check.hint)
        raise StepFailed(f"Missing prerequisites: {names}. {hints}")


def make_target(debug: bool, mingw: bool) -> Target:
    # Off Windows, MinGW is the only option, so --mingw changes nothing there
    return Target(config="Debug" if debug else "Release", msvc=IS_WINDOWS and not mingw)


# --------------------------------------------------------------------------------------------------
# Steps


def configure(target: Target, defines: tuple[str, ...], verbose: bool) -> None:
    log = target.build_dir / "logs" / "configure.log"
    command = ["cmake", "-S", str(ROOT), "-B", str(target.build_dir), *target.configure_args(),
               *(f"-D{define}" for define in defines)]
    result = run(f"Configuring ({target.description})", command, log, verbose=verbose)
    if not result.ok:
        hint = " If you changed generator or toolchain, try again with --clean."
        raise StepFailed("CMake configure failed." + hint, result, log)
    console.print(f"    [green]✓[/] configured in {result.seconds:.1f}s")


def compile_(target: Target, jobs: int | None, verbose: bool, cmake_target: str | None = None) -> None:
    log = target.build_dir / "logs" / "build.log"
    command = ["cmake", "--build", str(target.build_dir), *target.config_args(), "--parallel"]
    if jobs:
        command.append(str(jobs))
    if cmake_target:
        command += ["--target", cmake_target]
    title = "Building" + (f" {cmake_target}" if cmake_target else "")
    if not any(target.build_dir.glob("*mesdk_sdk*")):
        title += " (the first build compiles the whole SDK, this takes a few minutes)"
    result = run(title, command, log, verbose=verbose)
    if not result.ok:
        raise StepFailed("Compilation failed.", result, log)
    console.print(f"    [green]✓[/] built in {result.seconds:.1f}s")


def build_target(target: Target, *, clean: bool, jobs: int | None, defines: tuple[str, ...], verbose: bool) -> None:
    require(build_checks(target))
    if clean:
        remove(target.build_dir)
    configure(target, defines, verbose)
    compile_(target, jobs, verbose)


def remove(path: Path) -> bool:
    if not path.exists():
        return False
    console.print(f"[bold cyan]==>[/] [bold]Removing {escape(relative(path))}[/]")
    try:
        shutil.rmtree(path)
    except OSError as error:
        raise StepFailed(f"Could not remove {path}: {error}") from error
    return True


def outputs(target: Target) -> list[str]:
    patterns = ["**/*mesdk*.a", "**/*mesdk*.lib", "examples/**/*.dll"]
    found = sorted({path for pattern in patterns for path in target.build_dir.glob(pattern)
                    if "CMakeFiles" not in path.parts and "_deps" not in path.parts})
    return [relative(path) for path in found]


def parse_junit(path: Path) -> list[tuple[str, str, float, str]]:
    """(name, status, seconds, output) for every test case in CTest's JUnit report."""
    if not path.exists():
        return []
    cases = []
    for case in ET.parse(path).getroot().iter("testcase"):
        status = case.get("status", "run")
        if case.find("failure") is not None or status == "fail":
            status = "failed"
        elif case.find("skipped") is not None or status in ("notrun", "disabled"):
            status = "skipped"
        else:
            status = "passed"
        output = (case.findtext("system-out") or "").strip()
        cases.append((case.get("name", "?"), status, float(case.get("time", 0) or 0), output))
    return cases


# --------------------------------------------------------------------------------------------------
# Commands

common_options = [
    click.option("-d", "--debug", is_flag=True, help="Debug configuration (default: Release)."),
    click.option("--mingw", is_flag=True, help="Windows only: build with MinGW-w64 from PATH instead of Visual Studio."),
    click.option("-v", "--verbose", is_flag=True, help="Show the raw CMake/compiler output instead of a progress bar."),
]


def with_common_options(function):
    for option in reversed(common_options):
        function = option(function)
    return function


def guarded(banner: str):
    """Turns StepFailed / Ctrl+C into a red summary panel and a non-zero exit code."""

    def decorator(function):
        def wrapper(*args, **kwargs):
            try:
                return function(*args, **kwargs)
            except StepFailed as error:
                report_failure(banner, error)
                sys.exit(1)
            except KeyboardInterrupt:
                console.print("\n[bold red]Interrupted[/]")
                sys.exit(130)

        wrapper.__name__ = function.__name__
        wrapper.__doc__ = function.__doc__
        return wrapper

    return decorator


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="mesdk")
def main() -> None:
    """Build, test and clean the mesdk C++ project.

    Mirror's Edge is a 32-bit Windows game, so mesdk is built with MinGW-w64 i686 (cross-compiled on
    Linux/macOS) or Visual Studio Win32 on Windows. Build directories match build.sh / build.bat and
    the CMake presets (build/mingw-release, build/mingw-debug, build/msvc-x86).
    """


@main.command()
@with_common_options
@click.option("-c", "--clean", is_flag=True, help="Delete the build directory first.")
@click.option("-j", "--jobs", type=click.IntRange(min=1), help="Parallel build jobs (default: all cores).")
@click.option("-D", "defines", multiple=True, metavar="VAR=VALUE", help="Extra CMake cache variable, e.g. -D MESDK_BUILD_SDK_DOCS=ON.")
@guarded("BUILD FAILED")
def build(debug: bool, mingw: bool, verbose: bool, clean: bool, jobs: int | None, defines: tuple[str, ...]) -> None:
    """Configure and build the library, examples and tests."""
    target = make_target(debug, mingw)
    build_target(target, clean=clean, jobs=jobs, defines=defines, verbose=verbose)
    finish_ok("BUILD SUCCEEDED", [f"[bold]{target.description}[/] in {relative(target.build_dir)}", "",
                                  *(f"• {path}" for path in outputs(target))])


@main.command()
@with_common_options
@click.option("-R", "--regex", help="Only run tests whose name matches this regular expression.")
@click.option("-n", "--no-build", is_flag=True, help="Don't build first; test the existing build.")
@guarded("TESTS FAILED")
def test(debug: bool, mingw: bool, verbose: bool, regex: str | None, no_build: bool) -> None:
    """Build (incrementally) and run the tests. On Linux/macOS they run through Wine."""
    target = make_target(debug, mingw)

    if not target.msvc and not IS_WINDOWS:
        wine = check_wine()
        if not wine.found:
            raise StepFailed(f"Wine is needed to run the Windows test executables: {wine.hint}")

    if no_build:
        if not (target.build_dir / "CMakeCache.txt").exists():
            raise StepFailed(f"No build in {relative(target.build_dir)}. Run without --no-build, or `mesdk build` first.")
    else:
        build_target(target, clean=False, jobs=None, defines=(), verbose=verbose)

    cache = (target.build_dir / "CMakeCache.txt").read_text(encoding="utf-8", errors="replace")
    if "MESDK_BUILD_TESTS:BOOL=ON" not in cache:
        raise StepFailed(f"{relative(target.build_dir)} was configured with MESDK_BUILD_TESTS=OFF. Rebuild with `mesdk build --clean`.")

    junit = target.build_dir / "logs" / "tests.xml"
    junit.unlink(missing_ok=True)
    log = target.build_dir / "logs" / "tests.log"
    command = ["ctest", "--test-dir", str(target.build_dir), *(["-C", target.config] if target.multi_config else []),
               "--no-tests=error", "--output-on-failure", "--output-junit", str(junit)]
    if regex:
        command += ["-R", regex]

    # Wine's own debug messages would bury the test output
    result = run("Running tests", command, log, verbose=verbose, env={"WINEDEBUG": "-all"})
    cases = parse_junit(junit)

    if cases:
        table = Table(title="Test results", title_style="bold", show_lines=False)
        table.add_column("Test")
        table.add_column("Result")
        table.add_column("Time", justify="right")
        styles = {"passed": "[green]✓ passed[/]", "failed": "[red]✗ failed[/]", "skipped": "[yellow]- skipped[/]"}
        for name, status, seconds, _ in cases:
            table.add_row(escape(name), styles[status], f"{seconds:.2f}s")
        console.print(table)

    if not result.ok:
        if regex and not cases:
            raise StepFailed(f"No tests match '{regex}'.", result, log)
        for name, status, _, output in cases:
            if status == "failed" and output:
                console.print(Panel(escape(output), title=f"[red]{escape(name)} output[/]", border_style="red"))
        raise StepFailed("One or more tests failed.", result, log)

    passed = sum(1 for case in cases if case[1] == "passed")
    finish_ok("TESTS PASSED", [f"{passed}/{len(cases)} tests passed ({target.description}) in {result.seconds:.1f}s"])


@main.command()
@click.option("-d", "--debug", is_flag=True, help="Clean the Debug build (default: Release).")
@click.option("--mingw", is_flag=True, help="Windows only: clean the MinGW build instead of the Visual Studio one.")
@click.option("-a", "--all", "everything", is_flag=True, help="Remove the whole build/ directory (every configuration).")
@guarded("CLEAN FAILED")
def clean(debug: bool, mingw: bool, everything: bool) -> None:
    """Delete build directories. Downloaded dependencies in the CPM cache are kept."""
    path = BUILD_ROOT if everything else make_target(debug, mingw).build_dir
    if remove(path):
        finish_ok("CLEANED", [f"Removed {relative(path)}"])
    else:
        finish_ok("NOTHING TO CLEAN", [f"{relative(path)} does not exist"])


@main.command()
@with_common_options
@click.argument("prefix", type=click.Path(file_okay=False, path_type=Path))
@guarded("INSTALL FAILED")
def install(debug: bool, mingw: bool, verbose: bool, prefix: Path) -> None:
    """Build, then install the library and its CMake package to PREFIX."""
    target = make_target(debug, mingw)
    build_target(target, clean=False, jobs=None, defines=(), verbose=verbose)

    prefix = prefix.expanduser().resolve()
    log = target.build_dir / "logs" / "install.log"
    result = run(f"Installing to {prefix}", ["cmake", "--install", str(target.build_dir), *target.config_args(),
                                              "--prefix", str(prefix)], log, verbose=verbose)
    if not result.ok:
        raise StepFailed(f"Install to {prefix} failed.", result, log)
    finish_ok("INSTALLED", [f"{target.description} → {prefix}", "",
                            f"Use it with find_package(mesdk) and -DCMAKE_PREFIX_PATH={prefix}"])


@main.command()
@click.option("--mingw", is_flag=True, help="Windows only: check the MinGW toolchain instead of Visual Studio.")
def doctor(mingw: bool) -> None:
    """Check that the tools needed to build and test are installed."""
    target = make_target(False, mingw)
    checks = all_checks(target)

    table = Table(title=f"mesdk prerequisites ({target.description.split(',')[0]})", title_style="bold")
    table.add_column("")
    table.add_column("Tool")
    table.add_column("Status")
    table.add_column("Install")
    for check in checks:
        if check.found:
            mark = "[green]✓[/]"
        else:
            mark = "[red]✗[/]" if check.required else "[yellow]![/]"
        table.add_row(mark, check.name + ("" if check.required else " [dim](optional)[/]"),
                      escape(check.detail), escape(check.hint) if not check.found else "")
    console.print(table)

    if any(check.required and not check.found for check in checks):
        console.print("[bold red]Some required tools are missing.[/]")
        sys.exit(1)
    console.print("[bold green]Ready to build.[/]")


if __name__ == "__main__":
    main()
