# Worklog: 058 Researched Game Data Map 2026 07 11

## Researched game-data map (2026-07-11)

- `DATA_MAP.md` is no longer an auto-generated XML-class dump. It is assembled
  from 13 manually researched subsystem reports under `_analysis/`.
- The effective merged set is 1,263 files (`common_0/data` plus update
  overrides). `_downloads/audit_data_map.py` verifies exact-path coverage;
  current result is 1,263/1,263 (100%).
- Required description standard: gameplay system controlled, concrete edits
  enabled, confidence/evidence, precedence/conflict notes, and web references
  where available. Root class names alone are not useful descriptions.
- Build with `_downloads/build_researched_data_map.py`. Do not overwrite it
  with the old `_downloads/gen_datamap.py` schema-summary output.

- CoreVignetteRamp: v1 AND v2 pulsed — CONFIRMED the throb is baked into the
  vanilla PlayerRPGEmptyCore* effect assets (ANIMPOSTFX_SET_STRENGTH only
  scales the breathing amplitude, can't stop it). Do NOT revisit animpostfx
  for this. v3 abandons animpostfx entirely and draws OUR OWN vignette:
  * corevignette.png (512² white RGB, radial alpha) built by
    _downloads/make_vignette_texture.py.
  * script.cpp DRAW_SPRITEs it fullscreen per enabled attribute each frame,
    tinted (ini ColorR/G/B) with alpha = emptiness ramp. Static = no pulse;
    3 draws blend = combine; full look control. Bars tracked as in v2.
  * Needs corevignette.ytd (PNG packed via OpenIV, game closed) dropped in
    lml/stream/ (that's where PDO's PDOR_ICONS.ytd lives) — and in
    MyOverhaul/stream/ for distribution. **YTD NOT YET BUILT; .asi installed
    but draws nothing until the ytd is streamed (safe no-op meanwhile).**
  * DRAW_SPRITE=0xC9884ECADE94CB34, REQUEST_STREAMED_TEXTURE_DICT=
    0xC1BA29DF5631B0F8, HAS..LOADED=0x54D6900929CCF162. Note: `TXD` is an SDK
    namespace — don't name identifiers TXD.
- Ambient-vignette removal (timecycle zeroing) **not yet tested in-game**.
- Editor multi-dataset tested via API + browser; vanilla dataset populated
  (4,990 items — base-game catalog version; Kiddo's set has 5,059 incl. 69
  post-1.0 DLC components and 349 vs 335 effects).
- MyOverhaul install.xml now has 67 file replacements (7 data + challenges +
  59 timecycle).
- Editor shows V/K (vanilla/Kiddo) reference values under editable fields in
  the "mine" dataset; click a reference to apply it. Hashed effect keys:
  ~16 of 310 recovered by brute-forcing family-pattern names against the
  joaat hash (shown with *); the rest are unnamed even in CodeX's DB —
  their readable `id` field is shown in the chip tooltip instead.
- Planned editor feature: a "mod settings" section to configure script-mod
  values (first customer: skills XP amounts — TODO item 2).

