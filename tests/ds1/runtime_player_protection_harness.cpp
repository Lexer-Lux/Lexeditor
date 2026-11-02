/* Exercise the imported guards and the vanilla-session adapter without a game
 * or network. All inputs are synthetic; no real player is contacted. */
#include "../../plugins/ds1/runtime/overhaul/AntiCheat.cpp"
#include "../../plugins/ds1/runtime/overhaul/PlayerProtection.cpp"
#include <cassert>
#include <stdexcept>

void ConsoleWrite(const char *, ...) {}
[[noreturn]] void FATALERROR(const char *, ...) { throw std::runtime_error("protection rejected input"); }
bool sp::mem::patch_bytes(void *, const void *, size_t) { return true; }
void sp::mem::code::x64::inject_jmp_14b(void *, uint64_t *, size_t, void (*)()) {}
extern "C" {
void lx_debug_log(const char *) {}
void dmg_guard_asm_check() {}
void TeleBackstabProtect_store_AnimationId() {}
void TeleBackstabProtect_setPosition_check() {}
void NameCrash_prevent() {}
void ReadParseType18_packet_injection() {}
void ReadParseType35_packet_injection() {}
void ReadParseType3_packet_injection() {}
void ReadParseType39_packet_injection() {}
void ReadParseType34_packet_injection() {}
void ReadParseType50_packet_injection() {}
void ApplyType33_packet_injection() {}
void getNetMessageAC_injection() {}
void BreakIn_UserSteamId_injection() {}
}

static void test_sessions_and_npc_guards()
{
    alignas(8) unsigned char target[0x600] = {};
    PlayerProtectionPlayerCtrl ctrl = {};
    auto chr = (ChrIns *)target;
    chr->playerCtrl = &ctrl;
    *(uint32_t *)(target + 0xc8) = 0x40740; // Andre
    assert(dmg_guard_asm_check_helper(chr, 0) == 0); // offline: ordinary gameplay
    uint64_t ids[] = {1, 2, 3};
    PlayerProtection::update_session(100, 2, 1, ids, 3);
    assert(!PlayerProtection::hosting_peers()); // guest
    assert(dmg_guard_asm_check_helper(chr, 0) == 0);
    PlayerProtection::update_session(100, 1, 1, ids, 3);
    assert(PlayerProtection::hosting_peers());
    assert(dmg_guard_asm_check_helper(chr, 0) == 1);
    assert(ReadParseType3_packet_injection_helper(chr) == 0);
    assert(ReadParseType39_packet_injection_helper(chr) == 0);
    assert(ReadParseType34_packet_injection_helper(chr, 10) == 0);
    assert(ReadParseType50_packet_injection_helper(chr) == 0);
    assert(ApplyType33_packet_injection_helper(chr) == 0);
    assert(dmg_guard_asm_check_helper(nullptr, 0) == 0);
    *(uint32_t *)(target + 0xc8) = 0;
    *(uint32_t *)(target + 0x2b0) = 1000800; // inactive Gaping Dragon
    assert(dmg_guard_asm_check_helper(chr, 0) == 1);
    assert(dmg_guard_asm_check_helper(chr, 3000) == 0); // summon HP scaling
    *(uint32_t *)((unsigned char *)&ctrl + 0x100) = 1;
    assert(dmg_guard_asm_check_helper(chr, 0) == 0); // active boss
    *(uint32_t *)(target + 0x2b0) = 1234;
    assert(ReadParseType3_packet_injection_helper(chr) == (uint64_t)chr);
    PlayerProtection::record_invader("2");
    assert(PlayerProtection::is_invader(2) && !PlayerProtection::is_invader(3));
    assert(!getNetMessageAC_helper(3, 2));
    assert(getNetMessageAC_helper(3, 3)); // cooperative peer
    assert(getNetMessageAC_helper(18, 2)); // ordinary attack packet
    PlayerProtection::record_invader("3bad-input");
    assert(!PlayerProtection::is_invader(3));
    // A departure removes that player's role before a subsequent summon.
    PlayerProtection::update_session(100, 1, 1, ids, 1);
    PlayerProtection::update_session(100, 1, 1, ids, 3);
    assert(!PlayerProtection::is_invader(2));
    // A break-in notification may arrive before the peer joins the lobby.
    PlayerProtection::update_session(100, 1, 1, ids, 1);
    PlayerProtection::record_invader("2");
    PlayerProtection::update_session(100, 1, 1, ids, 1);
    assert(!PlayerProtection::is_invader(2));
    PlayerProtection::update_session(100, 1, 1, ids, 3);
    assert(PlayerProtection::is_invader(2));
    PlayerProtection::update_session(101, 1, 1, ids, 3);
    assert(!PlayerProtection::is_invader(2)); // new session never inherits roles
    PlayerProtection::record_invader("2");
    PlayerProtection::update_session(101, 2, 1, ids, 3);
    assert(!PlayerProtection::is_invader(2) && getNetMessageAC_helper(3, 2));
    PlayerProtection::update_session(0, 0, 0, nullptr, 0);
    assert(dmg_guard_asm_check_helper(chr, 0) == 0);
}

