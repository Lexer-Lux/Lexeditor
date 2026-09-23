// GPL-3.0-or-later. Additional listing; never changes saved shop slot layout.
#include "flare_shop.h"
#include "common.h"
#include "globals.h"
#include "cfg.h"
#include "patch.h"
#include <cstring>
#include <utility>
#include <initializer_list>

extern "C" int __cdecl lexeditor_ff8_flare_definition_ready();

namespace {
lexeditor_flare::ShopView view;
std::uint32_t selected_shops = lexeditor_flare::all_shops;
unsigned availability = lexeditor_flare::shop_stock;
bool installed = false;
std::uint32_t first_continue = 0x004C2B30;
std::uint32_t second_continue = 0x004EDC50;
std::uint32_t page_continue = 0x004EC30A;
unsigned buy_pages = 2;
}

// Lexer selected every shop. Keep the listing configurable for clean reset and
// diagnostics. Purchase remains guarded until use and persistence are ready.
extern "C" __declspec(dllexport) int __cdecl lexeditor_ff8_flare_shop_configure(
        std::uint32_t mask, unsigned stock) {
    if (mask >> 20 || (mask && (!stock || stock > 100))) return 0;
    selected_shops = mask;
    availability = stock;
    return 1;
}

extern "C" __declspec(dllexport) void __cdecl lexeditor_ff8_flare_shop_refresh(unsigned shop) {
    lexeditor_flare::ShopRow stock[16];
    std::memcpy(stock, view.rows.data(), sizeof stock);
    const bool offer = lexeditor_ff8_flare_definition_ready() && shop < 20 && (selected_shops & (1u << shop));
    if (!lexeditor_flare::make_shop_view(stock, offer, availability, view)) {
        // Preserve visible stock rows but clear a previous shop's added tail.
        view = {};
        std::memcpy(view.rows.data(), stock, sizeof stock);
    }
    buy_pages = view.pages;
}

extern "C" __declspec(dllexport) const void *__cdecl lexeditor_ff8_flare_shop_rows() {
    return view.rows.data();
}

#if defined(_M_IX86)
extern "C" __declspec(dllexport) __declspec(naked) void lexeditor_ff8_flare_shop_first() {
    __asm {
        pushfd
        pushad
        push edi
        call lexeditor_ff8_flare_shop_refresh
        add esp,4
        popad
        popfd
        jmp dword ptr [first_continue]
    }
}
extern "C" __declspec(dllexport) __declspec(naked) void lexeditor_ff8_flare_shop_second() {
    __asm {
        pushfd
        pushad
        push edi
        call lexeditor_ff8_flare_shop_refresh
        add esp,4
        popad
        popfd
        jmp dword ptr [second_continue]
    }
}
extern "C" __declspec(dllexport) __declspec(naked) void lexeditor_ff8_flare_shop_pages() {
    __asm {
        push eax
        mov eax,dword ptr [buy_pages]
        mov byte ptr [esi+047h],al
        pop eax
        jmp dword ptr [page_continue]
    }
}
#endif

static int prepare_shop(bool apply) {
#if !defined(_M_IX86)
    return 0;
#else
    if (!ff8 || !FF8_US_VERSION) return 0;
    if (installed) return 1;
    // All supported executable references, including writes, row lookup,
    // quantity/price rendering, both menu entry paths, and stock filtering.
    constexpr std::uint32_t id_operands[] = {
        0x4EBCB2,0x4EBCF0,0x4EBD17,0x4EBD29,0x4EBD40,0x4EC02B,0x4EC48D,
        0x4EC799,0x4EC818,0x4ECBE6,0x4ECE8D,0x4ED0EB,0x4ED347,0x4ED61A,
        0x4ED81E,0x4EDB83,0x4EDBC1,0x4EDBE8,0x4EDBFA,0x4EDC11};
    constexpr std::uint32_t quantity_operands[] = {
        0x4EBFEA,0x4EC184,0x4ECB9E,0x4ECE45,0x4ED144,0x4ED878};
    constexpr std::uint32_t end_operands[] = {0x4EBD4F,0x4EDC20};
    for (auto address : id_operands)
        if (*reinterpret_cast<const std::uint32_t *>(address) != 0x01D8D038) return 0;
    for (auto address : quantity_operands)
        if (*reinterpret_cast<const std::uint32_t *>(address) != 0x01D8D039) return 0;
    for (auto address : end_operands)
        if (*reinterpret_cast<const std::uint32_t *>(address) != 0x01D8D058) return 0;
    const unsigned char pages[] = {0xC6,0x46,0x47,0x02,0xEB,0x11};
    if (std::memcmp(reinterpret_cast<void *>(0x4EC2F3), pages, sizeof pages)) return 0;
    for (auto pair : {std::pair<std::uint32_t,std::uint32_t>{0x4EBD55,0x4C2B30}, {0x4EDC26,0x4EDC50}}) {
        if (*reinterpret_cast<const unsigned char *>(pair.first) != 0xE8 ||
            pair.first + 5 + *reinterpret_cast<const std::int32_t *>(pair.first + 1) != pair.second) return 0;
    }
    if (!apply) return 1;
    const auto base = reinterpret_cast<std::uint32_t>(view.rows.data());
    for (auto address : id_operands) patch_code_dword(address, base);
    for (auto address : quantity_operands) patch_code_dword(address, base + 1);
    // Native compaction clears just its original sixteen rows. The refresh
    // owner clears all extra rows before adding this shop's offer.
    for (auto address : end_operands) patch_code_dword(address, base + 32);
    replace_call(0x4EBD55, reinterpret_cast<void *>(&lexeditor_ff8_flare_shop_first));
    replace_call(0x4EDC26, reinterpret_cast<void *>(&lexeditor_ff8_flare_shop_second));
    replace_function(0x4EC2F3, reinterpret_cast<void *>(&lexeditor_ff8_flare_shop_pages));
    patch_code_byte(0x4EC2F8, 0x90);
    installed = true;
    return 1;
#endif
}

extern "C" __declspec(dllexport) int __cdecl lexeditor_ff8_flare_shop_validate() {return prepare_shop(false);}
extern "C" __declspec(dllexport) int __cdecl lexeditor_ff8_flare_shop_install() {return prepare_shop(true);}
