// Lexeditor's path correction for the pinned DSR ModEngine2 launcher.
// This helper does not change file-redirection or injection behavior.
#pragma once

#include <filesystem>
#include <stdexcept>

namespace lexeditor_ds1 {

inline std::filesystem::path application_root(
    const std::filesystem::path& executable,
    const std::filesystem::path& relative_executable)
{
    // The upstream launch table supplies the relative executable. DSR has one
    // component; DS3, ER and AC6 currently have two ("Game/<executable>").
    if (relative_executable.empty() || relative_executable.has_root_path()) {
        throw std::invalid_argument("Expected a relative executable path");
    }

    auto root = std::filesystem::absolute(executable).lexically_normal();
    for (const auto& component : relative_executable) {
        if (component.empty() || component == "." || component == "..") {
            throw std::invalid_argument("Invalid relative executable component");
        }
        root = root.parent_path();
    }
    return root;
}

} // namespace lexeditor_ds1
