# Template for your own mod/tool. Copy this folder out of the mesdk repo and build it with:
#
#   cmake --preset release && cmake --build --preset release
cmake_minimum_required(VERSION 3.21)
project(my_mod LANGUAGES CXX)

include(cmake/CPM.cmake)

# Pin a tag or commit of mesdk. Use a local checkout instead with -DCPM_mesdk_SOURCE=/path/to/mesdk
CPMAddPackage(
  NAME mesdk
  GITHUB_REPOSITORY connorfrancey/mesdk
  GIT_TAG v0.1.0)

# A DLL for MirrorsEdge.exe, linked against mesdk::mesdk (use add_library/add_executable and
# target_link_libraries(... mesdk::mesdk) or mesdk::sdk directly for anything else)
mesdk_add_mod(my_mod src/main.cpp)
