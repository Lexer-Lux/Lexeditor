#include "lexeditor_ff8_party_switch.h"
#include <windows.h>
#include <array>
#include <algorithm>
#include <cstdint>
#include <cstring>
#include "cfg.h"
#include "common.h"
#include "globals.h"
#include "ff8.h"
#include "patch.h"
#include "log.h"

namespace {
template<class T> T &mem(std::uintptr_t a) { return *reinterpret_cast<T *>(a); }
template<class R, class... A> R native(std::uintptr_t a, A... args) {
    return reinterpret_cast<R(__cdecl *)(A...)>(a)(args...);
}
constexpr std::uintptr_t kController=0x4BB9E0, kParty=0x1CFE74C;
constexpr std::uintptr_t kSaved=0x1CFE0E8, kStats=0x1CFF000, kActor=0x1D27B10;
using Controller=void(__cdecl *)();
Controller original=nullptr;
bool opened=false, pending=false;
int slot=-1, chosen=0, incoming=-1, outgoing=-1;
enum class Phase { idle, queued, retiring, rebuild_queued, loading };
Phase phase=Phase::idle;
std::uint32_t generation=0, pending_frames=0, outgoing_atb=0;
bool restoring=false;
std::uint8_t hud_enabled=1;
std::array<std::uint8_t,20> selector_backup{};
constexpr std::uintptr_t kModels=0x1D972C0, kQueue=0x1D96D68;
constexpr std::uintptr_t kSelector=0x1D76628+5*20;

// Native 00503270 allocates twelve-byte records from this thirty-entry pool.
// Count free records, including records still owned by presentation tasks;
// a queue-length check alone can miss an in-flight allocation.
bool event_room(unsigned needed) {
    const auto pool=mem<std::uint32_t>(kQueue+8);
    const int capacity=mem<std::int16_t>(kQueue+12);
    if(!pool || capacity<=0 || capacity>64) return false;
    unsigned free=0;
    for(int i=0;i<capacity;++i) if(!mem<std::uint8_t>(pool+i*12+1)) ++free;
    return free>=needed;
}
bool queue_callback(void(__cdecl *callback)(std::uint32_t), std::uint32_t ticket) {
    // 0047E200 wraps this allocator but discards its failure result. Event 0A
    // passes the four-byte payload to its callback (00500A3D..00500A47).
    const auto payload=native<std::uintptr_t>(0x500DF0,0x0A,0x80,reinterpret_cast<void *>(callback));
    if(payload<=8) return false;
    mem<std::uint32_t>(payload)=ticket;
    return true;
}
void __cdecl begin_swap(std::uint32_t ticket);
void __cdecl replace_actor(std::uint32_t ticket);
void __cdecl finish(std::uint32_t ticket);
std::array<int,8> choices{};
int count=0;
std::uint16_t previous=0;
struct ReserveState { bool known=false; std::uint16_t status16=0; std::uint32_t status32=0; };
std::array<ReserveState,8> reserve{};
std::uint8_t pause1=0,pause2=0,pause3=0;

bool eligible(int id) {
    if (id<0 || id>=8) return false;
    auto s=kSaved+id*0x98;
    if (!(mem<std::uint8_t>(s+0x94)&1) ||
        (mem<std::uint16_t>(s+0x96)&1) || mem<std::uint16_t>(s)==0) return false;
    for(int i=0;i<3;++i) if(mem<std::uint8_t>(kParty+i)==id) return false;
    return true;
}
void close_menu() {
    if(!opened) return;
    opened=false;
    std::memcpy(reinterpret_cast<void *>(kSelector),selector_backup.data(),selector_backup.size());
    // The underlying command controller was never closed or advanced.
}
std::uint32_t __cdecl draw(std::uint32_t ordering, std::uint32_t primitives, void *, int) {
    if(!opened || count<=0 || count>8 || !mem<std::uint32_t>(0x1D6D490)) return primitives;
    static const unsigned char cursor[]={0xCB,0x20,0};
    std::array<const unsigned char *,8> names{};
    int width=80;
    for(int i=0;i<count;++i) {
        // 004A7250 stops on control codes <=0x18; it cannot expand 03/ID.
        // Use the same native name resolver as the game's target-name path.
        names[i]=native<const unsigned char *>(0x47EB50,choices[i]);
        // Measure with the same glyph-width table as 004A7250.
        const int size=names[i] ? native<int>(0x4B1850,names[i]) : 0;
        width=std::max(width,size+30);
    }
    auto *context=mem<std::uint8_t *>(0x1D6D490);
    mem<std::uint8_t>(reinterpret_cast<std::uintptr_t>(context)+0x23)=8;
    auto *rect=reinterpret_cast<std::int16_t *>(context+0x34);
    rect[0]=20; rect[1]=26; rect[2]=static_cast<std::int16_t>(std::min(width,296));
    rect[3]=static_cast<std::int16_t>(count*16+12);
    primitives=native<std::uint32_t>(0x4A7510,ordering,primitives,0x1000,0);
    for(int i=0;i<count;++i) {
        if(i==chosen) primitives=native<std::uint32_t>(0x4A7250,ordering,primitives,24,32+i*16,cursor,7);
        primitives=native<std::uint32_t>(0x4A7250,ordering,primitives,38,32+i*16,names[i],7);
    }
    return primitives;
}
void abort_swap() {
    // Event11 inserts the ready actor removed by event12.
    if(slot>=0 && slot<3) native<void>(0x4AD620,slot,0x11,0x80,0);
    mem<std::uint8_t>(0x1D280C2)=pause1;
    mem<std::uint8_t>(0x1D28DF9)=pause2;
    mem<std::uint8_t>(0x1D28DFD)=pause3;
    pending=false; phase=Phase::idle; ++generation;
    ffnx_warning("Party Switch: cancelled before model retirement; ready turn restored.\n");
}
void __cdecl begin_swap(std::uint32_t ticket) {
    if(!pending || phase!=Phase::queued || ticket!=generation) return;
    if(slot<0 || slot>=3 || !eligible(incoming) ||
       mem<std::uint8_t>(kParty+slot)!=outgoing || !event_room(1) ||
       ((mem<std::uint16_t>(kModels+slot*0x9C)&3)==1)) {
        abort_swap(); return;
    }
    const auto actor=kActor+slot*0xD0, stats=kStats+slot*0x1D0;
    const auto saved=kSaved+outgoing*0x98;
    // Native saveback 0048B8C1..0048B8D2 persists this participant's current HP.
    mem<std::uint16_t>(saved)=static_cast<std::uint16_t>(mem<std::uint32_t>(actor+0x18));
    // Native 00486D1C..00486D2E copies each live ID/stock pair to its owner.
    for(int i=0;i<32;++i) {
        mem<std::uint8_t>(saved+0x10+i*2)=mem<std::uint8_t>(stats+0x82+i*5);
        mem<std::uint8_t>(saved+0x11+i*2)=mem<std::uint8_t>(stats+0x83+i*5);
    }
    reserve[outgoing]={true,mem<std::uint16_t>(actor+0x80),mem<std::uint32_t>(actor+8)};
    outgoing_atb=mem<std::uint32_t>(actor+0x14);
    hud_enabled=mem<std::uint8_t>(0x1D76928+slot*0x6C+0x51);
    // Event 66 waits for model flag 1 to clear. A living party member still
    // owns that model; the encounter-specific replacement relied on an
    // earlier death/removal. Explicitly retire the old model first.
    // Event 69 runs native 00502ED0 -> 0050C5F0, including native resource
    // release. Save HP/status BEFORE it: its native cleanup marks the old
    // participant removed/KO while the model leaves.
    if(mem<std::uint16_t>(kModels+slot*0x9C)&1) {
        const auto payload=native<std::uintptr_t>(0x500DF0,0x69,0x80,0);
        if(payload<=8) { abort_swap(); return; }
        mem<std::int16_t>(payload)=static_cast<std::int16_t>(slot);
    }
    native<void>(0x4B1830,slot,0);
    phase=Phase::retiring;
    ffnx_trace("Party Switch: slot %d, character %d -> %d; retiring old model.\n",slot,outgoing,incoming);
}
void __cdecl replace_actor(std::uint32_t ticket) {
    if(!pending || phase!=Phase::rebuild_queued || ticket!=generation) return;
    if((mem<std::uint16_t>(kModels+slot*0x9C)&1) || !event_room(5)) {
        phase=Phase::retiring; return; // retry safely before any identity change
    }
    // If the reserve became unavailable while queued, reload the original
    // participant instead. Never leave a retired model slot empty on abort.
    restoring=!eligible(incoming);
    const int target=restoring ? outgoing : incoming;
    const auto actor=kActor+slot*0xD0, stats=kStats+slot*0x1D0;
    // These are the native single-slot replacement primitives, in their native
    // order. The encounter callback and its private globals are not used.
    mem<std::uint8_t>(kParty+slot)=static_cast<std::uint8_t>(target);
    native<void>(0x495530,target,slot);
    native<void>(0x495960,target,slot);
    native<void>(0x495EC0);
    native<void>(0x48B5F0,slot);
    native<void>(0x48B310,slot);
    if(reserve[target].known) {
        mem<std::uint16_t>(actor+0x80)=reserve[target].status16;
        mem<std::uint32_t>(actor+8)=reserve[target].status32;
        mem<std::uint16_t>(stats+0x1B2)=reserve[target].status16;
    }
    // The native ATB initializer sets the incoming actor to zero, even if
    // Auto-Haste/startup randomness filled it during the participant refresh.
    native<void>(0x484490,slot);
    native<void>(0x47DD30,slot); // enqueue model replacement event66
    native<void>(0x47DAF0,slot); // enqueue status/model refresh event67
    native<void>(0x47E3F0,0x0E,0x80,0); // native presentation barrier
    native<void>(0x47E3F0,0x70,0x80,0); // same replacement presentation completion
    phase=Phase::loading;
    queue_callback(&finish,ticket); // five free records were reserved above
}
void __cdecl finish(std::uint32_t ticket) {
    if(!pending || phase!=Phase::loading || ticket!=generation) return;
    // Rebuild cached HUD name/HP, not just the battle participant. Otherwise
    // the panel can continue to display the outgoing character's data.
    native<void>(0x4B18C0,reinterpret_cast<void *>(0x1D76928+slot*0x6C),slot);
    native<void>(0x4B1830,slot,static_cast<int>(hud_enabled));
    if(restoring) {
        mem<std::uint32_t>(kActor+slot*0xD0+0x14)=outgoing_atb;
        native<void>(0x4AD620,slot,0x11,0x80,0);
    }
    native<void>(0x485FF0); // rebuild targetable/live masks from refreshed actor
    native<void>(0x4AB450); // publish those masks to battle target selection
    mem<std::uint8_t>(0x1D280C2)=pause1;
    mem<std::uint8_t>(0x1D28DF9)=pause2;
    mem<std::uint8_t>(0x1D28DFD)=pause3;
    pending=false; phase=Phase::idle;
    ffnx_trace("Party Switch: slot %d %s; ATB %u.\n",slot,
        restoring ? "original participant restored" : "replacement finished",
        mem<std::uint32_t>(kActor+slot*0xD0+0x14));
}
void __cdecl controller() {
    auto *mode=getmode_cached();
    if(!enable_ff8_party_switch || !mode || mode->driver_mode!=MODE_BATTLE) {
        opened=false; previous=0;
        original(); return;
    }
    const int active=mem<std::int8_t>(0x1D76844);
    const auto context=mem<std::uint32_t>(0x1D6D490);
    if(!context) { original(); return; }
    // Read exactly the same logical input record as the native controller.
    const auto held=mem<std::uint16_t>(context+0x10);
    const auto edge=static_cast<std::uint16_t>(held & ~previous);
    previous=held;
    if(pending) {
        // Keep native ready-list/command-panel housekeeping alive without
        // accepting commands during the transition.
        const auto held16=mem<std::uint16_t>(context+0x10);
        const auto edge16=mem<std::uint16_t>(context+0x12);
        const auto repeat16=mem<std::uint16_t>(context+0x14);
        mem<std::uint16_t>(context+0x10)=0;
        mem<std::uint16_t>(context+0x12)=0;
        mem<std::uint16_t>(context+0x14)=0;
        original();
        mem<std::uint16_t>(context+0x10)=held16;
        mem<std::uint16_t>(context+0x12)=edge16;
        mem<std::uint16_t>(context+0x14)=repeat16;
        return;
    }
    if(opened) {
        if(active!=slot || mem<std::uint16_t>(kActor+slot*0xD0+0x80)&1) {
            close_menu(); original(); return;
        }
        if(edge&0x10) { close_menu(); ffnx_trace("Party Switch: selector cancelled; turn retained.\n"); return; }
        if(edge&0x1000) chosen=(chosen+count-1)%count;
        if(edge&0x4000) chosen=(chosen+1)%count;
        if(edge&0x40) {
            const int id=choices[chosen];
            if(!eligible(id)) { close_menu(); return; }
            if(!event_room(1)) return; // retain selector and turn on a full queue
            incoming=id; outgoing=mem<std::uint8_t>(kParty+slot);
            ++generation;
            if(!queue_callback(&begin_swap,generation)) return;
            close_menu(); pending=true; phase=Phase::queued; pending_frames=0;
            pause1=mem<std::uint8_t>(0x1D280C2);
            pause2=mem<std::uint8_t>(0x1D28DF9);
            pause3=mem<std::uint8_t>(0x1D28DFD);
            native<void>(0x4876D0);
            // Native menu event12 removes this actor from the ready list.
            // Other ready actors and queued commands remain owned by the game.
            native<void>(0x4AD620,slot,0x12,0x80,0);
        }
        return;
    }
    if((edge&4) && active>=0 && active<3 && mem<std::uint8_t>(kParty+active)<8 && mem<std::uint8_t>(context+0x2D)==4 &&
       mem<std::uint16_t>(0x1D76840)==0x1000 && mem<std::uint8_t>(0x1D7685B)==7 &&
       mem<std::uint8_t>(0x1D280C2)==1 && !mem<std::uint8_t>(0x1D28DF9)) {
        count=0;
        for(int id=0;id<8;++id) if(eligible(id)) choices[count++]=id;
        if(count) {
            slot=active; chosen=0;
            std::memcpy(selector_backup.data(),reinterpret_cast<const void *>(kSelector),selector_backup.size());
            opened=true;
            ffnx_trace("Party Switch: selector opened for slot %d, %d reserves.\n",slot,count);
            native<void>(0x4B9AD0,5,0,reinterpret_cast<void *>(&draw),0);
            native<void>(0x4B9B90,5,2);
            return;
        }
    }
    original();
}
}
void lexeditor_ff8_party_switch_install() {
    if(!ff8 || !FF8_US_VERSION || !enable_ff8_party_switch || original) return;
    const unsigned char expected[]={0x83,0xEC,0x14,0x53,0x55};
    if(std::memcmp(reinterpret_cast<void *>(kController),expected,5)!=0) { ffnx_warning("Party Switch: unsupported controller bytes.\n"); return; }
    auto *code=static_cast<unsigned char *>(VirtualAlloc(nullptr,16,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE));
    if(!code) { ffnx_warning("Party Switch: allocation failed.\n"); return; }
    std::memcpy(code,expected,5);
    code[5]=0xE9;
    const auto relative=static_cast<std::int32_t>(kController+5-reinterpret_cast<std::uintptr_t>(code+10));
    std::memcpy(code+6,&relative,4);
    FlushInstructionCache(GetCurrentProcess(),code,10);
    original=reinterpret_cast<Controller>(code);
    replace_function(kController,reinterpret_cast<void *>(&controller));
    ffnx_trace("Party Switch: native controller hook installed.\n");
}
void lexeditor_ff8_party_switch_tick() {
    if(!ff8 || !original) return;
    const auto *mode=getmode_cached();
    if(!mode || mode->driver_mode!=MODE_BATTLE) {
        if(pending || opened) ++generation;
        opened=false; pending=false; phase=Phase::idle; slot=-1; count=0; previous=0;
        reserve={};
        return;
    }
    if(pending) {
        ++pending_frames;
        // Poll only for resource retirement. All participant writes still
        // execute inside the engine's own event callback, never in flip().
        if(phase==Phase::retiring && !(mem<std::uint16_t>(kModels+slot*0x9C)&1) && event_room(6)) {
            if(queue_callback(&replace_actor,generation)) phase=Phase::rebuild_queued;
        }
        if(pending_frames%600==0) {
            ffnx_warning("Party Switch: transition waiting; phase=%d slot=%d modelFlags=%04X.\n",
                static_cast<int>(phase),slot,mem<std::uint16_t>(kModels+slot*0x9C));
        }
    }
}
