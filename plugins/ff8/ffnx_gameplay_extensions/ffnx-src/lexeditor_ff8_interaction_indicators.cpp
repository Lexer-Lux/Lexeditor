#include "lexeditor_ff8_interaction_indicators.h"
#include "interaction_indicator.h"

#include <algorithm>
#include <cstdint>

#include <imgui.h>

#include "cfg.h"
#include "common.h"
#include "ff8.h"
#include "globals.h"

namespace {

constexpr std::uintptr_t kFieldEntities = 0x01D9CF88;
constexpr std::uintptr_t kFieldEntityCount = 0x01D9D019;
constexpr std::uintptr_t kFieldPlayerEntity = 0x01CD8FD0;
constexpr std::uintptr_t kFieldControlLock = 0x01CE4775;
constexpr std::uintptr_t kFieldInstructions = 0x01D9CF50;
constexpr std::uintptr_t kFieldEntrypoints = 0x01D9D0E4;
constexpr std::uintptr_t kFieldOpcodeTable = 0x00B8DE94;
constexpr std::uintptr_t kCardgameHandler = 0x005225A0;
constexpr std::uintptr_t kDirectionAndDistance = 0x00477380;
constexpr std::size_t kEntitySize = 0x264;

constexpr std::size_t kPositionX = 0x190;
constexpr std::size_t kPositionY = 0x194;
constexpr std::size_t kPositionZ = 0x198;
constexpr std::size_t kPlayerRadius = 0x1F6;
constexpr std::size_t kTargetRadius = 0x1F8;
constexpr std::size_t kTalkState = 0x218;
constexpr std::size_t kFacing = 0x241;
constexpr std::size_t kInteractionDisabled = 0x24B;
constexpr std::size_t kScriptBase = 0x178;

struct Target {
    const std::uint8_t *entity = nullptr;
    bool card = false;
};

using DirectionAndDistance = std::uint32_t(__cdecl *)(
    const int *, const int *, int *);

int fixed_position(const std::uint8_t *entity, std::size_t offset)
{
    return *reinterpret_cast<const std::int32_t *>(entity + offset) >> 12;
}

bool layout_supported()
{
    if (!ff8 || !FF8_US_VERSION) return false;
    const auto *handlers =
        reinterpret_cast<const std::uintptr_t *>(kFieldOpcodeTable);
    return handlers[lexeditor_interaction_indicator::kCardgameOpcode] ==
        kCardgameHandler;
}

bool talk_script_has_cardgame(const std::uint8_t *entity)
{
    const auto *entrypoints =
        *reinterpret_cast<const std::uint16_t *const *>(kFieldEntrypoints);
    const auto *instructions =
        *reinterpret_cast<const std::uint32_t *const *>(kFieldInstructions);
    if (entrypoints == nullptr || instructions == nullptr) return false;

    const std::uint16_t base =
        *reinterpret_cast<const std::uint16_t *>(entity + kScriptBase);
    const std::uint32_t talk = static_cast<std::uint32_t>(base) + 2U;
    if (talk >= 0x3FFE) return false;

    // FF8 stores the runtime PC in dwords. Bit 15 on an entrypoint is metadata;
    // the native loader masks it before using the instruction offset.
    const std::uint16_t start = entrypoints[talk] & 0x7FFF;
    const std::uint16_t end = entrypoints[talk + 1] & 0x7FFF;
    if (end <= start) return false;
    const std::size_t count = static_cast<std::size_t>(end - start);
    return lexeditor_interaction_indicator::talk_script_has_cardgame(
        instructions + start, count);
}

Target current_target()
{
    if (!layout_supported() ||
        *reinterpret_cast<const std::uint8_t *>(kFieldControlLock) != 0) {
        return {};
    }

    const auto *entities =
        *reinterpret_cast<const std::uint8_t *const *>(kFieldEntities);
    const unsigned count =
        *reinterpret_cast<const std::uint8_t *>(kFieldEntityCount);
    const int player_index =
        *reinterpret_cast<const std::int16_t *>(kFieldPlayerEntity);
    if (entities == nullptr || count == 0 ||
        player_index < 0 || player_index >= static_cast<int>(count)) {
        return {};
    }

    const auto *player = entities +
        static_cast<std::size_t>(player_index) * kEntitySize;
    const int player_position[3] = {
        fixed_position(player, kPositionX),
        fixed_position(player, kPositionY),
        fixed_position(player, kPositionZ),
    };
    const std::uint8_t facing = player[kFacing];
    const std::uint16_t player_radius =
        *reinterpret_cast<const std::uint16_t *>(player + kPlayerRadius);
    const auto direction_and_distance =
        reinterpret_cast<DirectionAndDistance>(kDirectionAndDistance);

    std::uint16_t best_error =
        lexeditor_interaction_indicator::kFacingLimit;
    const std::uint8_t *best = nullptr;

    for (unsigned index = 0; index < count; ++index) {
        if (index == static_cast<unsigned>(player_index)) continue;
        const auto *target = entities +
            static_cast<std::size_t>(index) * kEntitySize;
        if (target[kInteractionDisabled] != 0 ||
            *reinterpret_cast<const std::uint16_t *>(target + kTalkState) ==
                0xFFFF) {
            continue;
        }

        const int target_position[3] = {
            fixed_position(target, kPositionX),
            fixed_position(target, kPositionY),
            fixed_position(target, kPositionZ),
        };
        if (target_position[0] == player_position[0] &&
            target_position[1] == player_position[1]) {
            continue;
        }
        if (!lexeditor_interaction_indicator::vertical_range(
                player_position[2], target_position[2])) {
            continue;
        }

        int distance = 0;
        const std::uint8_t direction = static_cast<std::uint8_t>(
            direction_and_distance(
                player_position, target_position, &distance));
        const std::uint16_t error =
            lexeditor_interaction_indicator::facing_error(facing, direction);
        const std::uint16_t target_radius =
            *reinterpret_cast<const std::uint16_t *>(target + kTargetRadius);
        if (!lexeditor_interaction_indicator::within_talk_radius(
                distance, player_radius, target_radius)) {
            continue;
        }

        // Native field_check_talk_interaction chooses the smallest facing
        // error, not the shortest distance, and requires error < 0x40.
        if (error < best_error) {
            best_error = error;
            best = target;
        }
    }

    return best == nullptr
        ? Target{}
        : Target{best, talk_script_has_cardgame(best)};
}

float badge_width(const char *text)
{
    return ImGui::CalcTextSize(text).x + 22.0f;
}

void draw_badge(ImDrawList *draw, float x, float y,
    const char *text, ImU32 edge, ImU32 fill)
{
    const ImVec2 size = ImGui::CalcTextSize(text);
    const float width = size.x + 22.0f;
    const float height = size.y + 12.0f;
    const ImVec2 minimum(x, y);
    const ImVec2 maximum(x + width, y + height);
    draw->AddRectFilled(minimum, maximum, fill, 4.0f);
    draw->AddRect(minimum, maximum, edge, 4.0f, 0, 1.5f);
    draw->AddText(ImVec2(x + 11.0f, y + 6.0f),
        IM_COL32(255, 255, 255, 255), text);
}

} // namespace

