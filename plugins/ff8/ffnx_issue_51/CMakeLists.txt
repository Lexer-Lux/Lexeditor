cmake_minimum_required(VERSION 3.20)
project(lexeditor_ff8_shared_magic_core LANGUAGES CXX)

add_executable(
    verify_shared_magic_core
    shared_magic_core.cpp
    shared_magic_core_test.cpp
)
target_compile_features(verify_shared_magic_core PRIVATE cxx_std_17)

enable_testing()
add_test(NAME shared_magic_core COMMAND verify_shared_magic_core)

