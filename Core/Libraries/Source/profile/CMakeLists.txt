set(PROFILE_SRC
    "Include/profile/profile_doc.h"
    "Include/profile/profile_funclevel.h"
    "Include/profile/profile_highlevel.h"
    "Include/profile/profile_result.h"
    "Include/profile/profile.h"
    "internal_cmd.h"
    "internal_funclevel.h"
    "internal_highlevel.h"
    "internal_result.h"
    "internal.h"
    "profile_cmd.cpp"
    "profile_funclevel.cpp"
    "profile_highlevel.cpp"
    "profile_result.cpp"
    "profile.cpp"
)

# The legacy profiler is x86 code; the other builds have no profiler.
if(RTS_POSIX_PORT OR IS_MINGW64)
    add_library(core_profile_legacy STATIC profile_macos.cpp)
    target_include_directories(core_profile_legacy PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/Include)
    target_link_libraries(core_profile_legacy PRIVATE depsi_always core_config deps_utility)
    return()
endif()

add_library(core_profile_legacy STATIC)

target_sources(core_profile_legacy PRIVATE ${PROFILE_SRC})

target_include_directories(core_profile_legacy PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/Include
)

target_precompile_headers(core_profile_legacy PRIVATE
    [["Precompiled/precompiled.h"]] # Must be first
    "Include/profile/profile.h"
    "internal.h"
    <windows.h>
)

target_link_libraries(core_profile_legacy PRIVATE
    depsi_always # Gives force included headers. Link early.
    core_config
    core_debug
    deps_utility
    stlport
)
