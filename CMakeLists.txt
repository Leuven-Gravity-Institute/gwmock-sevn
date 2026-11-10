cmake_minimum_required(VERSION 3.15...3.31)
project(gwmock_sevn LANGUAGES CXX)

# SEVN's own options, set before its CMakeLists reads them. Only the binary-evolution
# executable is built, linked statically, so the wheel carries one self-contained program.
set(exe ON CACHE BOOL "" FORCE)
set(bin ON CACHE BOOL "" FORCE)
set(sin OFF CACHE BOOL "" FORCE)
set(staticlib ON CACHE BOOL "" FORCE)
set(sharedlib OFF CACHE BOOL "" FORCE)
set(linklib "static" CACHE STRING "" FORCE)
set(test OFF CACHE BOOL "" FORCE)
set(doc OFF CACHE BOOL "" FORCE)
set(h5 OFF CACHE BOOL "" FORCE)
# OpenMP is off: Apple's compiler has no OpenMP runtime to link, and a population run is
# parallelised by running several SEVN processes instead (see gwmock_sevn.evolve).
set(openmp OFF CACHE BOOL "" FORCE)

# The SEVN commit the vendored source came from, reported by the program as its own (patch 0002).
file(STRINGS extern/sevn/VENDORED _vendored_commit REGEX "^commit = ")
string(REGEX REPLACE "^commit = " "" SEVN_VENDORED_COMMIT "${_vendored_commit}")

add_subdirectory(extern/sevn)

# Only these are installed into the wheel. SEVN's own install rules (libraries, headers,
# CMake package files) carry no component and are left out by tool.scikit-build.install.components.
install(TARGETS sevnB.x RUNTIME DESTINATION gwmock_sevn/bin COMPONENT gwmock_sevn)
install(DIRECTORY extern/sevn/auxiliary_data DESTINATION gwmock_sevn/data COMPONENT gwmock_sevn)
install(FILES extern/sevn/LICENSE DESTINATION gwmock_sevn/data RENAME SEVN_LICENSE COMPONENT gwmock_sevn)
install(FILES extern/sevn/VENDORED DESTINATION gwmock_sevn/data COMPONENT gwmock_sevn)
