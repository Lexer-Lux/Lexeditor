# GitHub #96 — Recon tagging for plants

## 2026-08-10 tag visibility distance

The live issue added a separate display-distance policy for completed recon
tags. This did not replace `MaxDistanceMeters`, which continued to control how
far away a new human, animal or plant could be acquired. The new settings were:

- `MaximumTagDisplayDistanceMeters`, validated to 1–10000 metres and defaulting
  to 1000 to preserve the existing visible range.
- `TagFadeStartPercent`, validated to 0–100 percent and defaulting to 75.

`ReconCachedSettings` loaded both through the existing two-real-second refresh
instead of touching the INI in a marker draw. A config log recorded the
effective values on startup and after a hot reload.

One common `reconTagDisplayOpacity(playerPos, tagPos)` curve was added at the
completed-tag render boundary. Ped tags use each entity's current world
position, which covers humans, animals, riders and horses. Plant tags use their
live visual/scenario world coordinates. Before and at the fade-start distance
the function returns alpha 255. Between fade start and the maximum it applies
`(maximum - distance) / (maximum - fadeStart)` linearly. At and beyond the
maximum it returns zero and the marker draw is skipped entirely. Integer alpha
is kept at least one for distances still strictly inside the maximum so
quantization cannot make a tag disappear early. A 100 percent fade start means
fully opaque below the maximum and absent exactly at it.

The common draw-site change preserved #2/#86's existing glyphs, textures,
rings, distance text and marker geometry. It also preserved #96's targeting,
multi-target dwell, plant catalogs and minimap blips; the new maximum governs
the completed world overlay only.

`editor/settings_schema.json` supplies clear player labels, metre/percent
ranges, validation, the 100 m / 75 percent example, independence from
acquisition distance and hot-reload semantics. The generic in-game settings
menu already assigns `m` and `%` from the exact `Meters` and `Percent` suffixes.
`GameplayTweaks/ini-fragments/github-96.ini` contains the integration defaults
without modifying the shared INI.

Static checks passed:

- `python tools/reverse-engineering/verify_recon_tag_visibility_issue_96.py`
- `python tools/reverse-engineering/verify_recon_plants_issue_96.py`
- `python -m json.tool editor/settings_schema.json`
- `git diff --check` on the issue-owned files

No build, install, shared dispatcher/INI/manifest edit or GitHub label change
was performed in this feature pass.

### Runtime acceptance

After integration and hash-verified installation, test completed human, animal,
mounted rider/horse and plant tags with multiple maximum/fade values. Confirm
full opacity below the fade start, smooth linear fading through the band, no
world tag at or beyond the maximum, reappearance when moving back inside, and
hot reload within about two real seconds. Build/static verification is not this
player-visible acceptance.

## Root cause (evidence first, code second)

### 1. The plant model table was fabricated

`recon.cpp` carried `kPlantModelNames[41]` under a comment asserting the names
were "copied verbatim" from a shipped model enumeration in
`fm_mission_controller` / `net_gun_for_hire_offline`.

Checked, not assumed:

- Neither file exists in `_downloads/RDR2-Decompiled-Scripts/script_rel/`.
  `ls | grep -i "fm_mission_controller\|net_gun_for_hire"` returns nothing.
  They are GTA Online script names.
- Grepping the entire decompiled Story Mode corpus, case-insensitive, for the
  names in that table (`THYME_P`, `VIOSNWDRP_P`, `S_VIOLETSNOWDROP01X`,
  `S_GINSENG01X`, `S_YARROW01X`, `ALASKANGINSENG_P`, `ORCHID_V_P`,
  `S_YARROW01_HERBALISTX`, ...) returns **zero** hits. The one apparent hit for
  `MILKWEED_P` is the substring inside `LEVDES_SPAWN_MILKWEED_PICKUP`
  (`campfire_always.c:18367`).

So `isKnownPlantModel()` compared live model hashes against 41 hashes of
invented strings. This is the Class-1 pattern in `fuckups.txt`.

### 2. A harvestable plant is a SCENARIO POINT, not an entity

Rockstar ships one pick script per species, `herb_<species>.c` (49 files). They
are identical apart from a species index:

- `herb_creeping_thyme.c:287` → `func_41(uParam0, 12)`
- `herb_evergreen_huckleberry.c:287` → `func_41(uParam0, 16)`

That single line is the **entire** diff between the two files Lexer named
(`diff herb_creeping_thyme.c herb_evergreen_huckleberry.c`).

The script's parameter is a scenario point id, and it never holds an entity
handle for the plant:

