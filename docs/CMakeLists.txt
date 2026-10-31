# mesdk_docs: Doxygen API reference for mesdk itself (include/mesdk), with the README as the main
# page. The generated SDK (namespace Classes) is documented by the fork's docs: MESDK_BUILD_SDK_DOCS.

find_package(Doxygen OPTIONAL_COMPONENTS dot)
if(NOT DOXYGEN_FOUND)
  message(WARNING "mesdk: Doxygen not found, so there is no mesdk_docs target "
    "(sudo apt install doxygen graphviz, or -DMESDK_BUILD_DOCS=OFF)")
  return()
endif()

set(DOXYGEN_PROJECT_NAME "mesdk")
set(DOXYGEN_PROJECT_NUMBER "${PROJECT_VERSION}")
set(DOXYGEN_PROJECT_BRIEF "${PROJECT_DESCRIPTION}")
set(DOXYGEN_OUTPUT_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}")
set(DOXYGEN_USE_MDFILE_AS_MAINPAGE "${PROJECT_SOURCE_DIR}/README.md")
set(DOXYGEN_STRIP_FROM_PATH "${PROJECT_SOURCE_DIR}/include" "${MESDK_GENERATED_INCLUDE_DIR}")
set(DOXYGEN_STRIP_FROM_INC_PATH "${PROJECT_SOURCE_DIR}/include" "${MESDK_GENERATED_INCLUDE_DIR}")
set(DOXYGEN_EXTRACT_ALL YES)
set(DOXYGEN_EXTRACT_STATIC YES)
set(DOXYGEN_GENERATE_TREEVIEW YES)
set(DOXYGEN_WARN_IF_UNDOCUMENTED NO)
set(DOXYGEN_WARN_NO_PARAMDOC NO)
set(DOXYGEN_QUIET YES)
set(DOXYGEN_ENABLE_PREPROCESSING YES)
set(DOXYGEN_MACRO_EXPANSION YES)
set(DOXYGEN_EXPAND_ONLY_PREDEF YES)
# Calling conventions are Windows-only keywords Doxygen doesn't know
set(DOXYGEN_PREDEFINED "__fastcall=" "__thiscall=" "__stdcall=" "__cdecl=")
set(DOXYGEN_EXCLUDE_SYMBOLS "Classes" "Classes::*")
if(DOXYGEN_DOT_FOUND)
  set(DOXYGEN_HAVE_DOT YES)
endif()

doxygen_add_docs(mesdk_docs
  "${PROJECT_SOURCE_DIR}/README.md"
  "${PROJECT_SOURCE_DIR}/include/mesdk"
  "${MESDK_GENERATED_INCLUDE_DIR}/mesdk/version.hpp"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  COMMENT "Generating the mesdk API docs: ${CMAKE_CURRENT_BINARY_DIR}/html/index.html")
