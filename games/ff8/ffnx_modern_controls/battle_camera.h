#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>

namespace lexeditor_battle_camera {
struct Vec3s {
    std::int16_t x;
    std::int16_t y;
    std::int16_t z;
};

inline float axis(int raw, int deadzone = 40) {
    const int value = std::clamp(raw - 128, -127, 127);
    const int magnitude = value < 0 ? -value : value;
    if (magnitude <= deadzone) return 0.0f;
    const float scaled = static_cast<float>(magnitude - deadzone) /
        static_cast<float>(127 - deadzone);
    return value < 0 ? -scaled : scaled;
}

// Mirrors updateBattleCamera's stable-idle condition after the native update:
// no camera bytecode sequence, no meaningful camera action flags, and no
// handoff blend in progress. 0x2000 is intentionally ignored because native
// FF8 masks it out in the same idle test.
inline bool safe_idle(std::uintptr_t sequence, std::uint16_t flags, std::int16_t blend) {
    return sequence == 0 && (flags & 0xDFFFu) == 0 && blend == 0;
}

inline std::int16_t word(float value) {
    const long rounded = std::lround(value);
    return static_cast<std::int16_t>(std::clamp<long>(rounded, -32768, 32767));
}

// Orbit position around the handed-back idle look-at point. There is no
// persistent yaw/pitch state: every step starts from FF8's current idle pose,
// so a native action camera can take ownership and return without a stale snap.
inline bool orbit(Vec3s &position, const Vec3s &look_at, int raw_x, int raw_y,
                  float yaw_speed = 0.035f, float pitch_speed = 0.025f) {
    const float input_x = axis(raw_x);
    const float input_y = axis(raw_y);
    if (input_x == 0.0f && input_y == 0.0f) return false;

    const float dx = static_cast<float>(position.x) - look_at.x;
    const float dy = static_cast<float>(position.y) - look_at.y;
    const float dz = static_cast<float>(position.z) - look_at.z;
    const float horizontal = std::hypot(dx, dz);
    const float radius = std::hypot(horizontal, dy);
    if (radius < 1.0f) return false;

    float yaw = std::atan2(dx, dz) + input_x * yaw_speed;
    float pitch = std::atan2(dy, horizontal) - input_y * pitch_speed;
    pitch = std::clamp(pitch, -1.35f, 1.35f);

    const float projected = radius * std::cos(pitch);
    position.x = word(static_cast<float>(look_at.x) + projected * std::sin(yaw));
    position.y = word(static_cast<float>(look_at.y) + radius * std::sin(pitch));
    position.z = word(static_cast<float>(look_at.z) + projected * std::cos(yaw));
    return true;
}
} // namespace lexeditor_battle_camera
