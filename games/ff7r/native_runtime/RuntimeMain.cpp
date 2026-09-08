#include <windows.h>

#include <cstdint>
#include <filesystem>
#include <fstream>
#include <string>

namespace {

HMODULE g_module = nullptr;
constexpr wchar_t kStatusFileName[] = L"LexeditorFF7RRuntime.status.json";

std::filesystem::path status_path() {
    wchar_t buffer[32768]{};
    const DWORD length = GetModuleFileNameW(g_module, buffer, static_cast<DWORD>(std::size(buffer)));
    if (length == 0 || length >= std::size(buffer)) {
        return {};
    }
    return std::filesystem::path(buffer).parent_path() / kStatusFileName;
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
    if (nt->Signature != IMAGE_NT_SIGNATURE) {
        return 0;
    }
    return nt->FileHeader.TimeDateStamp;
}

void remove_status() noexcept {
    try {
        const auto path = status_path();
        if (!path.empty()) {
            DeleteFileW(path.c_str());
        }
    } catch (...) {
        // Never allow runtime-status cleanup to escape DllMain.
    }
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
            << "  \"notes\": \"Runtime DLL loaded successfully; no gameplay feature hook is reported active until its installed-build signature and implementation are validated.\"\n"
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
        write_status();
    } catch (...) {
        // Native Mod Loader must never receive an exception from plugin Init().
    }
}

BOOL APIENTRY DllMain(HMODULE module, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        g_module = module;
        DisableThreadLibraryCalls(module);
        remove_status();
    } else if (reason == DLL_PROCESS_DETACH) {
        remove_status();
    }
    return TRUE;
}
