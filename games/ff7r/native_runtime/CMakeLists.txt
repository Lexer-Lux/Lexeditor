cmake_minimum_required(VERSION 3.20)
project(LexeditorFF7RRuntimeContract LANGUAGES CXX)

enable_testing()

function(lexeditor_ff7r_test target source test_name)
    add_executable(${target} ${source})
    target_compile_features(${target} PRIVATE cxx_std_20)
    if(MSVC)
        target_compile_options(${target} PRIVATE /W4 /WX /permissive- /utf-8)
    else()
        target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic -Werror)
    endif()
    add_test(NAME ${test_name} COMMAND ${target})
endfunction()

lexeditor_ff7r_test(
    ff7r_runtime_contract_test
    runtime_contract_test.cpp
    ff7r_runtime_contract
)
lexeditor_ff7r_test(
    ff7r_runtime_config_test
    runtime_config_test.cpp
    ff7r_runtime_config
)
lexeditor_ff7r_test(
    ff7r_runtime_signatures_test
    runtime_signatures_test.cpp
    ff7r_runtime_signatures
)
lexeditor_ff7r_test(
    ff7r_runtime_hp_test
    runtime_hp_test.cpp
    ff7r_runtime_hp
)
lexeditor_ff7r_test(
    ff7r_runtime_cutscene_test
    runtime_cutscene_test.cpp
    ff7r_runtime_cutscene
)
lexeditor_ff7r_test(
    ff7r_runtime_minimap_test
    runtime_minimap_test.cpp
    ff7r_runtime_minimap
)

if(WIN32)
    add_library(LexeditorFF7RRuntime SHARED RuntimeMain.cpp)
    target_compile_features(LexeditorFF7RRuntime PRIVATE cxx_std_20)
    target_compile_definitions(LexeditorFF7RRuntime PRIVATE
        UNICODE
        _UNICODE
        WIN32_LEAN_AND_MEAN
        NOMINMAX
    )
    if(MSVC)
        target_compile_options(LexeditorFF7RRuntime PRIVATE /W4 /WX /permissive- /utf-8)
    endif()
    set_target_properties(LexeditorFF7RRuntime PROPERTIES PREFIX "")

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
