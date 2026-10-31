include_guard(GLOBAL)

#[=======================================================================[.rst:
mesdk_add_mod
-------------

Adds a mod: a DLL that is loaded into MirrorsEdge.exe and links mesdk::mesdk.

  mesdk_add_mod(<name> [OUTPUT_NAME <file name without .dll>] <sources>...)

The DLL has no "lib" prefix, and with MinGW it links libgcc/libstdc++/winpthread statically so it
needs no extra DLLs next to the game. Add more libraries with target_link_libraries as usual.
#]=======================================================================]
function(mesdk_add_mod name)
  cmake_parse_arguments(PARSE_ARGV 1 ARG "" "OUTPUT_NAME" "")
  if(NOT ARG_OUTPUT_NAME)
    set(ARG_OUTPUT_NAME ${name})
  endif()

  add_library(${name} SHARED ${ARG_UNPARSED_ARGUMENTS})
  target_link_libraries(${name} PRIVATE mesdk::mesdk)
  set_target_properties(${name} PROPERTIES PREFIX "" OUTPUT_NAME ${ARG_OUTPUT_NAME})

  if(MINGW)
    target_link_options(${name} PRIVATE -static -static-libgcc -static-libstdc++)
  endif()
endfunction()
