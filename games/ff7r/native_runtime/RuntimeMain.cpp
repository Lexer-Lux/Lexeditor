#include <windows.h>

#include "RuntimeConfig.hpp"
#include "RuntimeSignatures.hpp"

#include <cstddef>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <optional>
#include <span>
#include <sstream>
#include <string>

namespace {

using lexeditor::ff7r::RuntimeConfig;

HMODULE g_module = nullptr;
constexpr wchar_t kStatusFileName[] = L"LexeditorFF7RRuntime.status.json";
constexpr wchar_t kConfigFileName[] = L"LexeditorFF7RRuntime.json";
constexpr DWORD kPathBufferSize = 32768;

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

std::uint32_t executable_timestamp() noexcept {
    const auto module = reinterpret_cast<const std::byte*>(GetModuleHandleW(nullptr));
    if (module == nullptr) {
        return 0;
    }
    const auto dos = reinterpret_cast<const IMAGE_DOS_HEADER*>(module);
    if (dos->e_magic != IMAGE_DOS_SIGNATURE || dos->e_lfanew <= 0) {
        return 0;
    }
    const auto nt = reinterpret_cast<const IMAGE_NT_HEADERS64*>(module + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE
            || nt->OptionalHeader.Magic != IMAGE_NT_OPTIONAL_HDR64_MAGIC) {
        return 0;
    }
    return nt->FileHeader.TimeDateStamp;
}

std::span<const std::uint8_t> executable_text() noexcept {
    const auto module = reinterpret_cast<const std::byte*>(GetModuleHandleW(nullptr));
    if (module == nullptr) {
        return {};
    }
    const auto dos = reinterpret_cast<const IMAGE_DOS_HEADER*>(module);
    if (dos->e_magic != IMAGE_DOS_SIGNATURE || dos->e_lfanew <= 0) {
        return {};
    }
    const auto nt = reinterpret_cast<const IMAGE_NT_HEADERS64*>(module + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE
            || nt->OptionalHeader.Magic != IMAGE_NT_OPTIONAL_HDR64_MAGIC) {
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
    const std::string text(
        std::istreambuf_iterator<char>(input),
        std::istreambuf_iterator<char>());
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
    };
}

std::string diagnostic_notes(const ConfigLoadResult& loaded,
                             const SignatureDiagnostics& signatures) {
    std::ostringstream notes;
    notes << "Runtime DLL loaded; gameplay hooks remain inactive until separately installed and validated. ";
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
        << "publicSignatureMatches.mapControl=" << signatures.mapControl << "; "
        << "publicSignatureMatches.rawInputRegistration=" << signatures.rawInputRegistration << "; "
        << "publicSignatureMatches.joystickMovement=" << signatures.joystickMovement << "; "
        << "signatureProvenance=TheUnlocked/ff7r-kbm-hook-MIT; "
        << "signature matches are candidates only.";
    return notes.str();
}

void write_status() {
    const auto path = status_path();
    if (path.empty()) {
        return;
    }
    const auto timestamp = executable_timestamp();
    if (timestamp == 0) {
        return;
    }
    const ConfigLoadResult loaded = load_config();
    const SignatureDiagnostics signatures = scan_signatures();
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
            << "    \"cutsceneSpeed\": false,\n"
            << "    \"minimapTapHold\": false,\n"
            << "    \"minimapState\": false,\n"
            << "    \"hpRebalance\": false,\n"
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

} // namespace

extern "C" __declspec(dllexport) void Init() noexcept {
    try {
        // Init runs after the loader has finished loading this module, so it is
        // safe to do filesystem work and scan the mapped executable here.
        write_status();
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
