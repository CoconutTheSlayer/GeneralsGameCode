# Direct3D 8 without a device for headless Linux builds. The graphical build will use DXVK.
set(D3D8METAL_DIR ${CMAKE_SOURCE_DIR}/Dependencies/D3D8Metal)
add_library(d3d8null STATIC
    null.cpp
    ${D3D8METAL_DIR}/src/d3dx8.cpp
    ${D3D8METAL_DIR}/src/formats.cpp
    ${D3D8METAL_DIR}/src/shadergen.cpp
    ${D3D8METAL_DIR}/src/shadertrans.cpp
)
target_include_directories(d3d8null PUBLIC ${D3D8METAL_DIR}/include ${DX8_SDK_DIR})
target_include_directories(d3d8null PRIVATE ${D3D8METAL_DIR}/src ${CMAKE_SOURCE_DIR}/Dependencies/Utility)
target_compile_features(d3d8null PUBLIC cxx_std_20)
target_compile_definitions(d3d8null PRIVATE NOMINMAX)
target_link_libraries(d3d8null PUBLIC deps_win32shim stb)

add_library(d3d8lib INTERFACE)
target_link_libraries(d3d8lib INTERFACE d3d8null)
target_compile_definitions(d3d8lib INTERFACE BUILD_WITH_D3D8)
