#include "lexeditor_ff8_bars.h"
#include "lexeditor_ff8_hp_colors.h"

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <ctime>
#include <vector>

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


struct HpTintState {
    bool active = false;
    std::uint16_t current = 0;
    std::uint16_t maximum = 0;
};
HpTintState g_hp_tint;
HpTintState g_hp_number_previous;
bool g_hp_number_scope = false;
struct MenuHpContext {
    bool active = false;
    std::uint32_t packed_position = 0;
    std::uint16_t current = 0;
    std::uint16_t maximum = 0;
};
MenuHpContext g_menu_hp;
HpTintState g_main_menu_hp;
const std::uint8_t *g_reserve_menu_state = nullptr;
bool g_better_hp_runtime_ready = false;
constexpr std::uint32_t kCharacterWidget = 0x004C0780;
constexpr std::uint32_t kHpNumberRenderer = 0x004A3530;
std::uint32_t g_hp_number_renderer = kHpNumberRenderer;
std::uint32_t g_hp_number_replace_id = 0;
std::uint32_t g_hp_number_return = 0;

void hp_number_begin(const std::uint32_t *stack)
{
    g_hp_number_scope = false;
    if (stack == nullptr) return;
    g_hp_number_return = stack[0];
    if (!g_better_hp_runtime_ready || !enable_ff8_better_hp_colors ||
        !g_menu_hp.active || stack[3] != g_menu_hp.packed_position) return;
    g_hp_number_previous = g_hp_tint;
    g_hp_tint = {lexeditor_ff8_hp_should_tint(g_menu_hp.current, g_menu_hp.maximum),
        g_menu_hp.current, g_menu_hp.maximum};
    g_hp_number_scope = true;
}
void hp_number_end()
{
    if (!g_hp_number_scope) return;
    g_hp_tint = g_hp_number_previous;
    g_hp_number_scope = false;
}
void __declspec(naked) __cdecl hp_number_hook()
{
    __asm {
        pushad
        lea eax, [esp + 32]
        push eax
        call hp_number_begin
        add esp, 4
        popad
        pushfd
        pushad
        push g_hp_number_replace_id
        call unreplace_function
        add esp, 4
        popad
        popfd
        mov dword ptr [esp], offset hp_number_after_native
        jmp dword ptr [g_hp_number_renderer]
hp_number_after_native:
        pushfd
        pushad
        push g_hp_number_replace_id
        call rereplace_function
        add esp, 4
        call hp_number_end
        popad
        popfd
        push dword ptr [g_hp_number_return]
        ret
    }
}

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
    const auto previous = g_hp_tint;
    if (g_better_hp_runtime_ready && enable_ff8_better_hp_colors && g_hp_row != nullptr)
        g_hp_tint = {lexeditor_ff8_hp_should_tint(g_hp_row->current, g_hp_row->maximum),
            g_hp_row->current, g_hp_row->maximum};
    const auto result = g_hp_glyph_renderer(a, b, x, y);
    g_hp_tint = previous;
    return result;
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

