# Finds the FFmpeg libraries through pkg-config (Homebrew) for the macOS build.
find_package(PkgConfig REQUIRED)
pkg_check_modules(FFMPEG_PC IMPORTED_TARGET libavformat libavcodec libavutil libswscale libswresample)

if(FFMPEG_PC_FOUND)
    set(FFMPEG_FOUND TRUE)
    set(FFMPEG_INCLUDE_DIRS ${FFMPEG_PC_INCLUDE_DIRS})
    set(FFMPEG_LIBRARY_DIRS ${FFMPEG_PC_LIBRARY_DIRS})
    set(FFMPEG_LIBRARIES PkgConfig::FFMPEG_PC)
endif()

include(FindPackageHandleStandardArgs)
find_package_handle_standard_args(FFMPEG DEFAULT_MSG FFMPEG_LIBRARIES)
