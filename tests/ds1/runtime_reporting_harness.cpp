/* Exercise upstream reporting filters without a game, network or patches. */
#include "../../plugins/ds1/runtime/overhaul/AntiAntiCheat.cpp"
#include <cstdarg>
#include <cassert>
void ConsoleWrite(const char *, ...) {}
[[noreturn]] void FATALERROR(const char *, ...) { exit(7); }
bool sp::mem::patch_bytes(void *, const void *, size_t) { return true; }
void sp::mem::code::x64::inject_jmp_14b(void *, uint64_t *, size_t, void (*)()) {}
extern "C" {
void game_write_playerdata_to_flatbuffer_injection() {}
void construct_flatbuffer_from_PlayerStatus_MemberFlags_injection() {}
void finish_construct_flatbuffer_from_PlayerStatus_MemberFlags_injection() {}
void set_MemberFlags_bitflag_injection() {}
void lx_debug_log(const char *) {}
}
int main()
{
    assert(allowed_flags(SoulLevel) && allowed_flags(MaxWeaponLevel) && allowed_flags(AreaId));
    for (auto id : {AntiCheatFlags, WeaponinSlot0, IteminQuickbar0, EquippedSpell1, attackR1, MaxHp})
        assert(!allowed_flags(id));
    alignas(8) unsigned char packet[0x400] = {};
    unsigned char *members = packet + 0x78;
    memset(members, 0xff, 32);
    construct_flatbuffer_from_PlayerStatus_MemberFlags_injection_helper((uint64_t)packet);
    for (unsigned id = 0; id < LAST; ++id) {
        bool set = (((uint64_t *)members)[id / 64] >> (id % 64)) & 1;
        assert(set == allowed_flags((MemberFlags_IdentifiersEnum)id));
    }
    finish_construct_flatbuffer_from_PlayerStatus_MemberFlags_injection_helper();
    for (unsigned i = 0; i < 32; ++i) assert(members[i] == 0xff);
    uint32_t flags[] = {0x1770, 0x37a, 0x1770, 0x3de, 0x1770};
    assert(game_write_playerdata_to_flatbuffer_injection_helper(flags, 5) == 2);
    assert(flags[0] == 0x37a && flags[1] == 0x3de);
    puts("report filters passed");
}