- `herb_evergreen_huckleberry.c:48` — `Var0.f_6 = ScriptParam_0.f_1;`
- `herb_evergreen_huckleberry.c:58` — `TASK::_DOES_SCENARIO_POINT_EXIST(ScriptParam_0.f_1)`
- `herb_evergreen_huckleberry.c:62` — `TASK::_GET_SCENARIO_POINT_COORDS(ScriptParam_0.f_1, true)`

The complete native list used by that script contains **no** `OBJECT::` native,
**no** pickup native and **no** `GET_ENTITY_MODEL`. Its species/definition table
resolves to `COMPOSITE_LOOTABLE_*_DEF` hashes (`herb_evergreen_huckleberry.c:2753-2800`).

Therefore:

- a plant is not a ped → the ped scan never enumerated it;
- a plant is not a script object or pickup → the object/pickup pool scan
  described in the previous worklog entry could never have found it, which is
  why the installed trace reported `plantobj=0 plantpickup=0`;
- the only path that ever produced a tag was the camera shape test, which
  returns the map-geometry entity under the reticle. That is why tagging worked
  at all and why it felt "weird and finnicky": it needed the probe to land on
  the mesh **and** the model hash to coincidentally match one of 41 invented
  hashes.

That is also the precise answer to "I can tag this creeping thyme but not this
evergreen huckleberry" — neither species was in the model table, so any success
was accidental, and nothing about huckleberry made it reachable.

### 3. The engine has a sanctioned, typed index of plants

This is Lexer's own observation ("rampage editor lets me spawn in plants at
will so there's clearly already a way of knowing what plants are"), and it is
correct. Scenario points are enumerable and typed:

| Native | Hash | natives.h |
|---|---|---|
| `_GET_SCENARIO_POINT_CLOSE_TO_COORDS` | `0x345EC3B7EBDE1CB5` | 7300 |
| `_GET_SCENARIO_POINT_TYPE` | `0xA92450B5AE687AAF` | 7394 |
| `_GET_SCENARIO_POINT_COORDS` | `0xA8452DD321607029` | 7289 |
| `_DOES_SCENARIO_POINT_EXIST` | `0x841475AC96E794D1` | 7284 |
| `_IS_SCENARIO_POINT_ACTIVE` | `0x0CC36D4156006509` | 7386 |
| `MAP::_BLIP_ADD_FOR_COORD` | `0x554D9D53F696D002` | 2809 |

The type table is shipped, not invented. Every `WB_*` name sits in Rockstar's
own scenario-type enumeration alongside `WORLD_HUMAN_*` and `PROP_HUMAN_*`:

- `campfire_always.c:20168` — `joaat("WB_BERRY_EVERGREEN_HUCKLEBERRY")`
- `campfire_always.c:20256` — `joaat("WB_SPICE_CREEPING_THYME")`
- duplicated at `campfire_gang.c:23362` and `campfire_gang.c:23450`

Proof that a `WB_*` name really is a scenario **type** and not a label: a live
call site passes one straight to the find-by-type native —
`act_fishing06.c:43764` passes `joaat("WB_GATOR_EGG_NEST")` to
`TASK::_FIND_CLOSEST_ACTIVE_SCENARIO_POINT_OF_TYPE`.

The shipped harvestable set (enumerated by grepping `"WB_[A-Z0-9_]*"` across the
corpus) is 4 berries, 22 herbs, 2 horse herbs, 4 mushrooms, 3 spices, 13
orchids, 18 flower entries — including both species Lexer named.

### 4. The white square

`drawReconObjectMarker` drew the glyph as texture `blip_ambient_herb` from txd
`blips`. **That texture does not exist.** `MyOverhaul/blipdata.ymt` — the
project's own stated authority for this dictionary — declares 737 `<Linkage>`
texture names; `blip_ambient_herb` is not among them in any casing, and neither
is the lowercase `blip_overlay_ring` that was used for the ring. `DRAW_SPRITE`
of a name the dictionary does not contain renders an untextured quad. That is
the white square, and it is the same wrong-name/wrong-dictionary defect as #23.

Lexer asked "Isn't there a white plant icon in the vanilla UI already?" — yes:

```
<Item key="BLIP_PLANT">
  <Linkage>BLIP_PLANT</Linkage>
  <TextureDictionary>blips</TextureDictionary>
```

## Changes (recon.cpp only)

