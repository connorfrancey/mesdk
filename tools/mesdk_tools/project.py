"""Where things are, which toolchain to use, and whether the prerequisites are installed."""

from __future__ import annotations

import platform
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILD_ROOT = ROOT / "build"
TOOLCHAIN_FILE = ROOT / "cmake" / "toolchains" / "mingw-i686.cmake"
MIN_CMAKE = (3, 21)

HOST = platform.system()  # "Linux", "Darwin", "Windows"
IS_WINDOWS = HOST == "Windows"


@dataclass(frozen=True)
class Target:
    """A build flavour. The build directories match the CMake presets and build.sh / build.bat."""

    config: str = "Release"  # Release or Debug
    msvc: bool = IS_WINDOWS  # Visual Studio on Windows, MinGW-w64 everywhere else

    @property
    def name(self) -> str:
        return "msvc-x86" if self.msvc else f"mingw-{self.config.lower()}"

    @property
    def build_dir(self) -> Path:
        return BUILD_ROOT / self.name

    @property
    def multi_config(self) -> bool:
        return self.msvc

    @property
    def description(self) -> str:
        return f"{'Visual Studio (Win32)' if self.msvc else 'MinGW-w64 i686'}, {self.config}"

    def configure_args(self) -> list[str]:
        if self.msvc:
            return ["-A", "Win32"]

        args = [f"-DCMAKE_BUILD_TYPE={self.config}", "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON"]
        if shutil.which("ninja"):
            args += ["-G", "Ninja"]

        if IS_WINDOWS:
            # MSYS2 & co.: use the MinGW g++ on PATH, no cross toolchain
            compiler = shutil.which("i686-w64-mingw32-g++") or shutil.which("g++")
            if compiler:
                args.append(f"-DCMAKE_CXX_COMPILER={compiler}")
        else:
            args.append(f"-DCMAKE_TOOLCHAIN_FILE={TOOLCHAIN_FILE}")

        return args

    def config_args(self) -> list[str]:
        """Arguments selecting the configuration for cmake --build / ctest / cmake --install."""
        return ["--config", self.config] if self.multi_config else []


# --------------------------------------------------------------------------------------------------
# Prerequisites


@dataclass
class Check:
    name: str
    found: bool
    detail: str
    required: bool
    hint: str = ""


def install_hint(linux: str, mac: str, windows: str) -> str:
    return {"Linux": linux, "Darwin": mac, "Windows": windows}.get(HOST, linux)


def tool_version(command: list[str]) -> str:
    try:
        output = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return output.strip().splitlines()[0] if output.strip() else ""


def check_cmake() -> Check:
    hint = install_hint("sudo apt install cmake", "brew install cmake",
                        "install CMake from https://cmake.org/download/ (or with Visual Studio)")
    if not shutil.which("cmake"):
        return Check("cmake", False, "not found", True, hint)

    line = tool_version(["cmake", "--version"])
    match = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", line)
    if not match:
        return Check("cmake", False, f"unrecognised version: {line!r}", True, hint)

    version = (int(match[1]), int(match[2]))
    if version < MIN_CMAKE:
        return Check("cmake", False, f"{match[0]} (needs {MIN_CMAKE[0]}.{MIN_CMAKE[1]}+)", True, hint)
    return Check("cmake", True, match[0], True)


def check_compiler(target: Target) -> Check:
    if target.msvc:
        vswhere = Path(r"C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe")
        hint = "install Visual Studio with the 'Desktop development with C++' workload"
        if not vswhere.exists():
            return Check("Visual Studio", False, "vswhere.exe not found", True, hint)
        name = tool_version([str(vswhere), "-latest", "-products", "*", "-requires",
                             "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
                             "-property", "displayName"])
        return Check("Visual Studio", bool(name), name or "no C++ toolset installed", True, hint)

    names = ["i686-w64-mingw32-g++-posix", "i686-w64-mingw32-g++"]
    if IS_WINDOWS:
        names.append("g++")
    hint = install_hint("sudo apt install g++-mingw-w64-i686", "brew install mingw-w64",
                        "MSYS2: pacman -S mingw-w64-i686-gcc, then add msys64\\mingw32\\bin to PATH")
    for name in names:
        if path := shutil.which(name):
            return Check("MinGW-w64 i686 g++", True, tool_version([path, "--version"]) or path, True)
    return Check("MinGW-w64 i686 g++", False, "not found", True, hint)


def check_ninja(target: Target) -> Check:
    hint = install_hint("sudo apt install ninja-build", "brew install ninja",
                        "MSYS2: pacman -S mingw-w64-i686-ninja")
    found = shutil.which("ninja")
    # Required for MinGW on Windows (no Makefiles fallback there); optional elsewhere
    required = IS_WINDOWS and not target.msvc
    if target.msvc:
        return Check("ninja", bool(found), tool_version(["ninja", "--version"]) if found else "not used with Visual Studio", False)
    return Check("ninja", bool(found), tool_version(["ninja", "--version"]) if found else "not found (falls back to Makefiles)", required, hint)


def check_wine() -> Check:
    if IS_WINDOWS:
        return Check("wine", True, "not needed on Windows", False)
    found = shutil.which("wine")
    return Check("wine", bool(found), tool_version(["wine", "--version"]) if found else "not found (needed to run the tests)",
                 False, install_hint("sudo apt install wine", "brew install --cask wine-stable", ""))


def check_doxygen() -> Check:
    found = shutil.which("doxygen")
    return Check("doxygen", bool(found), tool_version(["doxygen", "--version"]) if found else "not found (only for the docs)",
                 False, install_hint("sudo apt install doxygen", "brew install doxygen", "https://www.doxygen.nl/download.html"))


def all_checks(target: Target) -> list[Check]:
    return [check_cmake(), check_compiler(target), check_ninja(target), check_wine(), check_doxygen()]


def build_checks(target: Target) -> list[Check]:
    return [check_cmake(), check_compiler(target), check_ninja(target)]
