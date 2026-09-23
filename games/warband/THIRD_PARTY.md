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
- Files inspected: `module_skills.py`, `module_parties.py`,
  `module_scene_props.py`, `module_skins.py`, and
  `module_particle_systems.py`.

This is a read-only real-world compatibility reference. In particular,
Persistent World generates particle-system entries through a `psys(...)`
helper, which is valid Module System source but is not a literal record suitable
for Lexeditor's span-based structured editor. Lexeditor now reports such
helper/wrapper-generated records as source-only and refuses structured writes
instead of treating helper arguments as tuple fields. No Persistent World code
or data is bundled.

## Installed Warband assets

Warband's bitmap font remains proprietary installed-game data. Lexeditor does
not redistribute `font.dds` or `font_data.xml`; when present in the user's
Warband installation they are read locally and an alpha-only atlas is generated
inside the user's private application-data cache. No Warband sound effect is
bundled by this plugin.
