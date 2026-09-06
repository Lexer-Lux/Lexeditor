#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <span>
#include <vector>
#include <cmath>
#include <cassert>
#include <cstdio>
#include <sys/mman.h>
#define __cdecl
#define FF8_US_VERSION true
#define CHAR_NUM 8
#define G_FORCE_NUM 16
#define IM_COL32(R,G,B,A) ((std::uint32_t(R))|(std::uint32_t(G)<<8)|(std::uint32_t(B)<<16)|(std::uint32_t(A)<<24))
using ImU32=std::uint32_t;
struct ImVec2 { float x,y; ImVec2(float a=0,float b=0):x(a),y(b){} };
struct Rect { ImVec2 lo,hi;ImU32 color; };
struct ImDrawList {
    std::vector<Rect> rectangles;
    void AddRectFilled(ImVec2 lo,ImVec2 hi,ImU32 c) { rectangles.push_back({lo,hi,c}); }
} draw_list;
namespace ImGui {
struct IO { ImVec2 DisplaySize{640,480}; } io;
static IO &GetIO(){return io;}
static ImDrawList *GetForegroundDrawList(){return &draw_list;}
}
struct Renderer {
    std::array<float,2> projectGamePointToScreen(float x,float y) {return {x/640,y/480};}
} newRenderer;
struct sprite_viewport { float width=0,height=0,field_8=0,field_C=0,scale_x=1,scale_y=1,offset_x=0,offset_y=0; };
struct ff8_char_computed_stats {
    std::uint8_t unk1[370]{};std::uint16_t curr_hp=0,max_hp=0;std::uint8_t tail[90]{};
};
struct savemap_ff8_character {
    std::uint16_t current_hp=0,max_hp=0;std::uint32_t exp=0;
    std::uint8_t padding[0x50]{};std::uint16_t gfs=0;
};
struct savemap_ff8_gf {
    std::uint8_t name[12]{};std::uint32_t exp=0;
    std::uint8_t unused=0,exists=0;std::uint16_t HPs=0;
};
struct SaveMap {
    savemap_ff8_character chars[8]{};savemap_ff8_gf gfs[16]{};
    std::uint8_t party[4]{};
} save_map;
std::array<ff8_char_computed_stats,3> stats;
struct Callback {void(*func)(int)=nullptr;};
struct Externals {
    SaveMap *savemap=&save_map;
    std::span<ff8_char_computed_stats> char_comp_stats_1CFF000{stats};
    std::uint8_t character_data_1CFE74C[3]{0,1,2};
    int(*get_char_level_4961D0)(int,int)=nullptr;
    std::uintptr_t engine_reset_viewport_sub_4972D0=0,battle_menu_sub_4A3D20=0;
    Callback menu_callbacks[17]{};
} ff8_externals;
static bool ff8=true,enable_ff8_hp_bars=true,enable_ff8_xp_bars=false,enable_ff8_gf_hp_bars=true;
constexpr int MODE_BATTLE=1,MODE_MENU=2;
struct Mode {int driver_mode=MODE_BATTLE;} mode;
static Mode *getmode_cached(){return &mode;}
static std::uintptr_t get_absolute_value(std::uintptr_t,int){return 0;}
static std::uintptr_t get_relative_call(std::uintptr_t,int){return 0;}
static void replace_call(std::uintptr_t,void*){}
static void patch_code_dword(std::uintptr_t,std::uint32_t){}
