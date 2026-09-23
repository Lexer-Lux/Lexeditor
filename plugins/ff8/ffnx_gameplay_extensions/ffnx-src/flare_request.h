// GPL-3.0-or-later. One request survives only its own menu-to-location return.
#pragma once
#include <cstdint>
namespace lexeditor_flare {
enum class Location { other, field, world, menu };
struct Request {
    Location last=Location::other, origin=Location::other;
    bool pending=false, from_menu=false;
    unsigned age=0;
    void cancel() { pending=false;from_menu=false;age=0; }
    void observe(Location current, bool enabled) {
        if(!enabled) {cancel();origin=Location::other;last=current;return;}
        if(current==Location::menu) {
            if(last!=Location::menu) {cancel();origin=last;}
        } else if(current!=Location::field && current!=Location::world) {
            cancel();origin=Location::other;
        } else if(pending && current!=origin) cancel();
        if(pending && ++age>600) cancel();
        last=current;
    }
    bool request(bool owned) {
        if(pending || !owned) return false;
        const auto where=last==Location::menu?origin:last;
        if(where!=Location::field && where!=Location::world) return false;
        origin=where;from_menu=last==Location::menu;pending=true;age=0;return true;
    }
    bool take(Location gate, bool menu_closed) {
        if(!pending || gate!=origin || (from_menu && !menu_closed)) return false;
        cancel();return true;
    }
};
}
