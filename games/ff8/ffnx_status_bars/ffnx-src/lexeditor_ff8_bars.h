#pragma once

// Install FF8 renderer observations. This function is safe when all options
// are disabled; it does not patch a renderer in that case.
void lexeditor_ff8_bars_install();

// Draw the captured FF8 bars inside FFNx's active ImGui frame.
void lexeditor_ff8_bars_draw();

// Tell Renderer whether FFNx must create an ImGui frame for the bars.
bool lexeditor_ff8_bars_enabled();

struct polygon_set;
struct indexed_vertices;
struct game_obj;

// FF8's driver points here only while Better HP Colors is enabled. The
// implementation delegates unchanged unless an audited HP-number scope is live.
void lexeditor_ff8_hp_colors_draw_paletted2D(
    struct polygon_set *, struct indexed_vertices *, struct game_obj *);
