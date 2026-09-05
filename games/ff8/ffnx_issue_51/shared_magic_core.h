#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <string>

namespace lexeditor::ff8::shared_magic {

constexpr std::size_t kCharacterCount = 8;
constexpr std::size_t kSlotCount = 32;
constexpr std::uint8_t kDefaultStockLimit = 100;

struct MagicSlot {
    std::uint8_t id;
    std::uint8_t amount;
};

constexpr bool operator==(const MagicSlot left, const MagicSlot right)
{
    return left.id == right.id && left.amount == right.amount;
}

using MagicInventory = std::array<MagicSlot, kSlotCount>;
using PrivateInventories = std::array<MagicInventory, kCharacterCount>;

enum class MergeError {
    none,
    invalid_slot,
    too_many_distinct_spells,
    spell_stock_exceeds_limit,
};

struct MergeResult {
    MergeError error = MergeError::none;
    std::uint8_t spell_id = 0;
    MagicInventory inventory{};

    explicit operator bool() const { return error == MergeError::none; }
};

struct ActivationResult {
    // The setting remains selected after a blocked migration. The runtime
    // stays private until a later explicit activation attempt succeeds.
    bool setting_enabled = true;
    bool shared_pool_active = false;
    MergeError error = MergeError::none;
    std::uint8_t spell_id = 0;
};

enum class RuntimePhase {
    private_stocks,
    shared_mirror,
    scenario_private,
    save_canonical,
};

struct RuntimeState {
    bool setting_enabled = false;
    bool shared_pool_active = false;
    RuntimePhase phase = RuntimePhase::private_stocks;
    std::uint8_t stock_limit = kDefaultStockLimit;
    MagicInventory canonical_snapshot{};
};

// Builds a deterministic, lossless pool. It does not change the source.
MergeResult try_merge(const PrivateInventories &source,
                      std::uint8_t stock_limit = kDefaultStockLimit);

// On success, character zero owns the canonical pool and the other private
// arrays are cleared. This keeps the save valid and lossless if the FFNx hook
// is later disabled; vanilla then sees all magic on character zero.
MergeResult migrate_to_canonical(PrivateInventories &source,
                                 std::uint8_t stock_limit = kDefaultStockLimit);

// Applies the settled lossless activation rule. A failure returns a warning
// reason and does not change any inventory.
ActivationResult request_activation(PrivateInventories &source,
                                    std::uint8_t stock_limit = kDefaultStockLimit);

// Activates shared ownership and creates the normal eight-record live mirror.
// On failure, neither the runtime state nor any private inventory changes.
ActivationResult activate_runtime(RuntimeState &state, PrivateInventories &source);

// The live mirror lets untouched FF8 readers keep using their character-local
// address. These functions are called only at complete transaction boundaries.
bool verify_live_mirror(const RuntimeState &state,
                        const PrivateInventories &source);
bool mirror_canonical(RuntimeState &state, PrivateInventories &source);
bool restore_canonical_mirror(RuntimeState &state, PrivateInventories &source);
bool reconcile_from_character(RuntimeState &state, PrivateInventories &source,
                              std::size_t changed_character);
bool reconcile_from_inventory(RuntimeState &state, PrivateInventories &source,
                              const MagicInventory &changed_inventory);

// Temporary scenario presets use vanilla private arrays. Their writes must not
// become the persistent shared stock when the original character block returns.
bool suspend_for_private_scenario(RuntimeState &state,
                                  const PrivateInventories &source);
bool resume_after_private_scenario(RuntimeState &state,
                                   PrivateInventories &source);

// A save contains the canonical pool only in character zero. The caller must
// call finish_canonical_save on every serializer exit to restore the live mirror.
bool begin_canonical_save(RuntimeState &state, PrivateInventories &source);
bool finish_canonical_save(RuntimeState &state, PrivateInventories &source);

// These fixed English strings can be pre-encoded for FF8's native warning
// window. Each one states that no data was changed.
std::string migration_warning_template(
    MergeError error, std::uint8_t stock_limit = kDefaultStockLimit);

bool add_stock(MagicInventory &inventory, std::uint8_t spell_id, std::uint8_t amount,
               std::uint8_t stock_limit = kDefaultStockLimit);
bool consume_stock(MagicInventory &inventory, std::uint8_t spell_id, std::uint8_t amount);

} // namespace lexeditor::ff8::shared_magic
