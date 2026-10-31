#!/usr/bin/env bash
# Builds mesdk (incrementally) and runs its tests. The tests are Windows executables, so on Linux and
# macOS they run through Wine.
#
#   ./test.sh                     Release build + tests
#   ./test.sh --debug -R layout   Debug build, only tests matching "layout"
#   ./test.sh --no-build          Run the tests of an existing build
#
# Run ./test.sh --help for every option.

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG=Release
BUILD=1
VERBOSE=0
FILTER=""

if [[ -t 1 ]]; then
  RED=$'\e[31m' GREEN=$'\e[32m' BOLD=$'\e[1m' RESET=$'\e[0m'
else
  RED="" GREEN="" BOLD="" RESET=""
fi

info()    { echo "${BOLD}==>${RESET} $*"; }
fail()    { echo "${RED}${BOLD}error:${RESET} $*" >&2; echo "${RED}${BOLD}TESTS FAILED${RESET}" >&2; exit 1; }
success() { echo "${GREEN}${BOLD}$*${RESET}"; }

usage() {
  cat <<EOF
Usage: ./test.sh [options]

Options:
  -d, --debug            Test the Debug build (default: Release)
  -r, --release          Test the Release build
  -R, --regex REGEX      Only run tests whose name matches REGEX
  -n, --no-build         Don't build first; test the existing build directory
  -v, --verbose          Show the full test output, not only failures
  -h, --help             Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -d|--debug)    CONFIG=Debug ;;
    -r|--release)  CONFIG=Release ;;
    -R|--regex)    [[ $# -ge 2 ]] || fail "--regex needs a pattern"; FILTER="$2"; shift ;;
    -n|--no-build) BUILD=0 ;;
    -v|--verbose)  VERBOSE=1 ;;
    -h|--help)     usage; exit 0 ;;
    *)             usage >&2; fail "unknown option: $1" ;;
  esac
  shift
done

CONFIG_LOWER="$(echo "$CONFIG" | tr '[:upper:]' '[:lower:]')"
BUILD_DIR="$ROOT/build/mingw-$CONFIG_LOWER"

command -v ctest >/dev/null 2>&1 || fail "ctest not found (it comes with CMake): sudo apt install cmake"

case "$(uname -s)" in
  MINGW*|MSYS*) ;;
  *)
    command -v wine >/dev/null 2>&1 \
      || fail "wine not found. The tests are Windows executables; install Wine to run them (sudo apt install wine)"
    ;;
esac

if [[ $BUILD -eq 1 ]]; then
  BUILD_ARGS=()
  [[ $CONFIG == Debug ]] && BUILD_ARGS+=(--debug)
  "$ROOT/build.sh" ${BUILD_ARGS[@]+"${BUILD_ARGS[@]}"} \
    || fail "the build failed, so the tests were not run"
elif [[ ! -f "$BUILD_DIR/CMakeCache.txt" ]]; then
  fail "no build in $BUILD_DIR. Run without --no-build, or ./build.sh$([[ $CONFIG == Debug ]] && echo ' --debug') first"
fi

grep -q "^MESDK_BUILD_TESTS:BOOL=ON" "$BUILD_DIR/CMakeCache.txt" 2>/dev/null \
  || fail "$BUILD_DIR was configured with MESDK_BUILD_TESTS=OFF. Rebuild with: ./build.sh --clean"

CTEST_ARGS=(--test-dir "$BUILD_DIR" --no-tests=error)
if [[ $VERBOSE -eq 1 ]]; then
  CTEST_ARGS+=(--verbose)
else
  CTEST_ARGS+=(--output-on-failure)
fi
if [[ -n "$FILTER" ]]; then
  CTEST_ARGS+=(-R "$FILTER")
  if ctest --test-dir "$BUILD_DIR" -N -R "$FILTER" | grep -q "Total Tests: 0"; then
    fail "no tests match '$FILTER'. Available: $(ctest --test-dir "$BUILD_DIR" -N | sed -n 's/^ *Test *#[0-9]*: //p' | paste -sd ' ')"
  fi
fi

echo
info "Running tests ($CONFIG)$([[ -n "$FILTER" ]] && echo " matching '$FILTER'")"
# Wine's own debug messages would bury the test output
WINEDEBUG="${WINEDEBUG:--all}" ctest "${CTEST_ARGS[@]}" \
  || fail "one or more tests failed (see the output above)"

echo
success "TESTS PASSED ($CONFIG)"
exit 0
