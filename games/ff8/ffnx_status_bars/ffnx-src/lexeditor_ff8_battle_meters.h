#pragma once

#include <algorithm>
#include <array>
#include <cstdint>

// Pure meter policy shared by the renderer and the offline regression tests.
namespace lexeditor_ff8_meters {
struct Hp {
    std::uint32_t current = 0;
    std::uint32_t maximum = 0;
};
struct GuardianForce {
    Hp hp{};
    bool exists = false;
};
struct Summon {
    Hp hp{};
    int id = -1;
};

inline Hp junctioned_gf_hp(std::uint16_t junctions,
    const std::array<GuardianForce, 16> &gfs, const Summon &summon)
{
    Hp total;
    for (unsigned id = 0; id < gfs.size(); ++id) {
        if (!(junctions & (1U << id)) || !gfs[id].exists) continue;
        const Hp hp = summon.id == static_cast<int>(id) ? summon.hp : gfs[id].hp;
        if (hp.maximum == 0) continue;
        total.current += std::min(hp.current, hp.maximum);
        total.maximum += hp.maximum;
    }
    return total;
}

struct Line {
    float left = 0, right = 0, top = 0;
    float fill_left = 0, fill_right = 0;
    bool visible = false;
};

inline Line line(float left, float right, float top, Hp hp, bool left_to_right)
{
    Line result;
    if (hp.maximum == 0 || !(right > left)) return result;
    const float width = (right - left) * std::min(1.0f, hp.maximum / 9999.0f);
    result.left = left_to_right ? left : right - width;
    result.right = result.left + width;
    result.top = top;
    const float filled = width * std::min(1.0f, hp.current / static_cast<float>(hp.maximum));
    result.fill_left = left_to_right ? result.left : result.right - filled;
    result.fill_right = left_to_right ? result.left + filled : result.right;
    result.visible = true;
    return result;
}

// Native 004B0F80 defines a fifteen-pixel row. Keep the underline inside
// that row, rather than below the glyph's padded bounding rectangle.
inline float hp_top(float row_top, float glyph_bottom)
{
    return std::min(glyph_bottom, row_top + 13.0f);
}
// Native names start at row_top + 2, leaving one pixel of separation.
inline float gf_top(float row_top) { return row_top; }
} // namespace lexeditor_ff8_meters
