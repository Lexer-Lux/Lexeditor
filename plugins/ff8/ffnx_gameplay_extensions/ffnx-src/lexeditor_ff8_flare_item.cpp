// GPL-3.0-or-later. New item definition without changing fixed kernel tables.
#include "flare_item.h"
#include "cfg.h"
#include "common.h"
#include "globals.h"
#include "log.h"
#include "patch.h"

namespace {
bool installed = false;
bool metadata_ready = false;
bool prices_ready = false;
bool transactions_enabled = false;
constexpr unsigned char empty_text[] = {0};
using Loader = int(__cdecl *)(void **, const char *);
const auto stock_loader = reinterpret_cast<Loader>(0x004B96C0);
using MenuRequest = int(__cdecl *)();
MenuRequest request_from_menu = nullptr;
#if defined(_M_IX86)
std::uint32_t buy_continue = 0x004EC7AC;
std::uint32_t sell_continue = 0x004EC82B;
std::uint32_t refuse_transaction = 0x004EC7DC;
std::uint32_t menu_continue = 0x004F8A35;
std::uint32_t menu_done = 0x004FBF23;
#endif

const unsigned char *item_text(unsigned id, bool description) {
    if (id == lexeditor_flare::item_id)
        return metadata_ready ? (description ? lexeditor_flare::item_description :
                                 lexeditor_flare::item_name) : empty_text;
    if (id >= lexeditor_flare::item_id) return empty_text;
    // Keep the original fixed stock tables and their text-section offsets.
    // Appending kernel section 9 would shift the following fixed tables.
    const auto address = id < 33 ? 0x01CF7778u + id * 24 : 0x01CF7A0Cu + id * 4;
    const auto offset = *reinterpret_cast<const std::uint16_t *>(address + (description ? 2 : 0));
    if (offset == 0xffff) return reinterpret_cast<const unsigned char *>(0x01CFF84C);
    const auto text_section = *reinterpret_cast<const std::uint32_t *>(id < 33 ? 0x01CF3EE4 : 0x01CF3EE8);
    return reinterpret_cast<const unsigned char *>(0x01CF3E48 + text_section + offset);
}

// ID 199 enters stock transactions only when definition, price and use owner
// are ready. Stock commit scans 200 staged IDs but only 198 inventory slots.
extern "C" __declspec(dllexport) int __cdecl lexeditor_ff8_flare_transaction_allowed(unsigned buy) {
    if(!transactions_enabled || !metadata_ready || !prices_ready || !request_from_menu)return 0;
    if(!buy)return 1;
    const auto *inventory=reinterpret_cast<const unsigned char *>(0x01CFE79C);
    const auto *staged=reinterpret_cast<const unsigned char *>(0x01D8D058);
    bool capacity=false;unsigned owned=0;
    for(unsigned slot=0;slot<198;++slot) {
        const auto id=inventory[slot*2];
        if(id>=200)return 0;
        if(!id || !inventory[slot*2+1] || !staged[id])capacity=true;
        if(id==199)++owned;
    }
    return owned<=1 && (capacity || owned==1);
}
#if defined(_M_IX86)
extern "C" __declspec(dllexport) __declspec(naked) void lexeditor_ff8_flare_shop_buy_guard() {
    __asm {
        cmp ecx,199
        jb stock
        ja refuse
        pushfd
        pushad
        push 1
        call lexeditor_ff8_flare_transaction_allowed
        add esp,4
        test eax,eax
        jz denied
        popad
        popfd
    stock:
        mov eax,ecx
        mov cl,byte ptr [esi+048h]
        jmp dword ptr [buy_continue]
    denied:
        popad
        popfd
    refuse:
        jmp dword ptr [refuse_transaction]
    }
}
extern "C" __declspec(dllexport) __declspec(naked) void lexeditor_ff8_flare_shop_sell_guard() {
    __asm {
        cmp ecx,199
        jb stock
        ja refuse
        pushfd
        pushad
        push 0
        call lexeditor_ff8_flare_transaction_allowed
        add esp,4
        test eax,eax
        jz denied
        popad
        popfd
    stock:
        mov eax,ecx
        mov cl,byte ptr [esi+048h]
        jmp dword ptr [sell_continue]
    denied:
        popad
        popfd
    refuse:
        jmp dword ptr [refuse_transaction]
    }
}
#endif
}

extern "C" __declspec(dllexport) int __cdecl lexeditor_ff8_flare_menu_request_bind(MenuRequest request) {
    // Bind before metadata load so a use flag is never exposed without a
    // request owner. Disabling remains possible and makes confirm refuse.
    if (request && metadata_ready) return 0;
    request_from_menu = request;
    return 1;
}

extern "C" __declspec(dllexport) int __cdecl lexeditor_ff8_flare_menu_confirm(unsigned char *context) {
    if (!context || context[0x65] < lexeditor_flare::item_id) return 0;
    bool accepted = context[0x65] == lexeditor_flare::item_id && metadata_ready &&
        request_from_menu && request_from_menu() == 1;
    // Stock state 0x70 closes the item pane through its own fade/cleanup path.
    // The request owner must finish leaving the main menu before world service.
    *reinterpret_cast<std::uint16_t *>(context + 0x10) = accepted ? 0x70 : 4;
    if (!accepted) reinterpret_cast<void(__cdecl *)(int)>(0x004B92A0)(5);
    return 1;
}

