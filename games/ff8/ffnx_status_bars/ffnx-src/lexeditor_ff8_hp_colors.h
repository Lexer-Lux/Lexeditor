#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>

struct LexeditorFf8HpRgb { std::uint8_t r; std::uint8_t g; std::uint8_t b; };

inline std::uint8_t lexeditor_ff8_hp_lerp(std::uint8_t a, std::uint8_t b, double t)
{
    t = std::clamp(t, 0.0, 1.0);
    return static_cast<std::uint8_t>(std::lround(
        static_cast<double>(a) + (static_cast<double>(b) - a) * t));
}

inline LexeditorFf8HpRgb lexeditor_ff8_hp_rgb(std::uint32_t current, std::uint32_t maximum)
{
    if (maximum == 0) return {255, 255, 255};
    const double ratio = std::min(1.0, static_cast<double>(current) / maximum);
    if (ratio >= 0.5)
        return {255, 255, lexeditor_ff8_hp_lerp(0, 255, (ratio - 0.5) / 0.5)};
    if (ratio >= 0.25)
        return {255, lexeditor_ff8_hp_lerp(128, 255, (ratio - 0.25) / 0.25), 0};
    return {255, lexeditor_ff8_hp_lerp(0, 128, ratio / 0.25), 0};
}

inline bool lexeditor_ff8_hp_should_tint(std::uint32_t current, std::uint32_t maximum)
{
    return maximum != 0 && current != 0 && current < maximum;
}
