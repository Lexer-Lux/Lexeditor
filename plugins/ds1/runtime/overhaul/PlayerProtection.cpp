/* Vanilla Steam-session adapter for the pinned AntiCheat implementation.
 * SPDX-License-Identifier: AGPL-3.0-only
 * Uses the Steam flat C exports already shipped with DSR. No Steam SDK or
 * Overhaul matchmaking/transport replacement is linked into the loader. */
#include "PlayerProtection.h"
#include "SP/memory/injection/asm/x64.h"

namespace {
constexpr size_t max_peers = 64;
SRWLOCK session_lock = SRWLOCK_INIT;
uint64_t current_lobby, local_user, peer_ids[max_peers], invaders[max_peers];
size_t peer_count, invader_count;
bool invader_seen[max_peers];
uint64_t invader_expires[max_peers];
bool hosting;
void (*real_callbacks)();
void *matchmaking, *steam_user;
int (*member_count)(void *, uint64_t);
uint64_t (*member_id)(void *, uint64_t, int);
uint64_t (*owner_id)(void *, uint64_t);
uint64_t (*self_id)(void *);
uint64_t observed_lobby;

bool contains(const uint64_t *ids, size_t count, uint64_t id)
{
    for (size_t i = 0; i < count; ++i) if (ids[i] == id) return true;
    return false;
}

/* Steam's public CCallbackBase ABI: three virtual methods, then an 8-bit
 * registration flag and a 32-bit callback ID. No virtual destructor. */
class LobbyEnterCallback {
public:
    virtual void Run(void *data) {
        uint64_t lobby;
        uint32_t result;
        memcpy(&lobby, data, 8);
        memcpy(&result, (unsigned char *)data + 16, 4);
        observed_lobby = result == 1 ? lobby : 0;
        PlayerProtection::update_session(0, 0, 0, nullptr, 0);
    }
    virtual void Run(void *data, bool failed, uint64_t) { if (!failed) Run(data); }
    virtual int GetCallbackSizeBytes() { return 24; }
    unsigned char flags = 0;
    int callback = 504;
};
static_assert(sizeof(LobbyEnterCallback) == 16);
LobbyEnterCallback lobby_enter;

template<typename T> T resolve(HMODULE module, const char *name)
{
    T result = reinterpret_cast<T>(GetProcAddress(module, name));
    if (!result) FATALERROR("Player protection requires Steam export %s", name);
    return result;
}

void register_callbacks()
{
    HMODULE steam = GetModuleHandleW(L"steam_api64.dll");
    auto get_user = resolve<int (*)()>(steam, "SteamAPI_GetHSteamUser");
    auto get_pipe = resolve<int (*)()>(steam, "SteamAPI_GetHSteamPipe");
    auto get_matchmaking = resolve<void *(*)(void *, int, int, const char *)>(steam, "SteamAPI_ISteamClient_GetISteamMatchmaking");
    auto get_steam_user = resolve<void *(*)(void *, int, int, const char *)>(steam, "SteamAPI_ISteamClient_GetISteamUser");
    if (!get_user() || !get_pipe())
        return; // Steam initialization can fail while the user plays offline.
    auto client = resolve<void *(*)(const char *)>(steam, "SteamInternal_CreateInterface")("SteamClient017");
    if (!client) FATALERROR("Unsupported Steam client for player protection");
    matchmaking = get_matchmaking(client, get_user(), get_pipe(), "SteamMatchMaking009");
    steam_user = get_steam_user(client, get_user(), get_pipe(), "SteamUser019");
    if (!matchmaking || !steam_user) FATALERROR("Unsupported Steam interfaces for player protection");
    member_count = resolve<decltype(member_count)>(steam, "SteamAPI_ISteamMatchmaking_GetNumLobbyMembers");
    member_id = resolve<decltype(member_id)>(steam, "SteamAPI_ISteamMatchmaking_GetLobbyMemberByIndex");
    owner_id = resolve<decltype(owner_id)>(steam, "SteamAPI_ISteamMatchmaking_GetLobbyOwner");
    self_id = resolve<decltype(self_id)>(steam, "SteamAPI_ISteamUser_GetSteamID");
    resolve<void (*)(LobbyEnterCallback *, int)>(steam, "SteamAPI_RegisterCallback")(&lobby_enter, 504);
    ConsoleWrite("Player protection: vanilla Steam session tracking registered");
}

void refresh_session()
{
    uint64_t ids[max_peers];
    int count = observed_lobby && matchmaking ? member_count(matchmaking, observed_lobby) : 0;
    if (count < 1 || count > max_peers) {
        PlayerProtection::update_session(0, 0, 0, nullptr, 0);
        return;
    }
    for (int i = 0; i < count; ++i) ids[i] = member_id(matchmaking, observed_lobby, i);
    PlayerProtection::update_session(observed_lobby, owner_id(matchmaking, observed_lobby),
                                     self_id(steam_user), ids, count);
}

void run_callbacks()
{
    /* Register before the game dispatches its first lobby-enter callback. */
    if (!matchmaking) register_callbacks();
    real_callbacks();
    refresh_session();
}
}

