# Base headers and debug utilities shared by all libraries
add_subdirectory(Source/Lib)

# WW common libraries decended from earliest C&C games
add_subdirectory(Source/WWVegas)

# profiling library
add_subdirectory(Source/profile)

# debugging library
if(NOT RTS_POSIX_PORT)
    add_subdirectory(Source/debug)
    add_subdirectory(Source/MiniDumper)
    add_subdirectory(Source/EABrowserDispatch)
    add_subdirectory(Source/EABrowserEngine)
else()
    # Native ports use their platform diagnostics and do not embed the Windows browser.
    add_library(core_debug INTERFACE)
    target_include_directories(core_debug INTERFACE ${CMAKE_CURRENT_SOURCE_DIR}/Source/debug/Include)
    add_library(core_minidumper INTERFACE)
    target_include_directories(core_minidumper INTERFACE ${CMAKE_CURRENT_SOURCE_DIR}/Source/MiniDumper/Include)
    add_library(core_browserdispatch INTERFACE)
    add_library(core_browserengine INTERFACE)
endif()
add_subdirectory(Source/Compression)

if(APPLE AND RTS_POSIX_PORT)
    add_executable(native_math_test EXCLUDE_FROM_ALL Tests/native_math_test.cpp)
    target_link_libraries(native_math_test PRIVATE corei_always core_wwcommon detmath)
    target_compile_features(native_math_test PRIVATE cxx_std_20)
    add_executable(cost_bucket_index_test EXCLUDE_FROM_ALL Tests/cost_bucket_index_test.cpp)
    target_include_directories(cost_bucket_index_test PRIVATE Source/Lib/Include)
    target_compile_features(cost_bucket_index_test PRIVATE cxx_std_17)
    target_compile_options(cost_bucket_index_test PRIVATE -UNDEBUG)
    add_executable(visual_jobs_test EXCLUDE_FROM_ALL
        Tests/visual_jobs_test.cpp
        ${CMAKE_SOURCE_DIR}/Dependencies/D3D8Metal/src/profile.cpp)
    target_include_directories(visual_jobs_test PRIVATE Source/Lib/Include
        ${CMAKE_SOURCE_DIR}/Dependencies/D3D8Metal/include)
    target_compile_definitions(visual_jobs_test PRIVATE RTS_POSIX_PORT)
    target_compile_features(visual_jobs_test PRIVATE cxx_std_20)
endif()
