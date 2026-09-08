#pragma once

#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <optional>

namespace lexeditor::ff7r {

// Publicly documented FF7R player-stat layout used only after the runtime has
// resolved and validated the current process's AGameState pointer.
inline constexpr std::size_t kPlayerStatsSize = 0x40;
inline constexpr std::size_t kPlayerHPFieldOffset = 0x10;
inline constexpr std::size_t kPlayerMaxHPFieldOffset = 0x14;
inline constexpr std::size_t kPlayerMPFieldOffset = 0x18;
inline constexpr std::size_t kPlayerMaxMPFieldOffset = 0x1C;
inline constexpr std::size_t kGameStateCloudStatsOffset = 0x8A0;
inline constexpr std::size_t kGameStatePartyStatsOffset = 0x8E0;
inline constexpr std::size_t kGameStatePartyStatsCount = 6;

struct PlayerStatsPrefix {
    std::int32_t hp = 0;
    std::int32_t maxHP = 0;
    std::int32_t mp = 0;
    std::int32_t maxMP = 0;
};

inline bool emptyPlayerStats(const PlayerStatsPrefix& stats) noexcept {
    return stats.hp == 0 && stats.maxHP == 0 && stats.mp == 0 && stats.maxMP == 0;
}

inline bool plausiblePlayerStats(const PlayerStatsPrefix& stats) noexcept {
    // Intentionally broad limits: these checks are structural tripwires, not
    // gameplay balance constraints. They reject obvious bad pointers while
    // allowing mods and late-game values substantially beyond vanilla ranges.
    constexpr std::int32_t kMaxPlausibleHP = 10'000'000;
    constexpr std::int32_t kMaxPlausibleMP = 1'000'000;
    return stats.maxHP > 0
        && stats.maxHP <= kMaxPlausibleHP
        && stats.hp >= 0
        && stats.hp <= kMaxPlausibleHP
        && stats.maxMP >= 0
        && stats.maxMP <= kMaxPlausibleMP
        && stats.mp >= 0
        && stats.mp <= kMaxPlausibleMP;
}

inline std::optional<std::int32_t> scaledMaxHP(
    std::int32_t vanillaMaxHP,
    double multiplier) noexcept {
    if (vanillaMaxHP <= 0 || !std::isfinite(multiplier) || multiplier <= 0.0) {
        return std::nullopt;
    }
    const double scaled = static_cast<double>(vanillaMaxHP) * multiplier;
    if (!std::isfinite(scaled)
            || scaled > static_cast<double>(std::numeric_limits<std::int32_t>::max())) {
        return std::nullopt;
    }
    if (scaled <= 1.0) {
        return 1;
    }
    const auto rounded = std::llround(scaled);
    if (rounded < 1 || rounded > std::numeric_limits<std::int32_t>::max()) {
        return std::nullopt;
    }
    return static_cast<std::int32_t>(rounded);
}

struct HPTrackState {
    bool initialized = false;
    std::int32_t vanillaMaxHP = 0;
    std::int32_t lastAppliedMaxHP = 0;
};

struct HPWritePlan {
    bool valid = false;
    bool writeMaxHP = false;
    bool writeHP = false;
    std::int32_t vanillaMaxHP = 0;
    std::int32_t maxHP = 0;
    std::int32_t hp = 0;
};

inline HPWritePlan makeHPWritePlan(
    const HPTrackState& state,
    const PlayerStatsPrefix& current,
    double multiplier) noexcept {
    if (!plausiblePlayerStats(current)) {
        return {};
    }

    // If the game changes MaxHP after our previous write (level/equipment/stat
    // recalculation), treat that new value as the fresh vanilla/composed MaxHP.
    // Otherwise retain the raw value so polling never compounds the multiplier.
    std::int32_t vanillaMaxHP = current.maxHP;
    if (state.initialized && current.maxHP == state.lastAppliedMaxHP) {
        vanillaMaxHP = state.vanillaMaxHP;
    }

    const auto desired = scaledMaxHP(vanillaMaxHP, multiplier);
    if (!desired.has_value()) {
        return {};
    }

    const std::int32_t desiredHP = current.hp > *desired ? *desired : current.hp;
    return {
        true,
        current.maxHP != *desired,
        current.hp != desiredHP,
        vanillaMaxHP,
        *desired,
        desiredHP,
    };
}

inline void commitHPWritePlan(HPTrackState& state, const HPWritePlan& plan) noexcept {
    if (!plan.valid) {
        return;
    }
    state.initialized = true;
    state.vanillaMaxHP = plan.vanillaMaxHP;
    state.lastAppliedMaxHP = plan.maxHP;
}

} // namespace lexeditor::ff7r
