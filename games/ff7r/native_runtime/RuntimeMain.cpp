#include <windows.h>

#include "RuntimeConfig.hpp"
#include "RuntimeCutscene.hpp"
#include "RuntimeFeatureHealth.hpp"
#include "RuntimeHP.hpp"
#include "RuntimeSignatures.hpp"

#include <array>
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <mutex>
#include <optional>
#include <span>
#include <sstream>
#include <string>

namespace {

using lexeditor::ff7r::CutsceneSpeedTrack;
using lexeditor::ff7r::FeatureHealth;
using lexeditor::ff7r::HPTrackState;
using lexeditor::ff7r::HPWritePlan;
using lexeditor::ff7r::PlayerStatsPrefix;
using lexeditor::ff7r::RuntimeConfig;

HMODULE g_module = nullptr;
constexpr wchar_t kStatusFileName[] = L"LexeditorFF7RRuntime.status.json";
constexpr wchar_t kConfigFileName[] = L"LexeditorFF7RRuntime.json";
constexpr DWORD kPathBufferSize = 32768;
constexpr DWORD kCutsceneWorkerIntervalMs = 25;
constexpr DWORD kHPWorkerIntervalMs = 100;

std::atomic_bool g_cutsceneSpeedActive{false};
std::atomic<double> g_cutsceneBaseMultiplier{1.25};
std::atomic_bool g_hpRebalanceActive{false};
std::atomic<double> g_hpMultiplier{0.5};
std::mutex g_statusWriteMutex;

enum class CutsceneWorkerState : int {
    disabled = 0,
    signatureMissing,
    signatureAmbiguous,
    signatureInvalid,
    blockMissing,
    blockAmbiguous,
    blockUnreadable,
    startFailed,
    armed,
    active,
};
std::atomic<CutsceneWorkerState> g_cutsceneWorkerState{CutsceneWorkerState::disabled};

enum class HPWorkerState : int {
    disabled = 0,
    signatureMissing,
    signatureAmbiguous,
    signatureInvalid,
    startFailed,
    armed,
    active,
};
std::atomic<HPWorkerState> g_hpWorkerState{HPWorkerState::disabled};

std::filesystem::path module_directory() {
    wchar_t buffer[kPathBufferSize]{};
    const DWORD length = GetModuleFileNameW(g_module, buffer, kPathBufferSize);
    if (length == 0 || length >= kPathBufferSize) {
        return {};
    }
    return std::filesystem::path(buffer).parent_path();
}

std::filesystem::path status_path() {
    const auto directory = module_directory();
    return directory.empty() ? std::filesystem::path{} : directory / kStatusFileName;
}

std::filesystem::path config_path() {
    const auto directory = module_directory();
    return directory.empty() ? std::filesystem::path{} : directory / kConfigFileName;
}

const IMAGE_NT_HEADERS64* executable_headers() noexcept {
    const auto module = reinterpret_cast<const std::byte*>(GetModuleHandleW(nullptr));
    if (module == nullptr) {
        return nullptr;
    }
    const auto dos = reinterpret_cast<const IMAGE_DOS_HEADER*>(module);
    if (dos->e_magic != IMAGE_DOS_SIGNATURE || dos->e_lfanew <= 0) {
        return nullptr;
    }
    const auto nt = reinterpret_cast<const IMAGE_NT_HEADERS64*>(module + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE
            || nt->OptionalHeader.Magic != IMAGE_NT_OPTIONAL_HDR64_MAGIC) {
        return nullptr;
    }
    return nt;
}

std::uint32_t executable_timestamp() noexcept {
    const auto* nt = executable_headers();
    return nt == nullptr ? 0 : nt->FileHeader.TimeDateStamp;
}

std::span<const std::uint8_t> executable_text() noexcept {
    const auto module = reinterpret_cast<const std::byte*>(GetModuleHandleW(nullptr));
    const auto* nt = executable_headers();
    if (module == nullptr || nt == nullptr) {
        return {};
    }
    const auto* section = IMAGE_FIRST_SECTION(nt);
    for (WORD index = 0; index < nt->FileHeader.NumberOfSections; ++index, ++section) {
        const char textName[] = ".text";
        if (std::memcmp(section->Name, textName, sizeof(textName) - 1) != 0) {
            continue;
        }
        const std::size_t size = static_cast<std::size_t>(section->Misc.VirtualSize);
        if (size == 0) {
            return {};
        }
        const auto* begin = reinterpret_cast<const std::uint8_t*>(
            module + section->VirtualAddress);
        return {begin, size};
    }
    return {};
}

bool address_in_main_image(std::uintptr_t address, std::size_t size) noexcept {
    const auto module = reinterpret_cast<std::uintptr_t>(GetModuleHandleW(nullptr));
    const auto* nt = executable_headers();
    if (module == 0 || nt == nullptr || size == 0) {
        return false;
    }
    const auto imageSize = static_cast<std::uintptr_t>(nt->OptionalHeader.SizeOfImage);
    if (address < module || address - module > imageSize) {
        return false;
    }
    const auto offset = address - module;
    return size <= imageSize - offset;
}

template <typename T>
bool read_process_value(std::uintptr_t address, T& output) noexcept {
    SIZE_T bytesRead = 0;
    return ReadProcessMemory(
        GetCurrentProcess(),
        reinterpret_cast<LPCVOID>(address),
        &output,
        sizeof(T),
        &bytesRead) != FALSE
        && bytesRead == sizeof(T);
}

template <typename T>
bool write_process_value(std::uintptr_t address, const T& value) noexcept {
    SIZE_T bytesWritten = 0;
    return WriteProcessMemory(
        GetCurrentProcess(),
        reinterpret_cast<LPVOID>(address),
        &value,
        sizeof(T),
        &bytesWritten) != FALSE
        && bytesWritten == sizeof(T);
}

std::optional<std::uintptr_t> resolve_game_state_global() noexcept {
    const auto text = executable_text();
    if (text.empty()) {
        return std::nullopt;
    }
    const auto matches = lexeditor::ff7r::findGameStateLoad(text);
    if (matches.size() != 1) {
        return std::nullopt;
    }
    const auto* instruction = text.data() + matches[0].offset;
    std::int32_t displacement = 0;
    std::memcpy(&displacement, instruction + 3, sizeof(displacement));
    const auto next = reinterpret_cast<std::intptr_t>(instruction + 7);
    const auto targetSigned = next + static_cast<std::intptr_t>(displacement);
    if (targetSigned <= 0) {
        return std::nullopt;
    }
    const auto target = static_cast<std::uintptr_t>(targetSigned);
    if (!address_in_main_image(target, sizeof(std::uintptr_t))) {
        return std::nullopt;
    }
    return target;
}

std::string json_escape(std::string_view value) {
    std::string result;
    result.reserve(value.size());
    for (const unsigned char ch : value) {
        switch (ch) {
            case '"': result += "\\\""; break;
            case '\\': result += "\\\\"; break;
            case '\b': result += "\\b"; break;
            case '\f': result += "\\f"; break;
            case '\n': result += "\\n"; break;
            case '\r': result += "\\r"; break;
            case '\t': result += "\\t"; break;
            default:
                if (ch >= 0x20 && ch <= 0x7E) {
                    result.push_back(static_cast<char>(ch));
                } else {
                    result.push_back('?');
                }
                break;
        }
    }
    return result;
}

struct ConfigLoadResult {
    std::optional<RuntimeConfig> config;
    std::string error;
};

ConfigLoadResult load_config() {
    const auto path = config_path();
    if (path.empty()) {
        return {{}, "runtime DLL path could not be resolved"};
    }
    std::ifstream input(path, std::ios::binary);
    if (!input) {
        return {{}, "LexeditorFF7RRuntime.json is missing or unreadable"};
    }
    const std::string text{
        std::istreambuf_iterator<char>{input},
        std::istreambuf_iterator<char>{}};
    if (!input.eof() && input.fail()) {
        return {{}, "LexeditorFF7RRuntime.json could not be read completely"};
    }
    try {
        return {lexeditor::ff7r::parseRuntimeConfig(text), ""};
    } catch (const std::exception& error) {
        return {{}, error.what()};
    }
}

struct SignatureDiagnostics {
    std::size_t mapControl = 0;
    std::size_t rawInputRegistration = 0;
    std::size_t joystickMovement = 0;
    std::size_t gameStateLoad = 0;
};

SignatureDiagnostics scan_signatures() {
    const auto text = executable_text();
    if (text.empty()) {
        return {};
    }
    return {
        lexeditor::ff7r::findMapControl(text).size(),
        lexeditor::ff7r::findRawInputRegistration(text).size(),
        lexeditor::ff7r::findJoystickMovement(text).size(),
        lexeditor::ff7r::findGameStateLoad(text).size(),
    };
}

const char* cutscene_worker_state_name(CutsceneWorkerState state) noexcept {
    switch (state) {
        case CutsceneWorkerState::disabled: return "disabled";
        case CutsceneWorkerState::signatureMissing: return "signature-missing";
        case CutsceneWorkerState::signatureAmbiguous: return "signature-ambiguous";
        case CutsceneWorkerState::signatureInvalid: return "signature-invalid";
        case CutsceneWorkerState::blockMissing: return "game-speed-block-missing";
        case CutsceneWorkerState::blockAmbiguous: return "game-speed-block-ambiguous";
        case CutsceneWorkerState::blockUnreadable: return "game-speed-block-unreadable";
        case CutsceneWorkerState::startFailed: return "start-failed";
        case CutsceneWorkerState::armed: return "armed";
        case CutsceneWorkerState::active: return "active";
    }
    return "unknown";
}

const char* hp_worker_state_name(HPWorkerState state) noexcept {
    switch (state) {
        case HPWorkerState::disabled: return "disabled";
        case HPWorkerState::signatureMissing: return "signature-missing";
        case HPWorkerState::signatureAmbiguous: return "signature-ambiguous";
        case HPWorkerState::signatureInvalid: return "signature-invalid";
        case HPWorkerState::startFailed: return "start-failed";
        case HPWorkerState::armed: return "armed";
        case HPWorkerState::active: return "active";
    }
    return "unknown";
}

std::string diagnostic_notes(const ConfigLoadResult& loaded,
                             const SignatureDiagnostics& signatures) {
    std::ostringstream notes;
    notes << "Runtime DLL loaded. ";
    if (loaded.config.has_value()) {
        const auto& config = *loaded.config;
        notes
            << "runtimeConfigLoaded=true; "
            << "requested.cutsceneSpeed=" << (config.cutsceneSpeed.enabled ? "true" : "false") << "; "
            << "requested.minimap=" << (config.minimap.enabled ? "true" : "false") << "; "
            << "requested.hpRebalance=" << (config.hpRebalance.enabled ? "true" : "false") << "; "
            << "requested.betterSprint=" << (config.betterSprint.enabled ? "true" : "false") << "; ";
    } else {
        notes << "runtimeConfigLoaded=false; configError=" << loaded.error << "; ";
    }
    notes
        << "signatureMatches.mapControl=" << signatures.mapControl << "; "
        << "signatureMatches.rawInputRegistration=" << signatures.rawInputRegistration << "; "
        << "signatureMatches.joystickMovement=" << signatures.joystickMovement << "; "
        << "signatureMatches.gameStateLoad=" << signatures.gameStateLoad << "; "
        << "cutsceneSpeed.worker=" << cutscene_worker_state_name(g_cutsceneWorkerState.load()) << "; "
        << "hpRebalance.worker=" << hp_worker_state_name(g_hpWorkerState.load()) << "; "
        << "signatureProvenance=" << lexeditor::ff7r::kSignatureProvenance << "; "
        << "remaining unimplemented gameplay hooks stay inactive.";
    return notes.str();
}

void write_status(const ConfigLoadResult& loaded, const SignatureDiagnostics& signatures) {
    // Both native workers can change live-state concurrently. Serialize the
    // fixed .tmp -> status replacement so they cannot truncate or rename each
    // other's heartbeat writes.
    const std::lock_guard<std::mutex> lock(g_statusWriteMutex);
    const auto path = status_path();
    if (path.empty()) {
        return;
    }
    const auto timestamp = executable_timestamp();
    if (timestamp == 0) {
        return;
    }
    const std::string notes = diagnostic_notes(loaded, signatures);

    const auto temporary = std::filesystem::path(path.wstring() + L".tmp");
    {
        std::ofstream output(temporary, std::ios::binary | std::ios::trunc);
        if (!output) {
            return;
        }
        output
            << "{\n"
            << "  \"statusVersion\": 1,\n"
            << "  \"processId\": " << GetCurrentProcessId() << ",\n"
            << "  \"exeTimestamp\": " << timestamp << ",\n"
            << "  \"loaded\": true,\n"
            << "  \"features\": {\n"
            << "    \"cutsceneSpeed\": " << (g_cutsceneSpeedActive.load() ? "true" : "false") << ",\n"
            << "    \"minimapTapHold\": false,\n"
            << "    \"minimapState\": false,\n"
            << "    \"hpRebalance\": " << (g_hpRebalanceActive.load() ? "true" : "false") << ",\n"
            << "    \"betterSprint\": false,\n"
            << "    \"atbTweaks\": false,\n"
            << "    \"dogWhistle\": false,\n"
            << "    \"unscannedNames\": false\n"
            << "  },\n"
            << "  \"notes\": \"" << json_escape(notes) << "\"\n"
            << "}\n";
        output.flush();
        if (!output) {
            return;
        }
    }
    MoveFileExW(temporary.c_str(), path.c_str(), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH);
}

void publish_feature_state(std::atomic_bool& feature, bool active) noexcept {
    const bool previous = feature.exchange(active);
    if (previous == active) {
        return;
    }
    try {
        write_status(load_config(), scan_signatures());
    } catch (...) {
        // Worker health reporting must never terminate a Native Mod Loader
        // thread because status-file I/O or diagnostics failed.
    }
}

void observe_feature_health(
    std::atomic_bool& feature,
    FeatureHealth& health,
    bool successful) noexcept {
    if (health.observe(successful)) {
        publish_feature_state(feature, health.active);
    }
}

enum class GameSpeedBlockResolveState : int {
    unique = 0,
    missing,
    ambiguous,
    unreadable,
};

struct GameSpeedBlockResolveResult {
    GameSpeedBlockResolveState state = GameSpeedBlockResolveState::unreadable;
    std::uintptr_t address = 0;
};

GameSpeedBlockResolveResult resolve_game_speed_block(std::uintptr_t gameState) noexcept {
    std::array<std::uint8_t, lexeditor::ff7r::kGameSpeedDiscoveryBytes> prefix{};
    SIZE_T bytesRead = 0;
    if (ReadProcessMemory(
            GetCurrentProcess(),
            reinterpret_cast<LPCVOID>(gameState),
            prefix.data(),
            prefix.size(),
            &bytesRead) == FALSE
            || bytesRead != prefix.size()) {
        return {GameSpeedBlockResolveState::unreadable, 0};
    }

    const auto matches = lexeditor::ff7r::findInitialGameSpeedBlocks(
        std::span<const std::uint8_t>(prefix));
    if (matches.empty()) {
        return {GameSpeedBlockResolveState::missing, 0};
    }
    if (matches.size() != 1) {
        return {GameSpeedBlockResolveState::ambiguous, 0};
    }
    return {GameSpeedBlockResolveState::unique, gameState + matches[0].offset};
}

bool apply_cutscene_speed_tick(
    std::uintptr_t gameSpeedBlock,
    double multiplier,
    CutsceneSpeedTrack& track) noexcept {
    const std::uintptr_t address = gameSpeedBlock
        + lexeditor::ff7r::kCutsceneGameSpeedIndex * sizeof(float);
    float snapshot = 0.0F;
    if (!read_process_value(address, snapshot)) {
        return false;
    }
    const auto plan = lexeditor::ff7r::makeCutsceneSpeedWritePlan(track, snapshot, multiplier);
    if (!plan.valid) {
        return false;
    }

    if (plan.write) {
        float current = 0.0F;
        if (!read_process_value(address, current) || current != snapshot) {
            return false;
        }
        if (!write_process_value(address, plan.appliedSpeed)) {
            return false;
        }
    }
    lexeditor::ff7r::commitCutsceneSpeedWritePlan(track, plan);
    return true;
}

DWORD WINAPI cutscene_worker(LPVOID) noexcept {
    const auto gameStateGlobal = resolve_game_state_global();
    if (!gameStateGlobal.has_value()) {
        g_cutsceneWorkerState.store(CutsceneWorkerState::signatureInvalid);
        return 0;
    }

    FeatureHealth health{};
    std::uintptr_t previousGameState = 0;
    std::uintptr_t gameSpeedBlock = 0;
    CutsceneSpeedTrack track{};
    for (;;) {
        std::uintptr_t gameState = 0;
        if (!read_process_value(*gameStateGlobal, gameState) || gameState == 0) {
            g_cutsceneWorkerState.store(CutsceneWorkerState::armed);
            observe_feature_health(g_cutsceneSpeedActive, health, false);
            Sleep(kCutsceneWorkerIntervalMs);
            continue;
        }
        if (gameState != previousGameState) {
            previousGameState = gameState;
            gameSpeedBlock = 0;
            track = {};
            g_cutsceneWorkerState.store(CutsceneWorkerState::armed);
        }

        if (gameSpeedBlock == 0) {
            const auto resolved = resolve_game_speed_block(gameState);
            switch (resolved.state) {
                case GameSpeedBlockResolveState::unique:
                    gameSpeedBlock = resolved.address;
                    g_cutsceneWorkerState.store(CutsceneWorkerState::armed);
                    break;
                case GameSpeedBlockResolveState::missing:
                    g_cutsceneWorkerState.store(CutsceneWorkerState::blockMissing);
                    observe_feature_health(g_cutsceneSpeedActive, health, false);
                    Sleep(kCutsceneWorkerIntervalMs);
                    continue;
                case GameSpeedBlockResolveState::ambiguous:
                    g_cutsceneWorkerState.store(CutsceneWorkerState::blockAmbiguous);
                    observe_feature_health(g_cutsceneSpeedActive, health, false);
                    Sleep(kCutsceneWorkerIntervalMs);
                    continue;
                case GameSpeedBlockResolveState::unreadable:
                    g_cutsceneWorkerState.store(CutsceneWorkerState::blockUnreadable);
                    observe_feature_health(g_cutsceneSpeedActive, health, false);
                    Sleep(kCutsceneWorkerIntervalMs);
                    continue;
            }
        }

        const bool applied = apply_cutscene_speed_tick(
            gameSpeedBlock, g_cutsceneBaseMultiplier.load(), track);
        g_cutsceneWorkerState.store(
            applied ? CutsceneWorkerState::active : CutsceneWorkerState::armed);
        observe_feature_health(g_cutsceneSpeedActive, health, applied);
        Sleep(kCutsceneWorkerIntervalMs);
    }
}

void start_cutscene_worker(
    const ConfigLoadResult& loaded,
    const SignatureDiagnostics& signatures) noexcept {
    if (!loaded.config.has_value() || !loaded.config->cutsceneSpeed.enabled) {
        g_cutsceneWorkerState.store(CutsceneWorkerState::disabled);
        return;
    }
    if (signatures.gameStateLoad == 0) {
        g_cutsceneWorkerState.store(CutsceneWorkerState::signatureMissing);
        return;
    }
    if (signatures.gameStateLoad != 1) {
        g_cutsceneWorkerState.store(CutsceneWorkerState::signatureAmbiguous);
        return;
    }
    if (!resolve_game_state_global().has_value()) {
        g_cutsceneWorkerState.store(CutsceneWorkerState::signatureInvalid);
        return;
    }

    g_cutsceneBaseMultiplier.store(loaded.config->cutsceneSpeed.baseMultiplier);
    g_cutsceneWorkerState.store(CutsceneWorkerState::armed);

    HMODULE pinned = nullptr;
    if (!GetModuleHandleExW(
            GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_PIN,
            reinterpret_cast<LPCWSTR>(&g_module),
            &pinned)) {
        g_cutsceneWorkerState.store(CutsceneWorkerState::startFailed);
        return;
    }
    HANDLE thread = CreateThread(nullptr, 0, cutscene_worker, nullptr, 0, nullptr);
    if (thread == nullptr) {
        g_cutsceneWorkerState.store(CutsceneWorkerState::startFailed);
        return;
    }
    CloseHandle(thread);
}

bool read_player_stats(std::uintptr_t statsAddress, PlayerStatsPrefix& stats) noexcept {
    return read_process_value(statsAddress + lexeditor::ff7r::kPlayerHPFieldOffset, stats);
}

bool apply_hp_rebalance_tick(
    std::uintptr_t gameState,
    double multiplier,
    std::array<HPTrackState, 1 + lexeditor::ff7r::kGameStatePartyStatsCount>& tracks) noexcept {
    constexpr std::size_t kSlotCount = 1 + lexeditor::ff7r::kGameStatePartyStatsCount;
    std::array<std::uintptr_t, kSlotCount> addresses{};
    std::array<PlayerStatsPrefix, kSlotCount> snapshots{};
    std::array<HPWritePlan, kSlotCount> plans{};
    std::array<bool, kSlotCount> populated{};

    addresses[0] = gameState + lexeditor::ff7r::kGameStateCloudStatsOffset;
    for (std::size_t index = 0; index < lexeditor::ff7r::kGameStatePartyStatsCount; ++index) {
        addresses[index + 1] = gameState
            + lexeditor::ff7r::kGameStatePartyStatsOffset
            + index * lexeditor::ff7r::kPlayerStatsSize;
    }

    for (std::size_t index = 0; index < kSlotCount; ++index) {
        if (!read_player_stats(addresses[index], snapshots[index])) {
            return false;
        }
        if (index != 0 && lexeditor::ff7r::emptyPlayerStats(snapshots[index])) {
            tracks[index] = {};
            continue;
        }
        if (!lexeditor::ff7r::plausiblePlayerStats(snapshots[index])) {
            return false;
        }
        populated[index] = true;
        plans[index] = lexeditor::ff7r::makeHPWritePlan(tracks[index], snapshots[index], multiplier);
        if (!plans[index].valid) {
            return false;
        }
    }

    // Re-read before mutation so a level/equipment recalculation that races the
    // polling worker causes a retry rather than an overwrite of fresh values.
    for (std::size_t index = 0; index < kSlotCount; ++index) {
        if (!populated[index]) {
            continue;
        }
        PlayerStatsPrefix current{};
        if (!read_player_stats(addresses[index], current)
                || current.hp != snapshots[index].hp
                || current.maxHP != snapshots[index].maxHP
                || current.mp != snapshots[index].mp
                || current.maxMP != snapshots[index].maxMP) {
            return false;
        }
    }

    for (std::size_t index = 0; index < kSlotCount; ++index) {
        if (!populated[index]) {
            continue;
        }
        const auto& plan = plans[index];
        // Clamp current HP first when lowering MaxHP so it never remains above
        // the new maximum if the second write fails.
        if (plan.writeHP
                && !write_process_value(addresses[index] + lexeditor::ff7r::kPlayerHPFieldOffset, plan.hp)) {
            return false;
        }
        if (plan.writeMaxHP
                && !write_process_value(addresses[index] + lexeditor::ff7r::kPlayerMaxHPFieldOffset, plan.maxHP)) {
            return false;
        }
        lexeditor::ff7r::commitHPWritePlan(tracks[index], plan);
    }
    return true;
}

DWORD WINAPI hp_worker(LPVOID) noexcept {
    const auto gameStateGlobal = resolve_game_state_global();
    if (!gameStateGlobal.has_value()) {
        g_hpWorkerState.store(HPWorkerState::signatureInvalid);
        return 0;
    }

    FeatureHealth health{};
    std::array<HPTrackState, 1 + lexeditor::ff7r::kGameStatePartyStatsCount> tracks{};
    std::uintptr_t previousGameState = 0;
    for (;;) {
        std::uintptr_t gameState = 0;
        if (!read_process_value(*gameStateGlobal, gameState) || gameState == 0) {
            g_hpWorkerState.store(HPWorkerState::armed);
            observe_feature_health(g_hpRebalanceActive, health, false);
            Sleep(kHPWorkerIntervalMs);
            continue;
        }
        if (gameState != previousGameState) {
            tracks = {};
            previousGameState = gameState;
        }
        const bool applied = apply_hp_rebalance_tick(gameState, g_hpMultiplier.load(), tracks);
        g_hpWorkerState.store(applied ? HPWorkerState::active : HPWorkerState::armed);
        observe_feature_health(g_hpRebalanceActive, health, applied);
        Sleep(kHPWorkerIntervalMs);
    }
}

void start_hp_worker(
    const ConfigLoadResult& loaded,
    const SignatureDiagnostics& signatures) noexcept {
    if (!loaded.config.has_value() || !loaded.config->hpRebalance.enabled) {
        g_hpWorkerState.store(HPWorkerState::disabled);
        return;
    }
    if (signatures.gameStateLoad == 0) {
        g_hpWorkerState.store(HPWorkerState::signatureMissing);
        return;
    }
    if (signatures.gameStateLoad != 1) {
        g_hpWorkerState.store(HPWorkerState::signatureAmbiguous);
        return;
    }
    if (!resolve_game_state_global().has_value()) {
        g_hpWorkerState.store(HPWorkerState::signatureInvalid);
        return;
    }

    g_hpMultiplier.store(loaded.config->hpRebalance.multiplier);
    g_hpWorkerState.store(HPWorkerState::armed);

    // The Native Mod Loader owns process lifetime. Pin the DLL before starting a
    // detached worker so an unexpected FreeLibrary cannot unmap executing code.
    HMODULE pinned = nullptr;
    if (!GetModuleHandleExW(
            GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_PIN,
            reinterpret_cast<LPCWSTR>(&g_module),
            &pinned)) {
        g_hpWorkerState.store(HPWorkerState::startFailed);
        return;
    }
    HANDLE thread = CreateThread(nullptr, 0, hp_worker, nullptr, 0, nullptr);
    if (thread == nullptr) {
        g_hpWorkerState.store(HPWorkerState::startFailed);
        return;
    }
    CloseHandle(thread);
}

} // namespace

extern "C" __declspec(dllexport) void Init() noexcept {
    try {
        // Init runs after the loader has finished loading this module, so it is
        // safe to do filesystem work and scan the mapped executable here.
        const ConfigLoadResult loaded = load_config();
        const SignatureDiagnostics signatures = scan_signatures();
        start_cutscene_worker(loaded, signatures);
        start_hp_worker(loaded, signatures);
        write_status(loaded, signatures);
    } catch (...) {
        // Native Mod Loader must never receive an exception from plugin Init().
    }
}

BOOL APIENTRY DllMain(HMODULE module, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        g_module = module;
        DisableThreadLibraryCalls(module);
    }
    return TRUE;
}
