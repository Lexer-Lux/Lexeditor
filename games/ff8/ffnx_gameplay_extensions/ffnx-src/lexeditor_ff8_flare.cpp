// GPL-3.0-or-later. Encounter backend only; item ownership is not assigned here.
#include "flare_encounter.h"
#include "flare_item.h"
#include <cstring>
#include "cfg.h"
#include "common.h"
#include "ff8.h"
#include "ff8/save_data.h"
#include "globals.h"

// Called by a future item-use owner at the native world battle gate. Do not
// bind Square here: inventory debit and remaining-count feedback must be wired
// together first. Calling this outside that gate would skip transition/music.
extern "C" __declspec(dllexport) int __cdecl lexeditor_ff8_flare_select_world(unsigned short *encounter) {
    if (!ff8 || !encounter) return 0;
    const auto *mode = getmode_cached();
    if (!mode || mode->driver_mode != MODE_WORLDMAP) return 0;
    const auto selector = ff8_externals.sub_541C80;
    if (reinterpret_cast<std::uintptr_t>(selector) != 0x00541C80) return 0;
    const unsigned char entry[] = {0x55, 0x8B, 0xEC, 0x83, 0xEC, 0x14, 0xA1, 0x68, 0x00, 0x04, 0x02};
    if (std::memcmp(reinterpret_cast<const void *>(selector), entry, sizeof entry)) return 0;
    const int vehicle = *reinterpret_cast<const int *>(0x020409E0);
    if (!((vehicle >= 0 && vehicle <= 9) || vehicle == 0x80)) return 0;
    if (*reinterpret_cast<const unsigned char *>(0x01CFF6D8) & 8) return 0;
    auto &counters = *reinterpret_cast<lexeditor_flare::WorldCounters *>(0x02040A5C);
    auto &movement = *reinterpret_cast<std::int32_t *>(0x020409F4);
    return lexeditor_flare::request_world(counters, movement, *encounter, selector) ? 1 : 0;
}

// Both locations debit the same validated inventory only after selection.
static int use_at_gate(unsigned item_id, unsigned short *encounter, unsigned char *remaining,
                       int(__cdecl *selector)(unsigned short *)) {
    if (!ff8 || !encounter || !remaining) return 0;
    // Only the allocated Signal Flare definition can be consumed by this entry.
    if (item_id != lexeditor_flare::item_id) return 0;
    const auto add_item = ff8_externals.add_item_to_player_sub_47ED00;
    if (reinterpret_cast<std::uintptr_t>(add_item) != 0x0047ED00) return 0;
    const unsigned char inventory_load[] = {0xB8, 0x9C, 0xE7, 0xCF, 0x01};
    if (std::memcmp(reinterpret_cast<const void *>(0x0047ED0F), inventory_load,
                    sizeof inventory_load)) return 0;
    static_assert(sizeof(savemap_ff8_item) == 2, "Inventory pair layout changed");
    auto &inventory = *reinterpret_cast<savemap_ff8_item (*)[198]>(0x01CFE79C);
    return lexeditor_flare::use_item(inventory, static_cast<std::uint8_t>(item_id),
        *encounter, *remaining, selector) ? 1 : 0;
}

// Match the native field selector's input/activity guards before admitting a
// shortcut. NPC/card/dialog/movie input keeps priority; no notice is queued.
extern "C" __declspec(dllexport) int __cdecl lexeditor_ff8_flare_field_input_available() {
    if(!ff8)return 0;
    const auto *mode=getmode_cached();
    if(!mode || mode->driver_mode!=MODE_FIELD)return 0;
    if(*reinterpret_cast<const unsigned char *>(0x01CE4760)!=0 ||
       *reinterpret_cast<const unsigned char *>(0x01CDC74C)==1 ||
       (*reinterpret_cast<const unsigned char *>(0x01CFF6D8)&8))return 0;
    const auto transition=*reinterpret_cast<const unsigned short *>(0x01CE4868);
    if(transition==2 || transition==3 || transition==4)return 0;
    const auto actor=*reinterpret_cast<const std::uintptr_t *>(0x00B8EE90);
    if(!actor || *reinterpret_cast<const unsigned char *>(actor+0xCF))return 0;
    return reinterpret_cast<int(__cdecl*)()>(0x0052B3A0)()==0;
}

// Call only from the normal field battle gate, so FFNx still owns transition
// and music. Safe maps with zero encounter rate stay safe.
extern "C" __declspec(dllexport) int __cdecl lexeditor_ff8_flare_select_field(unsigned short *encounter) {
    if (!ff8 || !encounter) return 0;
    const auto *mode=getmode_cached();
    if (!mode || mode->driver_mode != MODE_FIELD) return 0;
    const auto selector=ff8_externals.sub_47CA90;
    const unsigned char entry[]={0xA0,0x60,0x47,0xCE,0x01,0x3C,0x01};
    if (reinterpret_cast<std::uintptr_t>(selector)!=0x0047CA90 ||
        std::memcmp(reinterpret_cast<const void *>(selector),entry,sizeof entry)) return 0;
    auto &state=*reinterpret_cast<std::uint8_t *>(0x01CE4760);
    if(state != 0) return 0;
    const auto rate_pointer=*reinterpret_cast<const std::uintptr_t *>(0x01CF3D48);
    const auto formation_pointer=*reinterpret_cast<const std::uintptr_t *>(0x01CF3D78);
    if(!rate_pointer || !formation_pointer) return 0;
    const auto rate=*reinterpret_cast<const unsigned char *const *>(rate_pointer);
    const auto formations=*reinterpret_cast<const unsigned short *const *>(formation_pointer);
    if(!rate || !formations || !rate[0]) return 0;
    const bool success=lexeditor_flare::request_field(
        *reinterpret_cast<std::uint16_t *>(0x01CDC740),
        *reinterpret_cast<std::uint16_t *>(0x01CDC74A),
        *reinterpret_cast<std::uint8_t *>(0x01CD2FB8),
        *reinterpret_cast<std::uint8_t *>(0x01CDC748),
        *reinterpret_cast<std::uint8_t *>(0x01CDBFEC), [&]() {
            selector();
            return state==3 && *reinterpret_cast<const std::uint8_t *>(0x01CD2EF8)==1;
        });
    if(success) *encounter=*reinterpret_cast<const unsigned short *>(0x01CE4762);
    return success ? 1 : 0;
}

extern "C" __declspec(dllexport) int __cdecl lexeditor_ff8_flare_use_world(
        unsigned item_id, unsigned short *encounter, unsigned char *remaining) {
    return use_at_gate(item_id, encounter, remaining, lexeditor_ff8_flare_select_world);
}
extern "C" __declspec(dllexport) int __cdecl lexeditor_ff8_flare_use_field(
        unsigned item_id, unsigned short *encounter, unsigned char *remaining) {
    return use_at_gate(item_id, encounter, remaining, lexeditor_ff8_flare_select_field);
}
