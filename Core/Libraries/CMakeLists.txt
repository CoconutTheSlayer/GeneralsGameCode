# Base headers shared by all libraries
add_subdirectory(Include)

# WW common libraries decended from earliest C&C games
add_subdirectory(Source/WWVegas)

# profiling library
add_subdirectory(Source/profile)

# debugging library
if(NOT RTS_POSIX_PORT)
    add_subdirectory(Source/debug)
    add_subdirectory(Source/EABrowserDispatch)
    add_subdirectory(Source/EABrowserEngine)
else()
    # The embedded browser is not available on macOS.
    add_library(core_browserdispatch INTERFACE)
    add_library(core_browserengine INTERFACE)
endif()
add_subdirectory(Source/Compression)