- Replaced `kPlantModelNames` with `kPlantScenarioTypeNames` (the shipped `WB_*`
  harvestable table) and repurposed `g_plantModels` to hold scenario type
  hashes. `g_plantModels`, `g_plantModelsLoaded` and `learnPlantModels()` keep
  their names and signatures because `script.cpp` declares/calls them and this
  change does not own that file. `isKnownPlantModel` → `isKnownPlantScenarioType`.
- `ReconObjectTarget` now stores `scenarioPoint` / `scenarioType` / `coords`
  instead of an `Object` handle. Tag lifetime is the scenario point's lifetime,
  so a picked plant drops its tag without needing a "picked variant" model list.
- New `selectReconPlantScenarioPoint()` enumerates scenario points in radius,
  filters by the shipped type table, and picks the one nearest the reticle. No
  pool sweep, no persistent entity handles, no learner.
- Minimap marker is now `MAP::_BLIP_ADD_FOR_COORD(joaat("BLIP_PLANT"), ...)`
  instead of an entity blip with `BLIP_STYLE_PICKUP_ANIMAL`.
- Glyph is `BLIP_PLANT`, ring is `BLIP_OVERLAY_RING`, both with the casing
  blipdata.ymt declares.
- Marker lift is `[ReconTagging] PlantMarkerLiftCm` (default 85 cm), replacing
  the flat 0.35 m that put the icon inside the foliage.
- Diagnostics: a 5-second **idle heartbeat** on every early return
  (`disabled` / `unavailable` / `noplayer` / `notaiming`), so an empty log
  proves "not running" rather than "nothing found"; and the per-second scan line
  now names the entity classes consulted (`ped,scenario_point`) and reports
  plant candidates found and how many survived each gate
  (`plantPoints/exist/typed/inRange/projected/reticle/alreadyTagged`), plus one
  `rejectedType` hash per pass so a genuinely missing `WB_` entry is
  identifiable from the log rather than guessed at.

## Not done / open

- **Not compiled, not linked, not installed.** Static analysis only.
- The `Any*` out-buffer stride for `_GET_SCENARIO_POINT_CLOSE_TO_COORDS` is
  taken from the SDK declaration (`Any = uint64_t`, `types.h:12`); no call site
  exists in the decompiled corpus to confirm it. If the first scan line reports
  a nonzero `plantPoints` but `exist=0`, the stride is wrong and the buffer
  should be re-typed as `int[]`.
- Shared drawing code touched, for the integrator to serialize against #2/#86:
  `drawReconObjectMarker()` only (signature `Object` → `Vector3`, plus the two
  sprite names and the lift). `drawReconMarker()`, `drawReconArc()`,
  `drawReconDisc()`, `configureReconBlip()` and `reconAnimalBlipScale()` are
  untouched.

## Second white-square site, reported not fixed (belongs to #2, not #96)

`drawReconMarker()` — the **ped** tag — draws its health ring from
`kReconMeterTextureDict = "generic_textures"` with textures
`lex_fortification_meter_0..99`:

- `GameplayTweaks/modules/recon.cpp:631` — `static const char* const kReconMeterTextureDict = "generic_textures";`
- `recon.cpp:687` — the `HAS_STREAMED_TEXTURE_DICT_LOADED` gate
- `recon.cpp:693` — `sprintf_s(healthTexture, "lex_fortification_meter_%d", healthPercent);`
- `recon.cpp:696-698` — the dark backing draw, hard-coded to `lex_fortification_meter_99`
- `recon.cpp:730-731` — the live fill draw

Those textures are a custom build (`GameplayTweaks/icons/fortification/prepare_fortification_meters.py`
writes `lex_fortification_meter_1..99.dds`; `build_fortification_generic_textures.ps1`
packs them into `generic_textures.ytd`, staged at `MyOverhaul/stream/generic_textures.ytd`).
The shipped `.ytd` is an `RSC8` compressed resource so its texture names could
not be verified by inspection here — this is stated as unverified, not as
disproven. The proven pattern is the one `fortification_hud.cpp` now uses:
txd `rpg_meter`, textures `rpg_meter_0..99`, one `DRAW_SPRITE` after a
`HAS_STREAMED_TEXTURE_DICT_LOADED` / `REQUEST_STREAMED_TEXTURE_DICT` gate
(`fortification_hud.cpp:105-106, 260-261, 336-339`).

Separately, three sprite names in the same function are **confirmed absent**
from all 737 `<Linkage>` entries in `MyOverhaul/blipdata.ymt`:

- `recon.cpp:720` — `"blip_ambient_bounty_target"` (ABSENT)
- `recon.cpp:721` — `"blip_animal"` (ABSENT; `BLIP_ANIMAL` exists)
- `recon.cpp:722` — `"blip_ambient_companion"` (ABSENT)
- `recon.cpp:723` — `"blip_ambient_npc"` (ABSENT)

