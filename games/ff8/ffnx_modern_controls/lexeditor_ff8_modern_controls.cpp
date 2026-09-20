#include "lexeditor_ff8_modern_controls.h"
#include "camera_axis.h"
#include "battle_camera.h"
#include "vehicle_drive.h"
#include <cstring>
#include "cfg.h"
#include "common.h"
#include "ff8.h"
#include "gamepad.h"
#include "globals.h"
#include "log.h"
#include "patch.h"
#include "sdl_gamepad.h"

extern int right_stick_x;
extern int right_stick_y;
extern HWND gameHwnd;
extern int ff8_get_analog_value(std::int8_t, int, std::int8_t);

namespace {
using CameraUpdate = std::uint32_t(__cdecl *)(void *, void *, void *, void *);
using BattleCameraUpdate = void(__cdecl *)();
CameraUpdate original_update = nullptr;
BattleCameraUpdate original_battle_update = nullptr;
bool world_installed = false;
bool battle_installed = false;
lexeditor_camera::ManualYaw manual;
lexeditor_camera::ManualPitch manual_pitch;
std::uint32_t last_frame = ~0u;
int last_axis = -1;
std::uint32_t last_log = 0;
std::uint32_t last_state[3] = {~0u, ~0u, ~0u};
std::uint32_t last_world_input_frame = ~0u;
bool world_square_down = false;
bool world_square_pressed = false;

constexpr std::uintptr_t kWorldInputStates = 0x0203FDE8;
constexpr std::uintptr_t kWorldInputParity = 0x020409BC;
constexpr std::uintptr_t kWorldVehicle = 0x020409E0;
constexpr std::uint32_t kL2 = 0x0001u;
constexpr std::uint32_t kR2 = 0x0002u;
constexpr std::uint32_t kTriangle = 0x0010u;
constexpr std::uint32_t kSquare = 0x0080u;

constexpr std::uintptr_t kBattleCameraCall = 0x00500988;
constexpr std::uintptr_t kBattleCameraUpdate = 0x00504060;
constexpr std::uintptr_t kBattleCameraSequence = 0x01D99A34;
constexpr std::uintptr_t kBattleCameraFlags = 0x01D97718;
constexpr std::uintptr_t kBattleCameraBlend = 0x01D9771E;
constexpr std::uintptr_t kBattleLivePosition = 0x00B8B7F0;
constexpr std::uintptr_t kBattleIdlePosition = 0x00B8B800;
constexpr std::uintptr_t kBattleIdleLookAt = 0x00B8B808;

// Battle bindings (FF8_EN.exe 064d466b...). The per-frame battle input at
// 004A84E0 reads the keyscan three times - held into +0x10, newly pressed
// into +0x12, repeating into +0x14 of the battle input block - each through
// the button-layout translator 004A2D60. What comes out is FF8's own function
// bits after the player's button layout: L2 0x01, R2 0x02, R1 0x08. The
// battle loop at 004A85CC counts a flee while L2 and R2 are both held; R1 is
// the gunblade trigger and Shot's fire button.
constexpr std::uintptr_t kBattleHeldCall = 0x004A8505;
constexpr std::uintptr_t kBattlePressedCall = 0x004A8521;
constexpr std::uintptr_t kBattleRepeatCall = 0x004A853D;
constexpr std::uintptr_t kBattleKeyTranslate = 0x004A2D60;
constexpr int kL2Function = 0x01, kR2Function = 0x02, kR1Function = 0x08;
// Shot registers its widget in slot 6 of the table at 01D76628 (20-byte
// entries, update callback first) and clears it on close (004ADBAC). Its
// update ends Shot through its own path when the request byte is set
// (004AD92B: state 8, countdown 0xFFFF, request cleared).
constexpr std::uintptr_t kShotWidgetUpdate = 0x01D766A0;
constexpr std::uintptr_t kShotUpdate = 0x004AD8D0;
constexpr std::uintptr_t kShotEndRequest = 0x01D7675B;

using KeyTranslate = int(__cdecl *)(int);
KeyTranslate original_translate = nullptr;
bool bindings_installed = false;

struct BattleButtons { bool fire = false, flee = false, back = false; };
BattleButtons buttons_now, buttons_before;
std::uint32_t buttons_frame = ~0u;

void read_battle_buttons() {
    if (buttons_frame == frame_counter) return;
    buttons_frame = frame_counter;
    buttons_before = buttons_now;
    // The mouse and keyboard only count while FF8 is the window in front.
    const bool focused = GetForegroundWindow() == gameHwnd;
    const auto down = [&](int key) { return focused && (GetAsyncKeyState(key) & 0x8000) != 0; };
    const float left = use_sdl_gamepad ? sdlgamepad.leftTrigger : gamepad.leftTrigger;
    const float right = use_sdl_gamepad ? sdlgamepad.rightTrigger : gamepad.rightTrigger;
    const bool b = use_sdl_gamepad ? sdlgamepad.IsPressed(SDL_GAMEPAD_BUTTON_EAST)
                                   : gamepad.IsPressed(XINPUT_GAMEPAD_B);
    buttons_now.fire = right > 0.5f || down(VK_LBUTTON);
    buttons_now.flee = left > 0.5f || down(VK_RBUTTON);
    buttons_now.back = b || down(VK_BACK);
}

// channel: 0 held, 1 newly pressed, 2 repeating.
int translate_battle_keys(int keyscan, int channel) {
    int bits = original_translate(keyscan);
    if (!lexeditor_ff8_modern_controls_battle_active()) return bits;
    read_battle_buttons();
    const bool fire_edge = buttons_now.fire && !buttons_before.fire;
    // The right trigger is also FF8's R2. Alone, that is half a flee and
    // nothing else, so it is withheld while the trigger means "fire".
    if (buttons_now.fire && !buttons_now.flee) bits &= ~kR2Function;
    if (channel == 0 ? buttons_now.fire : fire_edge) bits |= kR1Function;
    if (channel == 0 && buttons_now.flee) bits |= kL2Function | kR2Function;
    if (channel == 1 && buttons_now.back && !buttons_before.back &&
        *reinterpret_cast<const std::uintptr_t *>(kShotWidgetUpdate) == kShotUpdate) {
        *reinterpret_cast<std::uint8_t *>(kShotEndRequest) = 1;
    }
    return bits & 0xFFFF;
}
int __cdecl translate_held(int keyscan) { return translate_battle_keys(keyscan, 0); }
int __cdecl translate_pressed(int keyscan) { return translate_battle_keys(keyscan, 1); }
int __cdecl translate_repeat(int keyscan) { return translate_battle_keys(keyscan, 2); }

lexeditor_battle_camera::Vec3s read_vec(std::uintptr_t address) {
    lexeditor_battle_camera::Vec3s value{};
    std::memcpy(&value, reinterpret_cast<const void *>(address), sizeof value);
    return value;
}

void write_vec(std::uintptr_t address, const lexeditor_battle_camera::Vec3s &value) {
    std::memcpy(reinterpret_cast<void *>(address), &value, sizeof value);
}

void reset_world_input_state() {
    last_world_input_frame = ~0u;
    world_square_down = false;
    world_square_pressed = false;
}

std::uint32_t capture_world_input(bool suppress_legacy_drive) {
    const int parity = *reinterpret_cast<const std::int16_t *>(kWorldInputParity);
    if (parity < 0 || parity > 1) return 0;
    auto *states = reinterpret_cast<std::uint32_t *>(kWorldInputStates);
    const std::uint32_t keys = states[parity];
    if (last_world_input_frame != frame_counter) {
        const bool square = (keys & kSquare) != 0;
        world_square_pressed = square && !world_square_down;
        world_square_down = square;
        last_world_input_frame = frame_counter;
    }
    if (suppress_legacy_drive)
        states[parity] &= ~(kTriangle | kSquare);
    return keys;
}

int vehicle_drive_axis(std::uint32_t keys) {
    const float left = use_sdl_gamepad ? sdlgamepad.leftTrigger : gamepad.leftTrigger;
    const float right = use_sdl_gamepad ? sdlgamepad.rightTrigger : gamepad.rightTrigger;
    return lexeditor_vehicle_drive::axis(left, right, (keys & kL2) != 0, (keys & kR2) != 0);
}

std::uint32_t update(unsigned site, void *movement, void *input, void *player, void *camera) {
    const bool active = lexeditor_ff8_modern_controls_world_active() &&
        camera == reinterpret_cast<void *>(0x0203ECF8) && input == reinterpret_cast<void *>(0x0203ED50);
    auto *pitch = reinterpret_cast<std::int16_t *>(static_cast<std::uint8_t *>(camera) + 8);
    auto *yaw = reinterpret_cast<std::uint16_t *>(static_cast<std::uint8_t *>(camera) + 10);
    const auto pitch_before = active ? *pitch : 0;
    const auto before = active ? *yaw : 0;
    auto *legacy_turn = static_cast<std::int8_t *>(input) + 14;
    const auto saved_turn = active ? *legacy_turn : 0;
    // Native world input +14 contains only the L1/R1 camera turn amount.
    if (active) *legacy_turn = 0;
    const auto result = original_update(movement, input, player, camera);
    if (active) *legacy_turn = saved_turn;
    if (!active) { manual.reset(); manual_pitch.reset(); last_frame = ~0u; return result; }
    const auto pitch_native_after = *pitch;
    const auto native_after = *yaw;
    const std::uint32_t state[] = {
        *reinterpret_cast<const std::uint32_t *>(0x020409E0),
        *reinterpret_cast<const std::uint32_t *>(0x020409E4),
        *reinterpret_cast<const std::uint8_t *>(0x02036B70)};
    const bool reset_state = last_frame == ~0u ||
        std::memcmp(state, last_state, sizeof state) != 0;
    const bool shoulder = false;
    if (last_frame != frame_counter) {
        *yaw = static_cast<std::uint16_t>(manual.update(before, native_after,
            right_stick_x, shoulder, reset_state));
        *pitch = static_cast<std::int16_t>(manual_pitch.update(pitch_before, pitch_native_after,
            right_stick_y, shoulder, reset_state));
        last_frame = frame_counter;
        std::memcpy(last_state, state, sizeof state);
    } else if (reset_state) {
        manual.reset();
        manual_pitch.reset();
        std::memcpy(last_state, state, sizeof state);
    } else if ((manual.engaged || manual_pitch.engaged) && !shoulder) {
        // Two calls in one rendered frame may still run native auto-follow.
        // Preserve the chosen camera angles, but do not apply a second analog step.
        if (manual.engaged) *yaw = before;
        if (manual_pitch.engaged) *pitch = pitch_before;
    }
    const int packed_axis = (right_stick_x & 0xFF) | ((right_stick_y & 0xFF) << 8);
    if (last_axis != packed_axis || ((manual.engaged || manual_pitch.engaged) && frame_counter - last_log >= 30)) {
        ffnx_info("Lexeditor camera: frame=%u site=%u state=%u axis=(%d,%d) pitch=%d/%d/%d yaw=%u/%u/%u manual=(%u,%u) zoom=%u\n",
            frame_counter, site, state[0], right_stick_x, right_stick_y, pitch_before,
            pitch_native_after, *pitch, before, native_after, *yaw, manual.engaged,
            manual_pitch.engaged, *reinterpret_cast<const std::uint16_t *>(0x01CA92E4));
        last_axis = packed_axis;
        last_log = frame_counter;
    }
    return result;
}
std::uint32_t __cdecl update_fog(void *a, void *b, void *c, void *d) { return update(0, a, b, c, d); }
std::uint32_t __cdecl update_clear(void *a, void *b, void *c, void *d) { return update(1, a, b, c, d); }

std::uint32_t __cdecl world_actions() {
    const auto original = reinterpret_cast<std::uint32_t(__cdecl *)()>(0x0054A7F0);
    if (!lexeditor_ff8_modern_controls_world_active()) return original();
    const int parity = *reinterpret_cast<const std::int16_t *>(kWorldInputParity);
    if (parity < 0 || parity > 1) return original();
    auto *keys = reinterpret_cast<std::uint32_t *>(kWorldInputStates) + parity;
    const auto camera_toggle = *keys & kR2;
    // 0054A845 tests R2's rising edge before toggling overhead camera mode.
    // Mask only this consumer; R2 remains available to vehicle acceleration.
    *keys &= ~kR2;
    const auto result = original();
    *keys = (*keys & ~kR2) | camera_toggle;
    return result;
}

void __cdecl update_battle_camera() {
    original_battle_update();
    if (!lexeditor_ff8_modern_controls_battle_active()) return;

    const auto sequence = *reinterpret_cast<const std::uintptr_t *>(kBattleCameraSequence);
    const auto flags = *reinterpret_cast<const std::uint16_t *>(kBattleCameraFlags);
    const auto blend = *reinterpret_cast<const std::int16_t *>(kBattleCameraBlend);
    if (!lexeditor_battle_camera::safe_idle(sequence, flags, blend)) return;

    auto position = read_vec(kBattleIdlePosition);
    const auto look_at = read_vec(kBattleIdleLookAt);
    // The reader's own turn rate, and this scene's floor. orbit() clamps the
    // rate to a usable range, so a nonsense value in the config cannot make the
    // camera unusable, and it re-learns the floor from FF8's own pose whenever
    // the stick is centred - which is also what makes a new battle start from
    // that battle's floor rather than the last one's.
    static lexeditor_battle_camera::Floor camera_floor;
    if (!lexeditor_battle_camera::orbit(
            position, look_at, right_stick_x, right_stick_y, 0.035f, 0.025f,
            static_cast<float>(ff8_modern_controls_camera_speed),
            &camera_floor)) return;

    // Native has already handed ownership back to the idle/default pose. Move
    // both copies together so the current frame and the next native idle copy
    // agree. Never touch the look-at point or scripted camera state.
    write_vec(kBattleIdlePosition, position);
    write_vec(kBattleLivePosition, position);
}
}

