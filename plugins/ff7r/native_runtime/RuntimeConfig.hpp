#pragma once

#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <string>
#include <string_view>
#include <unordered_set>

namespace lexeditor::ff7r {

struct CutsceneSpeedConfig {
    bool enabled = false;
    double baseMultiplier = 1.25;
};

struct MinimapConfig {
    bool enabled = false;
    std::uint32_t holdMilliseconds = 350;
    bool persistChosenState = true;
};

struct HPRebalanceConfig {
    bool enabled = false;
    double multiplier = 0.5;
};

struct BetterSprintConfig {
    bool enabled = false;
    double multiplier = 1.0;
};

struct RuntimeConfig {
    std::uint32_t schemaVersion = 1;
    CutsceneSpeedConfig cutsceneSpeed;
    MinimapConfig minimap;
    HPRebalanceConfig hpRebalance;
    BetterSprintConfig betterSprint;
};

class RuntimeConfigError : public std::runtime_error {
public:
    using std::runtime_error::runtime_error;
};

namespace detail {

class JsonCursor {
public:
    explicit JsonCursor(std::string_view input) : input_(input) {}

    [[nodiscard]] bool finished() {
        skipWhitespace();
        return position_ == input_.size();
    }

    void expect(char expected) {
        skipWhitespace();
        if (position_ >= input_.size() || input_[position_] != expected) {
            throw RuntimeConfigError(
                std::string("expected '") + expected + "' at byte " + std::to_string(position_));
        }
        ++position_;
    }

    [[nodiscard]] bool consume(char expected) {
        skipWhitespace();
        if (position_ < input_.size() && input_[position_] == expected) {
            ++position_;
            return true;
        }
        return false;
    }

    [[nodiscard]] std::string parseString() {
        skipWhitespace();
        if (position_ >= input_.size() || input_[position_] != '"') {
            throw RuntimeConfigError("expected JSON string at byte " + std::to_string(position_));
        }
        ++position_;
        std::string output;
        while (position_ < input_.size()) {
            const char ch = input_[position_++];
            if (ch == '"') {
                return output;
            }
            if (static_cast<unsigned char>(ch) < 0x20) {
                throw RuntimeConfigError("control character in JSON string");
            }
            if (ch != '\\') {
                output.push_back(ch);
                continue;
            }
            if (position_ >= input_.size()) {
                throw RuntimeConfigError("unterminated JSON escape");
            }
            const char escaped = input_[position_++];
            switch (escaped) {
                case '"': output.push_back('"'); break;
                case '\\': output.push_back('\\'); break;
                case '/': output.push_back('/'); break;
                case 'b': output.push_back('\b'); break;
                case 'f': output.push_back('\f'); break;
                case 'n': output.push_back('\n'); break;
                case 'r': output.push_back('\r'); break;
                case 't': output.push_back('\t'); break;
                default:
                    // Lexeditor's canonical runtime config is ASCII-only. Reject
                    // unicode escapes rather than implementing an incomplete UTF-16
                    // decoder in the native loader.
                    throw RuntimeConfigError("unsupported JSON string escape");
            }
        }
        throw RuntimeConfigError("unterminated JSON string");
    }

    [[nodiscard]] bool parseBoolean() {
        skipWhitespace();
        if (input_.substr(position_, 4) == "true") {
            position_ += 4;
            return true;
        }
        if (input_.substr(position_, 5) == "false") {
            position_ += 5;
            return false;
        }
        throw RuntimeConfigError("expected boolean at byte " + std::to_string(position_));
    }

    [[nodiscard]] std::uint32_t parseUnsignedInteger() {
        skipWhitespace();
        if (position_ >= input_.size() || input_[position_] < '0' || input_[position_] > '9') {
            throw RuntimeConfigError("expected unsigned integer at byte " + std::to_string(position_));
        }
        std::uint64_t value = 0;
        while (position_ < input_.size() && input_[position_] >= '0' && input_[position_] <= '9') {
            value = value * 10 + static_cast<unsigned>(input_[position_] - '0');
            if (value > std::numeric_limits<std::uint32_t>::max()) {
                throw RuntimeConfigError("integer is outside uint32 range");
            }
            ++position_;
        }
        if (position_ < input_.size()
                && (input_[position_] == '.' || input_[position_] == 'e' || input_[position_] == 'E')) {
            throw RuntimeConfigError("expected integer but found floating-point value");
        }
        return static_cast<std::uint32_t>(value);
    }

