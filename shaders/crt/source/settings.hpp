// SPDX-License-Identifier: MIT
// The editable preset: a RetroArch-style wrapper that references the original
// chain and overrides some of its parameters, e.g.
//
//     #reference "PS1-original.slangp"
//     HSM_INTRO_WHEN_TO_SHOW = "0"
//
// RetroArch and librashader both load it, so settings saved from the ReShade
// overlay are the same settings RetroArch sees.
#pragma once
#include <cmath>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <map>
#include <regex>
#include <sstream>
#include <string>
#include <algorithm>
#include <vector>

namespace lexer_crt {

struct Param {
    std::string name, label;
    float value = 0;     // live value in the running chain
    float saved = 0;     // value in the wrapper file on disk
    float base = 0;      // value in the referenced original preset
    float minimum = 0, maximum = 0, step = 0;
    // Mega Bezel lays its settings out with parameters: "[ SECTION ]" labels
    // are titles and blank labels are spacers. Neither is a real setting.
    bool heading() const { return !label.empty() && label.front() == '[' && maximum - minimum <= 0.0011f; }
    bool spacer() const { return label.empty() || (minimum == maximum && !heading()); }
    bool setting() const { return !heading() && !spacer(); }
};

struct Wrapper {
    std::string reference;                         // path as written after #reference
    std::vector<std::string> comments;             // other lines, kept in order
    std::map<std::string, std::string> overrides;  // NAME -> value
};

inline std::string trim(std::string s) {
    auto first = s.find_first_not_of(" \t\r\n");
    auto last = s.find_last_not_of(" \t\r\n");
    return first == std::string::npos ? std::string() : s.substr(first, last - first + 1);
}

inline Wrapper read_wrapper(const std::filesystem::path& path) {
    Wrapper wrapper;
    std::ifstream file(path);
    static const std::regex reference(R"re(^#reference\s+"?([^"]+)"?$)re");
    static const std::regex assignment(R"re(^([A-Za-z0-9_]+)\s*=\s*"?([^"]*)"?$)re");
    for (std::string line; std::getline(file, line);) {
        line = trim(line);
        std::smatch match;
        if (std::regex_match(line, match, reference)) wrapper.reference = match[1];
        else if (std::regex_match(line, match, assignment)) wrapper.overrides[match[1]] = match[2];
        else if (!line.empty()) wrapper.comments.push_back(line);
    }
    return wrapper;
}

inline std::string format_value(float value) {
    char text[32];
    std::snprintf(text, sizeof text, "%.6g", value);
    return text;
}

// Write through a temporary file so a crash never leaves a half-written preset.
inline void write_wrapper(const std::filesystem::path& path, const Wrapper& wrapper) {
    std::ostringstream text;
    text << "#reference \"" << wrapper.reference << "\"\n";
    for (const auto& line : wrapper.comments) text << line << "\n";
    for (const auto& [name, value] : wrapper.overrides) text << name << " = \"" << value << "\"\n";
    auto temporary = path;
    temporary += ".tmp";
    {
        std::ofstream file(temporary, std::ios::binary | std::ios::trunc);
        file << text.str();
        if (!file) throw std::runtime_error("Could not write " + temporary.u8string());
    }
    std::filesystem::rename(temporary, path);
}

// Keep an override only where the value differs from the original chain.
inline void store(Wrapper& wrapper, const std::vector<Param>& params) {
    for (const auto& param : params) {
        if (!param.setting()) continue;
        if (std::fabs(param.value - param.base) > 1e-6f) wrapper.overrides[param.name] = format_value(param.value);
        else wrapper.overrides.erase(param.name);
    }
}

// The order the chain declares its parameters in: pass by pass (shader0,
// shader1, ...), following #include, first appearance wins. librashader lists
// them in no particular order, which scattered section titles.
inline void collect_parameters(const std::filesystem::path& file, std::vector<std::string>& order,
                               std::vector<std::filesystem::path>& visited) {
    auto canonical = std::filesystem::weakly_canonical(file);
    for (const auto& seen : visited) if (seen == canonical) return;
    visited.push_back(canonical);
    std::ifstream stream(file);
    static const std::regex include(R"re(^\s*#include\s+"([^"]+)")re");
    static const std::regex parameter(R"re(^\s*#pragma\s+parameter\s+([A-Za-z0-9_]+))re");
    for (std::string line; std::getline(stream, line);) {
        std::smatch match;
        if (std::regex_search(line, match, include)) collect_parameters(file.parent_path() / std::filesystem::u8path(match[1].str()), order, visited);
        else if (std::regex_search(line, match, parameter)) {
            const std::string name = match[1];
            if (std::find(order.begin(), order.end(), name) == order.end()) order.push_back(name);
        }
    }
}

inline std::vector<std::string> parameter_order(std::filesystem::path preset) {
    static const std::regex shader(R"re(^\s*shader(\d+)\s*=\s*"?([^"]+?)"?\s*$)re");
    static const std::regex reference(R"re(^\s*#reference\s+"?([^"]+?)"?\s*$)re");
    for (int depth = 0; depth < 8; ++depth) {
        std::map<int, std::filesystem::path> passes;
        std::filesystem::path next;
        std::ifstream stream(preset);
        for (std::string line; std::getline(stream, line);) {
            std::smatch match;
            if (std::regex_match(line, match, shader)) passes[std::stoi(match[1])] = preset.parent_path() / std::filesystem::u8path(match[2].str());
            else if (std::regex_match(line, match, reference)) next = preset.parent_path() / std::filesystem::u8path(match[1].str());
        }
        if (!passes.empty()) {
            std::vector<std::string> order;
            std::vector<std::filesystem::path> visited;
            for (const auto& [index, path] : passes) collect_parameters(path, order, visited);
            return order;
        }
        if (next.empty()) break;
        preset = next;
    }
    return {};
}

}  // namespace lexer_crt