bool lexeditor_ff8_modern_controls_world_active() {
    const auto *mode = getmode_cached();
    const bool active = world_installed && enable_ff8_modern_controls && mode && mode->driver_mode == MODE_WORLDMAP;
    if (!active) {
        manual.reset();
        manual_pitch.reset();
        last_frame = ~0u;
        reset_world_input_state();
    }
    return active;
}

bool lexeditor_ff8_modern_controls_battle_active() {
    const auto *mode = getmode_cached();
    return (battle_installed || bindings_installed) && enable_ff8_modern_controls && mode &&
        mode->driver_mode == MODE_BATTLE;
}

bool lexeditor_ff8_modern_controls_take_square_press() {
    const bool pressed = world_square_pressed;
    world_square_pressed = false;
    return pressed;
}

int lexeditor_ff8_modern_world_axis(std::int8_t port, int type, std::int8_t offset) {
    // The native right-stick fields mean movement/zoom in some camera modes.
    // Under Modern Controls they are camera-owned, except vehicle rY: cars,
    // Garden and Ragnarok now use RT/LT proportionally with R2/L2 logical-key
    // fallbacks. Capture Square before clearing its legacy reverse-drive role so
    // the Flare shortcut can consume that edge separately.
    if (lexeditor_ff8_modern_controls_world_active() && (type == 0 || type == 1)) {
        const unsigned vehicle = *reinterpret_cast<const std::uint32_t *>(kWorldVehicle);
        const bool drive = lexeditor_vehicle_drive::supported_state(vehicle);
        const auto keys = capture_world_input(drive);
        if (type == 1 && drive) return vehicle_drive_axis(keys);
        return 128;
    }
    return ff8_get_analog_value(port, type, offset);
}