    [[nodiscard]] double parseNumber() {
        skipWhitespace();
        const std::size_t start = position_;
        if (position_ < input_.size() && input_[position_] == '-') {
            ++position_;
        }
        bool digits = false;
        while (position_ < input_.size() && input_[position_] >= '0' && input_[position_] <= '9') {
            digits = true;
            ++position_;
        }
        if (position_ < input_.size() && input_[position_] == '.') {
            ++position_;
            bool fractionDigits = false;
            while (position_ < input_.size() && input_[position_] >= '0' && input_[position_] <= '9') {
                fractionDigits = true;
                ++position_;
            }
            if (!fractionDigits) {
                throw RuntimeConfigError("invalid JSON number fraction");
            }
        }
        if (!digits) {
            throw RuntimeConfigError("expected number at byte " + std::to_string(start));
        }
        if (position_ < input_.size() && (input_[position_] == 'e' || input_[position_] == 'E')) {
            ++position_;
            if (position_ < input_.size() && (input_[position_] == '+' || input_[position_] == '-')) {
                ++position_;
            }
            bool exponentDigits = false;
            while (position_ < input_.size() && input_[position_] >= '0' && input_[position_] <= '9') {
                exponentDigits = true;
                ++position_;
            }
            if (!exponentDigits) {
                throw RuntimeConfigError("invalid JSON number exponent");
            }
        }
        const std::string raw(input_.substr(start, position_ - start));
        std::size_t consumed = 0;
        double value = 0.0;
        try {
            value = std::stod(raw, &consumed);
        } catch (const std::exception&) {
            throw RuntimeConfigError("invalid JSON numeric value");
        }
        if (consumed != raw.size() || !std::isfinite(value)) {
            throw RuntimeConfigError("runtime numeric value must be finite");
        }
        return value;
    }

private:
    void skipWhitespace() {
        while (position_ < input_.size()) {
            const char ch = input_[position_];
            if (ch != ' ' && ch != '\t' && ch != '\r' && ch != '\n') {
                break;
            }
            ++position_;
        }
    }

