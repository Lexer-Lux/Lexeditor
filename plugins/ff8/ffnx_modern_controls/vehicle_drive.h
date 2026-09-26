#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>

namespace lexeditor_vehicle_drive {
// FF8's remapped 16-bit pad mask (PSX layout as used by World_HandleInputs).
constexpr std::uint32_t kL2 = 0x0001u;
constexpr std::uint32_t kR2 = 0x0002u;
constexpr std::uint32_t kTriangle = 0x0010u;
constexpr std::uint32_t kSquare = 0x0080u;

inline bool supported_state(unsigned state) {
    return state == 0x30u || state == 0x32u || state == 0x84u ||
        (state >= 0x20u && state <= 0x28u);
}

// FF8's world rY is centered at 128. A LOW raw value drives forward and a high
// one reverses: the first build assumed the opposite and Lexer found RT
// reversing ("the triggers for forward/reverse are well, reversed"). RT is
// forward, LT is reverse. L2/R2 logical keys are digital fallbacks, so
// keyboard users get the same controls.
inline float pressure(float left_trigger, float right_trigger,
                      bool left_digital = false, bool right_digital = false) {
    float left = std::isfinite(left_trigger) ? std::clamp(left_trigger, 0.0f, 1.0f) : 0.0f;
    float right = std::isfinite(right_trigger) ? std::clamp(right_trigger, 0.0f, 1.0f) : 0.0f;
    // A physical trigger can also set its logical L2/R2 bit. Do not let that
    // alias turn a partial trigger pull into full throttle. Digital-only
    // keyboard input still supplies the complete axis range.
    if (left_digital && left == 0.0f) left = 1.0f;
    if (right_digital && right == 0.0f) right = 1.0f;
    const float drive = right - left;
    return std::abs(drive) < 0.02f ? 0.0f : drive;
}

inline int speed_limit(int native_limit, float drive) {
    if (native_limit <= 0 || !std::isfinite(drive)) return native_limit;
    return std::clamp(static_cast<int>(std::lround(native_limit * std::abs(drive))),
                      0, native_limit);
}

inline int axis(float left_trigger, float right_trigger,
                bool left_digital = false, bool right_digital = false) {
    const float drive = pressure(left_trigger, right_trigger, left_digital, right_digital);
    if (!drive) return 128;
    // Native input ignores magnitudes <=45; car acceleration then divides by
    // 48. Cross both thresholds even for a light pull. The separate speed cap
    // uses the original pressure, so this does not turn it into full throttle.
    const float maximum = drive > 0.0f ? 127.0f : 128.0f;
    const int magnitude = 49 + static_cast<int>(std::lround(std::abs(drive) * (maximum - 49)));
    return 127 + (drive > 0.0f ? -magnitude : magnitude);
}
} // namespace lexeditor_vehicle_drive
