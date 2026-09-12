// GPL-3.0-or-later. Close the stock menus before servicing a Signal Flare.
#include <cstdint>
#include <cstring>
#include "cfg.h"
#include "globals.h"
#include "patch.h"

namespace {
enum class ExitState { idle, requested, closing, ready };
ExitState exit_state = ExitState::idle;
bool installed = false;
using Controller = int(__cdecl *)(unsigned char *);
const auto stock_controller = reinterpret_cast<Controller>(0x004C0CF0);
}

// The complete encounter owner must check origin, ownership and feature
// readiness before requesting exit. No item is consumed by menu transitions.
extern "C" __declspec(dllexport) int __cdecl lexeditor_ff8_flare_menu_exit_request() {
    if (!installed || exit_state != ExitState::idle) return 0;
    exit_state = ExitState::requested;
    return 1;
}
extern "C" __declspec(dllexport) int __cdecl lexeditor_ff8_flare_menu_exit_ready() {
    return exit_state == ExitState::ready;
}
extern "C" __declspec(dllexport) void __cdecl lexeditor_ff8_flare_menu_exit_reset() {
    exit_state = ExitState::idle;
}

extern "C" __declspec(dllexport) int __cdecl lexeditor_ff8_flare_root_menu_controller(unsigned char *context) {
    auto &depth = *reinterpret_cast<const unsigned char *>(0x01D77079);
    // Root state 7 waits for its child. Depth 1 means the item pane completed
    // its own cleanup. State 21 commits the party, then fades and removes the
    // root context through states 21/22. Never skip either native cleanup.
    if (context && exit_state == ExitState::requested && depth == 1 &&
        *reinterpret_cast<const std::uint16_t *>(context + 0x10) == 7) {
        *reinterpret_cast<std::uint16_t *>(context + 0x10) = 21;
        exit_state = ExitState::closing;
    }
    const int result = stock_controller(context);
    // The controller may have freed context. Do not read it after the call.
    if (exit_state == ExitState::closing && depth == 0) exit_state = ExitState::ready;
    return result;
}

static int prepare_menu_exit(bool apply) {
#if !defined(_M_IX86)
    return 0;
#else
    if (!ff8 || !FF8_US_VERSION) return 0;
    if (installed) return 1;
    const unsigned char registration[] = {0x68,0xF0,0x0C,0x4C,0x00};
    const unsigned char entry[] = {0x83,0xEC,0x0C,0xA1,0x98,0x6A,0xD7,0x01};
    if (std::memcmp(reinterpret_cast<const void *>(0x004C0B4B), registration, sizeof registration) ||
        std::memcmp(reinterpret_cast<const void *>(stock_controller), entry, sizeof entry)) return 0;
    if (!apply) return 1;
    patch_code_dword(0x004C0B4C, reinterpret_cast<std::uint32_t>(&lexeditor_ff8_flare_root_menu_controller));
    installed = true;
    return 1;
#endif
}

extern "C" __declspec(dllexport) int __cdecl lexeditor_ff8_flare_menu_exit_validate() {return prepare_menu_exit(false);}
extern "C" __declspec(dllexport) int __cdecl lexeditor_ff8_flare_menu_exit_install() {return prepare_menu_exit(true);}
