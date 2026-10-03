# Applied to the fetched DirectX 8 SDK headers for the macOS build: enable the
# declarations that are hidden behind _WIN32.
file(READ d3d8types.h content)
string(REPLACE "#ifdef _WIN32\n    LARGE_INTEGER   DriverVersion;" "#if 1\n    LARGE_INTEGER   DriverVersion;" content "${content}")
file(WRITE d3d8types.h "${content}")

file(READ d3d8.h content)
string(REPLACE "#if defined( _WIN32 ) && !defined( _NO_COM)" "#if !defined( _NO_COM)" content "${content}")
file(WRITE d3d8.h "${content}")