bool lexeditor_ff8_interaction_indicators_enabled()
{
    if (!enable_ff8_interaction_indicators || !layout_supported()) return false;
    const auto *mode = getmode_cached();
    return mode != nullptr && mode->driver_mode == MODE_FIELD;
}

void lexeditor_ff8_interaction_indicators_draw()
{
    if (!lexeditor_ff8_interaction_indicators_enabled()) return;
    const Target target = current_target();
    if (target.entity == nullptr) return;

    // The issue explicitly accepts a fixed-HUD fallback. Keeping this overlay
    // screen-space avoids guessing field-model projection state and does not
    // touch native interaction or field-script state.
    ImDrawList *draw = ImGui::GetForegroundDrawList();
    const ImVec2 display = ImGui::GetIO().DisplaySize;
    constexpr float gap = 8.0f;
    const float interact = badge_width("INTERACT");
    const float card = target.card ? badge_width("CARD") : 0.0f;
    const float total = interact + (target.card ? gap + card : 0.0f);
    float x = std::max(8.0f, (display.x - total) * 0.5f);
    const float y = std::max(8.0f, display.y * 0.80f);

    draw_badge(draw, x, y, "INTERACT",
        IM_COL32(216, 224, 255, 255), IM_COL32(12, 24, 72, 220));
    if (target.card) {
        x += interact + gap;
        draw_badge(draw, x, y, "CARD",
            IM_COL32(255, 220, 96, 255), IM_COL32(80, 48, 8, 228));
    }
}
