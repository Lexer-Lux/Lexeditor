#include "lexeditor_ff8_modern_controls.h"
#include "camera_axis.h"
#include <cstring>
#include "cfg.h"
#include "common.h"
#include "ff8.h"
#include "globals.h"
#include "log.h"
#include "patch.h"

extern int right_stick_x;
extern int ff8_get_analog_value(std::int8_t, int, std::int8_t);

namespace {
using CameraUpdate = std::uint32_t(__cdecl *)(void *, void *, void *, void *);
CameraUpdate original_update = nullptr;
bool installed = false;
lexeditor_camera::ManualYaw manual;
std::uint32_t last_frame = ~0u;
int last_axis = -1;
std::uint32_t last_log = 0;
std::uint32_t last_state[3] = {~0u, ~0u, ~0u};

std::uint32_t update(unsigned site, void *movement, void *input, void *player, void *camera) {
    const bool active = lexeditor_ff8_modern_controls_world_active() &&
        camera == reinterpret_cast<void *>(0x0203ECF8) && input == reinterpret_cast<void *>(0x0203ED50);
    auto *yaw = reinterpret_cast<std::uint16_t *>(static_cast<std::uint8_t *>(camera) + 10);
    const auto before = active ? *yaw : 0;
    const auto result = original_update(movement, input, player, camera);
    if (!active) { manual.reset(); last_frame = ~0u; return result; }
    const auto native_after = *yaw;
    const std::uint32_t state[] = {
        *reinterpret_cast<const std::uint32_t *>(0x020409E0),
        *reinterpret_cast<const std::uint32_t *>(0x020409E4),
        *reinterpret_cast<const std::uint8_t *>(0x02036B70)};
    const bool reset_state = last_frame == ~0u ||
        std::memcmp(state, last_state, sizeof state) != 0;
    const bool shoulder = *(static_cast<const std::int8_t *>(input) + 14) != 0;
    if (last_frame != frame_counter) {
        *yaw = static_cast<std::uint16_t>(manual.update(before, native_after,
            right_stick_x, shoulder, reset_state));
        last_frame = frame_counter;
        std::memcpy(last_state, state, sizeof state);
    } else if (reset_state) {
        manual.reset();
        std::memcpy(last_state, state, sizeof state);
    } else if (manual.engaged && !shoulder) {
        // Two calls in one rendered frame may still run native auto-follow.
        // Preserve the chosen yaw, but do not apply a second analog step.
        *yaw = before;
    }
    if (last_axis != right_stick_x || (manual.engaged && frame_counter - last_log >= 30)) {
        ffnx_info("Lexeditor camera: frame=%u site=%u state=%u axis=%d yaw=%u native=%u final=%u manual=%u zoom=%u\n",
            frame_counter, site, state[0], right_stick_x, before, native_after, *yaw,
            manual.engaged, *reinterpret_cast<const std::uint16_t *>(0x01CA92E4));
        last_axis = right_stick_x;
        last_log = frame_counter;
    }
    return result;
}
std::uint32_t __cdecl update_fog(void *a, void *b, void *c, void *d) { return update(0, a, b, c, d); }
std::uint32_t __cdecl update_clear(void *a, void *b, void *c, void *d) { return update(1, a, b, c, d); }
}

bool lexeditor_ff8_modern_controls_world_active() {
    const auto *mode = getmode_cached();
    const bool active = installed && enable_ff8_modern_controls && mode && mode->driver_mode == MODE_WORLDMAP;
    if (!active) { manual.reset(); last_frame = ~0u; }
    return active;
}

int lexeditor_ff8_modern_world_axis(std::int8_t port, int type, std::int8_t offset) {
    // The native right-stick fields mean movement/zoom in some camera modes.
    // The original callbacks stay unchanged outside the world-map call sites.
    if (lexeditor_ff8_modern_controls_world_active() && (type == 0 || type == 1)) return 128;
    return ff8_get_analog_value(port, type, offset);
}

void lexeditor_ff8_modern_controls_install() {
    if (!ff8 || !enable_ff8_modern_controls || installed) return;
    const unsigned char first[] = {0xE8, 0xD7, 0x7E, 0x01, 0x00};
    const unsigned char second[] = {0xE8, 0x6F, 0x6A, 0x01, 0x00};
    if (std::memcmp(reinterpret_cast<void *>(0x0053FBB4), first, sizeof first) ||
        std::memcmp(reinterpret_cast<void *>(0x0054101C), second, sizeof second)) {
        ffnx_warning("Lexeditor Modern Controls: unsupported camera call sites; no camera changes installed.\n");
        return;
    }
    original_update = reinterpret_cast<CameraUpdate>(0x00557A90);
    replace_call(0x0053FBB4, reinterpret_cast<void *>(&update_fog));
    replace_call(0x0054101C, reinterpret_cast<void *>(&update_clear));
    installed = true;
    ffnx_info("Lexeditor Modern Controls: complete world camera update installed; native right-stick aliases suppressed.\n");
}
