// GPL-3.0-or-later. Reptile Fire/Ice ATB runtime for Lexeditor #323.
#include "lexeditor_ff8_reptile_atb.h"
#include "reptile_atb_runtime.h"

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <string>

#include "common.h"
#include "ff8.h"
#include "globals.h"
#include "log.h"
#include "patch.h"

namespace {
using SceneLoad = void(__cdecl *)(std::uint32_t, void *);
using ApplyDamage = void(__cdecl *)(std::uint32_t);

constexpr std::uintptr_t kSceneLoadCall = 0x0047D539;
constexpr std::uintptr_t kSceneLoad = 0x0048D0E0;
constexpr std::uintptr_t kAtbPatch = 0x004843CF;
constexpr std::uintptr_t kAtbContinueAddress = 0x004843D5;
constexpr std::uintptr_t kApplyDamage = 0x0048FE20;
constexpr std::uintptr_t kHitElement = 0x01D2A239;
constexpr std::uintptr_t kAttackHitCount = 0x01D280C1;
constexpr std::uintptr_t kEncounter = 0x01D287DC;
constexpr std::uintptr_t kDamageCalls[] = {
    0x004850FA, 0x004851F1, 0x0048EA93, 0x0048F3CB, 0x0048F44C,
};

SceneLoad original_scene_load = nullptr;
ApplyDamage original_apply_damage = nullptr;
std::uintptr_t g_atb_continue = kAtbContinueAddress;
lexeditor_reptile_atb::SpeedState g_speed;
bool g_reptile_ids[255]{};
bool g_enabled = false;
bool g_installed = false;
std::uint16_t g_seen_targets = 0;
std::uint8_t g_last_hit_count = 0xFF;

std::string trim(std::string value)
{
    const auto first = value.find_first_not_of(" \t\r\n");
    if (first == std::string::npos) return {};
    const auto last = value.find_last_not_of(" \t\r\n");
    return value.substr(first, last - first + 1);
}

bool parse_ids(const std::string &line, bool (&ids)[255])
{
    constexpr const char *prefix = "enemyIds = \"";
    if (line.rfind(prefix, 0) != 0 || line.size() < std::strlen(prefix) + 1 || line.back() != '"')
        return false;
    const auto body = line.substr(std::strlen(prefix), line.size() - std::strlen(prefix) - 1);
    if (body.empty()) return true;
    std::size_t start = 0;
    while (start < body.size()) {
        const auto comma = body.find(',', start);
        const auto token = body.substr(start, comma == std::string::npos ? std::string::npos : comma - start);
        if (token.empty()) return false;
        unsigned value = 0;
        for (char ch : token) {
            if (ch < '0' || ch > '9') return false;
            value = value * 10u + static_cast<unsigned>(ch - '0');
            if (value > 254u) return false;
        }
        ids[value] = true;
        if (comma == std::string::npos) break;
        start = comma + 1;
    }
    return true;
}

bool load_runtime()
{
    char path[MAX_PATH] = {};
    std::snprintf(path, sizeof(path), "%s/%s/lexeditor/reptile-atb.toml",
        basedir, direct_mode_path.c_str());
    std::ifstream stream(path);
    if (!stream) return false;

    bool ids[255]{};
    bool saw_schema = false;
    bool saw_enabled = false;
    bool saw_ids = false;
    bool enabled = false;
    std::string raw;
    while (std::getline(stream, raw)) {
        const auto line = trim(raw);
        if (line.empty() || line[0] == '#') continue;
        if (line == "schemaVersion = 1" && !saw_schema) {
            saw_schema = true;
            continue;
        }
        if ((line == "enabled = true" || line == "enabled = false") && !saw_enabled) {
            enabled = line == "enabled = true";
            saw_enabled = true;
            continue;
        }
        if (line.rfind("enemyIds", 0) == 0 && !saw_ids && parse_ids(line, ids)) {
            saw_ids = true;
            continue;
        }
        ffnx_warning("Reptile ATB: malformed runtime configuration; native ATB retained.\n");
        return false;
    }
    if (!saw_schema || !saw_enabled || !saw_ids) {
        ffnx_warning("Reptile ATB: incomplete runtime configuration; native ATB retained.\n");
        return false;
    }
    std::memcpy(g_reptile_ids, ids, sizeof(ids));
    g_enabled = enabled;
    return true;
}

void reset_battle_state()
{
    g_speed.reset();
    g_seen_targets = 0;
    g_last_hit_count = 0xFF;
}

bool relative_call_targets(std::uintptr_t site, std::uintptr_t target)
{
    const auto *code = reinterpret_cast<const unsigned char *>(site);
    if (code[0] != 0xE8) return false;
    std::int32_t relative = 0;
    std::memcpy(&relative, code + 1, sizeof(relative));
    return site + 5 + relative == target;
}

bool reptile_target(unsigned target)
{
    const int index = lexeditor_reptile_atb::enemy_index(target);
    if (index < 0) return false;
    const auto entity = *reinterpret_cast<const std::uint8_t *>(
        kEncounter + 0x38 + static_cast<unsigned>(index));
    const int id = lexeditor_reptile_atb::com_id(target, entity);
    return id >= 0 && id < 255 && g_reptile_ids[id];
}

void begin_resolved_hit()
{
    // Battle_UpdateDamage increments this byte immediately after every one of
    // the five Battle_applyDamage call sites below. FF8 resets it to zero at
    // the next action. A non-increasing value therefore marks a new move even
    // when a multi-hit animation spans several rendered frames.
    const auto hit_count = *reinterpret_cast<const std::uint8_t *>(kAttackHitCount);
    if (hit_count <= g_last_hit_count)
        g_seen_targets = 0;
    g_last_hit_count = hit_count;
}

void apply_resolved_element(unsigned target)
{
    begin_resolved_hit();
    if (!g_enabled || !reptile_target(target)) return;
    const auto element = *reinterpret_cast<const std::uint8_t *>(kHitElement);
    if (!(element & (lexeditor_reptile_atb::kFireElement | lexeditor_reptile_atb::kIceElement))) return;

    const auto bit = static_cast<std::uint16_t>(1u << target);
    if (g_seen_targets & bit) return;
    g_seen_targets = static_cast<std::uint16_t>(g_seen_targets | bit);
    g_speed.apply(target, element);
}

void __cdecl scene_load(std::uint32_t scene, void *destination)
{
    original_scene_load(scene, destination);
    reset_battle_state();
}

void __cdecl apply_damage(std::uint32_t target)
{
    original_apply_damage(target);
    apply_resolved_element(target);
}
}

