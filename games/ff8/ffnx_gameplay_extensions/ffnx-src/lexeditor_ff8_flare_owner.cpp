// GPL-3.0-or-later. Signal Flare admission, menu return and battle-gate service.
#include "lexeditor_ff8_flare_owner.h"
#include "flare_request.h"
#include <cstddef>
#include "flare_item.h"
#include "cfg.h"
#include "common.h"
#include "ff8.h"
#include "ff8/save_data.h"
#include "globals.h"
#include "log.h"
#include "lexeditor_ff8_modern_controls.h"
extern int ff8_toggle_battle_field();
extern "C" {
int __cdecl lexeditor_ff8_flare_use_world(unsigned,unsigned short*,unsigned char*);
int __cdecl lexeditor_ff8_flare_field_input_available();
int __cdecl lexeditor_ff8_flare_use_field(unsigned,unsigned short*,unsigned char*);
int __cdecl lexeditor_ff8_flare_menu_exit_request();
int __cdecl lexeditor_ff8_flare_menu_exit_ready();
void __cdecl lexeditor_ff8_flare_menu_exit_reset();
int __cdecl lexeditor_ff8_flare_menu_exit_install();
int __cdecl lexeditor_ff8_flare_menu_request_bind(int(__cdecl*)());
int __cdecl lexeditor_ff8_flare_definition_install();
int __cdecl lexeditor_ff8_flare_shop_install();
int __cdecl lexeditor_ff8_flare_definition_validate();
int __cdecl lexeditor_ff8_flare_shop_validate();
int __cdecl lexeditor_ff8_flare_menu_exit_validate();
int __cdecl lexeditor_ff8_flare_definition_ready();
void __cdecl lexeditor_ff8_flare_transactions_enable(int);
}
#if defined(_M_IX86)
static_assert(offsetof(savemap_ff8,items)+offsetof(savemap_ff8_items,items)==0xB44,
              "Signal Flare inventory offset changed");
#endif
namespace {
lexeditor_flare::Request request;
bool installed=false;
bool square_armed=false;
using Location=lexeditor_flare::Location;
Location location() {
    const auto *mode=getmode_cached();
    if(!mode)return Location::other;
    switch(mode->driver_mode) {
        case MODE_WORLDMAP:return Location::world;
        case MODE_FIELD:return Location::field;
        case MODE_MENU:return Location::menu;
        default:return Location::other;
    }
}
bool owns_item() {
    if(!ff8_externals.savemap)return false;
    unsigned matches=0;
    for(const auto &slot:ff8_externals.savemap->items.items) {
        if(slot.item_id!=lexeditor_flare::item_id)continue;
        if(!slot.item_quantity || slot.item_quantity>100)return false;
        ++matches;
    }
    return matches==1;
}
int __cdecl menu_request() {
    if(!installed || !lexeditor_ff8_flare_definition_ready() || location()!=Location::menu)return 0;
    // Tick observes the menu transition before an item can be selected. Never
    // infer the origin from stale saved module data or a remembered old request.
    request.observe(Location::menu,true);
    if(!request.request(owns_item()))return 0;
    if(!lexeditor_ff8_flare_menu_exit_request()) {request.cancel();return 0;}
    return 1;
}
int service(Location gate,unsigned short *encounter,bool allowed) {
    if(!installed || location()!=gate)return -1;
    if(!request.take(gate,lexeditor_ff8_flare_menu_exit_ready()!=0))return -1;
    lexeditor_ff8_flare_menu_exit_reset();
    unsigned char remaining=0;
    const int result=allowed ? (gate==Location::world ?
        lexeditor_ff8_flare_use_world(lexeditor_flare::item_id,encounter,&remaining):
        lexeditor_ff8_flare_use_field(lexeditor_flare::item_id,encounter,&remaining)):0;
    if(result)show_popup_msg(TEXTCOLOR_LIGHT_BLUE,"Signal Flare: %u remaining",static_cast<unsigned>(remaining));
    else show_popup_msg(TEXTCOLOR_LIGHT_BLUE,"Signal Flare cannot be used here.");
    return result;
}
}
void lexeditor_ff8_flare_tick() {
    if(!ff8 || !installed)return;
    const auto here=location();
    request.observe(here,true);
    // The stock mapped input's second word holds current logical buttons;
    // this includes the configured keyboard equivalent, not raw key codes.
    const bool held=ff8_externals.engine_input_valid_buttons &&
        (ff8_externals.engine_input_valid_buttons[1]&0x80)!=0;
    const bool focused=gameHwnd && GetForegroundWindow()==gameHwnd;
    if(!focused || !enable_ff8_modern_controls)square_armed=false;
    else if(!held)square_armed=true;
    else {
        if(square_armed && lexeditor_ff8_flare_definition_ready() &&
            (here==Location::world || (here==Location::field && lexeditor_ff8_flare_field_input_available())))request.request(owns_item());
        square_armed=false;
    }
    if(!request.pending)lexeditor_ff8_flare_menu_exit_reset();
}
int lexeditor_ff8_flare_world_gate(unsigned short *encounter,bool allowed) {
    return encounter?service(Location::world,encounter,allowed):-1;
}
int lexeditor_ff8_flare_field_gate(bool allowed) {
    unsigned short encounter=0;
    return service(Location::field,&encounter,allowed);
}
int lexeditor_ff8_flare_owner_install() {
    // Each lower installer verifies the supported EXE before startup writes.
    if(!ff8 || !FF8_US_VERSION)return 0;
    if(installed)return 1;
    // Native patch writes happen synchronously on the startup thread. Validate
    // every site's original bytes before any installer changes an instruction.
    if(!lexeditor_ff8_flare_menu_exit_validate() || !lexeditor_ff8_flare_shop_validate() ||
        !lexeditor_ff8_flare_definition_validate()) {
        ffnx_warning("Signal Flare disabled: incompatible native patch sites.\n");return 0;
    }
    if(!lexeditor_ff8_flare_menu_request_bind(menu_request))return 0;
    if(!lexeditor_ff8_flare_menu_exit_install() || !lexeditor_ff8_flare_shop_install() ||
        !lexeditor_ff8_flare_definition_install()) {
        lexeditor_ff8_flare_menu_request_bind(nullptr);return 0;
    }
    installed=true;
    lexeditor_ff8_flare_transactions_enable(1);
    ffnx_trace("Signal Flare enabled: item 199, all shops, 200 Gil; shortcut requires Modern Controls.\n");
    return 1;
}

void lexeditor_ff8_flare_service_stationary_field() {
    // The stock actor calls its encounter check only while moving. End-of-frame
    // service runs after field input/scripts, preserving native interaction
    // priority, and uses the same FFNx wrapper for battle scene/music tracking.
    if(installed && request.pending && request.origin==Location::field &&
        location()==Location::field && (!request.from_menu || lexeditor_ff8_flare_menu_exit_ready()))
        ff8_toggle_battle_field();
}
