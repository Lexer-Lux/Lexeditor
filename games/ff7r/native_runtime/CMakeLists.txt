cmake_minimum_required(VERSION 3.20)
project(LexeditorFF7RRuntimeContract LANGUAGES CXX)

enable_testing()

add_executable(ff7r_runtime_contract_test runtime_contract_test.cpp)
target_compile_features(ff7r_runtime_contract_test PRIVATE cxx_std_20)
if(MSVC)
    target_compile_options(ff7r_runtime_contract_test PRIVATE /W4 /WX /permissive- /utf-8)
else()
    target_compile_options(ff7r_runtime_contract_test PRIVATE -Wall -Wextra -Wpedantic -Werror)
endif()
add_test(NAME ff7r_runtime_contract COMMAND ff7r_runtime_contract_test)

if(WIN32)
    add_library(LexeditorFF7RRuntimeProbe SHARED RuntimeProbe.cpp)
    target_compile_features(LexeditorFF7RRuntimeProbe PRIVATE cxx_std_20)
    target_compile_definitions(LexeditorFF7RRuntimeProbe PRIVATE
        UNICODE
        _UNICODE
        WIN32_LEAN_AND_MEAN
        NOMINMAX
    )
    if(MSVC)
        target_compile_options(LexeditorFF7RRuntimeProbe PRIVATE /W4 /WX /permissive- /utf-8)
    endif()
    set_target_properties(LexeditorFF7RRuntimeProbe PROPERTIES PREFIX "")
endif()
