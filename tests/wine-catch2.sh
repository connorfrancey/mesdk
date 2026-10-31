#!/usr/bin/env bash
# Runs a Catch2 test executable through Wine. On Windows, Catch2 reads arguments starting with "/" as
# options, so the Unix path catch_discover_tests passes to --out becomes a Windows path (Z:\...).
#
#   wine-catch2.sh <wine> <test.exe> [args...]

set -euo pipefail

wine="$1"
shift

args=()
while [[ $# -gt 0 ]]; do
  args+=("$1")
  if [[ "$1" == "--out" || "$1" == "-o" ]] && [[ $# -ge 2 && "$2" == /* ]]; then
    args+=("$(winepath -w "$2" 2>/dev/null || echo "Z:${2//\//\\}")")
    shift
  fi
  shift
done

exec "$wine" "${args[@]}"
