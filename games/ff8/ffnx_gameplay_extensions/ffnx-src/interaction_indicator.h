#pragma once

#include <cstddef>
#include <cstdint>

namespace lexeditor_interaction_indicator {

constexpr std::uint32_t kCardgameOpcode = 0x13A;
constexpr std::uint16_t kFacingLimit = 0x40;
constexpr std::size_t kMaximumTalkScriptInstructions = 4096;

inline std::uint32_t opcode(std::uint32_t instruction)
{
    return (instruction & 0xFF000000U) != 0
        ? instruction >> 24
        : instruction;
}

inline bool talk_script_has_cardgame(
    const std::uint32_t *instructions, std::size_t count)
{
    if (instructions == nullptr || count == 0 ||
        count > kMaximumTalkScriptInstructions) {
        return false;
    }
    for (std::size_t i = 0; i < count; ++i) {
        if (opcode(instructions[i]) == kCardgameOpcode) return true;
    }
    return false;
}

inline std::uint16_t facing_error(std::uint8_t facing, std::uint8_t direction)
{
    const std::uint8_t wrapped = static_cast<std::uint8_t>(facing - direction);
    return wrapped > 0x80
        ? static_cast<std::uint16_t>(0x100 - wrapped)
        : wrapped;
}

inline bool vertical_range(int player_z, int target_z)
{
    const int delta = player_z - target_z;
    return delta > -0x100 && delta < 0x100;
}

inline bool within_talk_radius(
    int distance, std::uint16_t player_radius, std::uint16_t target_radius)
{
    return distance < static_cast<int>(player_radius) +
        static_cast<int>(target_radius);
}

} // namespace lexeditor_interaction_indicator