// Measured vanilla reserve HP reference: a 48-native-pixel rail is 264
// screen pixels wide. Its five-row profile is opaque, 133/255, clear,
// opaque, 43/255. The clear center shows the panel, not a black slab.
// Keep that profile proportional to the captured native viewport.
void draw_gauge(float x, float y, float width, float pixel, float fraction, ImU32 fill, bool reverse = false)
{
    ImDrawList *draw = ImGui::GetForegroundDrawList();
    const float left = scale_x(x), right = scale_x(x + width);
    const float top = scale_y(y);
    if (right <= left) {
        return;
    }
    fraction = std::clamp(fraction, 0.0f, 1.0f);
    const float unit = scale_y(pixel) / 5.5f;
    const float split = reverse ? right - (right-left)*fraction : left + (right-left)*fraction;
    constexpr unsigned coverage[] = {255,133,0,255,43};
    for (int row=0; row<5; ++row) {
        if (!coverage[row]) continue;
        const float y0=top+row*unit, y1=top+(row+1)*unit;
        const auto color=(fill & ~IM_COL32_A_MASK) | (coverage[row]<<IM_COL32_A_SHIFT);
        const auto empty=IM_COL32(0,0,0,coverage[row]);
        // Adjacent regions avoid blending translucent color over black twice.
        if (split>left) draw->AddRectFilled(ImVec2(left,y0),ImVec2(split,y1),reverse?empty:color);
        if (split<right) draw->AddRectFilled(ImVec2(split,y0),ImVec2(right,y1),reverse?color:empty);
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
using ClockLabelRenderer = std::uint32_t(__cdecl *)(std::uint32_t,std::uint32_t,
    std::uint32_t,std::uint32_t,std::uint32_t,std::uint32_t,std::uint32_t);
ClockLabelRenderer g_clock_label_renderer = nullptr;
bool g_show_clock_time_label = false;

std::uint32_t __cdecl clock_label_hook(std::uint32_t display, std::uint32_t cursor,
    std::uint32_t label, std::uint32_t x, std::uint32_t y,
    std::uint32_t texture, std::uint32_t flags)
{
    // Native clock glyphs: 0x142 is PLAY, 0x146 is TIME (countdown clock).
    // Keep the playtime arithmetic; change only the label for our clock call.
    if (g_show_clock_time_label && label == 0x142) label = 0x146;
    return g_clock_label_renderer(display,cursor,label,x,y,texture,flags);
}

std::uint32_t __cdecl main_menu_clock_hook(void *state, std::uint32_t display_list,
    std::uint32_t cursor, std::uint32_t x, std::uint32_t y,
    std::uint32_t seconds, std::uint32_t playtime)
{
    const auto *mode = getmode_cached();
    const bool previous_label = g_show_clock_time_label;
    g_show_clock_time_label = false;
    if (enable_ff8_ingame_time && playtime != 0 && mode != nullptr &&
        mode->driver_mode == MODE_MENU) {
        const std::time_t now = std::time(nullptr);
        std::tm local{};
        if (localtime_s(&local, &now) == 0) {
            seconds = static_cast<std::uint32_t>(
                local.tm_hour * 3600 + local.tm_min * 60 + local.tm_sec);
            g_show_clock_time_label = true;
        }
    }
    const auto result = g_clock_renderer(state, display_list, cursor, x, y, seconds, playtime);
    g_show_clock_time_label = previous_label;
    return result;
}

// Capture native widget coordinates and viewport, not guessed screen positions.
struct MenuXpRow { float x, y, width, fraction; sprite_viewport viewport; bool hp; };
std::array<MenuXpRow, 32> g_menu_xp;
std::size_t g_menu_xp_count = 0;
void capture_menu_xp(float x, float y, float width, float fraction, bool hp = false)
{
    const auto *mode = getmode_cached();
    if (!mode || mode->driver_mode != MODE_MENU || !g_active_viewport ||
        !*g_active_viewport || g_menu_xp_count == g_menu_xp.size()) return;
    g_menu_xp[g_menu_xp_count++] = {x,y,width,fraction,**g_active_viewport,hp};
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
    MenuHpContext previous_hp = g_menu_hp;
    bool number_detour = false;
    if(address>=base && (address-base)%sizeof(savemap_ff8_character)==0) {
        const auto id=(address-base)/sizeof(savemap_ff8_character);
        if(id<CHAR_NUM) {
            if (enable_ff8_xp_bars) capture_menu_xp(x+79,y+88,70,
                xp_fraction(ff8_externals.savemap->chars[id].exp,static_cast<std::uint8_t>(id)));
            if (g_better_hp_runtime_ready && enable_ff8_better_hp_colors && stats != nullptr) {
                const auto *computed = reinterpret_cast<const std::uint16_t *>(stats);
                g_menu_hp = {true,
                    (static_cast<std::uint32_t>(static_cast<std::uint16_t>(y + 75)) << 16) |
                        static_cast<std::uint16_t>(x + 141),
                    computed[4], computed[5]};
                rereplace_function(g_hp_number_replace_id);
                number_detour = true;
            }
        }
    }
    const auto result = reinterpret_cast<CharacterWidget>(kCharacterWidget)(
        display,cursor,x,y,saved,stats,flags);
    if (number_detour) unreplace_function(g_hp_number_replace_id);
    g_menu_hp = previous_hp;
    return result;
}
using MainRowWidget = std::uint32_t(__cdecl *)(const std::uint8_t *,unsigned,unsigned,int);
template<unsigned Address, int Spacing>
std::uint32_t __cdecl main_row_hook(const std::uint8_t *state,unsigned display,unsigned cursor,int slot)
{
    if(slot>=0 && slot<3) {
        const auto id=state[0x35+slot];
        if(id<CHAR_NUM) {
            if(enable_ff8_xp_bars) capture_menu_xp(114,55+Spacing*slot,46,
                xp_fraction(ff8_externals.savemap->chars[id].exp,id));
            if(enable_ff8_hp_bars) {
                // The menu uses this 32-byte computed-stat record, including
                // junctions and abilities, for the HP X/Y text at x162.
                const auto *stats=reinterpret_cast<const std::uint16_t *>(0x01D771B0+32*id);
                const auto current=stats[4], maximum=stats[5];
                if(maximum) capture_menu_xp(164,55+Spacing*slot,92,
                    current/static_cast<float>(maximum),true);
            }
        }
    }
    return reinterpret_cast<MainRowWidget>(Address)(state,display,cursor,slot);
}
using ReserveWidget = std::uint32_t(__cdecl *)(const std::uint8_t *,unsigned,unsigned);
using MainHpWidget = std::uint32_t(__cdecl *)(int,int,unsigned,unsigned,int,int,unsigned);
using MenuText = std::uint32_t(__cdecl *)(unsigned,unsigned,int,int,const void *,unsigned);

// These three calls draw only the current HP digits. The HP label, slash,
// maximum and other numbers retain their native palette.
std::uint32_t __cdecl main_hp_widget_hook(int current,int maximum,unsigned display,
    unsigned cursor,int x,int y,unsigned palette)
{
    const auto previous=g_main_menu_hp;
    g_main_menu_hp={current>0 && maximum>current,
        static_cast<std::uint16_t>(std::max(0,current)),
        static_cast<std::uint16_t>(std::max(0,maximum))};
    const auto result=reinterpret_cast<MainHpWidget>(0x004BF380)(
        current,maximum,display,cursor,x,y,palette);
    g_main_menu_hp=previous;
    return result;
}

HpTintState reserve_hp_at(int x,int y)
{
    // 004C2090: x=32+120*column+59+16, y=112+24*row+12.
    if(!g_reserve_menu_state || x<107 || y<124 || (x-107)%120 || (y-124)%24)
        return {};
    const int column=(x-107)/120,row=(y-124)/24;
    if(column>1 || row>3)return {};
    const auto id=g_reserve_menu_state[0x38+row*2+column];
    if(id>=CHAR_NUM)return {};
    const auto *stats=reinterpret_cast<const std::uint16_t *>(0x01D771B0+32*id);
    return {lexeditor_ff8_hp_should_tint(stats[4],stats[5]),stats[4],stats[5]};
}

template<bool Reserve> std::uint32_t __cdecl main_hp_text_hook(unsigned display,
    unsigned cursor,int x,int y,const void *text,unsigned palette)
{
    const auto previous=g_hp_tint;
    if(g_better_hp_runtime_ready && enable_ff8_better_hp_colors)
        g_hp_tint=Reserve?reserve_hp_at(x,y):g_main_menu_hp;
    const auto result=reinterpret_cast<MenuText>(0x0049F850)(display,cursor,x,y,text,palette);
    g_hp_tint=previous;
    return result;
}

std::uint32_t __cdecl reserve_widget_hook(const std::uint8_t *state,unsigned display,unsigned cursor)
{
    for(unsigned slot=0;slot<8;++slot) {
        const auto id=state[0x38+slot];
        if(enable_ff8_xp_bars && id<CHAR_NUM) capture_menu_xp(44+120*(slot%2),138+24*(slot/2),48,
            xp_fraction(ff8_externals.savemap->chars[id].exp,id));
    }
    const auto *previous=g_reserve_menu_state;
    g_reserve_menu_state=state;
    const auto result=reinterpret_cast<ReserveWidget>(0x004C2090)(state,display,cursor);
    g_reserve_menu_state=previous;
    return result;
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
        if(row.hp ? enable_ff8_hp_bars : enable_ff8_xp_bars)
            draw_gauge(row.x*v.scale_x+v.offset_x,row.y*v.scale_y+v.offset_y,
                row.width*v.scale_x, v.scale_y,row.fraction,
                row.hp ? IM_COL32(236,0,0,255) : IM_COL32(224,192,48,255));
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
        draw_gauge(x + viewport.scale_x, bottom - 3.0f * viewport.scale_y,
            std::max(0.0f, (row.rect[2] - 2.0f) * viewport.scale_x), viewport.scale_y,
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
        auto draw_line = [&](std::uint32_t current, std::uint32_t maximum,
                             float native_left, float native_right, float native_y, ImU32 color, bool scaled_hp = false) {
            if (!maximum || native_right <= native_left) return;
            if(scaled_hp) native_left = native_right - (native_right-native_left)*
                std::min(maximum/9999.0f,1.0f);
            draw_gauge(native_left * v.scale_x + v.offset_x, native_y * v.scale_y + v.offset_y,
                (native_right - native_left) * v.scale_x, v.scale_y,
                current / static_cast<float>(maximum), color, scaled_hp);
        };
        // Native rows are 15 pixels high (004B0FF6) and spaced by 15
        // (004B1978). Text starts at row_y+2 and is 12 pixels high, so the
        // gauge starts on the row's last pixel, under the HP digits. The
        // number is right-aligned; the bar spans a full four-digit field
        // ending where the digits end, so every row's bar has one length.
        if (enable_ff8_hp_bars && row.hp_visible && row.hp_right > row.hp_left) {
            const float field = std::max(row.hp_right - row.hp_left, 4.0f * row.digit);
            draw_line(row.current, row.maximum, row.hp_right - field, row.hp_right,
                row.top + 14.0f, IM_COL32(236, 0, 0, 255), true);
        }
        // The blue gauge takes the two pixels above the name, whose text
        // starts at row_y+2, and spans the name's own area.
        if (enable_ff8_gf_hp_bars && row.name_right > row.left)
            draw_line(row.gf_current, row.gf_maximum, row.left, row.name_right,
                row.top, IM_COL32(48, 128, 255, 255));
    }
}

} // namespace

bool lexeditor_ff8_hp_colors_requested()
{
    return ff8 && enable_ff8_better_hp_colors;
}

void lexeditor_ff8_hp_colors_draw_paletted2D(
    struct polygon_set *polygon_set, struct indexed_vertices *iv, struct game_obj *game_object)
{
    if (!g_better_hp_runtime_ready || !enable_ff8_better_hp_colors ||
        !g_hp_tint.active || iv == nullptr) {
        common_draw_paletted2D(polygon_set, iv, game_object);
        return;
    }
    auto *ff8_iv = reinterpret_cast<ff8_indexed_vertices *>(iv);
    if (ff8_iv->vertices == nullptr || ff8_iv->palettes == nullptr ||
        ff8_iv->count == 0 || ff8_iv->vertexcount == 0) {
        common_draw_paletted2D(polygon_set, iv, game_object);
        return;
    }
    const auto white = static_cast<unsigned char>(text_colors[TEXTCOLOR_WHITE]);
    const auto yellow = static_cast<unsigned char>(text_colors[TEXTCOLOR_YELLOW]);
    for (std::uint32_t i=0;i<ff8_iv->count;++i)
        if (ff8_iv->palettes[i] != white && ff8_iv->palettes[i] != yellow) {
            common_draw_paletted2D(polygon_set, iv, game_object); return;
        }
    for (std::uint32_t i=0;i<ff8_iv->vertexcount;++i) {
        const auto &v=ff8_iv->vertices[i].color;
        if (v.r != 255 || v.g != 255 || v.b != 255) {
            common_draw_paletted2D(polygon_set, iv, game_object); return;
        }
    }
    std::vector<unsigned char> palettes(ff8_iv->palettes,ff8_iv->palettes+ff8_iv->count);
    std::vector<std::uint32_t> colors; colors.reserve(ff8_iv->vertexcount);
    for(std::uint32_t i=0;i<ff8_iv->vertexcount;++i) colors.push_back(ff8_iv->vertices[i].color.color);
    const auto rgb=lexeditor_ff8_hp_rgb(g_hp_tint.current,g_hp_tint.maximum);
    std::fill_n(ff8_iv->palettes,ff8_iv->count,white);
    for(std::uint32_t i=0;i<ff8_iv->vertexcount;++i) {
        ff8_iv->vertices[i].color.r=rgb.r;ff8_iv->vertices[i].color.g=rgb.g;ff8_iv->vertices[i].color.b=rgb.b;
    }
    common_draw_paletted2D(polygon_set, iv, game_object);
    std::copy(palettes.begin(),palettes.end(),ff8_iv->palettes);
    for(std::uint32_t i=0;i<ff8_iv->vertexcount;++i) ff8_iv->vertices[i].color.color=colors[i];
}

bool lexeditor_ff8_bars_enabled()
{
    return ff8 && (enable_ff8_xp_bars || enable_ff8_hp_bars || enable_ff8_gf_hp_bars || enable_ff8_ingame_time);
}

void lexeditor_ff8_bars_install()
{
    if (!ff8 || (!enable_ff8_xp_bars && !enable_ff8_hp_bars && !enable_ff8_gf_hp_bars &&
        !enable_ff8_ingame_time && !enable_ff8_better_hp_colors)) return;
    g_better_hp_runtime_ready=false;
    g_active_viewport=reinterpret_cast<sprite_viewport **>(get_absolute_value(
        ff8_externals.engine_reset_viewport_sub_4972D0,0x12));
    const auto original_call=[](std::uintptr_t address,std::uintptr_t target) {
        return *reinterpret_cast<const std::uint8_t *>(address)==0xE8 && get_relative_call(address,0)==target;
    };
    const std::array<std::uint32_t,7> character_widget_calls={
        0x4C08F4U,0x4CB66CU,0x4CC846U,0x4F6E8EU,0x4F6F17U,0x4F7361U,0x4F73EEU};
    const bool battle_hp_supported=FF8_US_VERSION &&
        original_call(0x004B17D5,0x004B0F10) &&
        original_call(0x004B1100,0x004A7210) &&
        original_call(0x004B127B,0x004A7210);
    bool menu_hp_supported=FF8_US_VERSION;
    for(const auto call:character_widget_calls)
        menu_hp_supported=menu_hp_supported && original_call(call,kCharacterWidget);
    const bool main_hp_supported=original_call(0x004C1DF6,0x004BF380) &&
        original_call(0x004C1F78,0x004BF380) && original_call(0x004BF407,0x0049F850) &&
        original_call(0x004C22CD,0x0049F850) && original_call(0x004C1AED,0x004C2090);
    const bool better_hp_supported=battle_hp_supported && menu_hp_supported && main_hp_supported;
    if ((enable_ff8_hp_bars || enable_ff8_gf_hp_bars ||
        (enable_ff8_better_hp_colors && better_hp_supported)) && battle_hp_supported) {
        g_battle_row_renderer=reinterpret_cast<BattleRowRenderer>(get_relative_call(0x004B17D5,0));
        g_hp_glyph_renderer=reinterpret_cast<GlyphRenderer>(get_relative_call(0x004B1100,0));
        g_atb_glyph_renderer=reinterpret_cast<GlyphRenderer>(get_relative_call(0x004B127B,0));
        replace_call(0x004B17D5,reinterpret_cast<void *>(&battle_row_hook));
        replace_call(0x004B1100,reinterpret_cast<void *>(&hp_glyph_hook));
        replace_call(0x004B127B,reinterpret_cast<void *>(&atb_glyph_hook));
    }
    if(enable_ff8_better_hp_colors) {
        if(!better_hp_supported) ffnx_error("Better HP Colors: unsupported FF8 executable layout; leaving vanilla HP colors.\n");
        else {
            g_hp_number_replace_id=replace_function(kHpNumberRenderer,reinterpret_cast<void *>(&hp_number_hook));
            unreplace_function(g_hp_number_replace_id);g_better_hp_runtime_ready=true;
            replace_call(0x004C1DF6,reinterpret_cast<void *>(&main_hp_widget_hook));
            replace_call(0x004C1F78,reinterpret_cast<void *>(&main_hp_widget_hook));
            replace_call(0x004BF407,reinterpret_cast<void *>(&main_hp_text_hook<false>));
            replace_call(0x004C22CD,reinterpret_cast<void *>(&main_hp_text_hook<true>));
        }
    }
    if (enable_ff8_ingame_time && FF8_US_VERSION &&
        original_call(0x004C1C6E,0x004BF020) && original_call(0x004BF099,0x004B77C0)) {
        g_clock_renderer=reinterpret_cast<ClockRenderer>(get_relative_call(0x004C1C6E,0));
        g_clock_label_renderer=reinterpret_cast<ClockLabelRenderer>(get_relative_call(0x004BF099,0));
        replace_call(0x004BF099,reinterpret_cast<void *>(&clock_label_hook));
        replace_call(0x004C1C6E,reinterpret_cast<void *>(&main_menu_clock_hook));
    }
    if(FF8_US_VERSION && (enable_ff8_xp_bars || enable_ff8_hp_bars)) {
        if(original_call(0x4C1ADA,0x4C1D50)) replace_call(0x4C1ADA,reinterpret_cast<void *>(&main_row_hook<0x4C1D50,26>));
        if(original_call(0x4C1AC2,0x4C1ED0)) replace_call(0x4C1AC2,reinterpret_cast<void *>(&main_row_hook<0x4C1ED0,52>));
    }
    if(FF8_US_VERSION && (enable_ff8_xp_bars || g_better_hp_runtime_ready)) {
        const auto hook=[&](unsigned address,unsigned target,void *replacement) {
            if(original_call(address,target)) replace_call(address,replacement);
            else if(enable_ff8_xp_bars) ffnx_error("XP Bars: unsupported widget call at %08X\n",address);
        };
        for(const unsigned call:character_widget_calls) hook(call,kCharacterWidget,reinterpret_cast<void *>(&character_widget_hook));
    }
    if(FF8_US_VERSION && (enable_ff8_xp_bars || g_better_hp_runtime_ready) &&
        original_call(0x4C1AED,0x4C2090))
        replace_call(0x4C1AED,reinterpret_cast<void *>(&reserve_widget_hook));
    if (!enable_ff8_xp_bars) return;
    if(FF8_US_VERSION) {
        const auto hook=[&](unsigned address,unsigned target,void *replacement) {
            if(original_call(address,target)) replace_call(address,replacement);
            else ffnx_error("XP Bars: unsupported widget call at %08X\n",address);
        };
        hook(0x4D3DB5,0x4D3E40,reinterpret_cast<void *>(&gf_list_hook));
        for(const unsigned call:{0x4D3D34U,0x4D3D4AU}) hook(call,0x4D41B0,reinterpret_cast<void *>(&gf_detail_hook));
    }
    g_after_battle_renderer=reinterpret_cast<AfterBattleRenderer>(
        get_relative_call(ff8_externals.battle_menu_sub_4A3D20,0x139));
    g_result_state=reinterpret_cast<ResultState>(get_relative_call(
        reinterpret_cast<std::uintptr_t>(g_after_battle_renderer),0x9));
    g_active_viewport=reinterpret_cast<sprite_viewport **>(get_absolute_value(
        ff8_externals.engine_reset_viewport_sub_4972D0,0x12));
    const auto row_call=reinterpret_cast<std::uintptr_t>(g_after_battle_renderer)+0x2BD;
    g_result_row_renderer=reinterpret_cast<ResultRowRenderer>(get_relative_call(row_call,0));
    replace_call(row_call,reinterpret_cast<void *>(&result_row_renderer_hook));
    replace_call(ff8_externals.battle_menu_sub_4A3D20+0x139,reinterpret_cast<void *>(&after_battle_renderer_hook));
}

void lexeditor_ff8_bars_draw()
{
    if (enable_ff8_hp_bars || enable_ff8_gf_hp_bars) {
        draw_battle_hp();
    }
    if (enable_ff8_xp_bars || enable_ff8_hp_bars) draw_menu_xp();
    if (enable_ff8_xp_bars) {
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
