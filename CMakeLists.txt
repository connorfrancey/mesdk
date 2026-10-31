cmake_minimum_required(VERSION 3.21)

# Building mesdk on its own from Linux/macOS: default to the bundled MinGW i686 toolchain so a plain
# `cmake -B build` works. Consumers set their own toolchain (see README).
if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR AND NOT CMAKE_TOOLCHAIN_FILE
   AND NOT CMAKE_HOST_WIN32)
  set(CMAKE_TOOLCHAIN_FILE "${CMAKE_CURRENT_SOURCE_DIR}/cmake/toolchains/mingw-i686.cmake"
    CACHE FILEPATH "Toolchain file")
  message(STATUS "mesdk: no toolchain given, using ${CMAKE_TOOLCHAIN_FILE}")
endif()

project(mesdk
  VERSION 0.1.0
  DESCRIPTION "The Mirror's Edge SDK from mmultiplayer, packaged for CMake and CPM.cmake"
  HOMEPAGE_URL "https://github.com/connorfrancey/mmultiplayer"
  LANGUAGES CXX)

# -------------------------------------------------------------------------------------------------
# Options

option(MESDK_BUILD_EXAMPLES "Build the example mod DLL" ${PROJECT_IS_TOP_LEVEL})
option(MESDK_BUILD_TESTS "Build the tests" ${PROJECT_IS_TOP_LEVEL})
option(MESDK_BUILD_DOCS "Add the mesdk_docs target (Doxygen API docs for mesdk)" ${PROJECT_IS_TOP_LEVEL})
option(MESDK_BUILD_SDK_DOCS "Add the mesdk_sdk_docs target (Doxygen docs from the mmultiplayer fork)" OFF)
option(MESDK_INSTALL "Generate install rules and a CMake package" ${PROJECT_IS_TOP_LEVEL})

# The mmultiplayer revision the SDK sources come from. Point CPM at a local checkout instead with
# -DCPM_mmultiplayer_SOURCE=/path/to/mmultiplayer.
set(MESDK_MMULTIPLAYER_REPOSITORY "connorfrancey/mmultiplayer" CACHE STRING
  "GitHub repository (owner/name) to take the SDK from")
set(_mesdk_mmultiplayer_default_ref "7b1eb25ddc0fc1ce498d024e7b2f9d1980b9eca3")
set(MESDK_MMULTIPLAYER_REF "${_mesdk_mmultiplayer_default_ref}" CACHE STRING
  "Commit, tag or branch of the mmultiplayer repository")

if(NOT WIN32 OR NOT CMAKE_SIZEOF_VOID_P EQUAL 4)
  message(FATAL_ERROR
    "mesdk targets 32-bit Windows, because Mirror's Edge is a 32-bit Windows game.\n"
    "  Linux:   -DCMAKE_TOOLCHAIN_FILE=<mesdk>/cmake/toolchains/mingw-i686.cmake "
    "(sudo apt install g++-mingw-w64-i686)\n"
    "  Windows: cmake -A Win32 (Visual Studio), or an i686 MinGW toolchain")
endif()

# -------------------------------------------------------------------------------------------------
# Fetch the SDK sources

include(cmake/CPM.cmake)

# The archive hash is only known for the default revision
set(_mesdk_mmultiplayer_hash)
if(MESDK_MMULTIPLAYER_REPOSITORY STREQUAL "connorfrancey/mmultiplayer"
   AND MESDK_MMULTIPLAYER_REF STREQUAL _mesdk_mmultiplayer_default_ref)
  set(_mesdk_mmultiplayer_hash
    URL_HASH SHA256=7821d32b0f3a79949952d303e9063de05530ac8923cc3fc76a08bf67c744f269)
endif()

# A source archive is much smaller than a clone. DOWNLOAD_ONLY: mesdk defines its own targets, so
# the fork's own build (client DLL, launcher) is never configured.
CPMAddPackage(
  NAME mmultiplayer
  URL "https://github.com/${MESDK_MMULTIPLAYER_REPOSITORY}/archive/${MESDK_MMULTIPLAYER_REF}.tar.gz"
  ${_mesdk_mmultiplayer_hash}
  DOWNLOAD_ONLY YES)

