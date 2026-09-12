// GPL-3.0-or-later. Native world encounter request policy for the Signal Flare item.
#pragma once
#include <cstdint>

namespace lexeditor_flare {
// FF8_EN 0x02040A5C..0x02040A63. The native selector owns the RNG bytes.
struct WorldCounters {
    std::uint16_t steps;
    std::uint8_t danger;
    std::uint8_t danger_addend, danger_index, battle_addend, battle_index, misc_index;
};
static_assert(sizeof(WorldCounters) == 8, "World encounter counter layout changed");

// Use the stock ID/quantity pairs. The caller supplies a separately allocated
// Signal Flare ID; this policy does not reserve an ID or change the save layout.
// Selector must select the encounter only, before the battle transition.
template<class Inventory, class Selector>
bool use_item(Inventory &inventory, std::uint8_t item_id,
              std::uint16_t &encounter, std::uint8_t &remaining, Selector select) {
    if (!item_id) return false;
    decltype(&inventory[0]) owned = nullptr;
    for (auto &slot : inventory) {
        if (slot.item_id != item_id) continue;
        // Duplicate stacks or corrupt quantities need repair, not a debit
        // from an arbitrary slot. Never start a free encounter on failure.
        if (owned || !slot.item_quantity || slot.item_quantity > 100) return false;
        owned = &slot;
    }
    if (!owned) return false;
    std::uint16_t selected = 0;
    if (!select(&selected)) return false;
    remaining = --owned->item_quantity;
    if (!remaining) owned->item_id = 0;
    encounter = selected;
    return true;
}

// Field selector uses separate step/danger counters and two RNG indices.
// The selector's return register is undefined on several refusal branches;
// its owner must report success from the native transition state instead.
template<class Selector>
bool request_field(std::uint16_t &steps, std::uint16_t &danger,
                   std::uint8_t &danger_index, std::uint8_t &danger_addend,
                   std::uint8_t &formation_index, Selector select) {
    const auto old_steps=steps, old_danger=danger;
    const auto old_index=danger_index, old_addend=danger_addend, old_formation=formation_index;
    struct Restore {
        std::uint16_t &steps, &danger;
        std::uint8_t &index, &addend, &formation;
        std::uint16_t old_steps, old_danger;
        std::uint8_t old_index, old_addend, old_formation;
        bool success=false;
        ~Restore() { if(!success) {steps=old_steps;danger=old_danger;index=old_index;
            addend=old_addend;formation=old_formation;} }
    } restore{steps,danger,danger_index,danger_addend,formation_index,
              old_steps,old_danger,old_index,old_addend,old_formation};
    steps=257; danger=256;
    restore.success=select();
    return restore.success;
}

template<class Selector>
bool request_world(WorldCounters &counters, std::int32_t &movement,
                   std::uint16_t &encounter, Selector select) {
    struct Restore {
        WorldCounters &live;
        WorldCounters before;
        std::int32_t &movement;
        std::int32_t before_movement;
        bool success = false;
        ~Restore() { movement = before_movement; if (!success) live = before; }
    } restore{counters, counters, movement, movement};
    // Native formation selection and location/vehicle guards stay in charge.
    // At zero base rate, the one RNG value 255 can still reject maximum
    // danger. Permit one bounded full byte cycle; never spin indefinitely.
    for (unsigned attempt = 0; attempt < 256; ++attempt) {
        counters.steps = 256;
        counters.danger = 255;
        movement = 1; // Native step input; never move the world actor.
        std::uint16_t selected = 0;
        if (select(&selected) > 0) {
            encounter = selected;
            restore.success = true;
            return true;
        }
    }
    return false;
}
} // namespace lexeditor_flare
