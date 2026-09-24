# Warband third-party references

Lexeditor does not bundle code or data from the following Module System mirror.
It is a public format/schema reference used to verify record fields and export
semantics before implementing Warband-specific editors.

## WarbandModuleSystem

- Repository: https://github.com/Sea-Monster/WarbandModuleSystem
- Reference revision: `66c67147692707b85c457db10a112627118733a5`
- Referenced subtree: `Module_system 1.171/`
- License: MIT
- Copyright notice in upstream license: Copyright (c) 2018 Sea-Monster
- Files consulted: `module_skills.py`, `process_skills.py`,
  `module_quests.py`, `process_quests.py`, `module_factions.py`,
  `process_factions.py`, `module_strings.py`, `process_strings.py`,
  `module_info_pages.py`, `module_meshes.py`, `process_meshes.py`,
  `module_music.py`, `process_music.py`, `module_sounds.py`, `process_sounds.py`,
  `module_parties.py`, `module_party_templates.py`, `module_map_icons.py`,
  `module_scenes.py`, `module_scene_props.py`, `module_mission_templates.py`,
  `module_game_menus.py`, `module_presentations.py`, `module_tableau_materials.py`,
  `module_skins.py`, `module_particle_systems.py`, and their relevant
  `header_*.py` declarations.

The implementation in Lexeditor is original span-preserving source editing code.
The upstream repository is credited because its documented schemas materially
inform which Warband fields can be represented without guessing.

## Persistent World compatibility reference

- Repository: https://github.com/vornne/pw_module_system
- Reference revision: `a35fd5d89cbb4e684ddf2fe4a6de9fe5066b9988`
- License: 3-clause BSD-style terms in upstream `LICENSE.txt`
- Copyright notice: Copyright (c) 2010 Steven Schwartfeger, Persistent World
- Files inspected include `module_items.py`, `module_troops.py`,
  `module_skills.py`, `module_parties.py`, `module_scene_props.py`,
  `module_skins.py`, and `module_particle_systems.py`.

This is a read-only real-world compatibility reference. In particular,
Persistent World generates particle-system entries through a `psys(...)`
helper, which is valid Module System source but is not a literal record suitable
for Lexeditor's span-based structured editor. Lexeditor now reports such
helper/wrapper-generated records as source-only and refuses structured writes
instead of treating helper arguments as tuple fields.

The Items audit found 463 literal top-level records using the supported 8-9
field forms and no duplicate item IDs. The Troops audit exposed a 13-entry
quoted equipment list that matched the old line-based troop heuristic even
though it is nested data, not a troop. Structured troop discovery now limits
records to the top level of `troops = [...]`; this revision yields 50 true
top-level troop records and no `itm_*` false records.
 Its flat source
layout is also accepted by Lexeditor's non-destructive project importer:
`module_info.py` has one literal `export_dir` and `build_module.bat` reduces
to the allowlisted one-shot step `python -tt build_module.py`. The managed copy
redirects the export locally and never executes the interactive `pause`.
No Persistent World code or data is bundled.

## Native++ compatibility reference

- Repository: https://github.com/Batyan/MnB-Nativepp-mod
- Reference revision: `995afc62159d63ed08b369283c8924703ef11e1b`
- Repository terms: custom README terms permit private modification and require
  credit to the authors credited by the project for published reuse; no standard
  open-source LICENSE file was present at the inspected revision.
- Scope inspected: the 20 Module System source families exposed by Lexeditor's
  Misc. editor plus `module_items.py` and `module_troops.py`.

This is read-only compatibility evidence only; no Native++ code or data is
bundled or copied. A top-level tuple-shape audit matched Lexeditor's current
schema expectations for every inspected family except two legacy particle-system
records (`torch_smoke` and `pistol_smoke`), which use 22 fields rather than
the current 24-field shape. Lexeditor must keep those records source-only rather
than guessing missing rotation fields.

Native++ also contains 624 literal item records in supported 8-10 field forms,
including pre-existing duplicate tutorial IDs, and active/cut troop pairs that
share four IDs. Lexeditor keeps item IDs fixed and keys Items/Troops edits by
source record index, so those pre-existing identities can be preserved rather
than making the whole source unsavable.

Its pinned `build_module.bat` contains only the documented Python process
scripts plus display/cleanup/pause commands. Every referenced Python script is
present at the pinned revision, so the safe importer accepts the build plan and
redirects the copied `module_info.py` away from its hard-coded game path.

## Rome at War compatibility reference

- Repository: https://github.com/sndtaleworlds/RaW---Module-System
- Reference revision: `f4da7d5d242647506d8209e6f5fd22489c7fcabd`
- License stated by upstream README: NPOSL-3.0.
- Scope inspected: the 20 Module System source families exposed by Lexeditor's
  Misc. editor plus `module_items.py` and `module_troops.py`.

This is read-only compatibility evidence only; no Rome at War code or data is
bundled or copied. Its top-level tuple shapes match Lexeditor's current
expectations for every inspected family except the same two legacy 22-field
particle-system records. Those records are intentionally refused by structured
saving and remain available through source editing.

Rome at War contains 1,901 literal item records in supported 8-10 field forms,
including two pre-existing duplicate IDs, and an active/cut `woman_walker`
troop pair sharing one ID. The same source-record identity rules preserve these
records without rewriting game IDs or conflating the two source entries.

Its pinned build plan is also accepted: the importer keeps the one-pass Python
process sequence (including `flora_kinds.py`, resolved case-insensitively for
Warband's Windows runtime) while dropping the batch label, `pause`, and restart
loop. The copied `module_info.py` export is redirected locally rather than
writing to the upstream hard-coded Steam path.

## Installed Warband assets

Warband's bitmap font remains proprietary installed-game data. Lexeditor does
not redistribute `font.dds` or `font_data.xml`; when present in the user's
Warband installation they are read locally and an alpha-only atlas is generated
inside the user's private application-data cache. No Warband sound effect is
bundled by this plugin.

## BRF Sync

- Project: <https://github.com/markpryk/brf_sync_tools>
- Use: separate read-only tool for converting Warband model resources.
- Source and distribution notice: `tools/brf-sync/SOURCE.md`
- License: GNU GPL v2 (`tools/brf-sync/LICENSE`)