`"BLIP_HORSE_OWNED"` (`recon.cpp:716`) is present. Left alone: the ped tag's
appearance is #2's scope.

## Integration correction after runtime crash

The earlier SDK-based assumption about `_GET_SCENARIO_POINT_CLOSE_TO_COORDS`
was wrong. A runtime minidump proved that its undocumented out-buffer ABI
corrupted `selectReconPlantScenarioPoint`'s stack and ended in a `/GS`
stack-cookie fast-fail. Changing `Any[]` to another guessed array type was not a
valid repair, so the bulk native and caller-owned output buffer were removed.

The replacement retained the engine scenario index and the shipped WB_ type
table: the asynchronous reticle ray supplies a world hit, and a rate-limited
scan calls `_FIND_CLOSEST_ACTIVE_SCENARIO_POINT_OF_TYPE` once per known plant
type within three metres of that hit. The best valid point is cached and
revalidated between 250 ms scans so Study progress remains continuous. This
path returns a single handle per call and owns no native output array.

Development ASI
`BEB2B8D83DC829772957F3187C1D1C49A3B49BC0E126807D7E03DDAC75D9F446`
was built and installed while RDR2 was closed. Source, game-root ASI, and
release-manifest hashes matched. Static verification rejected the old bulk
native and required the fresh reticle hit, one-result typed query, point
deduplication, and 250 ms scan cadence. Plant acquisition and crash freedom
still required in-game confirmation.

## 2026-08-10 actionable correction: validated reticle visuals

The installed typed-scenario scan remained dead (`plantPoints=0`), but its same
live trace exposed the authoritative replacement: aimed model `0xF234A5A8` is
`s_inv_huckleberry01x`, and `0xD7063479` is `blackcurrant_p`. Both names are in
Rockstar's extracted `common_0_data/ai/looting/lootable_herbs.meta` and the
extracted object catalog.

Recon now prefers the actual reticle-hit object only when its model belongs to
the complete 154-model unlooted set derived from that metadata. The list omits
every `LootedOnly` entity and `UseRandomModelsSet`; a verifier reconstructs the
authoritative set from the XML and requires exact equality plus object-catalog
coverage, so invented names cannot silently return. The asynchronous reticle
entity is cached for at most 300 ms and revalidated for live handle plus
unchanged model on every use. The safe typed one-result scenario query remains
as fallback; the crashing bulk output-buffer native remains absent.

Entity-backed plant tags retain model and handle, disappear when the plant is
picked/replaced, use coordinate blips, and show the same eased acquisition
marker during dwell. `verify_recon_plants_issue_96.py` passes. This is build
evidence only; #96 remains `actionable` until the combined artifact is installed
and hash-verified.

## 2026-08-10 returned tagging feedback

Plant acquisition was confirmed working, but the same test exposed two ped-tag
defects. The binocular draw sets Rockstar's aim state before the scope camera is
up, so recon started filling tags during the pull-out animation. Recon now ignores
ordinary aim while a binocular weapon is equipped and only enables that path when
`g_binocularsActive` proves the scope is genuinely up; gun aiming remains valid.

Ped acquisition also used one `observed` clock and stopped scanning after a
single best candidate. A rider and mount therefore filled serially. Every valid
ped inside the reticle now owns an independent bounded dwell record, refreshed on
the 75 ms scan and dropped after 150 ms out of view. They can complete together;
the nearest candidate remains only the one whose Study progress is shown. The
static verifier rejects the old single-winner loop and requires both the scope-up
gate and independent observations. Runtime acceptance still covers rider/mount
parallel tagging and no visible progress during binocular draw.

The same feedback also confirmed the Cover input itself was allowed through
during the hold threshold, so Arthur began Rockstar's run-to-cover before the
binocular branch engaged. The shared binocular input owner now suppresses Cover
from the first physical down-frame and replays one native Cover pulse only when
the button is released before `HoldMs`. A real hold never reaches Cover.
## 2026-08-10 combined release

- Release ASI built successfully: `FC692F30C1EFB7B3DE5B101D08939FE1319676F2C50BD13768DAC948AAC43589`.
- RDR2 was running, so one hidden payload-only installer was queued. The issue remained actionable pending game-root hash verification.
- Current installed test artifact was later superseded, without an issue-owned source change, by `CDF66230508FBDB4AAF3A59D2B571A0229F6DD1E7FE7244F36AC9C6F7D0C23A2`.