#if defined(_M_IX86)
extern "C" __declspec(dllexport) __declspec(naked) void lexeditor_ff8_flare_menu_dispatch() {
    __asm {
        pushfd
        pushad
        push esi
        call lexeditor_ff8_flare_menu_confirm
        add esp,4
        test eax,eax
        jnz handled
        popad
        popfd
        mov edi,dword ptr ds:[01D2BB2Ch]
        jmp dword ptr [menu_continue]
    handled:
        popad
        popfd
        jmp dword ptr [menu_done]
    }
}
#endif

extern "C" __declspec(dllexport) const unsigned char *__cdecl lexeditor_ff8_flare_item_name(unsigned id) {
    return item_text(id, false);
}
extern "C" __declspec(dllexport) const unsigned char *__cdecl lexeditor_ff8_flare_item_description(unsigned id) {
    return item_text(id, true);
}

extern "C" __declspec(dllexport) int __cdecl lexeditor_ff8_flare_load_metadata(void **out, const char *name) {
    const int size = stock_loader(out, name);
    if (!out || !*out || size != lexeditor_flare::stock_metadata_size) {
        metadata_ready = false;
        ffnx_warning("Signal Flare: item metadata size differs; new definition is disabled.\n");
        return size;
    }
    auto *expanded = external_malloc(lexeditor_flare::overlay_metadata_size);
    if (!expanded) {
        metadata_ready = false;
        return size;
    }
    lexeditor_flare::make_metadata(*out, size, expanded, lexeditor_flare::overlay_metadata_size);
    if (request_from_menu)
        static_cast<unsigned char *>(expanded)[lexeditor_flare::item_id * 4 + 1] = 0x11;
    // Match the game's allocation domain. Its normal menu shutdown frees this
    // buffer, and later stock file reloads leave the added tail intact.
    external_free(*out);
    *out = expanded;
    metadata_ready = true;
    return lexeditor_flare::overlay_metadata_size;
}

extern "C" __declspec(dllexport) int __cdecl lexeditor_ff8_flare_load_prices(void **out, const char *name) {
    prices_ready = false;
    const int size = stock_loader(out, name);
    if (!out || !*out || size != lexeditor_flare::stock_metadata_size) return size;
    auto *expanded = external_malloc(800);
    if (!expanded) return size;
    lexeditor_flare::make_prices(*out, size, expanded, 800);
    external_free(*out);
    *out = expanded;
    prices_ready = true;
    return 800;
}

// Deliberately not called by startup yet. The full use/transition owner must
// install this with its remaining-count notification and save/load checks.
static int prepare_definition(bool apply) {
#if !defined(_M_IX86)
    return 0;
#else
    if (!ff8 || !FF8_US_VERSION) return 0;
    if (installed) return 1;
    constexpr std::uint32_t loads[] = {0x004A1C8E, 0x004A1D63, 0x004A1DB1};
    const unsigned char name_entry[] = {0x8B,0x44,0x24,0x04,0x83,0xF8,0x21};
    for (auto address : {0x0047EA30u, 0x0047EA90u})
        if (std::memcmp(reinterpret_cast<void *>(address), name_entry, sizeof name_entry)) return 0;
    for (auto address : loads) {
        if (*reinterpret_cast<const unsigned char *>(address) != 0xE8) return 0;
        const auto displacement = *reinterpret_cast<const std::int32_t *>(address + 1);
        if (address + 5 + displacement != 0x004B96C0) return 0;
    }
    constexpr std::uint32_t price_load = 0x004A1DA2;
    if (*reinterpret_cast<const unsigned char *>(price_load) != 0xE8 ||
        price_load + 5 + *reinterpret_cast<const std::int32_t *>(price_load + 1) != 0x004B96C0) return 0;
    const unsigned char transaction[] = {0x8B,0xC1,0x8A,0x4E,0x48};
    for (auto address : {0x004EC7A7u, 0x004EC826u})
        if (std::memcmp(reinterpret_cast<void *>(address), transaction, sizeof transaction)) return 0;
    const unsigned char menu[] = {0x8B,0x3D,0x2C,0xBB,0xD2,0x01};
    if (std::memcmp(reinterpret_cast<void *>(0x4F8A2F), menu, sizeof menu)) return 0;
    if (!apply) return 1;
    for (auto address : loads)
        replace_call(address, reinterpret_cast<void *>(&lexeditor_ff8_flare_load_metadata));
    replace_function(0x0047EA30, reinterpret_cast<void *>(&lexeditor_ff8_flare_item_name));
    replace_function(0x0047EA90, reinterpret_cast<void *>(&lexeditor_ff8_flare_item_description));
    replace_call(price_load, reinterpret_cast<void *>(&lexeditor_ff8_flare_load_prices));
    replace_function(0x004EC7A7, reinterpret_cast<void *>(&lexeditor_ff8_flare_shop_buy_guard));
    replace_function(0x004EC826, reinterpret_cast<void *>(&lexeditor_ff8_flare_shop_sell_guard));
    replace_function(0x004F8A2F, reinterpret_cast<void *>(&lexeditor_ff8_flare_menu_dispatch));
    patch_code_byte(0x004F8A34, 0x90);
    installed = true;
    ffnx_trace("Signal Flare: new item 199 metadata/text overlay installed; stock definitions retained.\n");
    return 1;
#endif
}

extern "C" __declspec(dllexport) int __cdecl lexeditor_ff8_flare_definition_validate() {return prepare_definition(false);}
extern "C" __declspec(dllexport) int __cdecl lexeditor_ff8_flare_definition_install() {return prepare_definition(true);}

extern "C" __declspec(dllexport) int __cdecl lexeditor_ff8_flare_definition_ready() {return metadata_ready && prices_ready;}

extern "C" __declspec(dllexport) void __cdecl lexeditor_ff8_flare_transactions_enable(int enabled) {transactions_enabled=enabled!=0;}
