cmake_minimum_required(VERSION 3.21)

project(LexeditorFF7RRuntimeProbe VERSION 0.1.0 LANGUAGES CXX)

add_library(LexeditorFF7RRuntimeProbe SHARED
    src/runtime_probe.cpp
)

target_compile_features(LexeditorFF7RRuntimeProbe PRIVATE cxx_std_20)
target_compile_definitions(LexeditorFF7RRuntimeProbe PRIVATE
    UNICODE
    _UNICODE
    WIN32_LEAN_AND_MEAN
    NOMINMAX
)

if(MSVC)
    target_compile_options(LexeditorFF7RRuntimeProbe PRIVATE
        /W4
        /WX
        /permissive-
        /utf-8
        /Zc:__cplusplus
    )
endif()

set_target_properties(LexeditorFF7RRuntimeProbe PROPERTIES
    OUTPUT_NAME "LexeditorFF7RRuntimeProbe"
    PREFIX ""
)
