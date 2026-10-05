# Native macOS (Apple Silicon) build settings.

list(PREPEND CMAKE_MODULE_PATH "${CMAKE_SOURCE_DIR}/cmake/macos")

find_package(SDL3 REQUIRED CONFIG)

# Legacy code base: silence the noisiest warnings so real errors stand out.
add_compile_options(
    -ferror-limit=0
    -Wno-deprecated-declarations
    -Wno-deprecated-register
    -Wno-dangling-else
    -Wno-switch
    -Wno-parentheses
    -Wno-format
    -Wno-char-subscripts
    -Wno-unused-value
    -Wno-writable-strings
    -Wno-inconsistent-missing-override
    -Wno-suggest-override
    -Wno-microsoft-cast
    -Wno-int-to-pointer-cast
    -Wno-shift-negative-value
    -Wno-null-conversion
    -Wno-ignored-attributes
    -Wno-unknown-pragmas
    -Wno-c++11-narrowing
    -Wno-comment
    -Wno-invalid-offsetof
    -Wno-nonportable-include-path
    -Wno-undefined-var-template
)

# Deterministic simulation across platforms and CPUs (crossplay, replays): never fuse a multiply and
# an add into one differently rounded operation, and take sin, cos, pow and the like from
# Dependencies/DetMath instead of the platform's C library.
add_compile_options(-ffp-contract=off)
set(RTS_DETMATH_HEADER "${CMAKE_SOURCE_DIR}/Dependencies/DetMath/include/rts_detmath.h")
add_compile_options("$<$<COMPILE_LANGUAGE:C,CXX>:SHELL:-include ${RTS_DETMATH_HEADER}>")
add_subdirectory(Dependencies/DetMath)

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

add_subdirectory(Dependencies/Win32Shim)

# DirectX 8 SDK headers only; the implementation is our Metal backend.
FetchContent_Declare(
    dx8
    GIT_REPOSITORY https://github.com/TheSuperHackers/min-dx8-sdk.git
    GIT_TAG        7bddff8c01f5fb931c3cb73d4aa8e66d303d97bc
    SOURCE_SUBDIR  do-not-add-subdirectory
    PATCH_COMMAND  ${CMAKE_COMMAND} -P ${CMAKE_SOURCE_DIR}/cmake/macos/patch_dx8.cmake
    UPDATE_DISCONNECTED TRUE
)
FetchContent_MakeAvailable(dx8)
set(DX8_SDK_DIR ${dx8_SOURCE_DIR})

add_subdirectory(Dependencies/D3D8Metal)
