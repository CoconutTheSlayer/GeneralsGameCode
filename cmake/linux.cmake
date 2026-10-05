# Native Linux build settings.

list(PREPEND CMAKE_MODULE_PATH "${CMAKE_SOURCE_DIR}/cmake/macos")

# GCC's C++ library breaks on Windows style min and max macros (libc++ guards against them).
add_compile_definitions(NOMINMAX)

include(${CMAKE_SOURCE_DIR}/cmake/posix.cmake)

# GCC warnings the legacy code base triggers in large numbers.
if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
    add_compile_options(-fpermissive -Wno-narrowing -Wno-write-strings -Wno-multichar)
endif()

# Graphics: a stand in for Direct3D 8 that is enough for headless runs (replays, servers).
# The graphical build will use DXVK (Direct3D 8 on Vulkan).
add_subdirectory(Dependencies/D3D8Null)
