CPMAddPackage(
  NAME Catch2
  GITHUB_REPOSITORY catchorg/Catch2
  VERSION 3.16.1
  OPTIONS "CATCH_INSTALL_DOCS OFF" "CATCH_INSTALL_EXTRAS OFF")

add_executable(mesdk_tests
  layout.cpp
  runtime.cpp
  pattern.cpp)
target_link_libraries(mesdk_tests PRIVATE mesdk::mesdk Catch2::Catch2WithMain)
if(MINGW)
  target_link_options(mesdk_tests PRIVATE -static)
endif()

# Runs through CMAKE_CROSSCOMPILING_EMULATOR (Wine) when cross-compiling. PRE_TEST: the test list is
# read when ctest runs, not after every build, so building doesn't start Wine.
if(NOT CMAKE_CROSSCOMPILING OR CMAKE_CROSSCOMPILING_EMULATOR)
  list(APPEND CMAKE_MODULE_PATH "${Catch2_SOURCE_DIR}/extras")
  include(Catch)
  if(CMAKE_CROSSCOMPILING_EMULATOR MATCHES "wine")
    set_target_properties(mesdk_tests PROPERTIES CROSSCOMPILING_EMULATOR
      "${CMAKE_CURRENT_SOURCE_DIR}/wine-catch2.sh;${CMAKE_CROSSCOMPILING_EMULATOR}")
  endif()
  catch_discover_tests(mesdk_tests
    DISCOVERY_MODE PRE_TEST
    PROPERTIES ENVIRONMENT "WINEDEBUG=-all")
endif()
