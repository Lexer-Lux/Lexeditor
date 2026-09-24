// Included before the production Party Switch module, with only memory/native
// I/O and platform services substituted by the Python test driver.
#include <array>
#include <algorithm>
#include <cstdint>
#include <cstring>
#include <type_traits>
#include <vector>
#include <cassert>
#include <cstdio>
#include <sys/mman.h>
#define __cdecl
#define MEM_COMMIT 0
#define MEM_RESERVE 0
#define PAGE_EXECUTE_READWRITE 0
static void *VirtualAlloc(void *,int,int,int) { return nullptr; }
static void *GetCurrentProcess() { return nullptr; }
static void FlushInstructionCache(void *,void *,int) {}
static void replace_function(std::uintptr_t,void *) {}
static void ffnx_warning(const char *,...) {}
static void ffnx_trace(const char *,...) {}
static bool ff8=true,enable_ff8_party_switch=true;
#define FF8_US_VERSION true
constexpr int MODE_BATTLE=1;
struct Mode { int driver_mode=MODE_BATTLE; } mode;
static Mode *getmode_cached() { return &mode; }
constexpr std::uint32_t CTX=0x2100000,POOL=0x2101000;
struct Event { std::uint32_t record; int type; std::uintptr_t callback; };
static std::vector<Event> queued;
static std::vector<std::array<std::uintptr_t,5>> calls;
static bool allocation_fails=false;
static unsigned original_calls=0;
template<class T> T &test_mem(std::uintptr_t a) {
    if constexpr(std::is_pointer_v<T>) {
        static T pointer;
        pointer=reinterpret_cast<T>(*reinterpret_cast<std::uint32_t *>(a));
        return pointer;
    } else return *reinterpret_cast<T *>(a);
}
static std::uintptr_t dispatch(std::uintptr_t address,const std::vector<std::uintptr_t>& args) {
    std::array<std::uintptr_t,5> logged{};logged[0]=address;
    std::copy_n(args.begin(),std::min(args.size(),std::size_t(4)),logged.begin()+1);calls.push_back(logged);
    if(address==0x500DF0) {
        if(allocation_fails) return 8;
        for(unsigned i=0;i<30;++i) {
            const auto record=POOL+i*12;
            if(!test_mem<std::uint8_t>(record+1)) {
                test_mem<std::uint8_t>(record+1)=0x80;
                queued.push_back({record,int(args[0]),args[2]});return record+8;
            }
        }
        return 8;
    }
    if(address==0x4876D0) {
        test_mem<std::uint8_t>(0x1D280C2)=0;
        test_mem<std::uint8_t>(0x1D28DF9)=test_mem<std::uint8_t>(0x1D28DFD)=1;
    }
    if(address==0x495960) {
        auto st=0x1CFF000+args[1]*0x1D0,sv=0x1CFE0E8+args[0]*0x98;
        test_mem<std::uint16_t>(st+0x172)=test_mem<std::uint16_t>(sv);
        test_mem<std::uint16_t>(st+0x174)=9000;
    }
    if(address==0x48B310) {
        auto actor=0x1D27B10+args[0]*0xD0,st=0x1CFF000+args[0]*0x1D0;
        test_mem<std::uint32_t>(actor+0x18)=test_mem<std::uint16_t>(st+0x172);
        test_mem<std::uint16_t>(actor+0x80)=0;
        test_mem<std::uint32_t>(actor+8)=0;
    }
    if(address==0x484490) test_mem<std::uint32_t>(0x1D27B24+args[0]*0xD0)=0;
    if(address==0x4B1830) test_mem<std::uint8_t>(0x1D76979+args[0]*0x6C)=args[1];
    if(address==0x47DD30 || address==0x47DAF0)
        dispatch(0x500DF0,{address==0x47DD30?0x66U:0x67U,0x80,0});
    if(address==0x47E3F0) dispatch(0x500DF0,args);
    return 0;
}
template<class T> std::uintptr_t pack_arg(T v) {
    if constexpr(std::is_pointer_v<T>) return reinterpret_cast<std::uintptr_t>(v);
    else return static_cast<std::uintptr_t>(v);
}
template<class R,class... A> R test_native(std::uintptr_t address,A... args) {
    auto result=dispatch(address,{pack_arg(args)...});
    if constexpr(std::is_void_v<R>) return;
    else if constexpr(std::is_pointer_v<R>) return reinterpret_cast<R>(result);
    else return static_cast<R>(result);
}

// Shared pool integration is exercised by verify_ff8_shared_party.py. This
// policy harness records lifecycle calls without substituting private copies.
enum class SharedPartyStockOwnership { blocked, private_stocks, shared_pool };
static SharedPartyStockOwnership shared_ownership=SharedPartyStockOwnership::private_stocks;
static std::vector<std::array<int,2>> shared_events;
SharedPartyStockOwnership lexeditor_ff8_shared_party_begin(int s) { shared_events.push_back({1,s});return shared_ownership; }
void lexeditor_ff8_shared_party_materialized(int s) { shared_events.push_back({2,s}); }
void lexeditor_ff8_shared_party_cancel(int s) { shared_events.push_back({3,s}); }
void lexeditor_ff8_shared_party_reset() { shared_events.push_back({4,-1}); }
