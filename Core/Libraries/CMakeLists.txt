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

if(APPLE AND RTS_POSIX_PORT)
    add_executable(cost_bucket_index_test EXCLUDE_FROM_ALL Tests/cost_bucket_index_test.cpp)
    target_include_directories(cost_bucket_index_test PRIVATE Include)
    target_compile_features(cost_bucket_index_test PRIVATE cxx_std_17)
    target_compile_options(cost_bucket_index_test PRIVATE -UNDEBUG)
    add_executable(visual_jobs_test EXCLUDE_FROM_ALL
        Tests/visual_jobs_test.cpp
        ${CMAKE_SOURCE_DIR}/Dependencies/D3D8Metal/src/profile.cpp)
    target_include_directories(visual_jobs_test PRIVATE Include
        ${CMAKE_SOURCE_DIR}/Dependencies/D3D8Metal/include)
    target_compile_definitions(visual_jobs_test PRIVATE RTS_POSIX_PORT)
    target_compile_features(visual_jobs_test PRIVATE cxx_std_20)
endif()
