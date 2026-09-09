"""One-shot guarded integration for FF8's local main-menu clock."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one integration seam, found {count}")
    return text.replace(old, new, 1)


def patch_menu_contract() -> None:
    path = ROOT / "games/ff8/menu_qol_issue_61.py"
    text = path.read_text(encoding="utf-8")
    old = '''INGAME_TIME_BLOCKER = (
    "In-game Time is unresolved: FF8 imports GetLocalTime at IAT 0x00B69178, "
    "but no proved live main-menu renderer handoff was found for both the PLAY "
    "label and its digits. Writing clock time to played_time_secs would alter save data."
)
'''
    new = '''# The old blocker was the absence of a proved live main-menu draw handoff.
# The FFNx derivative now owns one: the same guarded callback used by XP bars
# identifies the real in-game main menu and excludes the title save browser.
# The clock reads Windows local time only; it never touches played_time_secs.
INGAME_TIME_AVAILABLE = True
INGAME_TIME_BLOCKER = ""
'''
    path.write_text(replace_once(text, old, new, "in-game time availability"), encoding="utf-8", newline="\n")


def patch_bars_runtime() -> None:
    path = ROOT / "games/ff8/ffnx_status_bars/ffnx-src/lexeditor_ff8_bars.cpp"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include <cstdint>\n\n#include <imgui.h>\n',
        '#include <cstdint>\n#include <cstdio>\n#include <ctime>\n\n#include <imgui.h>\n',
        "clock includes",
    )
    text = replace_once(
        text,
        'void draw_main_menu_xp()\n{\n',
        '''void draw_main_menu_clock()
{
    const auto *mode = getmode_cached();
    if (mode == nullptr || mode->driver_mode != MODE_MENU) return;
    const std::time_t now = std::time(nullptr);
    std::tm local{};
    if (localtime_s(&local, &now) != 0) return;
    char text[16]{};
    std::snprintf(text, sizeof text, "LOCAL %02d:%02d", local.tm_hour, local.tm_min);
    // The main menu is authored on FF8's 640x448 game surface. Keep the clock
    // in the lower-right information area, next to rather than on top of the
    // native PLAY/Gil block, and project it through FFNx's real viewport.
    const ImVec2 position(scale_x(500.0f), scale_y(412.0f));
    ImGui::GetForegroundDrawList()->AddText(
        position, IM_COL32(255, 255, 255, 255), text);
}

void draw_main_menu_xp()
{
''',
        "clock drawing function",
    )
    text = replace_once(
        text,
        '    return ff8 && (enable_ff8_xp_bars || enable_ff8_hp_bars || enable_ff8_gf_hp_bars);\n',
        '    return ff8 && (enable_ff8_xp_bars || enable_ff8_hp_bars || enable_ff8_gf_hp_bars || enable_ff8_ingame_time);\n',
        "bars enabled predicate",
    )
    text = replace_once(
        text,
        '    if (!ff8 || (!enable_ff8_xp_bars && !enable_ff8_hp_bars && !enable_ff8_gf_hp_bars)) {\n',
        '    if (!ff8 || (!enable_ff8_xp_bars && !enable_ff8_hp_bars && !enable_ff8_gf_hp_bars && !enable_ff8_ingame_time)) {\n',
        "runtime install gate",
    )
    text = replace_once(
        text,
        '    if (!enable_ff8_xp_bars) return;\n\n'
        '    // The callback entries contain PUSH-immediate renderer pointers. FFNx\n'
        '    // already resolves this same table from the supported executable.\n'
        '    const std::uint32_t main_callback = static_cast<std::uint32_t>(\n'
        '        reinterpret_cast<std::uintptr_t>(ff8_externals.menu_callbacks[16].func));\n'
        '    const std::uint32_t status_callback = static_cast<std::uint32_t>(\n'
        '        reinterpret_cast<std::uintptr_t>(ff8_externals.menu_callbacks[5].func));\n'
        '    g_main_menu_renderer = reinterpret_cast<MenuRenderer>(\n'
        '        get_absolute_value(main_callback, 0x3));\n'
        '    g_status_menu_renderer = reinterpret_cast<MenuRenderer>(\n'
        '        get_absolute_value(status_callback, 0x3));\n'
        '    g_after_battle_renderer = reinterpret_cast<AfterBattleRenderer>(\n'
        '        get_relative_call(ff8_externals.battle_menu_sub_4A3D20, 0x139));\n'
        '    g_result_state = reinterpret_cast<ResultState>(get_relative_call(\n'
        '        reinterpret_cast<std::uintptr_t>(g_after_battle_renderer), 0x9));\n'
        '    g_active_viewport = reinterpret_cast<sprite_viewport **>(get_absolute_value(\n'
        '        ff8_externals.engine_reset_viewport_sub_4972D0, 0x12));\n'
        '    const auto row_call = reinterpret_cast<std::uintptr_t>(g_after_battle_renderer) + 0x2BD;\n'
        '    g_result_row_renderer = reinterpret_cast<ResultRowRenderer>(get_relative_call(row_call, 0));\n'
        '    replace_call(row_call, reinterpret_cast<void *>(&result_row_renderer_hook));\n\n'
        '    patch_code_dword(main_callback + 0x3,\n'
        '        static_cast<std::uint32_t>(\n'
        '            reinterpret_cast<std::uintptr_t>(&main_menu_renderer_hook)));\n'
        '    patch_code_dword(status_callback + 0x3,\n'
        '        static_cast<std::uint32_t>(\n'
        '            reinterpret_cast<std::uintptr_t>(&status_menu_renderer_hook)));\n'
        '    replace_call(ff8_externals.battle_menu_sub_4A3D20 + 0x139,\n'
        '        reinterpret_cast<void *>(&after_battle_renderer_hook));\n',
        '''    if (!enable_ff8_xp_bars && !enable_ff8_ingame_time) return;

    // The callback entry contains a PUSH-immediate renderer pointer. The same
    // guarded hook can identify the real main-menu frame for XP bars and the
    // local clock; it explicitly excludes the title save-block browser.
    const std::uint32_t main_callback = static_cast<std::uint32_t>(
        reinterpret_cast<std::uintptr_t>(ff8_externals.menu_callbacks[16].func));
    g_main_menu_renderer = reinterpret_cast<MenuRenderer>(
        get_absolute_value(main_callback, 0x3));
    patch_code_dword(main_callback + 0x3,
        static_cast<std::uint32_t>(
            reinterpret_cast<std::uintptr_t>(&main_menu_renderer_hook)));
    if (!enable_ff8_xp_bars) return;

    const std::uint32_t status_callback = static_cast<std::uint32_t>(
        reinterpret_cast<std::uintptr_t>(ff8_externals.menu_callbacks[5].func));
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
    patch_code_dword(status_callback + 0x3,
        static_cast<std::uint32_t>(
            reinterpret_cast<std::uintptr_t>(&status_menu_renderer_hook)));
    replace_call(ff8_externals.battle_menu_sub_4A3D20 + 0x139,
        reinterpret_cast<void *>(&after_battle_renderer_hook));
''',
        "main menu hook split",
    )
    text = replace_once(
        text,
        '    if (enable_ff8_xp_bars) {\n        switch (g_capture.surface) {\n',
        '    if (enable_ff8_ingame_time && g_capture.surface == XpSurface::main_menu) {\n'
        '        draw_main_menu_clock();\n'
        '    }\n'
        '    if (enable_ff8_xp_bars) {\n        switch (g_capture.surface) {\n',
        "clock draw dispatch",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_prepare_build() -> None:
    path = ROOT / "tools/prepare_ff8_native_build.py"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "            ('bool enable_ff8_hp_bars;','bool enable_ff8_hp_bars;\\nbool enable_ff8_gf_hp_bars;'),\n"
        "            ('\\tenable_ff8_hp_bars = config[\"enable_ff8_hp_bars\"].value_or(false);',\n"
        "             '\\tenable_ff8_hp_bars = config[\"enable_ff8_hp_bars\"].value_or(false);\\n\\tenable_ff8_gf_hp_bars = config[\"enable_ff8_gf_hp_bars\"].value_or(false);'),\n",
        "            ('bool enable_ff8_hp_bars;','bool enable_ff8_hp_bars;\\nbool enable_ff8_gf_hp_bars;'),\n"
        "            ('\\tenable_ff8_hp_bars = config[\"enable_ff8_hp_bars\"].value_or(false);',\n"
        "             '\\tenable_ff8_hp_bars = config[\"enable_ff8_hp_bars\"].value_or(false);\\n\\tenable_ff8_gf_hp_bars = config[\"enable_ff8_gf_hp_bars\"].value_or(false);'),\n"
        "            ('bool enable_ff8_gf_hp_bars;','bool enable_ff8_gf_hp_bars;\\nbool enable_ff8_ingame_time;'),\n"
        "            ('\\tenable_ff8_gf_hp_bars = config[\"enable_ff8_gf_hp_bars\"].value_or(false);',\n"
        "             '\\tenable_ff8_gf_hp_bars = config[\"enable_ff8_gf_hp_bars\"].value_or(false);\\n\\tenable_ff8_ingame_time = config[\"enable_ff8_ingame_time\"].value_or(false);'),\n",
        "native cfg clock parser",
    )
    text = replace_once(
        text,
        "            ('extern bool enable_ff8_hp_bars;','extern bool enable_ff8_hp_bars;\\nextern bool enable_ff8_gf_hp_bars;'),\n",
        "            ('extern bool enable_ff8_hp_bars;','extern bool enable_ff8_hp_bars;\\nextern bool enable_ff8_gf_hp_bars;'),\n"
        "            ('extern bool enable_ff8_gf_hp_bars;','extern bool enable_ff8_gf_hp_bars;\\nextern bool enable_ff8_ingame_time;'),\n",
        "native cfg clock declaration",
    )
    text = replace_once(
        text,
        "            ('enable_ff8_hp_bars = false','enable_ff8_hp_bars = false\\n\\n# Blue junctioned-GF HP bar above each party name.\\nenable_ff8_gf_hp_bars = false'),\n",
        "            ('enable_ff8_hp_bars = false','enable_ff8_hp_bars = false\\n\\n# Blue junctioned-GF HP bar above each party name.\\nenable_ff8_gf_hp_bars = false'),\n"
        "            ('enable_ff8_gf_hp_bars = false','enable_ff8_gf_hp_bars = false\\n\\n# Show the computer local clock on FF8 main menu without changing PLAY time.\\nenable_ff8_ingame_time = false'),\n",
        "native TOML clock option",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_gameplay_settings() -> None:
    path = ROOT / "games/ff8/gameplay_settings.py"
    text = path.read_text(encoding="utf-8")
    text = replace_once(text, "DEFAULT_GF_HP_BARS = False\n", "DEFAULT_GF_HP_BARS = False\nDEFAULT_INGAME_TIME = menu_qol_issue_61.DEFAULT_INGAME_TIME\n", "clock default")
    text = replace_once(text, '    "damageLimitRemoval", "fastStart", "xpBars", "hpBars", "gfHpBars",\n', '    "damageLimitRemoval", "fastStart", "xpBars", "hpBars", "gfHpBars", "inGameTime",\n', "accepted clock tweak")
    text = replace_once(
        text,
        '    gf_hp_bars = data.get("gfHpBars", DEFAULT_GF_HP_BARS)\n    if not isinstance(gf_hp_bars, bool):\n        gf_hp_bars = DEFAULT_GF_HP_BARS\n',
        '    gf_hp_bars = data.get("gfHpBars", DEFAULT_GF_HP_BARS)\n    if not isinstance(gf_hp_bars, bool):\n        gf_hp_bars = DEFAULT_GF_HP_BARS\n'
        '    in_game_time = data.get("inGameTime", DEFAULT_INGAME_TIME)\n'
        '    if not isinstance(in_game_time, bool):\n'
        '        in_game_time = DEFAULT_INGAME_TIME\n',
        "load clock setting",
    )
    old_payload = '        "gfHpBars": gf_hp_bars,\n        "noMagicConsumption": no_magic_consumption,\n'
    new_payload = '        "gfHpBars": gf_hp_bars,\n        "inGameTime": in_game_time,\n        "noMagicConsumption": no_magic_consumption,\n'
    if text.count(old_payload) != 2:
        raise RuntimeError(f"load/save clock payload: expected two integration seams, found {text.count(old_payload)}")
    text = text.replace(old_payload, new_payload, 1)
    text = replace_once(
        text,
        '                             gf_hp_bars: bool = False,\n                             no_magic_consumption: bool = False) -> None:\n',
        '                             gf_hp_bars: bool = False,\n                             in_game_time: bool = False,\n                             no_magic_consumption: bool = False) -> None:\n',
        "runtime tweak clock argument",
    )
    text = replace_once(text, '        ("enable_ff8_gf_hp_bars", gf_hp_bars),\n', '        ("enable_ff8_gf_hp_bars", gf_hp_bars),\n        ("enable_ff8_ingame_time", in_game_time),\n', "runtime clock TOML writer")
    text = replace_once(text, '        "gfHpBars": False,\n        "noMagicConsumption": False,\n', '        "gfHpBars": False,\n        "inGameTime": False,\n        "noMagicConsumption": False,\n', "new project clock default")
    text = replace_once(
        text,
        '    gf_hp_bars = _boolean(data.get("gfHpBars", DEFAULT_GF_HP_BARS), "GF HP Bars")\n',
        '    gf_hp_bars = _boolean(data.get("gfHpBars", DEFAULT_GF_HP_BARS), "GF HP Bars")\n'
        '    in_game_time = _boolean(data.get("inGameTime", DEFAULT_INGAME_TIME), "In-game Time")\n',
        "save clock setting",
    )
    text = replace_once(text, '        "gfHpBars": gf_hp_bars,\n        "noMagicConsumption": no_magic_consumption,\n', '        "gfHpBars": gf_hp_bars,\n        "inGameTime": in_game_time,\n        "noMagicConsumption": no_magic_consumption,\n', "saved clock setting")
    text = replace_once(
        text,
        '        (shared_magic_inventory or xp_bars or hp_bars or gf_hp_bars or better_targeting or fast_start_enabled\n         or modern_controls or party_switch or no_magic_consumption)\n',
        '        (shared_magic_inventory or xp_bars or hp_bars or gf_hp_bars or in_game_time or better_targeting or fast_start_enabled\n         or modern_controls or party_switch or no_magic_consumption)\n',
        "clock runtime installation gate",
    )
    text = replace_once(
        text,
        '                game / "FFNx.toml", xp_bars=xp_bars, hp_bars=hp_bars, gf_hp_bars=gf_hp_bars,\n'
        '                better_targeting=better_targeting,\n',
        '                game / "FFNx.toml", xp_bars=xp_bars, hp_bars=hp_bars, gf_hp_bars=gf_hp_bars,\n'
        '                in_game_time=in_game_time, better_targeting=better_targeting,\n',
        "clock runtime config call",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_editor() -> None:
    path = ROOT / "games/ff8/editor.html"
    text = path.read_text(encoding="utf-8")
    text = replace_once(text, 'gfHpBars:state.data.settings.gfHpBars,noMagicConsumption:', 'gfHpBars:state.data.settings.gfHpBars,inGameTime:state.data.settings.inGameTime,noMagicConsumption:', "settings payload clock")
    text = replace_once(
        text,
        '    const gfHpBars=el("input",{type:"checkbox",checked:settings.gfHpBars,"aria-label":"GF HP Bars",onchange:event=>{settings.gfHpBars=event.target.checked;shell.refresh()}});\n',
        '    const gfHpBars=el("input",{type:"checkbox",checked:settings.gfHpBars,"aria-label":"GF HP Bars",onchange:event=>{settings.gfHpBars=event.target.checked;shell.refresh()}});\n'
        '    const inGameTime=el("input",{type:"checkbox",checked:settings.inGameTime,"aria-label":"In-game Time",onchange:event=>{settings.inGameTime=event.target.checked;shell.refresh()}});\n',
        "clock checkbox",
    )
    text = replace_once(
        text,
        '      row("GF HP BARS","Shows blue GF HP bars above party names, filling left to right. Uses the junctioned GF, or combined HP when multiple GFs are junctioned; includes damage during summoning.",gfHpBars,"boolean"),\n',
        '      row("GF HP BARS","Shows blue GF HP bars above party names, filling left to right. Uses the junctioned GF, or combined HP when multiple GFs are junctioned; includes damage during summoning.",gfHpBars,"boolean"),\n'
        '      row("IN-GAME TIME","Shows your computer local clock on the live FF8 main menu. It does not replace FF8\'s saved play-time counter.",inGameTime,"boolean"),\n',
        "clock settings row",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    patch_menu_contract()
    patch_bars_runtime()
    patch_prepare_build()
    patch_gameplay_settings()
    patch_editor()
    print("Integrated FF8 local main-menu clock")
