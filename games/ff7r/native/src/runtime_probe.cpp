#include <Windows.h>

#include <algorithm>
#include <array>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <mutex>
#include <optional>
#include <sstream>
#include <string>
#include <string_view>
#include <vector>

namespace {

HMODULE g_module = nullptr;
std::once_flag g_probe_once;

struct Region {
    const std::byte* begin{};
    std::size_t size{};
};

struct ProbeResult {
    std::string name;
    std::vector<std::uintptr_t> matches;
};

std::optional<Region> main_text_region() {
    const auto module = reinterpret_cast<const std::byte*>(GetModuleHandleW(nullptr));
    if (module == nullptr) {
        return std::nullopt;
    }

    const auto* dos = reinterpret_cast<const IMAGE_DOS_HEADER*>(module);
    if (dos->e_magic != IMAGE_DOS_SIGNATURE || dos->e_lfanew <= 0) {
        return std::nullopt;
    }

    const auto* nt = reinterpret_cast<const IMAGE_NT_HEADERS64*>(module + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE || nt->OptionalHeader.Magic != IMAGE_NT_OPTIONAL_HDR64_MAGIC) {
        return std::nullopt;
    }

    const auto* section = IMAGE_FIRST_SECTION(nt);
    for (WORD index = 0; index < nt->FileHeader.NumberOfSections; ++index, ++section) {
        std::array<char, IMAGE_SIZEOF_SHORT_NAME + 1> name{};
        std::copy_n(reinterpret_cast<const char*>(section->Name), IMAGE_SIZEOF_SHORT_NAME, name.data());
        if (std::string_view(name.data()) != ".text") {
            continue;
        }
        return Region{
            module + section->VirtualAddress,
            static_cast<std::size_t>(section->Misc.VirtualSize),
        };
    }
    return std::nullopt;
}

template <std::size_t N>
std::vector<std::uintptr_t> find_exact(const Region& region, const std::array<std::uint8_t, N>& signature) {
    std::vector<std::uintptr_t> matches;
    if (N == 0 || region.size < N) {
        return matches;
    }

    const auto* bytes = reinterpret_cast<const std::uint8_t*>(region.begin);
    for (std::size_t offset = 0; offset <= region.size - N; ++offset) {
        if (std::equal(signature.begin(), signature.end(), bytes + offset)) {
            matches.push_back(reinterpret_cast<std::uintptr_t>(region.begin + offset));
        }
    }
    return matches;
}

std::vector<std::uintptr_t> find_ascii(const Region& region, std::string_view needle) {
    std::vector<std::uintptr_t> matches;
    if (needle.empty() || region.size < needle.size()) {
        return matches;
    }

    const auto* chars = reinterpret_cast<const char*>(region.begin);
    for (std::size_t offset = 0; offset <= region.size - needle.size(); ++offset) {
        if (std::equal(needle.begin(), needle.end(), chars + offset)) {
            matches.push_back(reinterpret_cast<std::uintptr_t>(region.begin + offset));
        }
    }
    return matches;
}

std::string hex_address(std::uintptr_t address) {
    std::ostringstream stream;
    stream << "0x" << std::hex << std::uppercase << address;
    return stream.str();
}

std::string json_escape(std::string_view value) {
    std::string output;
    output.reserve(value.size());
    for (const char ch : value) {
        switch (ch) {
        case '\\': output += "\\\\"; break;
        case '"': output += "\\\""; break;
        case '\n': output += "\\n"; break;
        case '\r': output += "\\r"; break;
        case '\t': output += "\\t"; break;
        default:
            if (static_cast<unsigned char>(ch) >= 0x20U) {
                output += ch;
            }
            break;
        }
    }
    return output;
}

std::string narrow(const std::wstring& value) {
    if (value.empty()) {
        return {};
    }
    const int required = WideCharToMultiByte(
        CP_UTF8, 0, value.data(), static_cast<int>(value.size()), nullptr, 0, nullptr, nullptr);
    if (required <= 0) {
        return {};
    }
    std::string output(static_cast<std::size_t>(required), '\0');
    WideCharToMultiByte(
        CP_UTF8, 0, value.data(), static_cast<int>(value.size()), output.data(), required, nullptr, nullptr);
    return output;
}

std::filesystem::path module_path(HMODULE module) {
    std::wstring buffer(32768, L'\0');
    const DWORD length = GetModuleFileNameW(module, buffer.data(), static_cast<DWORD>(buffer.size()));
    if (length == 0 || length >= buffer.size()) {
        return {};
    }
    buffer.resize(length);
    return std::filesystem::path(buffer);
}

std::filesystem::path process_path() {
    return module_path(GetModuleHandleW(nullptr));
}

std::uintmax_t file_size_or_zero(const std::filesystem::path& path) {
    std::error_code error;
    const auto size = std::filesystem::file_size(path, error);
    return error ? 0U : size;
}

void write_report(const Region& text) {
    // These two signatures are independently useful compatibility probes because
    // an MIT-licensed current FF7R native mod uses them successfully on recent
    // Steam/Epic builds. They are probes only; Lexeditor does not patch them.
    constexpr std::array<std::uint8_t, 15> map_control_signature{
        0x56, 0x49, 0x8D, 0xAB, 0x78, 0xFD, 0xFF, 0xFF,
        0x48, 0x81, 0xEC, 0x70, 0x03, 0x00, 0x00,
    };
    constexpr std::array<std::uint8_t, 14> raw_input_signature{
        0x89, 0x5C, 0x24, 0x24, 0x48, 0x8D, 0x4C,
        0x24, 0x20, 0x48, 0x89, 0x44, 0x24, 0x28,
    };

    std::vector<ProbeResult> probes;
    probes.push_back({"knownMapControl", find_exact(text, map_control_signature)});
    probes.push_back({"knownRawInputRegistration", find_exact(text, raw_input_signature)});
    for (const std::string_view token : {
             "FastForward", "EventScene", "Navimap", "HideNavimap", "TimeDilation"}) {
        probes.push_back({std::string("ascii:") + std::string(token), find_ascii(text, token)});
    }

    const auto dll = module_path(g_module);
    const auto exe = process_path();
    const auto report = dll.parent_path() / L"LexeditorFF7RRuntimeProbe.json";

    std::ofstream output(report, std::ios::binary | std::ios::trunc);
    if (!output) {
        return;
    }

    output << "{\n"
           << "  \"schemaVersion\": 1,\n"
           << "  \"probeOnly\": true,\n"
           << "  \"process\": \"" << json_escape(narrow(exe.wstring())) << "\",\n"
           << "  \"processSize\": " << file_size_or_zero(exe) << ",\n"
           << "  \"textBase\": \"" << hex_address(reinterpret_cast<std::uintptr_t>(text.begin)) << "\",\n"
           << "  \"textSize\": " << text.size << ",\n"
           << "  \"probes\": [\n";

    for (std::size_t index = 0; index < probes.size(); ++index) {
        const auto& probe = probes[index];
        output << "    {\"name\": \"" << json_escape(probe.name) << "\", \"matches\": [";
        for (std::size_t match_index = 0; match_index < probe.matches.size(); ++match_index) {
            if (match_index != 0) {
                output << ", ";
            }
            output << "\"" << hex_address(probe.matches[match_index]) << "\"";
        }
        output << "]}";
        if (index + 1 != probes.size()) {
            output << ',';
        }
        output << '\n';
    }

    output << "  ]\n}\n";
}

void run_probe() {
    const auto text = main_text_region();
    if (!text.has_value()) {
        return;
    }
    write_report(*text);
}

} // namespace

extern "C" __declspec(dllexport) void __cdecl Init() {
    std::call_once(g_probe_once, run_probe);
}

BOOL APIENTRY DllMain(HMODULE module, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        g_module = module;
        DisableThreadLibraryCalls(module);
    }
    return TRUE;
}
