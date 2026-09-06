#include "lexeditor_ff8_bars.h"

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>

#include <imgui.h>

#include "cfg.h"
#include "common.h"
#include "ff8.h"
#include "globals.h"
#include "patch.h"
#include "renderer.h"

namespace {

enum class XpSurface : std::uint8_t {
    none,
    main_menu,
    status_menu,
    after_battle,
};

struct XpCapture {
    XpSurface surface = XpSurface::none;
    std::uint8_t status_character = 0xFF;
};

using MenuRenderer = std::uint32_t(__cdecl *)(void *, std::uint32_t, std::uint32_t);
using AfterBattleRenderer = void(__cdecl *)();
using ResultState = std::uint8_t *(__cdecl *)(int);
using ResultRowRenderer = std::uint32_t(__cdecl *)(
    std::uint32_t, std::uint32_t, int, int, int, int, std::uint32_t);
struct ResultRow {
    std::array<std::int16_t, 4> rect{};
    sprite_viewport viewport{};
    bool visible = false;
};
std::array<ResultRow, 3> g_result_rows;

XpCapture g_capture;
MenuRenderer g_main_menu_renderer = nullptr;
MenuRenderer g_status_menu_renderer = nullptr;
AfterBattleRenderer g_after_battle_renderer = nullptr;
ResultState g_result_state = nullptr;
ResultRowRenderer g_result_row_renderer = nullptr;
sprite_viewport **g_active_viewport = nullptr;

using BattleRowRenderer = std::uint32_t(__cdecl *)(std::uint8_t *, std::uint32_t, std::uint32_t, int);
using GlyphRenderer = std::uint32_t(__cdecl *)(std::uint32_t, std::uint32_t, int, int);
BattleRowRenderer g_battle_row_renderer = nullptr;
GlyphRenderer g_hp_glyph_renderer = nullptr, g_atb_glyph_renderer = nullptr;
struct HpCapture {
    float left = 0, right = 0, top = 0;
    sprite_viewport viewport{};
    std::uint16_t current = 0, maximum = 0;
    std::uint32_t gf_current = 0, gf_maximum = 0;
    bool hp_visible = false, atb_visible = false;
};
std::array<HpCapture, 3> g_hp_rows;
HpCapture *g_hp_row = nullptr;

// Native 004B77F9 reads the menu sprite table. Each entry encodes a count
// and offset; each 8-byte sprite has width, signed x, height, signed y.
void capture_glyph(int x, int y, bool hp)
{
    if (g_hp_row == nullptr || g_active_viewport == nullptr || *g_active_viewport == nullptr) return;
    const auto *context = *reinterpret_cast<const std::uint8_t **>(0x01D6D490);
    const auto *table = *reinterpret_cast<const std::uint8_t **>(0x01D2BAE8);
    if (context == nullptr || table == nullptr) return;
    const auto id = *reinterpret_cast<const std::uint16_t *>(context + 0x44);
    if ((hp && id >= 0x6A) || (!hp && id != 0x5A)) return;
    const auto entry = *reinterpret_cast<const std::uint32_t *>(table + 4 + id * 4);
    const unsigned count = entry >> 16;
    if (count == 0 || count > 64) return;
    const auto *sprite = table + (entry & 0xFFFF);
    for (unsigned i = 0; i < count; ++i, sprite += 8) {
        const float right = x + static_cast<std::int8_t>(sprite[5]) + sprite[4];
        if (!hp) g_hp_row->right = std::max(g_hp_row->right, right);
    }
    g_hp_row->viewport = **g_active_viewport;
    if (hp) g_hp_row->hp_visible = true;
    else g_hp_row->atb_visible = true;
}

std::uint32_t __cdecl hp_glyph_hook(std::uint32_t a, std::uint32_t b, int x, int y)
{
    capture_glyph(x, y, true);
    return g_hp_glyph_renderer(a, b, x, y);
}
std::uint32_t __cdecl atb_glyph_hook(std::uint32_t a, std::uint32_t b, int x, int y)
{
    capture_glyph(x, y, false);
    return g_atb_glyph_renderer(a, b, x, y);
}
// Saved GF HP is authoritative outside a summon. During the charge the
// engine keeps a live copy in the summoner's computed record (+18/+1A), then
// writes it back at 0048E664. Reading only saved HP would miss incoming damage.
void capture_gf_hp(std::uint8_t slot, HpCapture &capture)
{
    if (!enable_ff8_gf_hp_bars || ff8_externals.savemap == nullptr ||
        ff8_externals.char_comp_stats_1CFF000.size() != 3) return;
    const auto character = ff8_externals.character_data_1CFE74C[slot];
    if (character >= CHAR_NUM) return;
    const auto junctions = ff8_externals.savemap->chars[character].gfs;
    const auto *stats = reinterpret_cast<const std::uint8_t *>(
        &ff8_externals.char_comp_stats_1CFF000[slot]);
    const bool summoning = (stats[0x1C] & 1) != 0;
    const int summoned = static_cast<int>(stats[0x1D]) - 0x40;
    for (int gf = 0; gf < G_FORCE_NUM; ++gf) {
        if (!(junctions & (1U << gf)) || !(ff8_externals.savemap->gfs[gf].exists & 1)) continue;
        // 00495D80 initializes twelve-byte GF stats; +2 is max HP, including
        // level and learned HP abilities. Do not duplicate the game's formula.
        auto maximum = *reinterpret_cast<const std::uint16_t *>(0x1CFF61A + gf * 12);
        auto current = ff8_externals.savemap->gfs[gf].HPs;
        if (summoning && summoned == gf) {
            current = *reinterpret_cast<const std::uint16_t *>(stats + 0x18);
            maximum = *reinterpret_cast<const std::uint16_t *>(stats + 0x1A);
        }
        capture.gf_maximum += maximum;
        capture.gf_current += std::min(current, maximum);
    }
}

std::uint32_t __cdecl battle_row_hook(std::uint8_t *row, std::uint32_t a, std::uint32_t b, int state)
{
    const auto actor = row[0x48];
    g_hp_row = nullptr;
    if (actor < 3) {
        auto &capture = g_hp_rows[actor];
        capture = {};
        // Native name origin is row+8 (004B0C0B); HP comes from this same
        // displayed row, not the stat editor's computed-stat scratch buffer.
        capture.left = *reinterpret_cast<const std::int16_t *>(row + 8);
        capture.top = *reinterpret_cast<const std::int16_t *>(row + 0xA);
        capture.maximum = *reinterpret_cast<const std::uint16_t *>(row + 0x1C);
        capture.current = *reinterpret_cast<const std::uint16_t *>(row + 0x1E);
        capture_gf_hp(actor, capture);
        g_hp_row = &capture;
    }
    const auto result = g_battle_row_renderer(row, a, b, state);
    g_hp_row = nullptr;
    return result;
}

constexpr std::uint32_t kMaxSearchExp = 99999999U;

static_assert(offsetof(ff8_char_computed_stats, curr_hp) == 370);
static_assert(offsetof(ff8_char_computed_stats, max_hp) == 372);
static_assert(offsetof(savemap_ff8_character, exp) == 4);
static_assert(offsetof(savemap_ff8_character, gfs) == 0x58);
static_assert(offsetof(savemap_ff8_gf, HPs) == 0x12);

std::uint32_t __cdecl main_menu_renderer_hook(
    void *state, std::uint32_t display_list, std::uint32_t ordering_table)
{
    const std::uint32_t result = g_main_menu_renderer(state, display_list, ordering_table);
    // FF8 also calls this renderer from the title-screen save-block browser.
    // Draw party XP only in the in-game menu, never across save slots.
    const auto *mode = getmode_cached();
    if (mode != nullptr && mode->driver_mode == MODE_MENU) {
        g_capture.surface = XpSurface::main_menu;
    } else {
        g_capture = {};
    }
    return result;
}

std::uint32_t __cdecl status_menu_renderer_hook(
    void *state, std::uint32_t display_list, std::uint32_t ordering_table)
{
    const std::uint32_t result = g_status_menu_renderer(state, display_list, ordering_table);
    // FF8_EN.exe 004CEF94 reads this byte and uses it to form the selected
    // savemap_ff8_character address at 004CEFA5.
    g_capture.status_character = *(static_cast<std::uint8_t *>(state) + 0x36);
    g_capture.surface = XpSurface::status_menu;
    return result;
}

void __cdecl after_battle_renderer_hook()
{
    g_result_rows = {};
    g_after_battle_renderer();
    g_capture.surface = XpSurface::after_battle;
}

std::uint32_t __cdecl result_row_renderer_hook(
    std::uint32_t ordering, std::uint32_t primitives, int slot,
    int x, int y, int transition, std::uint32_t color)
{
    const auto result = g_result_row_renderer(
        ordering, primitives, slot, x, y, transition, color);
    auto *state = g_result_state(0);
    if (state != nullptr && g_active_viewport != nullptr && *g_active_viewport != nullptr && slot >= 0 && slot < 3 && transition != 0 &&
        *reinterpret_cast<const std::uint32_t *>(state + 0x54 + slot * 4) != 0) {
        auto &row = g_result_rows[slot];
        // Native row renderer expands its panel into state+8 at 004A5F34.
        // Capture now, before another row or widget reuses that rectangle.
        std::copy_n(reinterpret_cast<const std::int16_t *>(state + 8), 4, row.rect.begin());
        row.viewport = **g_active_viewport;
        row.visible = row.rect[2] > 2 && row.rect[3] > 2 &&
            row.viewport.scale_x > 0 && row.viewport.scale_y > 0;
    }
    return result;
}

float scale_x(float value)
{
    return newRenderer.projectGamePointToScreen(value, 0.0f)[0] * ImGui::GetIO().DisplaySize.x;
}

float scale_y(float value)
{
    return newRenderer.projectGamePointToScreen(0.0f, value)[1] * ImGui::GetIO().DisplaySize.y;
}

void draw_bar(float x, float y, float width, float height, float fraction, ImU32 fill)
{
    ImDrawList *draw = ImGui::GetForegroundDrawList();
    const ImVec2 minimum(scale_x(x), scale_y(y));
    const ImVec2 maximum(scale_x(x + width), scale_y(y + height));
    if (maximum.x <= minimum.x || maximum.y <= minimum.y) {
        return;
    }
    const float inset = std::max(1.0f, scale_y(1.0f) - scale_y(0.0f));
    fraction = std::clamp(fraction, 0.0f, 1.0f);

    draw->AddRectFilled(minimum, maximum, IM_COL32(0, 0, 0, 220));
    // The surrounding native panel supplies its own edge. No overlay outline.
    if (fraction > 0.0f) {
        const ImVec2 fill_min(minimum.x + inset, minimum.y + inset);
        const ImVec2 fill_max(
            fill_min.x + (maximum.x - minimum.x - 2.0f * inset) * fraction,
            maximum.y - inset);
        draw->AddRectFilled(fill_min, fill_max, fill);
    }
}

int level_for_exp(std::uint32_t exp, std::uint8_t character)
{
    return ff8_externals.get_char_level_4961D0(static_cast<int>(exp), character);
}

std::uint32_t first_exp_for_level(int level, std::uint8_t character)
{
    std::uint32_t low = 0;
    std::uint32_t high = kMaxSearchExp;
    while (low < high) {
        const std::uint32_t middle = low + (high - low) / 2;
        if (level_for_exp(middle, character) >= level) {
            high = middle;
        } else {
            low = middle + 1;
        }
    }
    return low;
}

float xp_fraction(std::uint32_t exp, std::uint8_t character)
{
    if (character >= CHAR_NUM) {
        return 0.0f;
    }
    const int level = level_for_exp(exp, character);
    if (level >= 100) {
        return 1.0f;
    }
    const std::uint32_t lower = first_exp_for_level(level, character);
    const std::uint32_t upper = first_exp_for_level(level + 1, character);
    if (upper <= lower) {
        return 0.0f;
    }
    const std::uint32_t bounded = std::clamp(exp, lower, upper);
    return static_cast<float>(bounded - lower) / static_cast<float>(upper - lower);
}

void draw_main_menu_xp()
{
    for (std::size_t slot = 0; slot < 3; ++slot) {
        const std::uint8_t character = ff8_externals.savemap->party[slot];
        if (character >= CHAR_NUM) {
            continue;
        }
        draw_bar(96.0f, 118.0f + 105.0f * slot, 210.0f, 6.0f,
            xp_fraction(ff8_externals.savemap->chars[character].exp, character),
            IM_COL32(224, 192, 48, 255));
    }
}

void draw_status_menu_xp(std::uint8_t character)
{
    if (character >= CHAR_NUM) {
        return;
    }
    draw_bar(348.0f, 104.0f, 218.0f, 7.0f,
        xp_fraction(ff8_externals.savemap->chars[character].exp, character),
        IM_COL32(224, 192, 48, 255));
}

void draw_after_battle_xp()
{
    // The native result renderer calls 00403E00(0). This is a menu-state
    // accessor, not the graphics game object returned by common_externals.
    auto *result_state = g_result_state == nullptr ? nullptr : g_result_state(0);
    // 004A4BA7 dispatches the result page through byte +0x38. Only page 0
    // calls the three character EXP renderers; subsequent pages show rewards.
    if (result_state == nullptr || result_state[0x38] != 0) {
        return;
    }
    for (std::size_t slot = 0; slot < 3; ++slot) {
        const std::uint8_t character = ff8_externals.character_data_1CFE74C[slot];
        const auto &row = g_result_rows[slot];
        if (character >= CHAR_NUM || !row.visible) {
            continue;
        }
        // 004A4485 initializes these totals. 004A48B1 advances them while the
        // post-battle report animates, so this is the value the report shows.
        const auto exp = *reinterpret_cast<const std::uint32_t *>(
            result_state + 0x234 + slot * sizeof(std::uint32_t));
        const auto &viewport = row.viewport;
        const float x = row.rect[0] * viewport.scale_x + viewport.offset_x;
        const float bottom = (row.rect[1] + row.rect[3]) * viewport.scale_y + viewport.offset_y;
        const float height = std::min(4.0f, row.rect[3] * viewport.scale_y);
        draw_bar(x + viewport.scale_x, bottom - height - viewport.scale_y,
            std::max(0.0f, (row.rect[2] - 2.0f) * viewport.scale_x), height,
            xp_fraction(exp, character), IM_COL32(224, 192, 48, 255));
    }
}

void draw_battle_hp()
{
    // FF8 uses the same raw module for Triple Triad and battle. FFNx's
    // resolved driver mode also checks the active callback; raw mode 999
    // is only a synthetic table identity and cannot gate live battle bars.
    const auto *mode = getmode_cached();
    if (mode == nullptr || mode->driver_mode != MODE_BATTLE ||
        ff8_externals.char_comp_stats_1CFF000.size() != 3) {
        return;
    }
    for (const auto &row : g_hp_rows) {
        if (!row.atb_visible || row.right <= row.left ||
            row.viewport.scale_x <= 0 || row.viewport.scale_y <= 0) continue;
        const auto &v = row.viewport;
        const float full_width = (row.right - row.left) * v.scale_x;
        auto draw_line = [&](std::uint32_t current, std::uint32_t maximum,
                             float native_y, bool from_left, ImU32 color) {
            if (!maximum) return;
            const float width = full_width * std::min(1.0f, maximum / 9999.0f);
            const float x = (from_left ? row.left : row.right) * v.scale_x + v.offset_x;
            const float top = native_y * v.scale_y + v.offset_y;
            const ImVec2 lo(scale_x(from_left ? x : x - width), scale_y(top));
            const ImVec2 hi(scale_x(from_left ? x + width : x), scale_y(top + v.scale_y));
            if (hi.x <= lo.x || hi.y <= lo.y) return;
            auto *draw = ImGui::GetForegroundDrawList();
            draw->AddRectFilled(lo, hi, IM_COL32(0, 0, 0, 255));
            const float fraction = std::min(1.0f, current / static_cast<float>(maximum));
            if (fraction <= 0) return;
            const float filled = (hi.x - lo.x) * fraction;
            draw->AddRectFilled(
                ImVec2(from_left ? lo.x : hi.x - filled, lo.y),
                ImVec2(from_left ? lo.x + filled : hi.x, hi.y), color);
        };
        // Native rows are 15 pixels high (004B0FF6) and spaced by 15
        // (004B1978). Text starts at row_y+2 and is 12 pixels high. Glyph
        // atlas cells can contain transparent padding beyond that row.
        // Anchor the red line to its final pixel, never to atlas-cell bounds.
        if (enable_ff8_hp_bars && row.hp_visible)
            draw_line(row.current, row.maximum, row.top + 14.0f, false, IM_COL32(224, 32, 32, 255));
        // One native pixel immediately above the name; independent toggle.
        if (enable_ff8_gf_hp_bars)
            draw_line(row.gf_current, row.gf_maximum, row.top + 1.0f, true, IM_COL32(48, 128, 255, 255));
    }
}

} // namespace

