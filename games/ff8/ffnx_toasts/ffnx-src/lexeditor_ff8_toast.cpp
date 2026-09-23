#include "lexeditor_ff8_toast.h"

#include <algorithm>
#include <cstdint>
#include <string>

// windows.h defines min and max as macros, which breaks every std::min and
// std::clamp below - including the ones inside the layout header.
#define NOMINMAX
#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <imgui.h>

#include "common.h"
#include "globals.h"
#include "renderer.h"
#include "toast_layout.h"
#include "toast_queue.h"

const char *const LEXEDITOR_SUMMON_UNAVAILABLE_REASON =
    "No GF is junctioned to this character. Junction one on the Junction "
    "screen to use Summon.";

namespace {

lexeditor_toast::Queue g_queue;

// FF8's window: a dark blue gradient behind a pale double edge. These are the
// colours the game's own window reads as on screen, not a theme of ours; a
// message that looked like an overlay would defeat the point of this file.
constexpr ImU32 kFillTop = IM_COL32(12, 24, 96, 232);
constexpr ImU32 kFillBottom = IM_COL32(4, 8, 40, 232);
constexpr ImU32 kEdgeOuter = IM_COL32(24, 32, 72, 255);
constexpr ImU32 kEdgeInner = IM_COL32(200, 208, 232, 255);
constexpr ImU32 kText = IM_COL32(255, 255, 255, 255);
constexpr ImU32 kTextWarning = IM_COL32(255, 216, 136, 255);
constexpr ImU32 kTextShadow = IM_COL32(0, 0, 0, 200);

// One line of FF8 text is about this tall in the game's own pixels, and its
// font is close enough to fixed width to size a box from a character count.
constexpr float kLineHeight = 20.0f;
constexpr float kCharWidth = 9.0f;

// The battle patch's refusal flag. Lexeditor's command-eligibility Hext patch
// raises it when a greyed Summon is pressed, and we lower it once the reason
// has been said. The address lives inside FF8's own image, so it is read only
// after the page it sits on is confirmed committed: a build running without
// that patch must not fault here.
constexpr std::uintptr_t kSummonRefusedFlag = 0x0279F4F0;

bool flag_readable()
{
    static int state = -1;
    if (state < 0) {
        MEMORY_BASIC_INFORMATION info{};
        const SIZE_T got = VirtualQuery(
            reinterpret_cast<LPCVOID>(kSummonRefusedFlag), &info, sizeof(info));
        const DWORD readable = PAGE_READWRITE | PAGE_READONLY |
            PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE;
        state = (got == sizeof(info) && info.State == MEM_COMMIT &&
                 (info.Protect & readable) != 0) ? 1 : 0;
    }
    return state == 1;
}

// Game pixels to window pixels, through the same projection the status bars
// use, so a toast keeps its place under widescreen and letterboxing alike.
float project_x(float value)
{
    return newRenderer.projectGamePointToScreen(value, 0.0f)[0] *
        ImGui::GetIO().DisplaySize.x;
}

float project_y(float value)
{
    return newRenderer.projectGamePointToScreen(0.0f, value)[1] *
        ImGui::GetIO().DisplaySize.y;
}

ImU32 with_alpha(ImU32 colour, float alpha)
{
    const ImU32 scaled = static_cast<ImU32>(
        std::clamp(alpha, 0.0f, 1.0f) * static_cast<float>((colour >> IM_COL32_A_SHIFT) & 0xFF));
    return (colour & ~IM_COL32_A_MASK) | (scaled << IM_COL32_A_SHIFT);
}

}  // namespace

void lexeditor_ff8_toast_push(const char *text, bool warning)
{
    if (text == nullptr || *text == '\0') return;
    g_queue.push(text, warning ? lexeditor_toast::Tone::warning
                               : lexeditor_toast::Tone::normal);
}

bool lexeditor_ff8_toast_enabled()
{
    return g_queue.showing() || g_queue.pending() > 0;
}

void lexeditor_ff8_toast_poll_battle()
{
    if (!flag_readable()) return;
    volatile std::uint8_t *flag = reinterpret_cast<volatile std::uint8_t *>(kSummonRefusedFlag);
    if (*flag == 0) return;
    *flag = 0;
    lexeditor_ff8_toast_push(LEXEDITOR_SUMMON_UNAVAILABLE_REASON, true);
}

void lexeditor_ff8_toast_draw()
{
    lexeditor_ff8_toast_poll_battle();

    const std::uint32_t now = static_cast<std::uint32_t>(GetTickCount64());
    const lexeditor_toast::Toast *toast = g_queue.update(now);
    if (toast == nullptr) return;

    lexeditor_toast::Metrics metrics;
    metrics.width = static_cast<float>(game_width > 0 ? game_width : 640);
    metrics.height = static_cast<float>(game_height > 0 ? game_height : 480);
    // FF8 renders at 640x480 and everything above is written for that frame,
    // so a different height scales the text with it rather than leaving a
    // box of the wrong proportions.
    const float scale = metrics.height / 480.0f;
    metrics.line_height = kLineHeight * scale;
    metrics.char_width = kCharWidth * scale;

    std::size_t columns = 0;
    for (const std::string &line : toast->lines) {
        columns = std::max(columns, line.size());
    }
    const lexeditor_toast::Box box =
        lexeditor_toast::layout(metrics, toast->lines.size(), columns);
    const float alpha = lexeditor_toast::fade(g_queue.progress(now));
    if (alpha <= 0.0f) return;

    ImDrawList *draw = ImGui::GetForegroundDrawList();
    const ImVec2 minimum(project_x(box.x), project_y(box.y));
    const ImVec2 maximum(project_x(box.x + box.width), project_y(box.y + box.height));
    if (maximum.x <= minimum.x || maximum.y <= minimum.y) return;
    const float rounding = std::max(2.0f, (maximum.y - minimum.y) * 0.06f);

    // Body first, then the two edges from the outside in, the way the game's
    // window is built up.
    draw->AddRectFilledMultiColor(minimum, maximum,
        with_alpha(kFillTop, alpha), with_alpha(kFillTop, alpha),
        with_alpha(kFillBottom, alpha), with_alpha(kFillBottom, alpha));
    draw->AddRect(minimum, maximum, with_alpha(kEdgeOuter, alpha), rounding, 0, 3.0f);
    draw->AddRect(ImVec2(minimum.x + 1.0f, minimum.y + 1.0f),
                  ImVec2(maximum.x - 1.0f, maximum.y - 1.0f),
                  with_alpha(kEdgeInner, alpha), rounding, 0, 1.5f);

    const float line_height = project_y(box.y + metrics.line_height) - project_y(box.y);
    const float font_size = std::max(8.0f, line_height * 0.86f);
    const ImU32 colour = with_alpha(
        toast->tone == lexeditor_toast::Tone::warning ? kTextWarning : kText, alpha);
    const ImU32 shadow = with_alpha(kTextShadow, alpha);
    float y = project_y(box.text_y);
    const float x = project_x(box.text_x);
    for (const std::string &line : toast->lines) {
        // FF8 draws its text over a one-pixel shadow. Without it the pale
        // glyphs disappear into the lighter top of the gradient.
        draw->AddText(nullptr, font_size, ImVec2(x + 1.0f, y + 1.0f), shadow, line.c_str());
        draw->AddText(nullptr, font_size, ImVec2(x, y), colour, line.c_str());
        y += line_height;
    }
}
