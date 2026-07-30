# Lexeditor

One standalone editor for the game files behind Lexer's Mods, with a per-game
plugin for each game.

## Why this exists

Every game needs its own file-format code, but the *shell* around it should not
be rewritten each time: project management, tabs, undo/redo, save, search,
diffing, validation, backups, and launching the game. Lexeditor is that shell,
plus one plugin per game.

The reusable fraction is smaller than it looks — expect the per-game plugin to
be most of each game's effort, because the formats share nothing. Warband is
space-separated integer opcode dumps; RDR2 is RAGE archives and binary
metadata. What is genuinely shared is the shell, a schema-driven table editor,
undo/redo, and the never-corrupt-the-original safety machinery.

## Layout

    games/warband/     Warband plugin
        paths.py           where the game and mod project live (env-overridable)
        dump_troops.py     every troop, including cut/commented-out content
        dump_infopages.py  extract a mod's own in-game manual
    out/               generated reports and dumps (git-ignored)

Core shell to follow. The parsers in the plugin are written to be the part a GUI
reuses, so nothing here gets thrown away when the UI lands.

## Warband plugin

Requires Python 3 (the Warband Module System itself needs 2.7; these tools do
not).

    python games\warband\dump_troops.py                  all troops
    python games\warband\dump_troops.py --cut             only cut content
    python games\warband\dump_troops.py --faction fac_undeads
    python games\warband\dump_infopages.py --list         installed modules
    python games\warband\dump_infopages.py BannerPage     extract its manual

`dump_troops.py` is validated against the game's own generated data: it reports
1072 active troops, matching `ID_troops.py` and the compiled `troops.txt`
exactly, plus 106 commented-out cut troops.

`dump_infopages.py` exists because most large Warband mods ship an in-game
manual describing their own features. Extracting that is a far better answer to
"what does this mod do" than diffing, which only surfaces changed numbers with
no labels attached.

Paths default to a Steam Warband install and `C:\Users\Lexer\Warbandmod`.
Override with `LEXEDITOR_WARBAND_ROOT`, `LEXEDITOR_MOD_PROJECT`, `LEXEDITOR_OUT`.

## Planned

- Desktop shell (framework decision pending: wrap existing HTML in pywebview or
  Tauri, versus a PySide6 rewrite)
- Troop and faction editing, including restoring cut content
- Save writes `settings.ini` and runs the mod build in one action
- RDR2 plugin, ported from the existing browser-based editor