extern "C" std::uint32_t __cdecl lexeditor_ff8_reptile_scale_increment(
    std::uint32_t slot, std::uint32_t native_increment)
{
    if (!g_enabled) return native_increment;
    return g_speed.scale_increment(slot, native_increment);
}

extern "C" __declspec(dllexport) __declspec(naked) void lexeditor_ff8_reptile_atb_increment()
{
    __asm {
        push eax
        push ecx
        push edx
        push edi
        call lexeditor_ff8_reptile_scale_increment
        add esp, 8
        mov edx, eax
        pop ecx
        pop eax
        mov ecx, dword ptr [esi]
        add edx, ecx
        mov dword ptr [esi], edx
        jmp dword ptr [g_atb_continue]
    }
}

void lexeditor_ff8_reptile_atb_install()
{
    if (!ff8 || !FF8_US_VERSION || g_installed || !load_runtime() || !g_enabled) return;

    const unsigned char atb[] = {0x8B,0x0E,0x03,0xD1,0x89,0x16};
    if (!relative_call_targets(kSceneLoadCall, kSceneLoad) ||
        std::memcmp(reinterpret_cast<void *>(kAtbPatch), atb, sizeof(atb))) {
        ffnx_warning("Reptile ATB: supported scene/ATB seam changed; native ATB retained.\n");
        return;
    }
    for (const auto site : kDamageCalls) {
        if (!relative_call_targets(site, kApplyDamage)) {
            ffnx_warning("Reptile ATB: supported damage seam changed; native ATB retained.\n");
            return;
        }
    }

    original_scene_load = reinterpret_cast<SceneLoad>(kSceneLoad);
    original_apply_damage = reinterpret_cast<ApplyDamage>(kApplyDamage);
    replace_call(static_cast<std::uint32_t>(kSceneLoadCall), reinterpret_cast<void *>(&scene_load));
    for (const auto site : kDamageCalls)
        replace_call(static_cast<std::uint32_t>(site), reinterpret_cast<void *>(&apply_damage));
    replace_function(static_cast<std::uint32_t>(kAtbPatch),
        reinterpret_cast<void *>(&lexeditor_ff8_reptile_atb_increment));
    patch_code_byte(static_cast<std::uint32_t>(kAtbPatch + 5), 0x90);
    reset_battle_state();
    g_installed = true;
    ffnx_info("Reptile ATB: cumulative Ice 0.92 / Fire 1.08 enemy speed runtime installed.\n");
}

extern "C" __declspec(dllexport) unsigned int lexeditor_ff8_reptile_atb_contract_version()
{
    return 1;
}
