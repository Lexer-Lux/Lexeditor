#pragma once

#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <span>
#include <vector>

namespace lexeditor::ff7r {

// Generated Remake API declarations expose AEndGameState::GameSpeed as eleven
// float channels. EGameSpeed_CUT is the tenth entry (index 9). The runtime does
// not trust a fixed AEndGameState field offset: it discovers the initialized
// eleven-float block inside the pre-Cloud portion of the live game-state object
// and requires exactly one match before any write is allowed.
inline constexpr std::size_t kGameSpeedChannelCount = 11;
inline constexpr std::size_t kCutsceneGameSpeedIndex = 9;
inline constexpr std::size_t kGameSpeedDiscoveryBytes = 0x880;
inline constexpr float kVanillaGameSpeed = 1.0F;
inline constexpr float kMaxPlausibleNativeGameSpeed = 16.0F;
inline constexpr float kMaxPlausibleAppliedGameSpeed = 64.0F;

struct GameSpeedBlockMatch {
    std::size_t offset = 0;
};

inline std::vector<GameSpeedBlockMatch> findInitialGameSpeedBlocks(
    std::span<const std::uint8_t> bytes,
    std::size_t maxMatches = 8) {
    std::vector<GameSpeedBlockMatch> matches;
    constexpr std::size_t kBlockBytes = kGameSpeedChannelCount * sizeof(float);
    if (bytes.size() < kBlockBytes || maxMatches == 0) {
        return matches;
    }

    for (std::size_t offset = 0; offset <= bytes.size() - kBlockBytes;
            offset += alignof(float)) {
        bool allVanilla = true;
        for (std::size_t index = 0; index < kGameSpeedChannelCount; ++index) {
            float value = 0.0F;
            std::memcpy(&value, bytes.data() + offset + index * sizeof(float), sizeof(value));
            if (value != kVanillaGameSpeed) {
                allVanilla = false;
                break;
            }
        }
        if (!allVanilla) {
            continue;
        }
        matches.push_back({offset});
        if (matches.size() >= maxMatches) {
            break;
        }
    }
    return matches;
}

inline bool plausibleNativeGameSpeed(float speed) noexcept {
    return std::isfinite(speed)
        && speed > 0.0F
        && speed <= kMaxPlausibleNativeGameSpeed;
}

struct CutsceneSpeedTrack {
    bool initialized = false;
    float nativeSpeed = kVanillaGameSpeed;
    float lastAppliedSpeed = kVanillaGameSpeed;
};

struct CutsceneSpeedWritePlan {
    bool valid = false;
    bool write = false;
    float nativeSpeed = kVanillaGameSpeed;
    float appliedSpeed = kVanillaGameSpeed;
};

inline CutsceneSpeedWritePlan makeCutsceneSpeedWritePlan(
    const CutsceneSpeedTrack& state,
    float currentSpeed,
    double baseMultiplier) noexcept {
    if (!plausibleNativeGameSpeed(currentSpeed)
            || !std::isfinite(baseMultiplier)
            || baseMultiplier <= 1.0) {
        return {};
    }

    // If the game has not changed the channel since our last write, retain the
    // native value we observed before applying Lexeditor's multiplier. If the
    // value differs, treat it as a fresh native transition (for example R2
    // fast-forward engaging/releasing) and compose the configured base on top.
    float nativeSpeed = currentSpeed;
    if (state.initialized && currentSpeed == state.lastAppliedSpeed) {
        nativeSpeed = state.nativeSpeed;
    }
    if (!plausibleNativeGameSpeed(nativeSpeed)) {
        return {};
    }

    const double desired = static_cast<double>(nativeSpeed) * baseMultiplier;
    if (!std::isfinite(desired)
            || desired <= 0.0
            || desired > static_cast<double>(kMaxPlausibleAppliedGameSpeed)) {
        return {};
    }
    const float applied = static_cast<float>(desired);
    if (!std::isfinite(applied) || applied <= 0.0F) {
        return {};
    }

    return {
        true,
        currentSpeed != applied,
        nativeSpeed,
        applied,
    };
}

inline void commitCutsceneSpeedWritePlan(
    CutsceneSpeedTrack& state,
    const CutsceneSpeedWritePlan& plan) noexcept {
    if (!plan.valid) {
        return;
    }
    state.initialized = true;
    state.nativeSpeed = plan.nativeSpeed;
    state.lastAppliedSpeed = plan.appliedSpeed;
}

} // namespace lexeditor::ff7r
