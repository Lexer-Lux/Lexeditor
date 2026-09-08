#include <Windows.h>

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <mutex>
#include <optional>
#include <sstream>
#include <string>
#include <string_view>
#include <vector>

namespace {

constexpr std::size_t kMaxMatches = 64;
HMODULE g_probeModule = nullptr;
std::once_flag g_probeOnce;

struct SectionView {
    std::string name;
    const std::byte* begin{};
    std::size_t size{};
    std::uint32_t rva{};
};

struct ImageView {
    const std::byte* base{};
    std::uint32_t timestamp{};
    std::vector<SectionView> sections;
};

struct StringHit {
    std::string encoding;
    std::uintptr_t address{};
    std::uint32_t rva{};
    std::vector<std::uint32_t> xrefRvas;
};

std::string sectionName(const IMAGE_SECTION_HEADER& section) {
    std::array<char, IMAGE_SIZEOF_SHORT_NAME + 1> buffer{};
    std::copy_n(reinterpret_cast<const char*>(section.Name), IMAGE_SIZEOF_SHORT_NAME, buffer.data());
    return std::string(buffer.data());
}

std::optional<ImageView> mainImage() {
    const auto* base = reinterpret_cast<const std::byte*>(GetModuleHandleW(nullptr));
    if (base == nullptr) {
        return std::nullopt;
    }
    const auto* dos = reinterpret_cast<const IMAGE_DOS_HEADER*>(base);
    if (dos->e_magic != IMAGE_DOS_SIGNATURE || dos->e_lfanew <= 0) {
        return std::nullopt;
    }
    const auto* nt = reinterpret_cast<const IMAGE_NT_HEADERS64*>(base + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE || nt->OptionalHeader.Magic != IMAGE_NT_OPTIONAL_HDR64_MAGIC) {
        return std::nullopt;
    }

    ImageView image;
    image.base = base;
    image.timestamp = nt->FileHeader.TimeDateStamp;
    const auto* section = IMAGE_FIRST_SECTION(nt);
    for (WORD index = 0; index < nt->FileHeader.NumberOfSections; ++index, ++section) {
        image.sections.push_back(SectionView{
            sectionName(*section),
            base + section->VirtualAddress,
            static_cast<std::size_t>(section->Misc.VirtualSize),
            section->VirtualAddress,
        });
    }
    return image;
}

const SectionView* findSection(const ImageView& image, std::string_view name) {
    const auto found = std::find_if(image.sections.begin(), image.sections.end(),
        [name](const SectionView& section) { return section.name == name; });
    return found == image.sections.end() ? nullptr : &*found;
}

template <typename Needle>
std::vector<std::uintptr_t> findBytes(const SectionView& section, const Needle& needle) {
    std::vector<std::uintptr_t> matches;
    const auto needleSize = static_cast<std::size_t>(needle.size());
    if (needleSize == 0 || section.size < needleSize) {
        return matches;
    }
    const auto* bytes = reinterpret_cast<const std::uint8_t*>(section.begin);
    for (std::size_t offset = 0; offset <= section.size - needleSize && matches.size() < kMaxMatches; ++offset) {
        if (std::equal(needle.begin(), needle.end(), bytes + offset)) {
            matches.push_back(reinterpret_cast<std::uintptr_t>(section.begin + offset));
        }
    }
    return matches;
}

std::vector<std::uint8_t> utf16le(std::string_view value) {
    std::vector<std::uint8_t> bytes;
    bytes.reserve(value.size() * 2);
    for (const unsigned char ch : value) {
        bytes.push_back(ch);
        bytes.push_back(0);
    }
    return bytes;
}

std::vector<std::uint32_t> ripLeaXrefs(const ImageView& image, std::uintptr_t target) {
    std::vector<std::uint32_t> results;
    const auto* text = findSection(image, ".text");
    if (text == nullptr || text->size < 7) {
        return results;
    }
    const auto* raw = reinterpret_cast<const std::uint8_t*>(text->begin);
    for (std::size_t offset = 0; offset <= text->size - 7 && results.size() < kMaxMatches; ++offset) {
        const std::uint8_t rex = raw[offset];
        if (rex < 0x48 || rex > 0x4F || raw[offset + 1] != 0x8D) {
            continue;
        }
        const std::uint8_t modrm = raw[offset + 2];
        if ((modrm & 0xC7U) != 0x05U) {
            continue;
        }
        std::int32_t displacement = 0;
        std::memcpy(&displacement, raw + offset + 3, sizeof(displacement));
        const auto instruction = reinterpret_cast<std::uintptr_t>(text->begin + offset);
        const auto resolved = static_cast<std::uintptr_t>(
            static_cast<std::intptr_t>(instruction + 7) + displacement);
        if (resolved == target) {
            results.push_back(text->rva + static_cast<std::uint32_t>(offset));
        }
    }
    return results;
}

std::vector<StringHit> stringHits(const ImageView& image, std::string_view needle) {
    std::vector<StringHit> hits;
    std::vector<std::uint8_t> ascii(needle.begin(), needle.end());
    const auto wide = utf16le(needle);
    for (const auto& section : image.sections) {
        if (section.name == ".text" || section.size == 0) {
            continue;
        }
        for (const auto& [encoding, bytes] : std::array{
                 std::pair<std::string_view, const std::vector<std::uint8_t>&>{"ascii", ascii},
                 std::pair<std::string_view, const std::vector<std::uint8_t>&>{"utf16le", wide}}) {
            for (const auto address : findBytes(section, bytes)) {
                const auto delta = address - reinterpret_cast<std::uintptr_t>(section.begin);
                hits.push_back(StringHit{
                    std::string(encoding),
                    address,
                    section.rva + static_cast<std::uint32_t>(delta),
                    ripLeaXrefs(image, address),
                });
                if (hits.size() >= kMaxMatches) {
                    return hits;
                }
            }
        }
    }
    return hits;
}

std::string hex(std::uintptr_t value) {
    std::ostringstream stream;
    stream << "0x" << std::hex << std::uppercase << value;
    return stream.str();
}

std::filesystem::path modulePath(HMODULE module) {
    std::wstring buffer(32768, L'\0');
    const DWORD length = GetModuleFileNameW(module, buffer.data(), static_cast<DWORD>(buffer.size()));
    if (length == 0 || length >= buffer.size()) {
        return {};
    }
    buffer.resize(length);
    return std::filesystem::path(buffer);
}

void writeAddressArray(std::ostream& output, const std::vector<std::uintptr_t>& values,
                       std::uintptr_t imageBase) {
    output << '[';
    for (std::size_t index = 0; index < values.size(); ++index) {
        if (index != 0) {
            output << ',';
        }
        output << "{\"va\":\"" << hex(values[index]) << "\",\"rva\":\""
               << hex(values[index] - imageBase) << "\"}";
    }
    output << ']';
}

void runProbe() {
    const auto image = mainImage();
    if (!image.has_value()) {
        return;
    }
    const auto* text = findSection(*image, ".text");
    if (text == nullptr) {
        return;
    }

    constexpr std::array<std::uint8_t, 15> mapSignature{
        0x56, 0x49, 0x8D, 0xAB, 0x78, 0xFD, 0xFF, 0xFF,
        0x48, 0x81, 0xEC, 0x70, 0x03, 0x00, 0x00,
    };
    constexpr std::array<std::uint8_t, 14> inputSignature{
        0x89, 0x5C, 0x24, 0x24, 0x48, 0x8D, 0x4C,
        0x24, 0x20, 0x48, 0x89, 0x44, 0x24, 0x28,
    };

    const auto mapMatches = findBytes(*text, mapSignature);
    const auto inputMatches = findBytes(*text, inputSignature);
    const auto imageBase = reinterpret_cast<std::uintptr_t>(image->base);
    const auto report = modulePath(g_probeModule).parent_path() / L"LexeditorFF7RRuntimeProbe.json";
    std::ofstream output(report, std::ios::binary | std::ios::trunc);
    if (!output) {
        return;
    }

    output << "{\n  \"schemaVersion\":1,\n  \"probeOnly\":true,\n"
           << "  \"imageBase\":\"" << hex(imageBase) << "\",\n"
           << "  \"peTimestamp\":\"" << hex(image->timestamp) << "\",\n"
           << "  \"knownMapControl\":";
    writeAddressArray(output, mapMatches, imageBase);
    output << ",\n  \"knownRawInputRegistration\":";
    writeAddressArray(output, inputMatches, imageBase);
    output << ",\n  \"strings\":[\n";

    constexpr std::array<std::string_view, 8> needles{
        "FastForward", "EventScene", "CutScene", "NaviMap", "Navimap",
        "HideNavimap", "trgCmn_NaviMap_Update_On", "trgCmn_NaviMap_Update_Off",
    };
    for (std::size_t needleIndex = 0; needleIndex < needles.size(); ++needleIndex) {
        const auto hits = stringHits(*image, needles[needleIndex]);
        output << "    {\"needle\":\"" << needles[needleIndex] << "\",\"hits\":[";
        for (std::size_t hitIndex = 0; hitIndex < hits.size(); ++hitIndex) {
            if (hitIndex != 0) {
                output << ',';
            }
            const auto& hit = hits[hitIndex];
            output << "{\"encoding\":\"" << hit.encoding << "\",\"va\":\""
                   << hex(hit.address) << "\",\"rva\":\"" << hex(hit.rva)
                   << "\",\"leaRipXrefRvas\":[";
            for (std::size_t xrefIndex = 0; xrefIndex < hit.xrefRvas.size(); ++xrefIndex) {
                if (xrefIndex != 0) {
                    output << ',';
                }
                output << "\"" << hex(hit.xrefRvas[xrefIndex]) << "\"";
            }
            output << "]}";
        }
        output << "]}" << (needleIndex + 1 == needles.size() ? "\n" : ",\n");
    }
    output << "  ]\n}\n";
}

}  // namespace

extern "C" __declspec(dllexport) void __cdecl Init() {
    std::call_once(g_probeOnce, runProbe);
}

BOOL APIENTRY DllMain(HMODULE module, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        g_probeModule = module;
        DisableThreadLibraryCalls(module);
    }
    return TRUE;
}
