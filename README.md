# mesdk

The Mirror's Edge (1.0) SDK from [mmultiplayer](https://github.com/connorfrancey/mmultiplayer), packaged as a CMake library you can use in your own mods and tools. You can add it with [CPM.cmake](https://github.com/cpm-cmake/CPM.cmake), `add_subdirectory` or `find_package`.

mesdk doesn't copy the SDK into this repository. At configure time, CPM downloads a pinned revision of the mmultiplayer fork, and mesdk builds its `Client/sdk` sources into a static library.

| Target | Header | What you get |
|---|---|---|
| `mesdk::sdk` | `#include <ME_SDK.hpp>` | The generated SDK: every game class in `namespace Classes` |
| `mesdk::mesdk` | `#include <mesdk/mesdk.hpp>` | `mesdk::sdk`, plus helpers that find `GNames`/`GObjects`, hook `ProcessEvent` and iterate objects. It also includes mmultiplayer's `Pattern::` and `Hook::` helpers. |

Mirror's Edge is a **32-bit Windows** game, so everything builds for 32-bit Windows. On Ubuntu, that means cross-compiling with MinGW-w64. The output is a DLL that you load into `MirrorsEdge.exe`, on Windows or under Wine/Proton.

## Building

The build scripts check the prerequisites, then configure, build and optionally test and install. They end with **BUILD SUCCEEDED** or **BUILD FAILED** plus a short explanation, and they exit non-zero on failure.

**Linux / macOS** (cross-compiles with MinGW-w64):

```sh
sudo apt install cmake ninja-build g++-mingw-w64-i686   # macOS: brew install cmake ninja mingw-w64
# optional: wine (to run the tests), doxygen + graphviz (to build the docs)

./build.sh                          # Release build into build/mingw-release
./build.sh --debug --test           # Debug build, then run the tests (through Wine)
./build.sh --clean --install ~/.local/mesdk-i686
./build.sh -- -DMESDK_BUILD_SDK_DOCS=ON # anything after -- goes to cmake
```

**Windows**:

```bat
build.bat                           :: Visual Studio (newest installed), Win32, into build\msvc-x86
build.bat --debug --test
build.bat --mingw                   :: i686 MinGW-w64 g++ + Ninja from PATH (e.g. MSYS2 mingw32\bin)
build.bat --install C:\libs\mesdk
```

Run either script with `--help` to list all options.

To test, run `./test.sh`. It builds incrementally, then runs the tests (through Wine on Linux/macOS) and ends with **TESTS PASSED** or **TESTS FAILED**. Options: `--debug`, `-R <regex>` to filter tests, `--no-build` and `--verbose`.

