# Win32 API replacement used for the native macOS build.
set(WIN32SHIM_SRC
    src/cursor.cpp
    src/gdi.cpp
    src/kernel.cpp
    src/log.cpp
    src/registry.cpp
    src/user.cpp
)

add_library(deps_win32shim STATIC ${WIN32SHIM_SRC})

target_include_directories(deps_win32shim PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_include_directories(deps_win32shim PUBLIC ${CMAKE_SOURCE_DIR}/Dependencies/Utility)
target_compile_features(deps_win32shim PUBLIC cxx_std_20)
target_link_libraries(deps_win32shim PUBLIC
    SDL3::SDL3
    "-framework CoreFoundation"
    "-framework CoreGraphics"
    "-framework CoreText"
    "-framework IOKit"
)

add_executable(win32shim_test EXCLUDE_FROM_ALL tests/shimtest.cpp)
target_link_libraries(win32shim_test PRIVATE deps_win32shim)
target_compile_definitions(win32shim_test PRIVATE NOMINMAX)
