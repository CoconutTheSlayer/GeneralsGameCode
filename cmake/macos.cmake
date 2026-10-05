# Native macOS (Apple Silicon) build settings.

list(PREPEND CMAKE_MODULE_PATH "${CMAKE_SOURCE_DIR}/cmake/macos")

include(${CMAKE_SOURCE_DIR}/cmake/posix.cmake)

# Tune for Apple Silicon. All Apple Silicon Macs implement the M1 feature set.
if(CMAKE_OSX_ARCHITECTURES STREQUAL "arm64" OR (NOT CMAKE_OSX_ARCHITECTURES AND CMAKE_SYSTEM_PROCESSOR STREQUAL "arm64"))
    add_compile_options(-mcpu=apple-m1)
endif()

# ThinLTO for optimized builds. The cache keeps relinks fast and holds the LTO
# object files that the debug map of RelWithDebInfo builds refers to.
option(RTS_BUILD_OPTION_MACOS_LTO "Use ThinLTO for optimized macOS builds (drops the replaced operator delete, crashes)" OFF)
if(RTS_BUILD_OPTION_MACOS_LTO)
    add_compile_options("$<$<CONFIG:Release,RelWithDebInfo,MinSizeRel>:-flto=thin>")
    add_link_options(
        "$<$<CONFIG:Release,RelWithDebInfo,MinSizeRel>:-flto=thin>"
        "$<$<CONFIG:Release,RelWithDebInfo,MinSizeRel>:LINKER:-cache_path_lto,${CMAKE_BINARY_DIR}/lto-cache>"
    )
endif()

add_subdirectory(Dependencies/D3D8Metal)
