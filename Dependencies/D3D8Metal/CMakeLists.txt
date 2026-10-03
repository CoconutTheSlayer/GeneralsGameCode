# Direct3D 8 implemented on Metal for the native macOS build.
set(D3D8METAL_SRC
    src/d3dx8.cpp
    src/device.mm
    src/direct3d.mm
    src/draw.mm
    src/formats.cpp
    src/formats.h
    src/internal.h
    src/resources.mm
    src/shadergen.cpp
    src/shadergen.h
)

add_library(d3d8metal STATIC ${D3D8METAL_SRC})
target_include_directories(d3d8metal PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${DX8_SDK_DIR}
)
target_include_directories(d3d8metal PRIVATE ${CMAKE_SOURCE_DIR}/Dependencies/Utility)
target_compile_features(d3d8metal PUBLIC cxx_std_20)
target_compile_definitions(d3d8metal PRIVATE NOMINMAX)
target_compile_options(d3d8metal PRIVATE "$<$<COMPILE_LANGUAGE:OBJCXX>:-fobjc-arc>")
target_link_libraries(d3d8metal PUBLIC
    deps_win32shim
    SDL3::SDL3
    stb
    "-framework Metal"
    "-framework QuartzCore"
    "-framework Foundation"
)

# Same target name the Windows build gets from the DirectX SDK.
add_library(d3d8lib INTERFACE)
target_link_libraries(d3d8lib INTERFACE d3d8metal)
target_compile_definitions(d3d8lib INTERFACE BUILD_WITH_D3D8)
