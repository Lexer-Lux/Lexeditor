# Worklog: Todo 190

## #190 MobProbe + per-model view — built and verified 2026-08-05

Why a probe at all: the model -> archetype binding was proven absent from the
data by exhaustion. `HEALTH_*` names occur nowhere in `_downloads/extract`
except `pedhealth.meta`, and only 6 times in all of `script_rel`
(`_SET_PED_HEALTH_CONFIG` in `gang3.c` and `odriscolls4.c`). No getter native
exists — a scan of `natives.json` returns only the setter plus
`GET_PED_MAX_HEALTH` (`0x4700A416E8324EF3`). So observation is the only route.

`tools/build_ped_model_list.py` sweeps the ambient/dispatch/persistent-character
files for `A|U|S|G|CS_[MF]_[MFY]_name_NN` and unions them: 253 distinct models
(126 ambient, 71 unique, 42 scenario, 14 gang, including `G_M_M_UNIDUSTER_01/02/03`
= the O'Driscolls). Explicitly NOT the game's full model list; the probe's
passive pass covers the remainder.

`MobProbe/` — standalone throwaway ASI, mirroring StealthProbe's scaffolding.
State machine per model: request -> wait load (4 s timeout) -> spawn at player
z-150 invisible/frozen/no-collision -> wait 120 ms -> `GET_PED_MAX_HEALTH` ->
delete -> release model. Rows stream to `mob_stats.csv` on write, not at the
end. `worldGetAllPeds` pass every 1.5 s records unrostered models by hash to
`mob_stats_discovered.csv` (no native resolves a model hash back to a name, so
no name is invented). Auto-starts 3 s after a player ped exists — no ini switch,
no arming key, per the "do not make Lexer babysit the loop" rule. F8 aborts.
HUD progress uses the `_SET_TEXT_COLOR` + `VAR_STRING` + `_DISPLAY_TEXT` path
StealthProbe proved works in retail; the UIDEBUG natives draw nothing.

Every native hash was re-verified against `natives.json` for name, params and
return type before use. First verification pass reported all 22 as NOT FOUND —
that was a bug in the lookup script (`.upper()` on the whole key uppercases the
`0x` prefix, and the JSON keys use a lowercase `x`), not a missing native.

Built with `MobProbe/build.bat` (exit 0, `vswhere` warning as documented).
Installed to the game root by `install-after-rdr2-exit.ps1`; RDR2 was not
running, so it copied immediately. Hash verified equal:
`3C698DECE1D9692191C3703A0037555782DA1BD62583346B1B676EB2209C030D`.

Editor: `get_mob_models` / `apply_mob_model_overrides` in `server.py`, routes
`GET /api/mob-models` and `POST /api/mob-models/save`; `renderMobModels` plus a
`mobView` split in `editor.html`. Overrides land in
`GameplayTweaks/mob_archetype_overrides.csv` (model,archetype), same shape as
`merchant_buy_overrides.csv`. `_health_by_hp` maps observed HP to ALL matching
archetypes; `effective` is only auto-filled when exactly one matches.

Verified on a second server instance (port 8799; Lexer's editor stayed up on
8765): endpoint 200 with 253 models / 37 archetypes / probeAvailable false
pre-sweep; with a simulated `mob_stats.csv`, HP 70 correctly returned all five
sharing archetypes and 75 returned six, both left ambiguous rather than guessed;
override write round-tripped to CSV and back into `effective`; an invalid
archetype name was rejected with a ValueError. In the browser: Mobs/Archetypes
subtabs both render, no console errors, dropdown -> header save -> correct row
on disk, Archetypes still shows `GANG_ODRISCOLLS` at 0.600000. All test
artifacts (`mob_stats.csv`, `mob_archetype_overrides.csv`) removed afterwards.

NOT BUILT: the GameplayTweaks side that consumes the override CSV and calls
`_SET_PED_HEALTH_CONFIG` at spawn. The editor says so on the tab rather than
implying the dropdown does something. Mission scripts that set their own config
will win against it whenever they run later.

## #190 Mobs tab — built and verified 2026-08-04

Built: `editor/server.py` gains `parse_with_comments`, `_mob_group`,
`_record_fields`, `_combat_records`, `_pedhealth_records`, `_mob_source`,
`get_mobs`, `MOB_FILES`, `apply_mob_edits`, plus `GET /api/mobs` and
`POST /api/mobs/save`. `editor/editor.html` gains the `mobs` nav button, TABS
entry, TAB_CONTEXT entry, `state.mobs` / `state.mobEdits`, a `dirtyCount()`
term, a `saveAllChanges()` branch, and `renderMobs` / `saveMobs`.

`parse_with_comments` exists because `load_file` parses with
`insert_comments=True` while a plain `ET.parse` does not. Index paths are
positional, so a vanilla fallback parsed without comments would shift every
path by one per preceding comment and write to the wrong node on the first
save. `lootconfigdata.meta` and `combatbehaviour.meta` both contain comments.

Verified against a second server instance on port 8799 (Lexer's own editor was
live on 8765 and was not touched):

- `get_mobs('mine')` -> combat 40 records from `ai/combatbehaviour.meta`,
  health 86 records from the vanilla `pedhealth.meta` extract.
- Index path resolution: `[0, 13, 14]` resolves to `WeaponAccuracy` inside the
  record whose `Name` is `GANG_ODRISCOLLS`.
- Grouping: combat 38 humans / 2 animals; `HealthConfig` 18 animals /
  17 humans / 2 other (`FLAMMABLE`, `HEALTH_MOONSHINE_BARBRAWL` — correctly
  refused a mob group rather than being forced into one).
- Browser: Mobs tab renders, no console errors. Combat profiles Humans shows
  38 rows with `GANG_ODRISCOLLS` accuracy `0.600000` against `PLAYER`
  `0.100000`. Health archetypes shows `HEALTH_ENEMY_EASIEST` 50 HP,
  `HEALTH_ENEMY_HARDEST` 70 HP; Animals shows 18 rows, bear 261, legendary 850.
- End to end: edited O'Driscoll accuracy to `0.850000` in the UI, pressed the
  header save, confirmed `<WeaponAccuracy value="0.850000" />` on disk in
  `MyOverhaul/ai/combatbehaviour.meta`, then reverted with `git checkout` and
  removed the `.bak` `save_file` created. Repo left clean.

`save_file` collapses `<Tag  value=` to `<Tag value=` on 27 lines of
`combatbehaviour.meta` — an ElementTree serialization artifact, present for any
editor save of that file, not introduced here and not a value change.

Not done, deliberately: `loadouts.meta` (304 KB, which ped carries which
weapon) is the second slice of #171 and is not in this tab. No enemy value was
retuned; the tab only exposes them.

Correction recorded because it caused a wrong claim to be written down: an
earlier pass in this session concluded from `pedaccuracy.meta` alone that
enemies have no per-faction accuracy, and shipped that assertion in draft help
text. `combatbehaviour.meta` — already in the AI tab and already named in
`DATA_MAP.md` — disproves it. Settled result is in `CODEX.txt` under
"Enemy accuracy, health and the Mobs tab".

