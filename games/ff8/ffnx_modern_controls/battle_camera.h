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

// How fast the stick turns the camera, as a multiple of the shipped rate. One
// is what the tweak has always done. The bounds are what stays usable: below a
// fifth of the rate the stick reads as unresponsive, above four times it
// overshoots the target before the reader lets go.
constexpr float MIN_SPEED_SCALE = 0.2f;
constexpr float MAX_SPEED_SCALE = 4.0f;
constexpr float DEFAULT_SPEED_SCALE = 1.0f;

inline float speed_scale(float value) {
    if (!(value > 0.0f)) return DEFAULT_SPEED_SCALE;
    return std::clamp(value, MIN_SPEED_SCALE, MAX_SPEED_SCALE);
}

// How far the camera may swing. FF8's battlefield is a plane with nothing under
// it, and the shipped clamp allowed seventy-seven degrees below level, so the
// scene ended up drawn from inside the terrain.
//
// Level is the fallback floor, not the rule. The rule is the scene's own: FF8
// hands the camera back at a pose it chose for this battle, and that pose is
// the lowest angle the game itself considers correct here. Some scenes sit
// slightly below level and clamping those to level would lift the camera off
// the pose the game just set. So the floor is whichever is lower, level or the
// pose FF8 last handed back, and it is re-learned every time the reader lets
// go of the stick.
constexpr float MIN_PITCH = 0.0f;
constexpr float MAX_PITCH = 1.35f;

// The floor this battle is using. The caller keeps one and passes it in; it
// costs a float and a flag and it is what makes the clamp per-scene rather
// than per-game.
struct Floor {
    float pitch = MIN_PITCH;
    bool known = false;
};

inline float pitch_of(const Vec3s &position, const Vec3s &look_at) {
    // FF8 battle coordinates have positive Y down. Elevation is the inverse.
    const float dy = static_cast<float>(look_at.y) - position.y;
    const float horizontal = std::hypot(static_cast<float>(position.x) - look_at.x,
                                        static_cast<float>(position.z) - look_at.z);
    return std::atan2(dy, horizontal);
}

// Orbit position around the handed-back idle look-at point. There is no
// persistent yaw/pitch state: every step starts from FF8's current idle pose,
// so a native action camera can take ownership and return without a stale snap.
inline bool orbit(Vec3s &position, const Vec3s &look_at, int raw_x, int raw_y,
                  float yaw_speed = 0.035f, float pitch_speed = 0.025f,
                  float scale = DEFAULT_SPEED_SCALE, Floor *floor = nullptr) {
    const float input_x = axis(raw_x);
    const float input_y = axis(raw_y);
    if (input_x == 0.0f && input_y == 0.0f) {
        // Nobody is holding the stick, so this pose is FF8's own. Learn the
        // scene's floor from it: whichever is lower, level or where the game
        // put the camera.
        if (floor) {
            const float resting = pitch_of(position, look_at);
            floor->pitch = std::min(MIN_PITCH, resting);
            floor->known = true;
        }
        return false;
    }

    const float dx = static_cast<float>(position.x) - look_at.x;
    const float dy = static_cast<float>(look_at.y) - position.y;
    const float dz = static_cast<float>(position.z) - look_at.z;
    const float horizontal = std::hypot(dx, dz);
    const float radius = std::hypot(horizontal, dy);
    if (radius < 1.0f) return false;

    const float rate = speed_scale(scale);
    float yaw = std::atan2(dx, dz) + input_x * yaw_speed * rate;
    // Pushing the stick up tilts the view up, so the camera drops: the
    // non-inverted convention. It used to raise the camera, which read inverted.
    float pitch = std::atan2(dy, horizontal) + input_y * pitch_speed * rate;
    // The scene's floor if one has been learned, level otherwise, and never
    // above where the camera already is - a pose that is somehow lower still
    // may be raised but is not yanked up on its own.
    const float current_pitch = std::atan2(dy, horizontal);
    const float scene_floor = (floor && floor->known) ? floor->pitch : MIN_PITCH;
    const float floor_pitch = std::min(scene_floor, current_pitch);
    pitch = std::clamp(pitch, floor_pitch, MAX_PITCH);

    const float projected = radius * std::cos(pitch);
    position.x = word(static_cast<float>(look_at.x) + projected * std::sin(yaw));
    position.y = word(static_cast<float>(look_at.y) - radius * std::sin(pitch));
    position.z = word(static_cast<float>(look_at.z) + projected * std::cos(yaw));
    return true;
}
} // namespace lexeditor_battle_camera
