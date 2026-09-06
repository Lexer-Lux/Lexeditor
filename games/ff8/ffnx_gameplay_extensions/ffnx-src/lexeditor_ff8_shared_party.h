#pragma once

// The event-driven Party Switch module must explicitly retire and re-register
// a shared-stock mirror. Its call to the native actor initializer originates
// in FFNx, not one of the game's previously reviewed return addresses.
enum class SharedPartyStockOwnership {
    blocked,
    private_stocks,
    shared_pool,
};
SharedPartyStockOwnership lexeditor_ff8_shared_party_begin(int slot);
void lexeditor_ff8_shared_party_materialized(int slot);
void lexeditor_ff8_shared_party_cancel(int slot);
void lexeditor_ff8_shared_party_reset();
