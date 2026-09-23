// Included by shared_magic_runtime.cpp, after its stock-reconciliation code.
// This deliberately uses the existing canonical pool, not a second inventory
// or a snapshot which could overwrite a Draw/cast during model retirement.
#include "../lexeditor_ff8_shared_party.h"

namespace {
int g_shared_party_retiring_slot = -1;
bool g_shared_party_was_ready = false;

bool shared_party_pool_owned()
{
    return g_state.shared_pool_active &&
        g_state.phase == RuntimePhase::shared_mirror &&
        ff8_externals.savemap != nullptr &&
        ff8_externals.shared_magic_battle_actor_base != nullptr;
}

bool shared_party_in_battle()
{
    const auto *mode = getmode_cached();
    return mode != nullptr && mode->driver_mode == MODE_BATTLE;
}
}

SharedPartyStockOwnership lexeditor_ff8_shared_party_begin(int slot)
{
    if (slot < 0 || slot >= static_cast<int>(kActorCount) ||
        !shared_party_in_battle() || g_shared_party_retiring_slot != -1) {
        return SharedPartyStockOwnership::blocked;
    }
    if (!g_state.shared_pool_active) {
        return SharedPartyStockOwnership::private_stocks;
    }
    // Never start a replacement inside a serializer, inventory transfer,
    // reconciliation owner, or one of its native nested writers.
    if (!shared_party_pool_owned() || g_frame_depth != 0 ||
        g_internal_depth != 0 || g_private_transaction_depth != 0 ||
        g_reconciliation_owner_depth != 0 || !g_actor_ready[slot]) {
        return SharedPartyStockOwnership::blocked;
    }
    preserve_canonical();
    if (!shared_party_pool_owned()) {
        return SharedPartyStockOwnership::blocked;
    }
    g_shared_party_retiring_slot = slot;
    g_shared_party_was_ready = g_actor_ready[slot];
    g_actor_ready[slot] = false;
    return SharedPartyStockOwnership::shared_pool;
}

void lexeditor_ff8_shared_party_materialized(int slot)
{
    if (slot != g_shared_party_retiring_slot || slot < 0 ||
        slot >= static_cast<int>(kActorCount)) {
        return;
    }
    g_shared_party_retiring_slot = -1;
    g_shared_party_was_ready = false;
    if (!shared_party_in_battle() || !shared_party_pool_owned()) {
        return; // A native load/fallback may have relinquished pool ownership.
    }
    // The game's initializer has already filled this record's non-stock
    // metadata. Publish the CURRENT pool and recompute junction quantities;
    // other ready actors may have changed the pool while this slot retired.
    g_actor_ready[slot] = true;
    preserve_canonical();
}

void lexeditor_ff8_shared_party_cancel(int slot)
{
    if (slot != g_shared_party_retiring_slot || slot < 0 ||
        slot >= static_cast<int>(kActorCount)) {
        return;
    }
    const bool was_ready = g_shared_party_was_ready;
    g_shared_party_retiring_slot = -1;
    g_shared_party_was_ready = false;
    // Called only BEFORE successful retirement, when the original record
    // remains materialized. After retirement Party Switch rebuilds the old
    // actor and calls materialized instead of this cancellation path.
    if (shared_party_in_battle() && shared_party_pool_owned()) {
        g_actor_ready[slot] = was_ready;
        preserve_canonical();
    }
}

void lexeditor_ff8_shared_party_reset()
{
    // Battle exit/save loading must not write through stale actor pointers.
    g_shared_party_retiring_slot = -1;
    g_shared_party_was_ready = false;
}

extern "C" __declspec(dllexport) unsigned int lexeditor_ff8_shared_party_contract_version()
{
    return 1;
}
