#pragma once
#include <algorithm>
#include <cmath>

namespace lexeditor_vehicle_drive {
inline bool supported_state(unsigned state) {
    return state == 0x30u || state == 0x32u || state == 0x84u ||
        (state >= 0x20u && state <= 0x28u);
}

// FF8's world rY is centered at 128. Native World_HandleInputs converts a high
// raw value into negative/full forward movement and a low raw value into
// positive/reverse movement. RT is forward, LT is reverse. L2/R2 logical keys
// are digital fallbacks, so keyboard users get the same controls.
inline int axis(float left_trigger, float right_trigger,
                bool left_digital = false, bool right_digital = false) {
    float left = std::clamp(left_trigger, 0.0f, 1.0f);
    float right = std::clamp(right_trigger, 0.0f, 1.0f);
    if (left_digital) left = 1.0f;
    if (right_digital) right = 1.0f;
    const float drive = right - left;
    if (std::abs(drive) < 0.02f) return 128;
    const float scale = drive > 0.0f ? 127.0f : 128.0f;
    return std::clamp(128 + static_cast<int>(std::lround(drive * scale)), 0, 255);
}
} // namespace lexeditor_vehicle_drive
