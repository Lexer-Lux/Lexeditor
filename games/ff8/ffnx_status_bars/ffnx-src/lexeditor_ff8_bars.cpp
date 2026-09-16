#include "lexeditor_ff8_bars.h"

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <ctime>

#include <imgui.h>

#include "cfg.h"
#include "common.h"
#include "ff8.h"
#include "globals.h"
#include "log.h"
#include "patch.h"
#include "renderer.h"

namespace {

enum class XpSurface : std::uint8_t {
    none,
    after_battle,
};

struct XpCapture {
    XpSurface surface = XpSurface::none;
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
AfterBattleRenderer g_after_battle_renderer = nullptr;
ResultState g_result_state = nullptr;
ResultRowRenderer g_result_row_renderer = nullptr;
sprite_viewport **g_active_viewport = nullptr;

using BattleRowRenderer = std::uint32_t(__cdecl *)(std::uint8_t *, std::uint32_t, std::uint32_t, int);
using GlyphRenderer = std::uint32_t(__cdecl *)(std::uint32_t, std::uint32_t, int, int);
BattleRowRenderer g_battle_row_renderer = nullptr;
GlyphRenderer g_hp_glyph_renderer = nullptr, g_atb_glyph_renderer = nullptr;
struct HpCapture {
    // left: visible start of the name; name_right: end of its 96-pixel area.
    // hp_left/hp_right: where the HP digits were actually drawn; digit: the
    // widest digit, so the bar can span a full four-digit field.
    float left = 0, right = 0, top = 0, name_right = 0;
    float hp_left = 0, hp_right = 0, digit = 0;
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
        const float left = x + static_cast<std::int8_t>(sprite[5]);
        const float right = left + sprite[4];
        if (!hp) {
            g_hp_row->right = std::max(g_hp_row->right, right);
        } else {
            g_hp_row->hp_left = g_hp_row->hp_visible ? std::min(g_hp_row->hp_left, left) : left;
            g_hp_row->hp_right = std::max(g_hp_row->hp_right, right);
            g_hp_row->digit = std::max(g_hp_row->digit, static_cast<float>(sprite[4]));
        }
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
    static bool reported[CHAR_NUM] = {};
    if (junctions && (junctions & (junctions - 1))) {
        if (!reported[character]) {
            ffnx_error("GF HP Bars: character %u has multiple GFs junctioned. Requires Monogamy; bar suppressed.\n", character);
            reported[character] = true;
        }
        capture.gf_current = capture.gf_maximum = 0;
        return;
    }
    reported[character] = false;
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
        capture.gf_maximum = maximum;
        capture.gf_current = std::min(current, maximum);
    }
}

std::uint32_t __cdecl battle_row_hook(std::uint8_t *row, std::uint32_t a, std::uint32_t b, int state)
{
    const auto actor = row[0x48];
    g_hp_row = nullptr;
    if (actor < 3) {
        auto &capture = g_hp_rows[actor];
        capture = {};
        // 004B0C0B reads the name area's origin. 004B0CCF..004B0CF0
        // right-aligns the name inside its 96-pixel area using row+0x4A.
        // Use that visible name edge, not the empty area's left edge.
        capture.name_right = *reinterpret_cast<const std::uint16_t *>(row + 8) + 96.0f;
        capture.left = capture.name_right
            - *reinterpret_cast<const std::uint16_t *>(row + 0x4A);
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

// Native main-menu PLAY clock: renderer state, display list, packet cursor,
// x, y, seconds, and playtime/countdown selector.
using ClockRenderer = std::uint32_t(__cdecl *)(void *, std::uint32_t,
    std::uint32_t, std::uint32_t, std::uint32_t, std::uint32_t, std::uint32_t);
ClockRenderer g_clock_renderer = nullptr;

std::uint32_t __cdecl main_menu_clock_hook(void *state, std::uint32_t display_list,
    std::uint32_t cursor, std::uint32_t x, std::uint32_t y,
    std::uint32_t seconds, std::uint32_t playtime)
{
    const auto *mode = getmode_cached();
    if (enable_ff8_ingame_time && playtime != 0 && mode != nullptr &&
        mode->driver_mode == MODE_MENU) {
        const std::time_t now = std::time(nullptr);
        std::tm local{};
        if (localtime_s(&local, &now) == 0) {
            seconds = static_cast<std::uint32_t>(
                local.tm_hour * 3600 + local.tm_min * 60 + local.tm_sec);
        }
    }
    return g_clock_renderer(state, display_list, cursor, x, y, seconds, playtime);
}

// Capture native widget coordinates and viewport, not guessed screen positions.
struct MenuXpRow { float x, y, width, fraction; sprite_viewport viewport; };
std::array<MenuXpRow, 32> g_menu_xp;
std::size_t g_menu_xp_count = 0;
void capture_menu_xp(float x, float y, float width, float fraction)
{
    const auto *mode = getmode_cached();
    if (!mode || mode->driver_mode != MODE_MENU || !g_active_viewport ||
        !*g_active_viewport || g_menu_xp_count == g_menu_xp.size()) return;
    g_menu_xp[g_menu_xp_count++] = {x,y,width,fraction,**g_active_viewport};
}
float gf_xp_fraction(unsigned gf)
{
    if (gf >= 16) return 0;
    const auto *saved = reinterpret_cast<const std::uint8_t *>(0x01CFDCA8 + gf * 68);
    if (!(saved[0x11] & 1)) return 0;
    const auto exp = *reinterpret_cast<const std::uint32_t *>(saved + 0xC);
    const auto level = reinterpret_cast<int(__cdecl *)(int,int)>(0x004960C0);
    const int current = level(exp,gf);
    if (current >= 100) return 1;
    const auto boundary = [&](int wanted) {
        unsigned low=0, high=kMaxSearchExp;
        while(low<high) { const auto mid=low+(high-low)/2;
            if(level(mid,gf)>=wanted) high=mid; else low=mid+1; }
        return low;
    };
    const auto low=boundary(current), high=boundary(current+1);
    return high>low ? static_cast<float>(std::clamp(exp,low,high)-low)/(high-low) : 0;
}
using CharacterWidget = std::uint32_t(__cdecl *)(unsigned,unsigned,int,int,const std::uint8_t *,const void *,unsigned);
std::uint32_t __cdecl character_widget_hook(unsigned display,unsigned cursor,int x,int y,
    const std::uint8_t *saved,const void *stats,unsigned flags)
{
    const auto base=reinterpret_cast<std::uintptr_t>(&ff8_externals.savemap->chars[0]);
    const auto address=reinterpret_cast<std::uintptr_t>(saved);
    if(address>=base && (address-base)%sizeof(savemap_ff8_character)==0) {
        const auto id=(address-base)/sizeof(savemap_ff8_character);
        if(id<CHAR_NUM) capture_menu_xp(x+79,y+88,70,
            xp_fraction(ff8_externals.savemap->chars[id].exp,static_cast<std::uint8_t>(id)));
    }
    return reinterpret_cast<CharacterWidget>(0x004C0780)(display,cursor,x,y,saved,stats,flags);
}
using MainRowWidget = std::uint32_t(__cdecl *)(const std::uint8_t *,unsigned,unsigned,int);
template<unsigned Address, int Spacing>
std::uint32_t __cdecl main_row_hook(const std::uint8_t *state,unsigned display,unsigned cursor,int slot)
{
    if(slot>=0 && slot<3) {
        const auto id=state[0x35+slot];
        if(id<CHAR_NUM) capture_menu_xp(40,34+Spacing*slot+23,65,
            xp_fraction(ff8_externals.savemap->chars[id].exp,id));
    }
    return reinterpret_cast<MainRowWidget>(Address)(state,display,cursor,slot);
}
using ReserveWidget = std::uint32_t(__cdecl *)(const std::uint8_t *,unsigned,unsigned);
std::uint32_t __cdecl reserve_widget_hook(const std::uint8_t *state,unsigned display,unsigned cursor)
{
    for(unsigned slot=0;slot<8;++slot) {
        const auto id=state[0x38+slot];
        if(id<CHAR_NUM) capture_menu_xp(41+120*(slot%2),128+24*(slot/2),50,
            xp_fraction(ff8_externals.savemap->chars[id].exp,id));
    }
    return reinterpret_cast<ReserveWidget>(0x004C2090)(state,display,cursor);
}
using GfListWidget = std::uint32_t(__cdecl *)(unsigned,unsigned,int,int,unsigned,unsigned);
std::uint32_t __cdecl gf_list_hook(unsigned display,unsigned cursor,int x,int y,unsigned gf,unsigned level)
{
    if(gf<16) capture_menu_xp(x-2,y+64,36,gf_xp_fraction(gf));
    return reinterpret_cast<GfListWidget>(0x004D3E40)(display,cursor,x,y,gf,level);
}
using GfDetailWidget = std::uint32_t(__cdecl *)(void *,unsigned,unsigned,int,int,unsigned);
std::uint32_t __cdecl gf_detail_hook(void *state,unsigned display,unsigned cursor,int x,int y,unsigned gf)
{
    if(gf<16) capture_menu_xp(x+79,y+88,70,gf_xp_fraction(gf));
    return reinterpret_cast<GfDetailWidget>(0x004D41B0)(state,display,cursor,x,y,gf);
}
void draw_menu_xp()
{
    for(std::size_t i=0;i<g_menu_xp_count;++i) {
        const auto &row=g_menu_xp[i]; const auto &v=row.viewport;
        draw_bar(row.x*v.scale_x+v.offset_x,row.y*v.scale_y+v.offset_y,
            row.width*v.scale_x, v.scale_y,row.fraction,IM_COL32(224,192,48,255));
    }
    g_menu_xp_count=0;
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
        // Only rows the native HUD drew this frame.
        if (!(row.hp_visible || row.atb_visible) ||
            row.viewport.scale_x <= 0 || row.viewport.scale_y <= 0) continue;
        const auto &v = row.viewport;
        // A gauge spans the thing it measures and fills by current/max. It
        // used to be anchored at the ATB gauge's far end and shortened by
        // max/9999, so a 479-HP character got a two-pixel stub floating past
        // the end of the ATB frame instead of a bar under its HP.
        auto draw_line = [&](std::uint32_t current, std::uint32_t maximum,
                             float native_left, float native_right, float native_y, ImU32 color) {
            if (!maximum || native_right <= native_left) return;
            const float left = scale_x(native_left * v.scale_x + v.offset_x);
            const float right = scale_x(native_right * v.scale_x + v.offset_x);
            const float top = native_y * v.scale_y + v.offset_y;
            const float fraction = std::min(1.0f, current / static_cast<float>(maximum));
            const float filled = (right - left) * fraction;
            if (filled <= 0) return;
            auto *draw = ImGui::GetForegroundDrawList();
            // Match the menu HP gauge: two thin parallel lines with a clear
            // gap. The unfilled part stays transparent, without a black track.
            for (int rail = 0; rail < 2; ++rail) {
                const float y = top + rail * 2.0f * v.scale_y;
                draw->AddRectFilled(ImVec2(left, scale_y(y)),
                    ImVec2(left + filled, scale_y(y + v.scale_y)), color);
            }
        };
        // Native rows are 15 pixels high (004B0FF6) and spaced by 15
        // (004B1978). Text starts at row_y+2 and is 12 pixels high, so the
        // red rails sit on the row's final pixel, under the HP digits. The
        // number is right-aligned; the bar spans a full four-digit field
        // ending where the digits end, so every row's bar has one length.
        if (enable_ff8_hp_bars && row.hp_visible && row.hp_right > row.hp_left) {
            const float field = std::max(row.hp_right - row.hp_left, 4.0f * row.digit);
            draw_line(row.current, row.maximum, row.hp_right - field, row.hp_right,
                row.top + 14.0f, IM_COL32(236, 0, 0, 255));
        }
        // Both blue rails fit above the name, whose text starts at row_y+2,
        // and span the name's own area.
        if (enable_ff8_gf_hp_bars && row.name_right > row.left)
            draw_line(row.gf_current, row.gf_maximum, row.left, row.name_right,
                row.top - 1.0f, IM_COL32(48, 128, 255, 255));
    }
}

} // namespace

bool lexeditor_ff8_bars_enabled()
{
    return ff8 && (enable_ff8_xp_bars || enable_ff8_hp_bars || enable_ff8_gf_hp_bars || enable_ff8_ingame_time);
}

void lexeditor_ff8_bars_install()
{
    if (!ff8 || (!enable_ff8_xp_bars && !enable_ff8_hp_bars && !enable_ff8_gf_hp_bars && !enable_ff8_ingame_time)) {
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
    if (enable_ff8_ingame_time && FF8_US_VERSION &&
        original_call(0x004C1C6E, 0x004BF020)) {
        g_clock_renderer = reinterpret_cast<ClockRenderer>(get_relative_call(0x004C1C6E, 0));
        replace_call(0x004C1C6E, reinterpret_cast<void *>(&main_menu_clock_hook));
    }
    if (!enable_ff8_xp_bars) return;

    if (FF8_US_VERSION) {
        const auto hook = [&](unsigned address,unsigned target,void *replacement) {
            if(original_call(address,target)) replace_call(address,replacement);
            else ffnx_error("XP Bars: unsupported widget call at %08X\n",address);
        };
        for(const unsigned call : {0x4C08F4U,0x4CB66CU,0x4CC846U,0x4F6E8EU,0x4F6F17U,0x4F7361U,0x4F73EEU})
            hook(call,0x4C0780,reinterpret_cast<void *>(&character_widget_hook));
        hook(0x4C1ADA,0x4C1D50,reinterpret_cast<void *>(&main_row_hook<0x4C1D50,26>));
        hook(0x4C1AC2,0x4C1ED0,reinterpret_cast<void *>(&main_row_hook<0x4C1ED0,52>));
        hook(0x4C1AED,0x4C2090,reinterpret_cast<void *>(&reserve_widget_hook));
        hook(0x4D3DB5,0x4D3E40,reinterpret_cast<void *>(&gf_list_hook));
        for(const unsigned call : {0x4D3D34U,0x4D3D4AU})
            hook(call,0x4D41B0,reinterpret_cast<void *>(&gf_detail_hook));
    }
    g_after_battle_renderer = reinterpret_cast<AfterBattleRenderer>(
        get_relative_call(ff8_externals.battle_menu_sub_4A3D20, 0x139));
    g_result_state = reinterpret_cast<ResultState>(get_relative_call(
        reinterpret_cast<std::uintptr_t>(g_after_battle_renderer), 0x9));
    g_active_viewport = reinterpret_cast<sprite_viewport **>(get_absolute_value(
        ff8_externals.engine_reset_viewport_sub_4972D0, 0x12));
    const auto row_call = reinterpret_cast<std::uintptr_t>(g_after_battle_renderer) + 0x2BD;
    g_result_row_renderer = reinterpret_cast<ResultRowRenderer>(get_relative_call(row_call, 0));
    replace_call(row_call, reinterpret_cast<void *>(&result_row_renderer_hook));
    replace_call(ff8_externals.battle_menu_sub_4A3D20 + 0x139,
        reinterpret_cast<void *>(&after_battle_renderer_hook));
}

void lexeditor_ff8_bars_draw()
{
    if (enable_ff8_hp_bars || enable_ff8_gf_hp_bars) {
        draw_battle_hp();
    }
    if (enable_ff8_xp_bars) {
        draw_menu_xp();
        switch (g_capture.surface) {
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
    g_menu_xp_count = 0;
    g_hp_rows = {};
}
