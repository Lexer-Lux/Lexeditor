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