void lexeditor_ff8_modern_controls_install() {
    if (!ff8 || !enable_ff8_modern_controls || world_installed || battle_installed || bindings_installed) return;

    const unsigned char first[] = {0xE8, 0xD7, 0x7E, 0x01, 0x00};
    const unsigned char second[] = {0xE8, 0x6F, 0x6A, 0x01, 0x00};
    if (!std::memcmp(reinterpret_cast<void *>(0x0053FBB4), first, sizeof first) &&
        !std::memcmp(reinterpret_cast<void *>(0x0054101C), second, sizeof second) &&
        *reinterpret_cast<const unsigned char *>(0x0053FD4A) == 0xE8 &&
        get_relative_call(0x0053FD4A,0) == 0x0054A7F0 &&
        *reinterpret_cast<const unsigned char *>(0x0054111A) == 0xE8 &&
        get_relative_call(0x0054111A,0) == 0x0054A7F0) {
        original_update = reinterpret_cast<CameraUpdate>(0x00557A90);
        replace_call(0x0053FBB4, reinterpret_cast<void *>(&update_fog));
        replace_call(0x0054101C, reinterpret_cast<void *>(&update_clear));
        replace_call(0x0053FD4A, reinterpret_cast<void *>(&world_actions));
        replace_call(0x0054111A, reinterpret_cast<void *>(&world_actions));
        world_installed = true;
    } else {
        ffnx_warning("Lexeditor Modern Controls: unsupported world-camera call sites; world camera changes not installed.\n");
    }

    const unsigned char battle[] = {0xE8, 0xD3, 0x36, 0x00, 0x00};
    if (!std::memcmp(reinterpret_cast<void *>(kBattleCameraCall), battle, sizeof battle)) {
        original_battle_update = reinterpret_cast<BattleCameraUpdate>(kBattleCameraUpdate);
        replace_call(kBattleCameraCall, reinterpret_cast<void *>(&update_battle_camera));
        battle_installed = true;
    } else {
        ffnx_warning("Lexeditor Modern Controls: unsupported battle-camera call site; battle camera changes not installed.\n");
    }

    // Each call site is E8 rel32 to 004A2D60; anything else is not this game.
    const auto calls_translator = [](std::uintptr_t site) {
        const auto *code = reinterpret_cast<const unsigned char *>(site);
        std::int32_t rel = 0;
        std::memcpy(&rel, code + 1, sizeof rel);
        return code[0] == 0xE8 && site + 5 + rel == kBattleKeyTranslate;
    };
    if (calls_translator(kBattleHeldCall) && calls_translator(kBattlePressedCall) &&
        calls_translator(kBattleRepeatCall)) {
        original_translate = reinterpret_cast<KeyTranslate>(kBattleKeyTranslate);
        replace_call(kBattleHeldCall, reinterpret_cast<void *>(&translate_held));
        replace_call(kBattlePressedCall, reinterpret_cast<void *>(&translate_pressed));
        replace_call(kBattleRepeatCall, reinterpret_cast<void *>(&translate_repeat));
        bindings_installed = true;
    } else {
        ffnx_warning("Lexeditor Modern Controls: unsupported battle input call sites; battle bindings not installed.\n");
    }

    if (world_installed || battle_installed) {
        ffnx_info("Lexeditor Modern Controls: analog camera/vehicle update installed (world=%u battle=%u).\n",
            world_installed, battle_installed);
    }
}
