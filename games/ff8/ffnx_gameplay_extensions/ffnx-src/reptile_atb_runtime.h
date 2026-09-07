#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>

namespace lexeditor_reptile_atb {
constexpr std::uint8_t kFireElement = 0x01;
constexpr std::uint8_t kIceElement = 0x02;
constexpr double kIceMultiplier = 0.92;
constexpr double kFireMultiplier = 1.08;
constexpr unsigned kFirstEnemySlot = 3;
constexpr unsigned kLastEnemySlot = 10;
constexpr unsigned kEnemySlots = 8;

inline int enemy_index(unsigned battle_slot) {
    return battle_slot >= kFirstEnemySlot && battle_slot <= kLastEnemySlot
        ? static_cast<int>(battle_slot - kFirstEnemySlot) : -1;
}

inline int com_id(unsigned battle_slot, std::uint8_t scene_entity_id) {
    if (enemy_index(battle_slot) < 0 || scene_entity_id < 0x10) return -1;
    return static_cast<int>(scene_entity_id) - 0x10;
}

struct SpeedState {
    double multiplier[kEnemySlots]{};
    double remainder[kEnemySlots]{};

    SpeedState() { reset(); }

    void reset() {
        for (unsigned i = 0; i < kEnemySlots; ++i) {
            multiplier[i] = 1.0;
            remainder[i] = 0.0;
        }
    }

    bool apply(unsigned battle_slot, std::uint8_t element_mask) {
        const int index = enemy_index(battle_slot);
        if (index < 0) return false;
        bool changed = false;
        if (element_mask & kIceElement) {
            multiplier[index] *= kIceMultiplier;
            changed = true;
        }
        if (element_mask & kFireElement) {
            multiplier[index] *= kFireMultiplier;
            changed = true;
        }
        return changed;
    }

    std::uint32_t scale_increment(unsigned battle_slot, std::uint32_t native_increment) {
        const int index = enemy_index(battle_slot);
        if (index < 0 || native_increment == 0) return native_increment;
        const double value = static_cast<double>(native_increment) * multiplier[index] + remainder[index];
        const double limit = static_cast<double>(std::numeric_limits<std::uint32_t>::max());
        if (value >= limit) {
            remainder[index] = 0.0;
            return std::numeric_limits<std::uint32_t>::max();
        }
        const double whole = std::floor(std::max(0.0, value));
        remainder[index] = value - whole;
        return static_cast<std::uint32_t>(whole);
    }
};
} // namespace lexeditor_reptile_atb
