# Deterministic transcendental math functions from musl libc (MIT, see COPYRIGHT.musl), so the game
# simulation computes the same results on every platform. include/rts_detmath.h is included in front
# of every source file and redirects the standard function names here.
file(GLOB DETMATH_SRC CONFIGURE_DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/src/*.c)
add_library(detmath STATIC ${DETMATH_SRC})
target_include_directories(detmath PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)
set_target_properties(detmath PROPERTIES C_STANDARD 11)
if(MSVC)
    target_compile_options(detmath PRIVATE /fp:precise /fp:contract- /w)
else()
    target_compile_options(detmath PRIVATE -ffp-contract=off -fno-fast-math -w)
endif()