set(MESDK_MMULTIPLAYER_DIR "${mmultiplayer_SOURCE_DIR}")
set(MESDK_SDK_DIR "${MESDK_MMULTIPLAYER_DIR}/Client/sdk")
if(NOT EXISTS "${MESDK_SDK_DIR}/ME_SDK.hpp")
  message(FATAL_ERROR "No Client/sdk/ME_SDK.hpp in ${MESDK_MMULTIPLAYER_DIR}")
endif()

include(GNUInstallDirs)
include(cmake/mesdk-functions.cmake)

# -------------------------------------------------------------------------------------------------
# mesdk::sdk: the generated SDK (namespace Classes, #include <ME_SDK.hpp>)

file(GLOB MESDK_SDK_SOURCES CONFIGURE_DEPENDS "${MESDK_SDK_DIR}/ME_*.cpp")
file(GLOB MESDK_SDK_HEADERS CONFIGURE_DEPENDS "${MESDK_SDK_DIR}/ME_*.hpp")

add_library(mesdk_sdk STATIC ${MESDK_SDK_SOURCES} ${MESDK_SDK_HEADERS})
add_library(mesdk::sdk ALIAS mesdk_sdk)
set_target_properties(mesdk_sdk PROPERTIES EXPORT_NAME sdk OUTPUT_NAME mesdk_sdk)

target_compile_features(mesdk_sdk PUBLIC cxx_std_17)

# The generated *_parameters.hpp headers include "../sdk.h", so the include directory must keep the
# fork's layout: <dir>/sdk.h next to <dir>/sdk/ME_*.hpp. Installed: include/mesdk/sdk.h, include/mesdk/sdk/.
# SYSTEM: warnings from generated code don't show up in consumers' -Wall / /W4 builds.
target_include_directories(mesdk_sdk SYSTEM PUBLIC
  "$<BUILD_INTERFACE:${MESDK_SDK_DIR}>"
  "$<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}/mesdk/sdk>")

if(MSVC)
  target_compile_options(mesdk_sdk PRIVATE /w /bigobj)
else()
  # ME_TdGame_functions.cpp and ME_Engine_functions.cpp exceed the default COFF section limit
  target_compile_options(mesdk_sdk PRIVATE -w $<$<BOOL:${MINGW}>:-Wa,-mbig-obj>)
endif()

source_group("SDK Headers" FILES ${MESDK_SDK_HEADERS})
source_group("SDK Sources" FILES ${MESDK_SDK_SOURCES})

# -------------------------------------------------------------------------------------------------
# mesdk::mesdk: the SDK plus runtime helpers (#include <mesdk/mesdk.hpp>)

# The fork's Pattern and Hook helpers are exposed as <mesdk/pattern.h> and <mesdk/hook.h>
set(MESDK_GENERATED_INCLUDE_DIR "${CMAKE_CURRENT_BINARY_DIR}/include")
configure_file("${MESDK_MMULTIPLAYER_DIR}/Client/pattern.h"
  "${MESDK_GENERATED_INCLUDE_DIR}/mesdk/pattern.h" COPYONLY)
configure_file("${MESDK_MMULTIPLAYER_DIR}/Client/hook.h"
  "${MESDK_GENERATED_INCLUDE_DIR}/mesdk/hook.h" COPYONLY)
configure_file(cmake/version.hpp.in "${MESDK_GENERATED_INCLUDE_DIR}/mesdk/version.hpp" @ONLY)

add_library(mesdk_mesdk STATIC
  src/mesdk.cpp
  "${MESDK_MMULTIPLAYER_DIR}/Client/pattern.cpp"
  "${MESDK_MMULTIPLAYER_DIR}/Client/hook.cpp"
  include/mesdk/mesdk.hpp)
