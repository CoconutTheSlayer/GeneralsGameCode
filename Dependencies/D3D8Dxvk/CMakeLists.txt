# Direct3D 8 for Linux on DXVK (Vulkan). libdxvk_d3d8.so is loaded at run time, so the game also
# runs headless without it. wrappers.inc is generated from d3d8.h by generate_wrappers.py.
set(D3D8METAL_DIR ${CMAKE_SOURCE_DIR}/Dependencies/D3D8Metal)
add_library(d3d8dxvk STATIC
    dxvk_adapter.cpp
    wrappers.inc
    ${D3D8METAL_DIR}/src/d3dx8.cpp
    ${D3D8METAL_DIR}/src/formats.cpp
    ${D3D8METAL_DIR}/src/shadergen.cpp
    ${D3D8METAL_DIR}/src/shadertrans.cpp
)
target_include_directories(d3d8dxvk PUBLIC ${D3D8METAL_DIR}/include ${DX8_SDK_DIR})
target_include_directories(d3d8dxvk PRIVATE ${CMAKE_CURRENT_SOURCE_DIR} ${D3D8METAL_DIR}/src ${CMAKE_SOURCE_DIR}/Dependencies/Utility)
target_compile_features(d3d8dxvk PUBLIC cxx_std_20)
target_compile_definitions(d3d8dxvk PRIVATE NOMINMAX)
target_link_libraries(d3d8dxvk PUBLIC deps_win32shim stb dl)

add_library(d3d8lib INTERFACE)
target_link_libraries(d3d8lib INTERFACE d3d8dxvk)
target_compile_definitions(d3d8lib INTERFACE BUILD_WITH_D3D8)
