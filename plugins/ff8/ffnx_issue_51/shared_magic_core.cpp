#include "shared_magic_core.h"

#include <algorithm>
#include <array>
#include <limits>
#include <string>

namespace lexeditor::ff8::shared_magic {

static_assert(sizeof(MagicSlot) == 2, "FF8 magic slots are two bytes");

MergeResult try_merge(const PrivateInventories &source, const std::uint8_t stock_limit)
{
    if (stock_limit == 0) {
        return {MergeError::invalid_slot, 0, {}};
    }
    std::array<std::uint16_t, 256> totals{};
    std::array<bool, 256> seen{};
    std::array<std::uint8_t, 255> order{};
    std::size_t distinct = 0;

    for (const MagicInventory &inventory : source) {
        for (const MagicSlot slot : inventory) {
            if (slot.id == 0 && slot.amount == 0) {
                continue;
            }
            if (slot.id == 0 || slot.amount == 0 || slot.amount > stock_limit) {
                return {MergeError::invalid_slot, slot.id, {}};
            }
            if (!seen[slot.id]) {
                if (distinct >= kSlotCount) {
                    return {MergeError::too_many_distinct_spells, slot.id, {}};
                }
                seen[slot.id] = true;
                order[distinct++] = slot.id;
            }
            totals[slot.id] = static_cast<std::uint16_t>(totals[slot.id] + slot.amount);
            if (totals[slot.id] > stock_limit) {
                return {MergeError::spell_stock_exceeds_limit, slot.id, {}};
            }
        }
    }

    MergeResult result{};
    for (std::size_t index = 0; index < distinct; ++index) {
        const std::uint8_t id = order[index];
        result.inventory[index] = {id, static_cast<std::uint8_t>(totals[id])};
    }
    return result;
}

MergeResult migrate_to_canonical(PrivateInventories &source, const std::uint8_t stock_limit)
{
    const MergeResult result = try_merge(source, stock_limit);
    if (!result) {
        return result;
    }
    for (MagicInventory &inventory : source) {
        inventory.fill({0, 0});
    }
    source[0] = result.inventory;
    return result;
}

ActivationResult request_activation(PrivateInventories &source, const std::uint8_t stock_limit)
{
    const MergeResult result = migrate_to_canonical(source, stock_limit);
    return {
        true,
        static_cast<bool>(result),
        result.error,
        result.spell_id,
    };
}

namespace {

bool canonicalize_inventory(const MagicInventory &source, MagicInventory &canonical,
                            const std::uint8_t stock_limit)
{
    PrivateInventories temporary{};
    temporary[0] = source;
    const MergeResult result = try_merge(temporary, stock_limit);
    if (!result) {
        return false;
    }
    canonical = result.inventory;
    return true;
}

void write_mirror(PrivateInventories &source, const MagicInventory &canonical)
{
    for (MagicInventory &inventory : source) {
        inventory = canonical;
    }
}

} // namespace

bool verify_live_mirror(const RuntimeState &state,
                        const PrivateInventories &source)
{
    if (!state.setting_enabled || !state.shared_pool_active ||
        state.phase != RuntimePhase::shared_mirror ||
        source[0] != state.canonical_snapshot) {
        return false;
    }
    return std::all_of(source.begin(), source.end(), [&](const MagicInventory &inventory) {
        return inventory == state.canonical_snapshot;
    });
}

ActivationResult activate_runtime(RuntimeState &state, PrivateInventories &source)
{
    PrivateInventories candidate = source;
    const ActivationResult result = request_activation(candidate, state.stock_limit);
    state.setting_enabled = true;
    if (!result.shared_pool_active) {
        state.shared_pool_active = false;
        state.phase = RuntimePhase::private_stocks;
        return result;
    }

    state.shared_pool_active = true;
    state.phase = RuntimePhase::shared_mirror;
    state.canonical_snapshot = candidate[0];
    write_mirror(candidate, state.canonical_snapshot);
    source = candidate;
    return result;
}

bool mirror_canonical(RuntimeState &state, PrivateInventories &source)
{
    if (!state.setting_enabled || !state.shared_pool_active ||
        state.phase != RuntimePhase::shared_mirror) {
        return false;
    }
    MagicInventory canonical{};
    if (!canonicalize_inventory(source[0], canonical, state.stock_limit)) {
        return false;
    }
    state.canonical_snapshot = canonical;
    write_mirror(source, canonical);
    return true;
}

bool restore_canonical_mirror(RuntimeState &state, PrivateInventories &source)
{
    if (!state.setting_enabled || !state.shared_pool_active ||
        state.phase != RuntimePhase::shared_mirror) {
        return false;
    }
    write_mirror(source, state.canonical_snapshot);
    return true;
}

bool reconcile_from_inventory(RuntimeState &state, PrivateInventories &source,
                              const MagicInventory &changed_inventory)
{
    if (!state.setting_enabled || !state.shared_pool_active ||
        state.phase != RuntimePhase::shared_mirror) {
        return false;
    }
    MagicInventory canonical{};
    if (!canonicalize_inventory(changed_inventory, canonical, state.stock_limit)) {
        return false;
    }
    state.canonical_snapshot = canonical;
    write_mirror(source, canonical);
    return true;
}

bool reconcile_from_character(RuntimeState &state, PrivateInventories &source,
                              const std::size_t changed_character)
{
    if (changed_character >= kCharacterCount) {
        return false;
    }
    return reconcile_from_inventory(state, source, source[changed_character]);
}

bool suspend_for_private_scenario(RuntimeState &state,
                                  const PrivateInventories &source)
{
    if (!state.setting_enabled || !state.shared_pool_active ||
        state.phase != RuntimePhase::shared_mirror) {
        return false;
    }
    MagicInventory canonical{};
    if (!canonicalize_inventory(source[0], canonical, state.stock_limit)) {
        return false;
    }
    state.canonical_snapshot = canonical;
    state.phase = RuntimePhase::scenario_private;
    return true;
}

bool resume_after_private_scenario(RuntimeState &state, PrivateInventories &source)
{
    if (!state.setting_enabled || !state.shared_pool_active ||
        state.phase != RuntimePhase::scenario_private) {
        return false;
    }
    write_mirror(source, state.canonical_snapshot);
    state.phase = RuntimePhase::shared_mirror;
    return true;
}

bool begin_canonical_save(RuntimeState &state, PrivateInventories &source)
{
    if (!state.setting_enabled || !state.shared_pool_active ||
        state.phase != RuntimePhase::shared_mirror) {
        return false;
    }
    MagicInventory canonical{};
    if (!canonicalize_inventory(source[0], canonical, state.stock_limit)) {
        return false;
    }
    state.canonical_snapshot = canonical;
    for (MagicInventory &inventory : source) {
        inventory.fill({0, 0});
    }
    source[0] = canonical;
    state.phase = RuntimePhase::save_canonical;
    return true;
}

bool finish_canonical_save(RuntimeState &state, PrivateInventories &source)
{
    if (!state.setting_enabled || !state.shared_pool_active ||
        state.phase != RuntimePhase::save_canonical) {
        return false;
    }
    write_mirror(source, state.canonical_snapshot);
    state.phase = RuntimePhase::shared_mirror;
    return true;
}

std::string migration_warning_template(const MergeError error,
                                       const std::uint8_t stock_limit)
{
    switch (error) {
    case MergeError::none:
        return "";
    case MergeError::invalid_slot:
        return "Shared Magic cannot start because a private Magic slot is invalid. No Magic was changed.";
    case MergeError::too_many_distinct_spells:
        return "Shared Magic cannot start while the party holds more than 32 different spells. No Magic was changed.";
    case MergeError::spell_stock_exceeds_limit:
        return "Shared Magic cannot start because the party holds more than " +
            std::to_string(static_cast<unsigned int>(stock_limit)) +
            " copies of one spell. No Magic was changed.";
    }
    return "Shared Magic cannot start. No Magic was changed.";
}

bool add_stock(MagicInventory &inventory, const std::uint8_t spell_id,
               const std::uint8_t amount, const std::uint8_t stock_limit)
{
    if (spell_id == 0 || amount == 0 || stock_limit == 0) {
        return false;
    }
    MagicSlot *empty = nullptr;
    for (MagicSlot &slot : inventory) {
        if (slot.id == spell_id) {
            if (slot.amount > stock_limit || amount > stock_limit - slot.amount) {
                return false;
            }
            slot.amount = static_cast<std::uint8_t>(slot.amount + amount);
            return true;
        }
        if (empty == nullptr && slot.id == 0 && slot.amount == 0) {
            empty = &slot;
        }
    }
    if (empty == nullptr || amount > stock_limit) {
        return false;
    }
    *empty = {spell_id, amount};
    return true;
}

bool consume_stock(MagicInventory &inventory, const std::uint8_t spell_id, const std::uint8_t amount)
{
    if (spell_id == 0 || amount == 0) {
        return false;
    }
    for (MagicSlot &slot : inventory) {
        if (slot.id != spell_id) {
            continue;
        }
        if (slot.amount < amount) {
            return false;
        }
        slot.amount = static_cast<std::uint8_t>(slot.amount - amount);
        if (slot.amount == 0) {
            slot = {0, 0};
        }
        return true;
    }
    return false;
}

} // namespace lexeditor::ff8::shared_magic