    std::string_view input_;
    std::size_t position_ = 0;
};

inline void rememberKey(std::unordered_set<std::string>& seen, const std::string& key) {
    if (!seen.insert(key).second) {
        throw RuntimeConfigError("duplicate runtime config field: " + key);
    }
}

inline void requireString(std::string_view actual, std::string_view expected, std::string_view field) {
    if (actual != expected) {
        throw RuntimeConfigError(std::string(field) + " must be " + std::string(expected));
    }
}

inline void parseCutscene(JsonCursor& cursor, RuntimeConfig& config) {
    cursor.expect('{');
    std::unordered_set<std::string> seen;
    if (cursor.consume('}')) {
        return;
    }
    while (true) {
        const std::string key = cursor.parseString();
        rememberKey(seen, key);
        cursor.expect(':');
        if (key == "enabled") {
            config.cutsceneSpeed.enabled = cursor.parseBoolean();
        } else if (key == "baseMultiplier") {
            config.cutsceneSpeed.baseMultiplier = cursor.parseNumber();
        } else if (key == "r2Behavior") {
            requireString(cursor.parseString(), "multiply-native", "cutsceneSpeed.r2Behavior");
        } else {
            throw RuntimeConfigError("unsupported cutsceneSpeed field: " + key);
        }
        if (cursor.consume('}')) {
            break;
        }
        cursor.expect(',');
    }
}

inline void parseMinimap(JsonCursor& cursor, RuntimeConfig& config) {
    cursor.expect('{');
    std::unordered_set<std::string> seen;
    if (cursor.consume('}')) {
        return;
    }
    while (true) {
        const std::string key = cursor.parseString();
        rememberKey(seen, key);
        cursor.expect(':');
        if (key == "enabled") {
            config.minimap.enabled = cursor.parseBoolean();
        } else if (key == "holdMilliseconds") {
            config.minimap.holdMilliseconds = cursor.parseUnsignedInteger();
        } else if (key == "persistChosenState") {
            config.minimap.persistChosenState = cursor.parseBoolean();
        } else if (key == "tapBehavior") {
            requireString(cursor.parseString(), "open-map", "minimap.tapBehavior");
        } else if (key == "holdBehavior") {
            requireString(cursor.parseString(), "toggle-minimap", "minimap.holdBehavior");
        } else {
            throw RuntimeConfigError("unsupported minimap field: " + key);
        }
        if (cursor.consume('}')) {
            break;
        }
        cursor.expect(',');
    }
}

inline void parseHP(JsonCursor& cursor, RuntimeConfig& config) {
    cursor.expect('{');
    std::unordered_set<std::string> seen;
    if (cursor.consume('}')) {
        return;
    }
    while (true) {
        const std::string key = cursor.parseString();
        rememberKey(seen, key);
        cursor.expect(':');
        if (key == "enabled") {
            config.hpRebalance.enabled = cursor.parseBoolean();
        } else if (key == "hpMultiplier") {
            config.hpRebalance.multiplier = cursor.parseNumber();
        } else {
            throw RuntimeConfigError("unsupported hpRebalance field: " + key);
        }
        if (cursor.consume('}')) {
            break;
        }
        cursor.expect(',');
    }
}

inline void parseSprint(JsonCursor& cursor, RuntimeConfig& config) {
    cursor.expect('{');
    std::unordered_set<std::string> seen;
    if (cursor.consume('}')) {
        return;
    }
    while (true) {
        const std::string key = cursor.parseString();
        rememberKey(seen, key);
        cursor.expect(':');
        if (key == "enabled") {
            config.betterSprint.enabled = cursor.parseBoolean();
        } else if (key == "speedMultiplier") {
            config.betterSprint.multiplier = cursor.parseNumber();
        } else {
            throw RuntimeConfigError("unsupported betterSprint field: " + key);
        }
        if (cursor.consume('}')) {
            break;
        }
        cursor.expect(',');
    }
}

} // namespace detail

inline RuntimeConfig parseRuntimeConfig(std::string_view input) {
    detail::JsonCursor cursor(input);
    RuntimeConfig config;
    cursor.expect('{');
    std::unordered_set<std::string> seen;
    if (cursor.consume('}')) {
        throw RuntimeConfigError("runtime config cannot be empty");
    }
    while (true) {
        const std::string key = cursor.parseString();
        detail::rememberKey(seen, key);
        cursor.expect(':');
        if (key == "schemaVersion") {
            config.schemaVersion = cursor.parseUnsignedInteger();
        } else if (key == "cutsceneSpeed") {
            detail::parseCutscene(cursor, config);
        } else if (key == "minimap") {
            detail::parseMinimap(cursor, config);
        } else if (key == "hpRebalance") {
            detail::parseHP(cursor, config);
        } else if (key == "betterSprint") {
            detail::parseSprint(cursor, config);
        } else {
            throw RuntimeConfigError("unsupported runtime config field: " + key);
        }
        if (cursor.consume('}')) {
            break;
        }
        cursor.expect(',');
    }
    if (!cursor.finished()) {
        throw RuntimeConfigError("unexpected data after runtime config object");
    }

    if (config.schemaVersion != 1) {
        throw RuntimeConfigError("unsupported runtime config schema version");
    }
    if (!std::isfinite(config.cutsceneSpeed.baseMultiplier)
            || config.cutsceneSpeed.baseMultiplier <= 1.0) {
        throw RuntimeConfigError("cutscene base multiplier must be greater than 1.0");
    }
    if (config.minimap.holdMilliseconds < 150 || config.minimap.holdMilliseconds > 1500) {
        throw RuntimeConfigError("minimap hold threshold must be between 150 and 1500 ms");
    }
    if (!std::isfinite(config.hpRebalance.multiplier) || config.hpRebalance.multiplier <= 0.0) {
        throw RuntimeConfigError("HP multiplier must be greater than 0");
    }
    if (!std::isfinite(config.betterSprint.multiplier) || config.betterSprint.multiplier <= 0.0) {
        throw RuntimeConfigError("sprint multiplier must be greater than 0");
    }
    return config;
}

} // namespace lexeditor::ff7r
