#!/usr/bin/env bash
# Builds mesdk for 32-bit Windows with MinGW-w64 (Linux, macOS, or an MSYS2 MINGW32 shell).
#
#   ./build.sh                    Release build
#   ./build.sh --debug --test     Debug build, then run the tests (through Wine on Linux)
#   ./build.sh --install ~/.local/mesdk-i686
#
# Run ./build.sh --help for every option.

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG=Release
RUN_TESTS=0
CLEAN=0
INSTALL_PREFIX=""
JOBS=""
EXTRA_ARGS=()

if [[ -t 1 ]]; then
  RED=$'\e[31m' GREEN=$'\e[32m' YELLOW=$'\e[33m' BOLD=$'\e[1m' RESET=$'\e[0m'
else
  RED="" GREEN="" YELLOW="" BOLD="" RESET=""
fi

info()    { echo "${BOLD}==>${RESET} $*"; }
warn()    { echo "${YELLOW}warning:${RESET} $*" >&2; }
fail()    { echo "${RED}${BOLD}error:${RESET} $*" >&2; echo "${RED}${BOLD}BUILD FAILED${RESET}" >&2; exit 1; }
success() { echo "${GREEN}${BOLD}$*${RESET}"; }

usage() {
  cat <<EOF
Usage: ./build.sh [options] [-- extra cmake configure args]

Options:
  -d, --debug            Debug build (default: Release)
  -r, --release          Release build
  -t, --test             Run the tests after building (needs Wine when cross-compiling)
  -c, --clean            Delete the build directory first
  -i, --install PREFIX   Install the library and CMake package to PREFIX
  -j, --jobs N           Parallel build jobs (default: all cores)
  -h, --help             Show this help

Anything after -- goes to the cmake configure step, e.g. -- -DMESDK_BUILD_SDK_DOCS=ON
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -d|--debug)   CONFIG=Debug ;;
    -r|--release) CONFIG=Release ;;
    -t|--test)    RUN_TESTS=1 ;;
    -c|--clean)   CLEAN=1 ;;
    -i|--install) [[ $# -ge 2 ]] || fail "--install needs a prefix"; INSTALL_PREFIX="$2"; shift ;;
    -j|--jobs)    [[ $# -ge 2 ]] || fail "--jobs needs a number"; JOBS="$2"; shift ;;
    -h|--help)    usage; exit 0 ;;
    --)           shift; EXTRA_ARGS=("$@"); break ;;
    *)            usage >&2; fail "unknown option: $1" ;;
  esac
  shift
done

CONFIG_LOWER="$(echo "$CONFIG" | tr '[:upper:]' '[:lower:]')"
BUILD_DIR="$ROOT/build/mingw-$CONFIG_LOWER"   # same directory as the mingw-* CMake presets
TOOLCHAIN="$ROOT/cmake/toolchains/mingw-i686.cmake"

# -------------------------------------------------------------------------------------------------
# Prerequisites

case "$(uname -s)" in
  Linux*)  INSTALL_HINT="sudo apt install cmake ninja-build g++-mingw-w64-i686" ;;
  Darwin*) INSTALL_HINT="brew install cmake ninja mingw-w64" ;;
  MINGW*|MSYS*) INSTALL_HINT="pacman -S mingw-w64-i686-cmake mingw-w64-i686-ninja mingw-w64-i686-gcc (MINGW32 shell)" ;;
  *)       INSTALL_HINT="install CMake 3.21+, Ninja and an i686 MinGW-w64 g++" ;;
esac

command -v cmake >/dev/null 2>&1 || fail "cmake not found. Install it: $INSTALL_HINT"

CMAKE_VERSION="$(cmake --version | head -n1 | awk '{print $3}')"
if [[ "$(printf '%s\n' 3.21 "$CMAKE_VERSION" | sort -V | head -n1)" != "3.21" ]]; then
  fail "CMake $CMAKE_VERSION is too old, mesdk needs 3.21 or newer"
fi

if ! command -v i686-w64-mingw32-g++ >/dev/null 2>&1 && ! command -v i686-w64-mingw32-g++-posix >/dev/null 2>&1; then
  fail "i686-w64-mingw32-g++ not found (Mirror's Edge is 32-bit Windows, so mesdk is cross-compiled). Install it: $INSTALL_HINT"
fi

GENERATOR_ARGS=()
if command -v ninja >/dev/null 2>&1; then
  GENERATOR_ARGS=(-G Ninja)
elif [[ ! -f "$BUILD_DIR/CMakeCache.txt" ]]; then
  warn "ninja not found, falling back to Makefiles (install ninja for faster builds)"
fi

if [[ -z "$JOBS" ]]; then
  JOBS="$(getconf _NPROCESSORS_ONLN 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)"
fi

# -------------------------------------------------------------------------------------------------
# Build

if [[ $CLEAN -eq 1 && -d "$BUILD_DIR" ]]; then
  info "Removing $BUILD_DIR"
  rm -rf "$BUILD_DIR" || fail "could not remove $BUILD_DIR"
fi

START=$SECONDS

info "Configuring ($CONFIG) in $BUILD_DIR"
cmake -S "$ROOT" -B "$BUILD_DIR" ${GENERATOR_ARGS[@]+"${GENERATOR_ARGS[@]}"} \
  -DCMAKE_TOOLCHAIN_FILE="$TOOLCHAIN" \
  -DCMAKE_BUILD_TYPE="$CONFIG" \
  -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
  ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"} \
  || fail "CMake configure failed (see the messages above). If a download failed, check your network; if the toolchain changed, retry with --clean."

info "Building with $JOBS jobs (the first build compiles the whole SDK and takes a few minutes)"
cmake --build "$BUILD_DIR" --parallel "$JOBS" \
  || fail "compilation failed (see the compiler errors above)"

if [[ $RUN_TESTS -eq 1 ]]; then
  info "Running tests"
  if [[ "$(uname -s)" != MINGW* && "$(uname -s)" != MSYS* ]] && ! command -v wine >/dev/null 2>&1; then
    fail "the tests are Windows executables and need Wine to run here (sudo apt install wine)"
  fi
  # Wine needs a while to start the first time; keep its debug noise out of the output
  WINEDEBUG=-all ctest --test-dir "$BUILD_DIR" --output-on-failure \
    || fail "tests failed (see the output above)"
  success "Tests passed"
fi

if [[ -n "$INSTALL_PREFIX" ]]; then
  info "Installing to $INSTALL_PREFIX"
  cmake --install "$BUILD_DIR" --prefix "$INSTALL_PREFIX" >/dev/null \
    || fail "install to $INSTALL_PREFIX failed"
fi

echo
success "BUILD SUCCEEDED ($CONFIG, $((SECONDS - START))s)"
echo "  Libraries: $BUILD_DIR/libmesdk_sdk.a, $BUILD_DIR/libmesdk.a"
[[ -f "$BUILD_DIR/examples/hello_mod/hello_mod.dll" ]] && echo "  Example:   $BUILD_DIR/examples/hello_mod/hello_mod.dll"
[[ -n "$INSTALL_PREFIX" ]] && echo "  Installed: $INSTALL_PREFIX (use -DCMAKE_PREFIX_PATH=$INSTALL_PREFIX with find_package(mesdk))"
exit 0