bool lexeditor_ff8_bars_enabled()
{
    return ff8 && (enable_ff8_xp_bars || enable_ff8_hp_bars || enable_ff8_gf_hp_bars);
}

void lexeditor_ff8_bars_install()
{
    if (!ff8 || (!enable_ff8_xp_bars && !enable_ff8_hp_bars && !enable_ff8_gf_hp_bars)) {
        return;
    }

    g_active_viewport = reinterpret_cast<sprite_viewport **>(get_absolute_value(
        ff8_externals.engine_reset_viewport_sub_4972D0, 0x12));
    const auto original_call = [](std::uintptr_t address, std::uintptr_t target) {
        return *reinterpret_cast<const std::uint8_t *>(address) == 0xE8 &&
            get_relative_call(address, 0) == target;
    };
    if ((enable_ff8_hp_bars || enable_ff8_gf_hp_bars) && FF8_US_VERSION &&
        original_call(0x004B17D5, 0x004B0F10) &&
        original_call(0x004B1100, 0x004A7210) &&
        original_call(0x004B127B, 0x004A7210)) {
        // Row call runs only after native HUD visibility and participant gates.
        g_battle_row_renderer = reinterpret_cast<BattleRowRenderer>(get_relative_call(0x004B17D5, 0));
        g_hp_glyph_renderer = reinterpret_cast<GlyphRenderer>(get_relative_call(0x004B1100, 0));
        g_atb_glyph_renderer = reinterpret_cast<GlyphRenderer>(get_relative_call(0x004B127B, 0));
        replace_call(0x004B17D5, reinterpret_cast<void *>(&battle_row_hook));
        replace_call(0x004B1100, reinterpret_cast<void *>(&hp_glyph_hook));
        replace_call(0x004B127B, reinterpret_cast<void *>(&atb_glyph_hook));
    }
    if (!enable_ff8_xp_bars) return;

    // The callback entries contain PUSH-immediate renderer pointers. FFNx
    // already resolves this same table from the supported executable.
    const std::uint32_t main_callback = static_cast<std::uint32_t>(
        reinterpret_cast<std::uintptr_t>(ff8_externals.menu_callbacks[16].func));
    const std::uint32_t status_callback = static_cast<std::uint32_t>(
        reinterpret_cast<std::uintptr_t>(ff8_externals.menu_callbacks[5].func));
    g_main_menu_renderer = reinterpret_cast<MenuRenderer>(
        get_absolute_value(main_callback, 0x3));
    g_status_menu_renderer = reinterpret_cast<MenuRenderer>(
        get_absolute_value(status_callback, 0x3));
    g_after_battle_renderer = reinterpret_cast<AfterBattleRenderer>(
        get_relative_call(ff8_externals.battle_menu_sub_4A3D20, 0x139));
    g_result_state = reinterpret_cast<ResultState>(get_relative_call(
        reinterpret_cast<std::uintptr_t>(g_after_battle_renderer), 0x9));
    g_active_viewport = reinterpret_cast<sprite_viewport **>(get_absolute_value(
        ff8_externals.engine_reset_viewport_sub_4972D0, 0x12));
    const auto row_call = reinterpret_cast<std::uintptr_t>(g_after_battle_renderer) + 0x2BD;
    g_result_row_renderer = reinterpret_cast<ResultRowRenderer>(get_relative_call(row_call, 0));
    replace_call(row_call, reinterpret_cast<void *>(&result_row_renderer_hook));

    patch_code_dword(main_callback + 0x3,
        static_cast<std::uint32_t>(
            reinterpret_cast<std::uintptr_t>(&main_menu_renderer_hook)));
    patch_code_dword(status_callback + 0x3,
        static_cast<std::uint32_t>(
            reinterpret_cast<std::uintptr_t>(&status_menu_renderer_hook)));
    replace_call(ff8_externals.battle_menu_sub_4A3D20 + 0x139,
        reinterpret_cast<void *>(&after_battle_renderer_hook));
}

void lexeditor_ff8_bars_draw()
{
    if (enable_ff8_hp_bars || enable_ff8_gf_hp_bars) {
        draw_battle_hp();
    }
    if (enable_ff8_xp_bars) {
        switch (g_capture.surface) {
        case XpSurface::main_menu:
            draw_main_menu_xp();
            break;
        case XpSurface::status_menu:
            draw_status_menu_xp(g_capture.status_character);
            break;
        case XpSurface::after_battle:
            draw_after_battle_xp();
            break;
        default:
            break;
        }
    }
    // A renderer hook must identify every XP frame. This prevents a bar from
    // leaking onto the next screen after a menu closes.
    g_capture = {};
    g_hp_rows = {};
}
