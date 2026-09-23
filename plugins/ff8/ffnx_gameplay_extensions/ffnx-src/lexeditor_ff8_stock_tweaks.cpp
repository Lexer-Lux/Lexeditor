// GPL-3.0-or-later. Narrow, guarded FF8_EN spell-cast debit hooks.
#include "lexeditor_ff8_stock_tweaks.h"
#include <cstdint>
#include <cstring>
#include "cfg.h"
#include "common.h"
#include "globals.h"
#include "patch.h"
#include "log.h"

namespace {
constexpr std::uintptr_t kBattleDebit = 0x004FE709;
constexpr std::uintptr_t kFieldDebit = 0x004F3027;
std::uintptr_t g_nonnegative = 0x004FE711;
std::uintptr_t g_underflow = 0x004FE70F;
bool g_installed = false;

// The same battle list controller handles BOTH Magic and Item. Never suppress
// the debit merely because this controller is running. The native list
// callback 004C8820 identifies the Magic inventory; Item keeps its debit.
// Hook AFTER the stock load so Max Spell's independent signed-byte repair at
// 004FE706 remains intact. Resume BEFORE the zero-ID cleanup and at the native
// branch destination so reserved-charge cleanup and command state are retained.
}

// Exported only for executable-backed verification of the linked register ABI.
extern "C" __declspec(dllexport) void __declspec(naked) lexeditor_ff8_no_consume_battle_debit()
{
    __asm {
        cmp dword ptr ds:[01D768D0h], 004C8820h
        jne debit
        movzx eax, byte ptr [ecx]
        jmp dword ptr [g_nonnegative]
    debit:
        sub eax, edi
        jns positive
        xor eax, eax
        jmp dword ptr [g_underflow]
    positive:
        jmp dword ptr [g_nonnegative]
    }
}

void lexeditor_ff8_stock_tweaks_install()
{
    if (!ff8 || !FF8_US_VERSION || g_installed ||
        !enable_ff8_no_magic_consumption) return;
    const unsigned char battle[] = {0x2B,0xC7,0x79,0x04,0x33,0xC0};
    // Field-menu spell effects have already succeeded before this decrement.
    // Discard, transfer, Refine and stock-removal APIs use other paths.
    const unsigned char field[] = {0xFE,0xCB,0x88,0x1C,0x45,0xF9,0xE0,0xCF,0x01};
    if (std::memcmp(reinterpret_cast<void *>(kBattleDebit),battle,sizeof(battle)) ||
        std::memcmp(reinterpret_cast<void *>(kFieldDebit),field,sizeof(field))) {
        ffnx_warning("No Magic Consumption: unsupported cast-debit bytes; no hook installed.\n");
        return;
    }
    replace_function(static_cast<std::uint32_t>(kBattleDebit),
        reinterpret_cast<void *>(&lexeditor_ff8_no_consume_battle_debit));
    patch_code_byte(static_cast<std::uint32_t>(kBattleDebit + 5),0x90);
    patch_code_word(static_cast<std::uint32_t>(kFieldDebit),0x9090);
    g_installed = true;
    ffnx_trace("No Magic Consumption: field and battle cast debits guarded; Item consumption retained.\n");
}

extern "C" __declspec(dllexport) unsigned int lexeditor_ff8_stock_tweaks_contract_version()
{
    return 1;
}