static void test_packets_and_names()
{
    alignas(8) unsigned char packet[0x80] = {};
    auto set = [&](unsigned at, uint32_t value) { memcpy(packet+at, &value, 4); };
    auto read = [&](unsigned at) { uint32_t value; memcpy(&value, packet+at, 4); return value; };
    float damage = 70;
    memcpy(packet, &damage, 4);
    set(0x28, 500); // damaging Tranquil Walk of Peace exploit
    set(0x3c, 5210); // known malicious effect
    ReadParseType18_packet_injection_helper((uint64_t)packet);
    assert(read(0) == 0 && read(0x28) == 500 && read(0x3c) == UINT32_MAX);
    set(0x28, 33);
    ReadParseType18_packet_injection_helper((uint64_t)packet);
    assert(read(0x28) == UINT32_MAX);
    memcpy(packet, &damage, 4);
    set(0x28, 1000);
    set(0x3c, 2000);
    unsigned char before[sizeof packet];
    memcpy(before, packet, sizeof packet);
    ReadParseType18_packet_injection_helper((uint64_t)packet);
    assert(!memcmp(before, packet, sizeof packet)); // legitimate damage unchanged
    uint32_t effect = 6;
    ReadParseType35_packet_injection_helper((uint64_t)&effect);
    assert(effect == UINT32_MAX);
    effect = 1000;
    ReadParseType35_packet_injection_helper((uint64_t)&effect);
    assert(effect == 1000);
    wchar_t name[] = L"abc<?tag?>def";
    NameCrash_prevent_helper(name);
    assert(!wcscmp(name, L"abc(?tag?)def"));
    // Unterminated input at a committed-page boundary must not read past it.
    SYSTEM_INFO info;
    GetSystemInfo(&info);
    auto pages = (unsigned char *)VirtualAlloc(nullptr, 2*info.dwPageSize, MEM_RESERVE, PAGE_NOACCESS);
    assert(pages && VirtualAlloc(pages, info.dwPageSize, MEM_COMMIT, PAGE_READWRITE));
    auto bounded_name = (wchar_t *)(pages + info.dwPageSize - 32*sizeof(wchar_t));
    for (unsigned i = 0; i < 32; ++i) bounded_name[i] = L'a';
    NameCrash_prevent_helper(bounded_name);
    VirtualFree(pages, 0, MEM_RELEASE);
}

static void test_backstabs()
{
    auto slot_address = (void *)(Game::ds1_base + 0x1c70000);
    assert(VirtualAlloc(slot_address, 0x10000, MEM_RESERVE|MEM_COMMIT, PAGE_READWRITE) == slot_address);
    alignas(16) unsigned char world[0x80] = {}, player[0x80] = {}, ctrl[0x80] = {}, havok[0x40] = {};
    *(uintptr_t *)((uintptr_t)slot_address+0x7e50) = (uintptr_t)world;
    *(uintptr_t *)(world+0x68) = (uintptr_t)player;
    *(uintptr_t *)(player+0x68) = (uintptr_t)ctrl;
    *(uintptr_t *)(ctrl+0x28) = (uintptr_t)havok;
    auto pos = (float *)(havok+0x10);
    saved_anim_id = 9000;
    new_player_position[0] = 9;
    TeleBackstabProtect_helper_check(pos);
    assert(pos[0] == 0); // remote teleport beyond eight units rejected
    new_player_position[0] = 4;
    TeleBackstabProtect_helper_check(pos);
    assert(pos[0] == 4); // ordinary backstab positioning allowed
    saved_anim_id = 100;
    new_player_position[0] = 20;
    TeleBackstabProtect_helper_check(pos);
    assert(pos[0] == 20); // non-backstab movement untouched
    float other_position[4] = {};
    saved_anim_id = 9000;
    TeleBackstabProtect_helper_check(other_position);
    assert(other_position[0] == 20); // other characters untouched
    VirtualFree(slot_address, 0, MEM_RELEASE);
}

int main()
{
    test_sessions_and_npc_guards();
    test_packets_and_names();
    test_backstabs();
    puts("player protections passed");
}
