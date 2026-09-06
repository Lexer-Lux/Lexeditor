static void underlying() {
    ++original_calls;
    assert(test_mem<std::uint16_t>(CTX+0x10)==0);
    assert(test_mem<std::uint16_t>(CTX+0x12)==0);
    assert(test_mem<std::uint16_t>(CTX+0x14)==0);
}
static void reset(int actor_slot) {
    std::memset(reinterpret_cast<void *>(0x1CF0000),0,0x500000);
    queued.clear();calls.clear();allocation_fails=false;original_calls=0;
    opened=pending=false;slot=-1;chosen=0;incoming=outgoing=-1;
    phase=Phase::idle;reserve={};previous=0;mode.driver_mode=MODE_BATTLE;original=&underlying;
    mem<std::uint32_t>(0x1D6D490)=CTX;
    mem<std::uint32_t>(kQueue+8)=POOL;mem<std::int16_t>(kQueue+12)=30;
    mem<std::int8_t>(0x1D76844)=actor_slot;
    mem<std::uint8_t>(CTX+0x2D)=4;
    mem<std::uint16_t>(0x1D76840)=0x1000;mem<std::uint8_t>(0x1D7685B)=7;
    mem<std::uint8_t>(0x1D280C2)=1;
    for(int id=0;id<8;++id) {
        mem<std::uint16_t>(kSaved+id*0x98)=5000+id;
        mem<std::uint8_t>(kSaved+id*0x98+0x94)=1;
    }
    for(int i=0;i<3;++i) {
        mem<std::uint8_t>(kParty+i)=i;
        mem<std::uint16_t>(kModels+i*0x9C)=3;
        mem<std::uint32_t>(kActor+i*0xD0+0x18)=1234+i;
        mem<std::uint16_t>(kActor+i*0xD0+0x80)=0x20;
        mem<std::uint32_t>(kActor+i*0xD0+8)=0x400;
        mem<std::uint32_t>(kActor+i*0xD0+0x14)=0xFFFF;
        mem<std::uint8_t>(0x1D76979+i*0x6C)=1;
        for(int m=0;m<32;++m) {
            mem<std::uint8_t>(kStats+i*0x1D0+0x82+m*5)=m;
            mem<std::uint8_t>(kStats+i*0x1D0+0x83+m*5)=m+10;
        }
    }
    std::memset(reinterpret_cast<void *>(kSelector),0x52,20);
}
static void press(unsigned key) {
    previous=0;mem<std::uint16_t>(CTX+0x10)=key;controller();
}
static void execute_callback() {
    assert(!queued.empty() && queued.front().type==0x0A);
    auto e=queued.front();queued.erase(queued.begin());
    reinterpret_cast<void(*)(std::uint32_t)>(e.callback)(mem<std::uint32_t>(e.record+8));
    mem<std::uint8_t>(e.record+1)=0;
}
static void retire_model(int actor_slot) {
    assert(queued.size()==1 && queued.front().type==0x69);
    auto e=queued.front();queued.erase(queued.begin());
    assert(mem<std::int16_t>(e.record+8)==actor_slot);
    // Native behavior independently executed by the Unicorn regression.
    mem<std::uint16_t>(kActor+actor_slot*0xD0+0x80)|=1;
    mem<std::uint16_t>(kModels+actor_slot*0x9C)=0;
    mem<std::uint8_t>(e.record+1)=0;
}
static void complete_model_load() {
    const int expected[]={0x66,0x67,0x0E,0x70};
    for(auto type:expected) {
        assert(!queued.empty() && queued.front().type==type);
        auto e=queued.front();queued.erase(queued.begin());mem<std::uint8_t>(e.record+1)=0;
    }
    execute_callback();
}
int main() {
    auto *mapped=mmap(reinterpret_cast<void *>(0x1CF0000),0x500000,PROT_READ|PROT_WRITE,
        MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED,-1,0);
    assert(mapped!=MAP_FAILED);
    for(int i=0;i<3;++i) for(bool invalidated:{false,true}) {
        reset(i);press(4);assert(opened && count==5);press(0x40);
        assert(pending && phase==Phase::queued && !opened);
        for(int b=0;b<20;++b) assert(mem<std::uint8_t>(kSelector+b)==0x52);
        execute_callback();assert(phase==Phase::retiring);
        assert(mem<std::uint16_t>(kSaved+i*0x98)==1234+i);
        assert(reserve[i].status16==0x20 && reserve[i].status32==0x400);
        for(int m=0;m<32;++m) assert(mem<std::uint8_t>(kSaved+i*0x98+0x11+m*2)==m+10);
        const auto count_before=queued.size();lexeditor_ff8_party_switch_tick();
        assert(queued.size()==count_before); // do not reuse an owned model
        mem<std::uint16_t>(CTX+0x12)=0x40;mem<std::uint16_t>(CTX+0x14)=0x4000;
        controller();assert(original_calls==1);
        assert(mem<std::uint16_t>(CTX+0x12)==0x40 && mem<std::uint16_t>(CTX+0x14)==0x4000);
        retire_model(i);
        if(invalidated) mem<std::uint8_t>(kSaved+incoming*0x98+0x94)=0;
        lexeditor_ff8_party_switch_tick();assert(phase==Phase::rebuild_queued);
        execute_callback();assert(phase==Phase::loading);
        complete_model_load();assert(!pending && phase==Phase::idle);
        assert(mem<std::uint8_t>(kParty+i)==(invalidated?i:3));
        assert(mem<std::uint8_t>(0x1D280C2)==1 && !mem<std::uint8_t>(0x1D28DF9));
        assert(mem<std::uint8_t>(0x1D76979+i*0x6C)==1);
        assert(mem<std::uint32_t>(kActor+i*0xD0+0x14)==(invalidated?0xFFFFU:0U));
        if(invalidated) assert(mem<std::uint16_t>(kActor+i*0xD0+0x80)==0x20);
        assert(std::any_of(calls.begin(),calls.end(),[](auto c){return c[0]==0x4B18C0;}));
        for(int other=0;other<3;++other) if(other!=i) {
            assert(mem<std::uint8_t>(kParty+other)==other);
            assert(mem<std::uint16_t>(kModels+other*0x9C)==3);
        }
    }
    reset(0);press(4);press(0x10);assert(!opened && !pending && queued.empty());
    reset(0);press(4);allocation_fails=true;press(0x40);
    assert(opened && !pending && mem<std::uint8_t>(0x1D280C2)==1);
    reset(0);press(4);
    for(int i=0;i<30;++i) mem<std::uint8_t>(POOL+i*12+1)=0x80;
    press(0x40);assert(opened && !pending && queued.empty());
    reset(0);press(4);press(0x40);auto old_ticket=generation;
    mode.driver_mode=0;lexeditor_ff8_party_switch_tick();
    begin_swap(old_ticket);assert(!pending && phase==Phase::idle);
    reset(0);press(4);press(0x40);mem<std::uint16_t>(kModels)=1;
    execute_callback();assert(!pending && mem<std::uint8_t>(0x1D280C2)==1);
    std::puts("PASS: compiled production Party Switch policy: 3 slots, cancellation, allocation failure, full queue, invalidated reserve rollback, HUD refresh, input suppression, stale callbacks.");
}
