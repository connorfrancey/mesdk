@echo off
rem Builds mesdk for 32-bit Windows (Mirror's Edge is a 32-bit game).
rem
rem   build.bat                     Release build with Visual Studio (Win32)
rem   build.bat --debug --test      Debug build, then run the tests
rem   build.bat --mingw             Use an i686 MinGW-w64 g++ from PATH (e.g. MSYS2 mingw32\bin) with Ninja
rem   build.bat --install C:\libs\mesdk
rem
rem Run build.bat --help for every option.

setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "CONFIG=Release"
set "RUN_TESTS=0"
set "CLEAN=0"
set "USE_MINGW=0"
set "INSTALL_PREFIX="
set "EXTRA_ARGS="

rem ANSI colours (Windows 10+ consoles)
for /F %%a in ('echo prompt $E ^| cmd') do set "ESC=%%a"
set "RED=%ESC%[31m"
set "GREEN=%ESC%[32m"
set "BOLD=%ESC%[1m"
set "RESET=%ESC%[0m"

:parse
if "%~1"=="" goto :parsed
if /I "%~1"=="-d"        (set "CONFIG=Debug"   & shift & goto :parse)
if /I "%~1"=="--debug"   (set "CONFIG=Debug"   & shift & goto :parse)
if /I "%~1"=="-r"        (set "CONFIG=Release" & shift & goto :parse)
if /I "%~1"=="--release" (set "CONFIG=Release" & shift & goto :parse)
if /I "%~1"=="-t"        (set "RUN_TESTS=1"    & shift & goto :parse)
if /I "%~1"=="--test"    (set "RUN_TESTS=1"    & shift & goto :parse)
if /I "%~1"=="-c"        (set "CLEAN=1"        & shift & goto :parse)
if /I "%~1"=="--clean"   (set "CLEAN=1"        & shift & goto :parse)
if /I "%~1"=="--mingw"   (set "USE_MINGW=1"    & shift & goto :parse)
if /I "%~1"=="-h"        goto :usage
if /I "%~1"=="--help"    goto :usage
if /I "%~1"=="/?"        goto :usage
if /I "%~1"=="-i"        goto :install_arg
if /I "%~1"=="--install" goto :install_arg
if "%~1"=="--"           goto :extra_args
call :usage
set "MESSAGE=unknown option: %~1"
goto :fail

:install_arg
if "%~2"=="" (set "MESSAGE=--install needs a prefix" & goto :fail)
set "INSTALL_PREFIX=%~2"
shift & shift
goto :parse

:extra_args
shift
:extra_loop
if "%~1"=="" goto :parsed
set "EXTRA_ARGS=!EXTRA_ARGS! %1"
shift
goto :extra_loop

:parsed

rem ------------------------------------------------------------------------------------------------
rem Prerequisites

where cmake >nul 2>&1
if errorlevel 1 (
  set "MESSAGE=cmake not found. Install CMake 3.21+ from https://cmake.org/download/ or with Visual Studio, and make sure it is on PATH"
  goto :fail
)

rem The project's own CMAKE_GENERATOR choice decides the generator below, not the environment's
set "CMAKE_GENERATOR="
set "CMAKE_GENERATOR_PLATFORM="

if "%USE_MINGW%"=="1" (
  set "BUILD_DIR=%ROOT%\build\mingw-%CONFIG%"
  where ninja >nul 2>&1
  if errorlevel 1 (
    set "MESSAGE=ninja not found on PATH. MSYS2: pacman -S mingw-w64-i686-ninja"
    goto :fail
  )
  set "COMPILER="
  for %%c in (i686-w64-mingw32-g++.exe g++.exe) do (
    if not defined COMPILER (
      where %%c >nul 2>&1 && set "COMPILER=%%c"
    )
  )
  if not defined COMPILER (
    set "MESSAGE=no MinGW g++ on PATH. Install MSYS2 and run: pacman -S mingw-w64-i686-gcc, then add msys64\mingw32\bin to PATH"
    goto :fail
  )
  set CONFIGURE_ARGS=-G Ninja -DCMAKE_CXX_COMPILER=!COMPILER! -DCMAKE_BUILD_TYPE=%CONFIG%
) else (
  set "BUILD_DIR=%ROOT%\build\msvc-x86"
  rem The newest installed Visual Studio, 32-bit target
  set CONFIGURE_ARGS=-A Win32
)

rem ------------------------------------------------------------------------------------------------
rem Build

if "%CLEAN%"=="1" if exist "%BUILD_DIR%" (
  echo %BOLD%==^>%RESET% Removing %BUILD_DIR%
  rmdir /S /Q "%BUILD_DIR%"
  if exist "%BUILD_DIR%" (set "MESSAGE=could not remove %BUILD_DIR%" & goto :fail)
)

echo %BOLD%==^>%RESET% Configuring (%CONFIG%) in %BUILD_DIR%
cmake -S "%ROOT%" -B "%BUILD_DIR%" %CONFIGURE_ARGS% %EXTRA_ARGS%
if errorlevel 1 (
  set "MESSAGE=CMake configure failed (see the messages above). Without --mingw this needs Visual Studio with the 'Desktop development with C++' workload. If you switched generators, retry with --clean."
  goto :fail
)

echo %BOLD%==^>%RESET% Building (the first build compiles the whole SDK and takes a few minutes)
cmake --build "%BUILD_DIR%" --config %CONFIG% --parallel
if errorlevel 1 (
  set "MESSAGE=compilation failed (see the compiler errors above)"
  goto :fail
)

if "%RUN_TESTS%"=="1" (
  echo %BOLD%==^>%RESET% Running tests
  ctest --test-dir "%BUILD_DIR%" -C %CONFIG% --output-on-failure
  if errorlevel 1 (
    set "MESSAGE=tests failed (see the output above)"
    goto :fail
  )
  echo %GREEN%%BOLD%Tests passed%RESET%
)

if defined INSTALL_PREFIX (
  echo %BOLD%==^>%RESET% Installing to %INSTALL_PREFIX%
  cmake --install "%BUILD_DIR%" --config %CONFIG% --prefix "%INSTALL_PREFIX%" >nul
  if errorlevel 1 (
    set "MESSAGE=install to %INSTALL_PREFIX% failed"
    goto :fail
  )
)

echo.
echo %GREEN%%BOLD%BUILD SUCCEEDED (%CONFIG%)%RESET%
echo   Build directory: %BUILD_DIR%
if defined INSTALL_PREFIX echo   Installed: %INSTALL_PREFIX% (use -DCMAKE_PREFIX_PATH=%INSTALL_PREFIX% with find_package(mesdk))
endlocal
exit /b 0

:usage
echo Usage: build.bat [options] [-- extra cmake configure args]
echo.
echo Options:
echo   -d, --debug            Debug build (default: Release)
echo   -r, --release          Release build
echo   -t, --test             Run the tests after building
echo   -c, --clean            Delete the build directory first
echo       --mingw            Build with an i686 MinGW-w64 g++ and Ninja from PATH instead of Visual Studio
echo   -i, --install PREFIX   Install the library and CMake package to PREFIX
echo   -h, --help             Show this help
echo.
echo Anything after -- goes to the cmake configure step, e.g. -- -DMESDK_BUILD_SDK_DOCS=ON
exit /b 0

:fail
echo %RED%%BOLD%error:%RESET% !MESSAGE! 1>&2
echo %RED%%BOLD%BUILD FAILED%RESET% 1>&2
endlocal
exit /b 1