add_library(mesdk::mesdk ALIAS mesdk_mesdk)
set_target_properties(mesdk_mesdk PROPERTIES EXPORT_NAME mesdk OUTPUT_NAME mesdk)

target_include_directories(mesdk_mesdk PUBLIC
  "$<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>"
  "$<BUILD_INTERFACE:${MESDK_GENERATED_INCLUDE_DIR}>"
  "$<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>")
target_include_directories(mesdk_mesdk PRIVATE "${MESDK_MMULTIPLAYER_DIR}/Client")
target_link_libraries(mesdk_mesdk PUBLIC mesdk::sdk PRIVATE psapi)

if(MSVC)
  target_compile_options(mesdk_mesdk PRIVATE /W3)
else()
  target_compile_options(mesdk_mesdk PRIVATE -Wall)
  # hook.cpp comes from the fork as-is; keep its warnings out of the way
  set_source_files_properties("${MESDK_MMULTIPLAYER_DIR}/Client/hook.cpp"
    "${MESDK_MMULTIPLAYER_DIR}/Client/pattern.cpp" PROPERTIES COMPILE_OPTIONS "-w")
endif()

# -------------------------------------------------------------------------------------------------
# Docs, examples, tests

if(MESDK_BUILD_DOCS)
  add_subdirectory(docs)
endif()

if(MESDK_BUILD_SDK_DOCS)
  # Reuse the fork's Doxygen setup (guides, API reference, SDK umbrella header)
  set(ME_SDK_BUILD_LIBRARY OFF CACHE BOOL "" FORCE)
  set(ME_SDK_BUILD_DOCS ON CACHE BOOL "" FORCE)
  add_subdirectory("${MESDK_SDK_DIR}" "${CMAKE_CURRENT_BINARY_DIR}/mmultiplayer-docs")
  add_custom_target(mesdk_sdk_docs)
  add_dependencies(mesdk_sdk_docs me_sdk_docs)
endif()

if(MESDK_BUILD_EXAMPLES)
  add_subdirectory(examples/hello_mod)
endif()

if(MESDK_BUILD_TESTS)
  enable_testing()
  add_subdirectory(tests)
endif()

# -------------------------------------------------------------------------------------------------
# Install / package

if(MESDK_INSTALL)
  include(CMakePackageConfigHelpers)

  install(TARGETS mesdk_sdk mesdk_mesdk EXPORT mesdkTargets
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})

  install(FILES ${MESDK_SDK_HEADERS} DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}/mesdk/sdk)
  install(FILES "${MESDK_MMULTIPLAYER_DIR}/Client/sdk.h" DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}/mesdk)
  install(DIRECTORY include/mesdk "${MESDK_GENERATED_INCLUDE_DIR}/mesdk"
    DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})

  set(MESDK_INSTALL_CMAKEDIR ${CMAKE_INSTALL_LIBDIR}/cmake/mesdk)
  install(EXPORT mesdkTargets NAMESPACE mesdk:: DESTINATION ${MESDK_INSTALL_CMAKEDIR})

  configure_package_config_file(cmake/mesdkConfig.cmake.in
    "${CMAKE_CURRENT_BINARY_DIR}/mesdkConfig.cmake"
    INSTALL_DESTINATION ${MESDK_INSTALL_CMAKEDIR})
  write_basic_package_version_file("${CMAKE_CURRENT_BINARY_DIR}/mesdkConfigVersion.cmake"
    COMPATIBILITY SameMinorVersion)

  install(FILES
    "${CMAKE_CURRENT_BINARY_DIR}/mesdkConfig.cmake"
    "${CMAKE_CURRENT_BINARY_DIR}/mesdkConfigVersion.cmake"
    cmake/mesdk-functions.cmake
    DESTINATION ${MESDK_INSTALL_CMAKEDIR})
  install(FILES cmake/toolchains/mingw-i686.cmake DESTINATION ${MESDK_INSTALL_CMAKEDIR}/toolchains)
endif()
