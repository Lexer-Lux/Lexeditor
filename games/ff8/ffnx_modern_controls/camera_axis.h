#pragma once
#include <algorithm>

namespace lexeditor_camera {
// FFNx's unsigned axis is centered at 128. A horizontal dead zone also
// prevents a vertical stick deflection from turning small horizontal noise
// into camera drift. Carry fractional steps instead of rounding small input
// into an on/off control.
inline int yaw_step(int raw, int &remainder) {
    const int axis = std::clamp(raw - 128, -127, 127);
    const int magnitude = axis < 0 ? -axis : axis;
    if (magnitude <= 40) { remainder = 0; return 0; }
    const int signed_speed = (axis < 0 ? -1 : 1) * (magnitude - 40) * 16;
    if ((signed_speed < 0 && remainder > 0) || (signed_speed > 0 && remainder < 0)) remainder = 0;
    const int total = signed_speed + remainder;
    const int step = total / 87;
    remainder = total % 87;
    return step;
}
inline unsigned wrap_yaw(int yaw) { return static_cast<unsigned>(yaw) & 0xFFFu; }

struct ManualYaw {
    bool engaged = false;
    int remainder = 0;
    void reset() { engaged = false; remainder = 0; }
    unsigned update(unsigned before, unsigned native_after, int raw, bool shoulder, bool reset_state) {
        if (reset_state) reset();
        const int axis = std::clamp(raw - 128, -127, 127);
        if (axis < -40 || axis > 40) engaged = true;
        const auto base = engaged && !shoulder && !reset_state ? before : native_after;
        return wrap_yaw(static_cast<int>(base) + yaw_step(raw, remainder));
    }
};
}
