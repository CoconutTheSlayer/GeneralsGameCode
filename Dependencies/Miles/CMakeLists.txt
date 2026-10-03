if(APPLE)
    # Miles is implemented on SDL3 audio and AudioToolbox on macOS.
    set(MILES_SRC
        mss/mss.h
        MilesLoader.h
        MilesMac.cpp
    )
else()
    set(MILES_SRC
        mss/mss.h
        MilesLoader.cpp
        MilesLoader.h
    )
endif()

add_library(deps_miles STATIC)

target_sources(deps_miles PRIVATE ${MILES_SRC})

target_include_directories(deps_miles PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/mss
)

target_link_libraries(deps_miles PRIVATE
    deps_precompiled # Gives force included headers. Link early.
    deps_utility
)

if(APPLE)
    target_link_libraries(deps_miles PUBLIC SDL3::SDL3 "-framework AudioToolbox" "-framework CoreFoundation")
    target_compile_definitions(deps_miles PRIVATE NOMINMAX)
endif()

if(APPLE)
    add_executable(miles_test EXCLUDE_FROM_ALL tests/milestest.cpp)
    target_link_libraries(miles_test PRIVATE deps_miles)
endif()
