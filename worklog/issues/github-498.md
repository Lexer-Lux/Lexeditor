# Issue 498 — Separate SFX and Music volume sliders

## Requirements
Replace the single in-game Sound slider with separate SFX and Music sliders.
Each controls only its category; values persist across restart and stay
consistent with the active audio backend. Research menu + FFNx audio paths first.

## Findings (2026-09-22)
- FFNx.toml audio paths surveyed in the local install:
  - External SFX layer: `use_external_sfx = false`, `external_sfx_volume = -1`
    (auto), path `lexeditor-sfx`. Scales only external SFX files.
  - External music layer: `use_external_music = false`,
    `external_music_volume = -1`. Scales only external music files.
  - Both layers are disabled here; neither follows the vanilla menu slider.
- The vanilla menu Sound slider drives the game's internal audio path. No
  SFX/Music split point is known in the exe or codex (codex/ff8 has no audio
  knowledge). The `volume` byte in `plugins/ff8/init_data.py` is save config,
  not the menu slider.
- No implementation exists; nothing to remove or wire.

## Next work (agent)
Find the menu slider handler and the SFX vs music gain application points
in FF8_EN.exe (capstone+pefile available in .venv), then propose a
Hext/native patch. Acceptance needs audible in-game checks (each slider
isolated, persistence across restart) — that part will need Lexer.

## 2026-09-23 misc-fixes: flipped to waiting with concrete checklist

Per Lexer's rule (needs concrete Lexer-side work means waiting), posted the
exact game-session/decision checklist as a comment and swapped actionable
for waiting. A failed session returns it to actionable with evidence; a
passed session closes it subject to the merge workflow.
