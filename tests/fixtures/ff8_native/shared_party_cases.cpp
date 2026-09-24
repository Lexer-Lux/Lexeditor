void setup(unsigned limit) {
    std::memset(&save,0xA5,sizeof(save));actors.fill(0xB6);refreshes.fill(0);
    mode.driver_mode=MODE_BATTLE;
    g_state={};g_state.stock_limit=static_cast<std::uint8_t>(limit);
    g_frame_depth=g_internal_depth=g_private_transaction_depth=g_reconciliation_owner_depth=0;
    lexeditor_ff8_shared_party_reset();
    PrivateInventories start{};start[0][0]={1,static_cast<std::uint8_t>(limit)};
    assert(activate_runtime(g_state,start).shared_pool_active);
    write_saved(start);g_actor_ready.fill(true);mirror_actors();
}
void identical(unsigned amount) {
    const auto pool=g_state.canonical_snapshot;
    assert(pool[0].id==(amount?1:0) && pool[0].amount==amount);
    for(const auto &inv:read_saved()) assert(inv==pool);
    for(int s=0;s<3;++s) if(g_actor_ready[s]) assert(read_actor(s)==pool);
    // Synchronization must never corrupt equipment, HP, party flags, or the
    // native five-byte battle-slot metadata following ID/quantity.
    for(const auto &ch:save.chars) for(auto value:ch.untouched) assert(value==0xA5);
    for(int s=0;s<3;++s) for(int m=0;m<32;++m) for(int b=2;b<5;++b)
        assert(actors[s*0x1D0+0x82+m*5+b]==0xB6);
}
void cast(int slot) {
    const auto before=read_actors();auto inventory=read_actor(slot);
    assert(consume_stock(inventory,1,1));write_actor(slot,inventory);
    adopt_actor_change(before);
}
void draw(int character, unsigned cap) {
    auto saved=read_saved();assert(add_stock(saved[character],1,1,cap));write_saved(saved);
    adopt_saved_change();
}
int main() {
    // Every supported stock cap, each active slot, repeated out/back swaps,
    // concurrent Draw/cast while the model is retired, and canonical saving.
    for(unsigned cap=1;cap<=255;++cap) for(int slot=0;slot<3;++slot) {
        setup(cap);identical(cap);
        for(int repeat=0;repeat<3;++repeat) {
            assert(lexeditor_ff8_shared_party_begin(slot)==SharedPartyStockOwnership::shared_pool);
            assert(!g_actor_ready[slot]);
            assert(lexeditor_ff8_shared_party_begin((slot+1)%3)==SharedPartyStockOwnership::blocked);
            cast((slot+1)%3);identical(cap-1);
            draw(7,cap);identical(cap);
            // The outgoing/incoming record can be cleared and filled by
            // native code: the bridge restores CURRENT stock, not old stock.
            write_actor(slot,{});
            lexeditor_ff8_shared_party_materialized(slot);
            assert(g_actor_ready[slot]);identical(cap);
            cast(slot);identical(cap-1);draw(3,cap);identical(cap);
        }
        auto saved=read_saved();
        assert(begin_canonical_save(g_state,saved));
        for(int c=1;c<8;++c) assert(saved[c]==MagicInventory{});
        const auto disk=saved;
        assert(finish_canonical_save(g_state,saved));write_saved(saved);identical(cap);
        RuntimeState reload{};reload.stock_limit=cap;auto loaded=disk;
        assert(activate_runtime(reload,loaded).shared_pool_active);
        assert(reload.canonical_snapshot==g_state.canonical_snapshot);
        // Lowering a cap refuses overflow without changing any saved stock.
        if(cap>1) {
            reload={};reload.stock_limit=cap-1;loaded=disk;
            assert(!activate_runtime(reload,loaded).shared_pool_active);assert(loaded==disk);
        }
        assert(lexeditor_ff8_shared_party_begin(slot)==SharedPartyStockOwnership::shared_pool);
        cast((slot+1)%3);lexeditor_ff8_shared_party_cancel(slot);
        assert(g_actor_ready[slot]);identical(cap-1);
    }
    setup(100);
    for(int invalid:{-1,3,255}) assert(lexeditor_ff8_shared_party_begin(invalid)==SharedPartyStockOwnership::blocked);
    for(auto *depth:{&g_internal_depth,&g_private_transaction_depth,&g_reconciliation_owner_depth}) {
        *depth=1;assert(lexeditor_ff8_shared_party_begin(0)==SharedPartyStockOwnership::blocked);*depth=0;identical(100);
    }
    g_frame_depth=1;assert(lexeditor_ff8_shared_party_begin(0)==SharedPartyStockOwnership::blocked);g_frame_depth=0;
    g_state.phase=RuntimePhase::save_canonical;
    assert(lexeditor_ff8_shared_party_begin(0)==SharedPartyStockOwnership::blocked);
    g_state.phase=RuntimePhase::shared_mirror;
    assert(lexeditor_ff8_shared_party_begin(0)==SharedPartyStockOwnership::shared_pool);
    lexeditor_ff8_shared_party_materialized(1);assert(!g_actor_ready[0]);
    mode.driver_mode=0;const auto before=actors;lexeditor_ff8_shared_party_reset();
    lexeditor_ff8_shared_party_materialized(0);assert(actors==before);
    setup(100);g_state.shared_pool_active=false;
    assert(lexeditor_ff8_shared_party_begin(0)==SharedPartyStockOwnership::private_stocks);
    assert(g_actor_ready[0]);identical(100);
    std::puts("PASS: real shared core/reconciliation/bridge: 255 caps x 3 slots, repeated swaps, concurrent Draw/cast, cancellation, ownership guards, metadata preservation and canonical save/reload.");
}
