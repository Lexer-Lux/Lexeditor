cmake_minimum_required(VERSION 3.20)
project(LexeditorFF7RRuntimeContract LANGUAGES CXX)

enable_testing()

add_executable(ff7r_runtime_contract_test runtime_contract_test.cpp)
target_compile_features(ff7r_runtime_contract_test PRIVATE cxx_std_20)
if(MSVC)
    target_compile_options(ff7r_runtime_contract_test PRIVATE /W4 /WX)
else()
    target_compile_options(ff7r_runtime_contract_test PRIVATE -Wall -Wextra -Wpedantic -Werror)
endif()

add_test(NAME ff7r_runtime_contract COMMAND ff7r_runtime_contract_test)
