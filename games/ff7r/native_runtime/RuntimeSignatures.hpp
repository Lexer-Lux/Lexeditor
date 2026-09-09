#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <span>
#include <string_view>
#include <vector>

namespace lexeditor::ff7r {

struct SignatureMatch {
    std::size_t offset = 0;
};

template <std::size_t N>
std::vector<SignatureMatch> findExactSignature(
    std::span<const std::uint8_t> bytes,
    const std::array<std::uint8_t, N>& signature,
    std::size_t maxMatches = 16) {
    std::vector<SignatureMatch> matches;
    if constexpr (N == 0) {
        return matches;
    }
    if (bytes.size() < N || maxMatches == 0) {
        return matches;
    }
    for (std::size_t offset = 0; offset <= bytes.size() - N; ++offset) {
        bool equal = true;
        for (std::size_t index = 0; index < N; ++index) {
            if (bytes[offset + index] != signature[index]) {
                equal = false;
                break;
            }
        }
        if (!equal) {
            continue;
        }
        matches.push_back({offset});
        if (matches.size() >= maxMatches) {
            break;
        }
    }
    return matches;
}

template <std::size_t N>
std::vector<SignatureMatch> findMaskedSignature(
    std::span<const std::uint8_t> bytes,
    const std::array<std::uint8_t, N>& signature,
    std::string_view mask,
    std::size_t maxMatches = 16) {
    std::vector<SignatureMatch> matches;
    if constexpr (N == 0) {
        return matches;
    }
    if (mask.size() != N || bytes.size() < N || maxMatches == 0) {
        return matches;
    }
    for (const char token : mask) {
        if (token != 'x' && token != '?') {
            return {};
        }
    }
    for (std::size_t offset = 0; offset <= bytes.size() - N; ++offset) {
        bool equal = true;
        for (std::size_t index = 0; index < N; ++index) {
            if (mask[index] == 'x' && bytes[offset + index] != signature[index]) {
                equal = false;
                break;
            }
        }
        if (!equal) {
            continue;
        }
        matches.push_back({offset});
        if (matches.size() >= maxMatches) {
            break;
        }
    }
    return matches;
}

struct KnownSignature {
    std::string_view name;
    std::span<const std::uint8_t> bytes;
    std::ptrdiff_t publicAddressAdjustment = 0;
    std::string_view provenance;
};

inline constexpr std::array<std::uint8_t, 15> kMapControlSignature{
    0x56,
    0x49, 0x8D, 0xAB, 0x78, 0xFD, 0xFF, 0xFF,
    0x48, 0x81, 0xEC, 0x70, 0x03, 0x00, 0x00,
};

inline constexpr std::array<std::uint8_t, 14> kRawInputRegistrationSignature{
    0x89, 0x5C, 0x24, 0x24,
    0x48, 0x8D, 0x4C, 0x24, 0x20,
    0x48, 0x89, 0x44, 0x24, 0x28,
};

inline constexpr std::array<std::uint8_t, 14> kJoystickMovementSignature{
    0xF3, 0x44, 0x0F, 0x10, 0x55, 0x40,
    0xF3, 0x0F, 0x10, 0x8B, 0x18, 0x07, 0x00, 0x00,
};

// `48 8B 05 disp32` loads the process-global AGameState* slot. The following
// instructions make the signature selective while stack-frame displacements
// remain wildcarded. The RIP-relative target is resolved only when this pattern
// has exactly one match in the installed executable.
inline constexpr std::array<std::uint8_t, 19> kGameStateLoadSignature{
    0x48, 0x8B, 0x05, 0x00, 0x00, 0x00, 0x00,
    0x4C, 0x89, 0xB4, 0x24, 0x00, 0x00, 0x00, 0x00,
    0x44, 0x0F, 0xB6, 0x76,
};
inline constexpr std::string_view kGameStateLoadMask = "xxx????xxxx????xxxx";

inline std::vector<SignatureMatch> findMapControl(std::span<const std::uint8_t> text) {
    return findExactSignature(text, kMapControlSignature);
}

inline std::vector<SignatureMatch> findRawInputRegistration(std::span<const std::uint8_t> text) {
    return findExactSignature(text, kRawInputRegistrationSignature);
}

inline std::vector<SignatureMatch> findJoystickMovement(std::span<const std::uint8_t> text) {
    return findExactSignature(text, kJoystickMovementSignature);
}

inline std::vector<SignatureMatch> findGameStateLoad(std::span<const std::uint8_t> text) {
    return findMaskedSignature(text, kGameStateLoadSignature, kGameStateLoadMask);
}

// Provenance notes are intentionally part of the source contract so these
// byte patterns are never mistaken for signatures reverse-engineered from the
// user's installed executable. The first three originate in TheUnlocked's MIT
// project; the game-state load shape is independently implemented from public
// xCENTx/FinalFantasy7Remake-Menu interoperability documentation.
inline constexpr std::string_view kSignatureProvenance =
    "TheUnlocked/ff7r-kbm-hook (MIT) and xCENTx/FinalFantasy7Remake-Menu public interoperability references; candidate signatures require installed-build validation";

} // namespace lexeditor::ff7r