void PlayerProtection::update_session(uint64_t lobby, uint64_t owner, uint64_t self,
                                      const uint64_t *members, size_t count)
{
    AcquireSRWLockExclusive(&session_lock);
    if (!members || count > max_peers || !self || !contains(members, count, self)) {
        lobby = 0;
        count = 0;
    }
    if (lobby != current_lobby || self != local_user) invader_count = 0;
    current_lobby = lobby;
    local_user = self;
    peer_count = count;
    if (count) memcpy(peer_ids, members, count * sizeof *members);
    hosting = lobby && owner == self && count > 1;
    for (size_t i = 0; i < invader_count;) {
        if (contains(peer_ids, peer_count, invaders[i])) { invader_seen[i] = true; ++i; }
        else if (!invader_seen[i] && GetTickCount64() < invader_expires[i]) ++i;
        else {
            --invader_count;
            invaders[i] = invaders[invader_count];
            invader_seen[i] = invader_seen[invader_count];
            invader_expires[i] = invader_expires[invader_count];
        }
    }
    ReleaseSRWLockExclusive(&session_lock);
}

bool PlayerProtection::hosting_peers()
{
    AcquireSRWLockShared(&session_lock);
    bool result = hosting;
    ReleaseSRWLockShared(&session_lock);
    return result;
}

void PlayerProtection::record_invader(const char *text)
{
    // The server supplies a hexadecimal Steam ID. Never scan an unbounded string.
    uint64_t id = 0;
    size_t i = 0;
    for (; i < 16 && text[i]; ++i) {
        unsigned char c = (unsigned char)text[i];
        unsigned digit = c >= '0' && c <= '9' ? c - '0' :
                         c >= 'a' && c <= 'f' ? c - 'a' + 10 :
                         c >= 'A' && c <= 'F' ? c - 'A' + 10 : 16;
        if (digit == 16) return;
        id = (id << 4) | digit;
    }
    if (!i || !id || text[i]) return;
    AcquireSRWLockExclusive(&session_lock);
    if (current_lobby && id != local_user && !contains(invaders, invader_count, id) && invader_count < max_peers) {
        invaders[invader_count] = id;
        invader_seen[invader_count] = contains(peer_ids, peer_count, id);
        invader_expires[invader_count] = GetTickCount64() + 30000;
        ++invader_count;
    }
    ReleaseSRWLockExclusive(&session_lock);
}

bool PlayerProtection::is_invader(uint64_t id)
{
    AcquireSRWLockShared(&session_lock);
    bool result = hosting && contains(peer_ids, peer_count, id) && contains(invaders, invader_count, id);
    ReleaseSRWLockShared(&session_lock);
    return result;
}

float *Game::get_pc_position()
{
    // Upstream GameData.cpp: WorldChrManImp -> local PlayerIns -> ChrCtrl -> HavokChara.
    uintptr_t node = *(uintptr_t *)(ds1_base + 0x1c77e50);
    if (!node || !(node = *(uintptr_t *)(node + 0x68)) ||
        !(node = *(uintptr_t *)(node + 0x68)) || !(node = *(uintptr_t *)(node + 0x28))) return nullptr;
    return (float *)(node + 0x10);
}

extern "C" {
    uint64_t BreakIn_UserSteamId_injection_return;
    void BreakIn_UserSteamId_injection();
    void BreakIn_UserSteamId_injection_helper(char *id) { PlayerProtection::record_invader(id); }
}

