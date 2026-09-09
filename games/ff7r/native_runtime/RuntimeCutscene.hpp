#pragma once

#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>
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

inline bool plausibleOwnedGameSpeed(float speed) noexcept {
    return std::isfinite(speed)
        && speed > 0.0F
        && speed <= kMaxPlausibleAppliedGameSpeed;
}

// The polling worker has no write notification from AEndGameState::SetGameSpeed.
// If Lexeditor wrote exactly 1.5 and the game later independently wrote native
// R2=1.5, value-only polling could not tell those writes apart. Store our applied
// value one representable float away from the logical product instead. The one-
// ULP delta is negligible for playback but provides an ownership marker: an exact
// native write becomes observably different even when its logical value equals
// Lexeditor's previous product.
inline float tagOwnedGameSpeed(float logicalSpeed) noexcept {
    if (!plausibleOwnedGameSpeed(logicalSpeed)) {
        return 0.0F;
    }
    float tagged = std::nextafter(logicalSpeed, std::numeric_limits<float>::infinity());
    if (!plausibleOwnedGameSpeed(tagged)) {
        // Preserve the inclusive 64x safety ceiling by tagging downward only at
        // the upper boundary. It remains distinct from the exact native value.
        tagged = std::nextafter(logicalSpeed, 0.0F);
    }
    if (!plausibleOwnedGameSpeed(tagged) || tagged == logicalSpeed) {
        return 0.0F;
    }
    return tagged;
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
    float logicalAppliedSpeed = kVanillaGameSpeed;
    float appliedSpeed = kVanillaGameSpeed;
};

inline CutsceneSpeedWritePlan makeCutsceneSpeedWritePlan(
    const CutsceneSpeedTrack& state,
    float currentSpeed,
    double baseMultiplier) noexcept {
    if (!std::isfinite(baseMultiplier) || baseMultiplier <= 1.0) {
        return {};
    }

    const bool currentIsOwned = state.initialized
        && currentSpeed == state.lastAppliedSpeed;
    if (currentIsOwned) {
        if (!plausibleOwnedGameSpeed(currentSpeed)
                || !plausibleNativeGameSpeed(state.nativeSpeed)) {
            return {};
        }
    } else if (!plausibleNativeGameSpeed(currentSpeed)) {
        return {};
    }

    // If the game has not changed the channel since our last tagged write,
    // retain the native value observed before applying Lexeditor's multiplier.
    // Any exact game write differs from the one-ULP ownership tag, so even a
    // native transition whose scalar equals our previous logical product is
    // detected and composed rather than mistaken for our own write.
    const float nativeSpeed = currentIsOwned ? state.nativeSpeed : currentSpeed;
    if (!plausibleNativeGameSpeed(nativeSpeed)) {
        return {};
    }

    const double desired = static_cast<double>(nativeSpeed) * baseMultiplier;
    if (!std::isfinite(desired)
            || desired <= 0.0
            || desired > static_cast<double>(kMaxPlausibleAppliedGameSpeed)) {
        return {};
    }
    const float logicalApplied = static_cast<float>(desired);
    if (!plausibleOwnedGameSpeed(logicalApplied)) {
        return {};
    }
    const float taggedApplied = tagOwnedGameSpeed(logicalApplied);
    if (taggedApplied == 0.0F) {
        return {};
    }

    return {
        true,
        currentSpeed != taggedApplied,
        nativeSpeed,
        logicalApplied,
        taggedApplied,
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
