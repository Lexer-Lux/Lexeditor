#include "shared_magic_core.h"

#include <cassert>

using namespace lexeditor::ff8::shared_magic;

int main()
{
    PrivateInventories source{};
    source[0][0] = {1, 60};
    source[3][7] = {1, 40};
    source[7][31] = {9, 12};

    MergeResult merged = try_merge(source);
    assert(merged);
    assert(merged.inventory[0].id == 1 && merged.inventory[0].amount == 100);
    assert(merged.inventory[1].id == 9 && merged.inventory[1].amount == 12);

    PrivateInventories migrated = source;
    MergeResult migration = migrate_to_canonical(migrated);
    assert(migration);
    assert(migrated[0][0].id == 1 && migrated[0][0].amount == 100);
    assert(migrated[0][1].id == 9 && migrated[0][1].amount == 12);
    for (std::size_t character = 1; character < kCharacterCount; ++character) {
        for (const MagicSlot slot : migrated[character]) {
            assert(slot.id == 0 && slot.amount == 0);
        }
    }

    PrivateInventories overstock = source;
    overstock[3][7].amount = 41;
    const PrivateInventories overstock_before = overstock;
    MergeResult overstock_result = migrate_to_canonical(overstock);
    assert(!overstock_result);
    assert(overstock_result.error == MergeError::spell_stock_exceeds_limit);
    assert(overstock_result.spell_id == 1);
    assert(overstock == overstock_before);
    ActivationResult blocked = request_activation(overstock);
    assert(blocked.setting_enabled);
    assert(!blocked.shared_pool_active);
    assert(blocked.error == MergeError::spell_stock_exceeds_limit);
    assert(blocked.spell_id == 1);
    assert(overstock == overstock_before);
    assert(migration_warning_template(blocked.error)[0] != '\0');

    // The selected setting can activate later after the player removes the
    // blocker. No periodic synchronization is needed or permitted.
    overstock[3][7].amount = 40;
    ActivationResult retry = request_activation(overstock);
    assert(retry.setting_enabled);
    assert(retry.shared_pool_active);
    assert(retry.error == MergeError::none);
    assert(overstock[0][0].id == 1 && overstock[0][0].amount == 100);

    PrivateInventories too_many{};
    for (std::size_t index = 0; index < kSlotCount; ++index) {
        too_many[0][index] = {static_cast<std::uint8_t>(index + 1), 1};
    }
    too_many[1][0] = {33, 1};
    const PrivateInventories too_many_before = too_many;
    MergeResult too_many_result = migrate_to_canonical(too_many);
    assert(!too_many_result);
    assert(too_many_result.error == MergeError::too_many_distinct_spells);
    assert(too_many == too_many_before);
    assert(migration_warning_template(too_many_result.error)[0] != '\0');

    MagicInventory stock{};
    assert(add_stock(stock, 5, 10));
    assert(add_stock(stock, 5, 90));
    assert(!add_stock(stock, 5, 1));
    assert(consume_stock(stock, 5, 99));
    assert(stock[0].amount == 1);
    assert(consume_stock(stock, 5, 1));
    assert(stock[0].id == 0 && stock[0].amount == 0);
    assert(!consume_stock(stock, 5, 1));

    PrivateInventories expanded{};
    expanded[0][0] = {3, 200};
    expanded[1][0] = {3, 55};
    assert(!try_merge(expanded));
    const MergeResult expanded_merge = try_merge(expanded, 255);
    assert(expanded_merge && expanded_merge.inventory[0].amount == 255);
    MagicInventory expanded_stock{};
    assert(add_stock(expanded_stock, 3, 200, 255));
    assert(add_stock(expanded_stock, 3, 55, 255));
    assert(!add_stock(expanded_stock, 3, 1, 255));
    assert(migration_warning_template(
        MergeError::spell_stock_exceeds_limit, 255).find("255") != std::string::npos);

    PrivateInventories live{};
    live[0][0] = {2, 25};
    live[4][3] = {2, 25};
    live[7][7] = {7, 8};
    RuntimeState runtime{};
    const ActivationResult runtime_activation = activate_runtime(runtime, live);
    assert(runtime_activation.shared_pool_active);
    assert(runtime.setting_enabled && runtime.shared_pool_active);
    assert(runtime.phase == RuntimePhase::shared_mirror);
    for (const MagicInventory &inventory : live) {
        assert(inventory == live[0]);
    }
    assert(verify_live_mirror(runtime, live));
    assert(live[0][0] == MagicSlot({2, 50}));
    assert(live[0][1] == MagicSlot({7, 8}));

    live[5][0].amount = 49;
    assert(!verify_live_mirror(runtime, live));
    assert(reconcile_from_character(runtime, live, 5));
    assert(verify_live_mirror(runtime, live));
    for (const MagicInventory &inventory : live) {
        assert(inventory == live[5]);
        assert(inventory[0] == MagicSlot({2, 49}));
    }

    const MagicInventory canonical_before_private_swap = live[0];
    live[0][0] = {77, 7};
    live[3][0] = {66, 6};
    assert(!verify_live_mirror(runtime, live));
    assert(restore_canonical_mirror(runtime, live));
    assert(verify_live_mirror(runtime, live));
    for (const MagicInventory &inventory : live) {
        assert(inventory == canonical_before_private_swap);
    }

    const PrivateInventories before_invalid_reconcile = live;
    MagicInventory invalid = live[0];
    invalid[0].amount = 101;
    assert(!reconcile_from_inventory(runtime, live, invalid));
    assert(live == before_invalid_reconcile);

    assert(suspend_for_private_scenario(runtime, live));
    assert(runtime.phase == RuntimePhase::scenario_private);
    const MagicInventory persistent_before_scenario = live[0];
    live[0][0] = {99, 99};
    live[7][0] = {88, 88};
    assert(!begin_canonical_save(runtime, live));
    assert(resume_after_private_scenario(runtime, live));
    assert(runtime.phase == RuntimePhase::shared_mirror);
    assert(verify_live_mirror(runtime, live));
    for (const MagicInventory &inventory : live) {
        assert(inventory == persistent_before_scenario);
    }

    assert(begin_canonical_save(runtime, live));
    assert(runtime.phase == RuntimePhase::save_canonical);
    assert(live[0] == persistent_before_scenario);
    for (std::size_t character = 1; character < kCharacterCount; ++character) {
        assert(live[character] == MagicInventory{});
    }
    assert(!reconcile_from_character(runtime, live, 0));
    assert(finish_canonical_save(runtime, live));
    assert(runtime.phase == RuntimePhase::shared_mirror);
    assert(verify_live_mirror(runtime, live));
    for (const MagicInventory &inventory : live) {
        assert(inventory == persistent_before_scenario);
    }

    PrivateInventories blocked_live = too_many_before;
    const PrivateInventories blocked_live_before = blocked_live;
    RuntimeState blocked_runtime{};
    const ActivationResult blocked_runtime_result =
        activate_runtime(blocked_runtime, blocked_live);
    assert(!blocked_runtime_result.shared_pool_active);
    assert(blocked_runtime.setting_enabled);
    assert(!blocked_runtime.shared_pool_active);
    assert(blocked_runtime.phase == RuntimePhase::private_stocks);
    assert(blocked_live == blocked_live_before);

    return 0;
}
