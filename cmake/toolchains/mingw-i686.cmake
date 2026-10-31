# Cross-compile for 32-bit Windows (Mirror's Edge is a 32-bit game) with MinGW-w64 i686.
#
#   sudo apt install g++-mingw-w64-i686 cmake ninja-build
#   cmake -B build -G Ninja -DCMAKE_TOOLCHAIN_FILE=cmake/toolchains/mingw-i686.cmake
#
# Override the compiler prefix with -DMINGW_TRIPLET=... if your distribution names it differently.

set(CMAKE_SYSTEM_NAME Windows)
set(CMAKE_SYSTEM_PROCESSOR i686)

if(NOT MINGW_TRIPLET)
  set(MINGW_TRIPLET i686-w64-mingw32)
endif()

# Prefer the POSIX threads variant (std::thread / std::mutex work) when Debian/Ubuntu provide it
find_program(_mesdk_mingw_cxx NAMES ${MINGW_TRIPLET}-g++-posix ${MINGW_TRIPLET}-g++ NO_CACHE)
find_program(_mesdk_mingw_cc NAMES ${MINGW_TRIPLET}-gcc-posix ${MINGW_TRIPLET}-gcc NO_CACHE)
if(NOT _mesdk_mingw_cxx OR NOT _mesdk_mingw_cc)
  message(FATAL_ERROR "${MINGW_TRIPLET}-g++ not found. On Ubuntu: sudo apt install g++-mingw-w64-i686")
endif()

set(CMAKE_C_COMPILER ${_mesdk_mingw_cc})
set(CMAKE_CXX_COMPILER ${_mesdk_mingw_cxx})
set(CMAKE_RC_COMPILER ${MINGW_TRIPLET}-windres)

set(CMAKE_FIND_ROOT_PATH /usr/${MINGW_TRIPLET})
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE BOTH)

# Lets CTest run the Windows test executables through Wine when it is installed
find_program(_mesdk_wine NAMES wine NO_CACHE)
if(_mesdk_wine AND NOT CMAKE_CROSSCOMPILING_EMULATOR)
  set(CMAKE_CROSSCOMPILING_EMULATOR ${_mesdk_wine})
endif()