The tests use [Catch2](https://github.com/catchorg/Catch2) v3, which CPM downloads. They live in `tests/` (`layout.cpp`, `runtime.cpp`, `pattern.cpp`). Each `TEST_CASE` is registered as its own CTest test through `catch_discover_tests`, so `-R` matches test case names. You can also run the executable directly, for example `wine build/mingw-release/tests/mesdk_tests.exe "[pattern]"`.

### Python CLI (uv)

If you have [uv](https://docs.astral.sh/uv/), `uv run mesdk` gives you the same build, test and clean steps with nicer output: a progress bar, a results table for tests, and a summary panel showing just the compiler errors when something fails. uv installs the dependencies, [click](https://click.palletsprojects.com/) and [rich](https://rich.readthedocs.io/), on first use. The CLI works on Linux, macOS and Windows.

```sh
uv run mesdk doctor                 # check that cmake, the compiler, ninja and wine are installed
uv run mesdk build                  # --debug, --clean, -j N, -D VAR=VALUE, --verbose (raw output)
uv run mesdk test                   # -R <regex>, --no-build, --debug
uv run mesdk clean                  # --debug, or --all for the whole build/ directory
uv run mesdk install ~/.local/mesdk-i686
```

On Windows, these commands use Visual Studio by default. Add `--mingw` to use MinGW-w64 from PATH instead. Full logs of every step go to `build/<config>/logs/`. The CLI uses the same build directories as the scripts and presets, so you can mix the scripts, the CLI and the presets.

The first build compiles about 6 MB of generated code, which takes a few minutes. The outputs are `libmesdk_sdk.a`, `libmesdk.a` and `examples/hello_mod/hello_mod.dll`. With MSVC, the outputs are `.lib` files.

You can also use CMake directly: `cmake --preset mingw-release && cmake --build --preset mingw-release && ctest --preset mingw-release`. On Windows, the preset is `msvc-x86`. A plain `cmake -B build` also works, because a standalone Linux build picks up `cmake/toolchains/mingw-i686.cmake` automatically.

## Using it in your project

### With CPM.cmake (recommended)

[`examples/consumer`](examples/consumer) is a complete template. Copy that folder to start a new mod. The core of it:

```cmake
cmake_minimum_required(VERSION 3.21)
project(my_mod LANGUAGES CXX)

include(cmake/CPM.cmake)
CPMAddPackage(
  NAME mesdk
  GITHUB_REPOSITORY connorfrancey/mesdk   # wherever you push this repository
  GIT_TAG v0.1.0)

mesdk_add_mod(my_mod src/main.cpp)        # -> my_mod.dll
```

Your project must be configured for 32-bit Windows **before** `project()`, so the template includes a copy of the toolchain file and a `CMakePresets.json` that uses it:

```sh
cmake --preset release && cmake --build --preset release
```

To develop against a local checkout of mesdk, add `-DCPM_mesdk_SOURCE=/path/to/mesdk`.

### With add_subdirectory

```cmake
add_subdirectory(external/mesdk)
target_link_libraries(my_tool PRIVATE mesdk::mesdk)
```

### With find_package (installed)

```sh
cmake --install build/mingw-release --prefix ~/.local/mesdk-i686
```

```cmake
find_package(mesdk 0.1 REQUIRED)    # configure with -DCMAKE_PREFIX_PATH=~/.local/mesdk-i686
mesdk_add_mod(my_mod src/main.cpp)
```

The installed package also ships its toolchain file at `lib/cmake/mesdk/toolchains/mingw-i686.cmake`.

### mesdk_add_mod

`mesdk_add_mod(<name> [OUTPUT_NAME <name>] <sources>...)` creates a DLL target that links `mesdk::mesdk`. The DLL has no `lib` prefix. With MinGW, it also links libgcc, libstdc++ and winpthread statically, so the DLL only depends on system DLLs. You can also skip the helper and use `add_library(... SHARED)` with `target_link_libraries(... mesdk::mesdk)` directly.

## Writing a mod

```cpp
#include <mesdk/mesdk.hpp>
#include <windows.h>

DWORD WINAPI Run(LPVOID) {
    if (mesdk::Initialize() != mesdk::Status::Ok) {   // finds GNames / GObjects in MirrorsEdge.exe
        return 1;
    }

    if (auto pawn = mesdk::FindFirstObject<Classes::ATdPlayerPawn>()) {
        pawn->Location;                               // fields match the game's memory
        pawn->GetFullName();                          // script functions are member functions
    }
    return 0;
}

BOOL WINAPI DllMain(HINSTANCE dll, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(dll);
        CloseHandle(CreateThread(nullptr, 0, Run, nullptr, 0, nullptr));
    }
    return TRUE;
}
```

[`examples/hello_mod`](examples/hello_mod/main.cpp) also hooks `ProcessEvent` and logs the player's position.

### API (`mesdk/mesdk.hpp`)

| Function | Description |
|---|---|
| `Status Initialize(const char *module = nullptr)` | Pattern-scans the game for `GNames` and `GObjects` and stores them in the SDK. You must call this before using `StaticClass()`, `FindObject()` or any script function. |
| `bool IsInitialized()` | True after a successful `Initialize()` |
| `const char *ToString(Status)` | Returns a readable error |
| `void *FindProcessEvent()` | Returns the address of `UObject::ProcessEvent` |
| `bool HookProcessEvent(detour, &original)` / `UnhookProcessEvent(original)` | Detours every UnrealScript call. Call `original` to let the call through. |
| `ForEachObject<T>(fn)` / `FindFirstObject<T>()` | Iterates the live objects of a class. Class default objects are skipped. |
| `UTdGameEngine *FindEngine()` | Returns the running game engine |
| `MESDK_VERSION`, `MESDK_MMULTIPLAYER_REF` | Macros in `<mesdk/version.hpp>` |

### Docs (Doxygen)

`cmake --build build/mingw-release --target mesdk_docs` generates the API reference for `mesdk/mesdk.hpp` and `mesdk/version.hpp`, with this README as the main page. It writes `<build>/docs/html/index.html`. The target exists when Doxygen is installed and `MESDK_BUILD_DOCS` is ON, which is the default for a top-level build. It isn't part of the default build.

The SDK itself is documented in the fork's [docs](https://github.com/connorfrancey/mmultiplayer/tree/main/docs): the game SDK concepts, finding game classes, and SDK basics. To build those docs locally with Doxygen, configure with `-DMESDK_BUILD_SDK_DOCS=ON` and build the `mesdk_sdk_docs` target. The output goes to `<build>/mmultiplayer-docs/docs/html`.

## Configuration

| Cache variable | Default | Description |
|---|---|---|
| `MESDK_MMULTIPLAYER_REPOSITORY` | `connorfrancey/mmultiplayer` | GitHub repository the SDK sources come from |
| `MESDK_MMULTIPLAYER_REF` | `7b1eb25…` | Commit, tag or branch of that repository. Only the default revision is hash-checked. |
| `CPM_mmultiplayer_SOURCE` | — | Use a local mmultiplayer checkout instead of downloading one |
| `MESDK_BUILD_EXAMPLES` / `MESDK_BUILD_TESTS` / `MESDK_INSTALL` | ON when top level | Build the examples and tests, and generate install rules |
| `MESDK_BUILD_DOCS` | ON when top level | Adds the `mesdk_docs` Doxygen target (mesdk's API), if Doxygen is installed |
| `MESDK_BUILD_SDK_DOCS` | OFF | Adds the `mesdk_sdk_docs` target (the fork's SDK guides and reference) |

Set `CPM_SOURCE_CACHE` (for example, `export CPM_SOURCE_CACHE=~/.cache/CPM`) to share downloads between build directories.

## Notes

- The tests check the SDK's layout against the offsets in the generated headers, using `static_assert`s for `UObject`, `AActor`, `APawn`, `ATdPlayerPawn` and others. One exception: `UClass` is hand-edited in the SDK and is 0x1EC bytes, while its header comment says 0x1F4.
- MSVC and MinGW lay out a few rarely used SDK classes differently. See the fork's `docs/_notes/code-issues.md`.
- `Initialize()` scans the game executable. Don't call it from a standalone process, which has no game to find.
