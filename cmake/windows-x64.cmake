# Windows x64 build (MinGW-w64 with clang). The game runs on the Win32 API as on 32-bit Windows, but
# with the cross platform pieces of the macOS and Linux ports: the simulation computes the same
# results as on the other platforms, audio is SDL3, and Direct3D 8 comes from D3D8.DLL at run time,
# which is DXVK's (Vulkan) when shipped next to the executable.

find_package(SDL3 REQUIRED CONFIG)

add_compile_definitions(DIRECTINPUT_VERSION=0x0800)

# Deterministic simulation across platforms and CPUs (see cmake/posix.cmake).
add_compile_options(-ffp-contract=off)
set(RTS_DETMATH_HEADER "${CMAKE_SOURCE_DIR}/Dependencies/DetMath/include/rts_detmath.h")
add_compile_options("$<$<COMPILE_LANGUAGE:C,CXX>:SHELL:-include ${RTS_DETMATH_HEADER}>")
add_subdirectory(Dependencies/DetMath)
link_libraries(detmath)

# DirectX 8 SDK headers only: its libraries are 32-bit.
FetchContent_Declare(
    dx8
    GIT_REPOSITORY https://github.com/TheSuperHackers/min-dx8-sdk.git
    GIT_TAG        7bddff8c01f5fb931c3cb73d4aa8e66d303d97bc
    SOURCE_SUBDIR  do-not-add-subdirectory
    UPDATE_DISCONNECTED TRUE
)
FetchContent_MakeAvailable(dx8)
set(DX8_SDK_DIR ${dx8_SOURCE_DIR})

# D3DX 8 from the macOS port; Direct3D itself is loaded at run time.
set(D3D8METAL_DIR ${CMAKE_SOURCE_DIR}/Dependencies/D3D8Metal)
add_library(d3dx8_portable STATIC
    ${D3D8METAL_DIR}/src/d3dx8.cpp
    ${D3D8METAL_DIR}/src/formats.cpp
    ${D3D8METAL_DIR}/src/shadergen.cpp
    ${D3D8METAL_DIR}/src/shadertrans.cpp
)
target_include_directories(d3dx8_portable PUBLIC ${DX8_SDK_DIR})
target_include_directories(d3dx8_portable PRIVATE ${D3D8METAL_DIR}/src ${CMAKE_SOURCE_DIR}/Dependencies/Utility)
target_compile_features(d3dx8_portable PUBLIC cxx_std_20)
target_compile_definitions(d3dx8_portable PRIVATE NOMINMAX)
target_link_libraries(d3dx8_portable PRIVATE stb)

add_library(d3d8lib INTERFACE)
target_link_libraries(d3d8lib INTERFACE d3dx8_portable)
target_compile_definitions(d3d8lib INTERFACE BUILD_WITH_D3D8)

# Names the Windows executables link; both are provided above.
add_library(d3d8 INTERFACE)
add_library(d3dx8 INTERFACE)
target_link_libraries(d3dx8 INTERFACE d3dx8_portable)
