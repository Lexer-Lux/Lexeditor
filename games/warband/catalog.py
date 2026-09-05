"""Warband data-file catalog shown by the plugin UI."""

DATA_CATALOG = {
    "Project": [
        ("settings.ini", "Lexer's exposed balance and feature settings."),
        ("module.ini", "Engine/module flags, resource loading, rendering and compatibility."),
    ],
    "Characters": [
        ("module_troops.py", "Troops, NPCs, merchants, lords: stats, skills, equipment, faces, faction."),
        ("module_items.py", "Weapons, armour, horses, goods: meshes, value, weight, damage and item flags."),
        ("module_skills.py", "Skill names, descriptions, governing attributes and maximum levels."),
        ("module_skins.py", "Human/undead bodies, faces, voices, skeletons and gender presentation."),
        ("module_animations.py", "Animation sequences, timing, flags and skeletal resources."),
    ],
    "World": [
        ("module_parties.py", "Permanent map entities: towns, castles, villages, bridges and spawn points."),
        ("module_party_templates.py", "Blueprints for spawned armies, caravans, bandits and quest parties."),
        ("module_factions.py", "Factions, colors, relations, ranks and naming conventions."),
        ("module_map_icons.py", "World-map meshes, scale, sound and icon triggers."),
        ("module_scenes.py", "Scene IDs, terrain codes, scene files, passages and chest references."),
        ("module_scene_props.py", "Placeable scene objects, collision/interaction triggers and destructibles."),
    ],
    "Gameplay": [
        ("module_quests.py", "Quest records, titles, descriptions and quest flags."),
        ("module_scripts.py", "Reusable gameplay procedures: economy, AI, quests, combat and initialization."),
        ("module_triggers.py", "Global timed/event logic."),
        ("module_simple_triggers.py", "Compact periodic campaign logic."),
        ("module_mission_templates.py", "Battle/town mission modes, spawn points, agents and mission triggers."),
        ("module_game_menus.py", "Settlement and campaign text menus, conditions and consequences."),
        ("module_dialogs.py", "Conversation states, conditions, text and consequences."),
    ],
    "Interface & Text": [
        ("module_presentations.py", "Scripted UI screens and overlays."),
        ("module_strings.py", "Reusable localized text."),
        ("module_info_pages.py", "In-game reference/manual pages."),
        ("module_meshes.py", "UI and other named mesh references."),
        ("module_tableau_materials.py", "Dynamically composed portraits, banners and equipment images."),
    ],
    "Audio & Effects": [
        ("module_sounds.py", "Sound events and sample variations."),
        ("module_music.py", "Music tracks and contextual playback flags."),
        ("module_particle_systems.py", "Particle emitters, materials, motion, lifetime and color."),
        ("module_postfx.py", "Post-processing profiles such as HDR and contrast."),
    ],
    "Generated output": [
        ("*.txt", "Compiled engine data. Source module_*.py remains authoritative."),
        ("SceneObj/*.sco", "Binary scene layouts edited with Warband's scene editor."),
        ("Resource/*.brf", "Binary meshes, materials, skeletons, animations and collision."),
        ("Textures/*.dds", "Texture images referenced by BRF resources."),
    ],
}