void PlayerProtection::validate()
{
    // Pinned supported executable, checked before *any* protection writes.
    // These are the instructions replayed/branched around by upstream ASM.
    static const struct { unsigned rva, size; unsigned char bytes[18]; } sites[] = {
        {0x322915,16,{0x48,0x83,0xec,0x20,0xf6,0x81,0x24,0x05,0,0,0x40,0x48,0x8b,0xd9,0x75,0x36}},
        {0x3ac6f3,14,{0x48,0x8b,0x46,0x10,0x48,0x85,0xc0,0x74,0x03,0x8b,0x78,0x28,0x8b,0xc7}},
        {0x2bb56a,15,{0xf3,0x0f,0x10,0x5c,0x24,0x20,0x0f,0x14,0xd8,0x0f,0x14,0xd1,0x0f,0x14,0xda}},
        {0x761041,14,{0x48,0x8b,0x5c,0x24,0x30,0x48,0x8b,0x74,0x24,0x38,0x48,0x83,0xc4,0x20}},
        {0x23b4342,16,{0x3d,0x80,0,0,0,0x55,0x48,0xbd,0xe6,0xd7,0xfd,0x42,0x01,0,0,0}},
        {0x2a5ec57,17,{0x48,0x8b,0xd3,0x83,0xf8,0x10,0x0f,0x84,0x76,0x9c,0xaa,0xfd,0xe9,0x50,0x9c,0xaa,0xfd}},
        {0x352dcf,18,{0xe8,0x3c,0xbe,0xfe,0xff,0x48,0x85,0xc0,0x74,0x4a,0xf2,0x0f,0x10,0x80,0x30,0x01,0,0}},
        {0x3521fe,14,{0x41,0x0f,0x28,0x94,0x24,0x40,0x01,0,0,0x48,0x8d,0x54,0x24,0x40}},
        {0x50861d,16,{0x49,0xc1,0xe8,0x22,0x8b,0xd1,0x48,0x8b,0xc8,0x41,0x81,0xe0,0xff,0xff,0xff,0x3f}},
        {0x353b1b,14,{0xe8,0x30,0xe0,0x01,0,0x48,0x85,0xc0,0x74,0x1c,0x48,0x8b,0x48,0x18}},
        {0x350903,14,{0xe8,0x08,0xe3,0xfe,0xff,0x48,0x85,0xc0,0x74,0x06,0x4c,0x8b,0x60,0x68}},
        {0x50b5e6,18,{0x44,0x8b,0x4c,0x24,0x50,0x4d,0x8b,0xc6,0x8b,0xd3,0x49,0x8b,0xca,0xe8,0x98,0xbf,0,0}},
        {0xbdf000,6,{0x0f,0x85,0x4a,0x02,0,0}},
        {0xbd0efb,16,{0x4c,0x8b,0xc6,0x48,0x8d,0x4d,0x07,0xe8,0x49,0xd0,0x53,0xff,0x49,0x8d,0x4f,0x68}}
    };
    for (auto &site : sites)
        if (memcmp((void *)(Game::ds1_base + site.rva), site.bytes, site.size))
            FATALERROR("Player protection hook at RVA %x conflicts with another patch", site.rva);
}

void PlayerProtection::start()
{
    unsigned char *image = (unsigned char *)GetModuleHandleW(nullptr);
    auto nt = (IMAGE_NT_HEADERS64 *)(image + ((IMAGE_DOS_HEADER *)image)->e_lfanew);
    auto entry = (IMAGE_IMPORT_DESCRIPTOR *)(image + nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT].VirtualAddress);
    bool found = false;
    HMODULE steam = GetModuleHandleW(L"steam_api64.dll");
    real_callbacks = resolve<decltype(real_callbacks)>(steam, "SteamAPI_RunCallbacks");
    for (; entry->Name; ++entry) {
        if (_stricmp((char *)image + entry->Name, "steam_api64.dll") || !entry->OriginalFirstThunk) continue;
        auto name = (IMAGE_THUNK_DATA64 *)(image + entry->OriginalFirstThunk);
        auto slot = (IMAGE_THUNK_DATA64 *)(image + entry->FirstThunk);
        for (; name->u1.AddressOfData; ++name, ++slot) {
            if (IMAGE_SNAP_BY_ORDINAL64(name->u1.Ordinal)) continue;
            auto import = (IMAGE_IMPORT_BY_NAME *)(image + name->u1.AddressOfData);
            if (strcmp((char *)import->Name, "SteamAPI_RunCallbacks")) continue;
            if (slot->u1.Function != (uint64_t)real_callbacks)
                FATALERROR("Another loader changed Steam callback dispatch");
            auto replacement = &run_callbacks;
            if (!sp::mem::patch_bytes(&slot->u1.Function, &replacement, sizeof replacement))
                FATALERROR("Unable to install player-protection session tracking");
            found = true;
        }
    }
    if (!found) FATALERROR("Steam callback import not found for player protection");
    sp::mem::code::x64::inject_jmp_14b(image + 0xbd0efb, &BreakIn_UserSteamId_injection_return,
                                     2, &BreakIn_UserSteamId_injection);
}
