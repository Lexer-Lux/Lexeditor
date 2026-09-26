"""Safe structured editing for documented Warband Module System record lists.

The parser never imports or executes mod source. It locates the documented
top-level record list and patches only selected field spans, preserving every
other byte of the source file.
"""
from __future__ import annotations

import ast
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
import threading

_LOCK = threading.Lock()


def _f(key, label, kind="expr", help="", **extra):
    value = {"key": key, "label": label, "kind": kind, "help": help}
    value.update(extra)
    return value


SCHEMAS = {
    "skills": {
        "label": "Skills", "filename": "module_skills.py", "variable": "skills",
        "status": "partial",
        "notes": "Names, maximum levels and descriptions have semantic controls. Skill flags remain a validated Module System expression.",
        "fields": [
            _f("id", "ID", "identity", "Stable skl_* source identity. Renaming is disabled because other Module System files reference it."),
            _f("name", "Name", "string", "Player-facing skill name."),
            _f("flags", "Flags", "expr", "sf_* governing-attribute, party-effect and inactive flags. The header_skills.py flags are checkboxes; anything else stays in the source expression.", bits=True),
            _f("maxLevel", "Maximum level", "integer", "Highest level the skill can reach.", min=0),
            _f("description", "Description", "text", "Player-facing skill description."),
        ],
        "columns": ["name", "id", "maxLevel"],
    },
    "quests": {
        "label": "Quests", "filename": "module_quests.py", "variable": "quests",
        "status": "partial",
        "notes": "Quest names and descriptions have semantic controls. Quest flags remain a validated Module System expression.",
        "fields": [
            _f("id", "ID", "identity", "Stable qst_* source identity. References are not rewritten."),
            _f("name", "Name", "string", "Name shown in the quest screen."),
            _f("flags", "Flags", "expr", "qf_* quest behavior flags, chosen from the project's header_quests.py.", bits=True),
            _f("description", "Description", "text", "Quest description compiled for the player."),
        ],
        "columns": ["name", "id", "flags"],
    },
    "strings": {
        "label": "Strings", "filename": "module_strings.py", "variable": "strings",
        "status": "integrated",
        "notes": "The complete documented (id, text) record is editable; IDs stay fixed so references remain valid.",
        "fields": [
            _f("id", "ID", "identity", "Stable str_* source identity. References are not rewritten."),
            _f("value", "Text", "text", "Reusable localized text compiled by the Module System."),
        ],
        "columns": ["id", "value"],
    },
    "info-pages": {
        "label": "Info pages", "filename": "module_info_pages.py", "variable": "info_pages",
        "status": "integrated",
        "notes": "The complete documented (id, name, text) source record is editable; installed compiled manuals remain read-only.",
        "fields": [
            _f("id", "ID", "identity", "Stable ip_* source identity. References are not rewritten."),
            _f("name", "Name", "string", "Name displayed in Warband's information page list."),
            _f("text", "Text", "text", "Body displayed on the information page."),
        ],
        "columns": ["name", "id", "text"],
    },
    "music": {
        "label": "Music", "filename": "module_music.py", "variable": "tracks",
        "status": "partial",
        "notes": "Track filenames are structured. Playback and continue masks remain validated mtf_* expressions.",
        "fields": [
            _f("id", "ID", "identity", "Stable track identity."),
            _f("file", "Audio file", "string", "Filename of the music track."),
            _f("flags", "Playback flags", "expr", "mtf_* situations/cultures in which the track may start.", bits=True),
            _f("continueFlags", "Continue flags", "expr", "mtf_* situations/cultures in which the track may continue.", bits=True),
        ],
        "columns": ["id", "file", "flags"],
    },
    "sounds": {
        "label": "Sounds", "filename": "module_sounds.py", "variable": "sounds",
        "status": "partial",
        "notes": "Sound event identities and flags are structured. The variable sample-list expression remains source syntax because entries may carry per-sample flags.",
        "fields": [
            _f("id", "ID", "identity", "Stable snd_* source identity."),
            _f("flags", "Flags", "expr", "sf_* sound-event flags, chosen from the project's header_sounds.py.", bits=True),
            _f("samples", "Samples", "expr", "Sample list. Entries may be filenames or filename/flag pairs."),
        ],
        "columns": ["id", "flags", "samples"],
    },
    "meshes": {
        "label": "Meshes", "filename": "module_meshes.py", "variable": "meshes",
        "status": "partial",
        "notes": "Resource name and all nine documented transform values have semantic controls. Mesh flags remain a validated expression.",
        "fields": [
            _f("id", "ID", "identity", "Stable mesh_* source identity."),
            _f("flags", "Flags", "expr", "header_meshes.py flags.", bits=True),
            _f("resource", "Resource name", "string", "BRF mesh resource name."),
            _f("translateX", "Translate X", "number", "Automatic X-axis translation."),
            _f("translateY", "Translate Y", "number", "Automatic Y-axis translation."),
            _f("translateZ", "Translate Z", "number", "Automatic Z-axis translation."),
            _f("rotateX", "Rotate X", "number", "Automatic rotation angle around X."),
            _f("rotateY", "Rotate Y", "number", "Automatic rotation angle around Y."),
            _f("rotateZ", "Rotate Z", "number", "Automatic rotation angle around Z."),
            _f("scaleX", "Scale X", "number", "Automatic X scale."),
            _f("scaleY", "Scale Y", "number", "Automatic Y scale."),
            _f("scaleZ", "Scale Z", "number", "Automatic Z scale."),
        ],
        "columns": ["id", "resource", "scaleX"],
    },
    "factions": {
        "label": "Factions", "filename": "module_factions.py", "variable": "factions",
        "status": "partial", "minFields": 6, "maxFields": 7,
        "notes": "Names and coherence are semantic. Flags, relation/rank lists and optional color remain validated source expressions; reference IDs stay fixed.",
        "fields": [
            _f("id", "ID", "identity", "Stable fac_* source identity."),
            _f("name", "Name", "string", "Faction display name."),
            _f("flags", "Flags", "expr", "Faction rating/behavior flags.", bits=True),
            _f("coherence", "Coherence", "number", "Self-relation/coherence value exported by process_factions.py."),
            _f("relations", "Relations", "expr", "List of (faction id, relation) pairs."),
            _f("ranks", "Ranks", "expr", "Faction rank-name list."),
            _f("color", "Color", "expr", "Optional faction color expression.", optional=True),
        ],
        "columns": ["name", "id", "coherence"],
    },
    "postfx": {
        "label": "Post-processing", "filename": "module_postfx.py", "variable": "postfx_params",
        "status": "partial",
        "notes": "Tonemap operator and the three documented four-value shader vectors have bounded/semantic controls. Flags remain a validated expression.",
        "fields": [
            _f("id", "ID", "identity", "Stable pfx_* source identity."),
            _f("flags", "Flags", "expr", "Post-processing flags from header_postfx.py.", bits=True),
            _f("tonemap", "Tonemap operator", "integer", "Documented operator type 0, 1, 2 or 3.", min=0, max=3),
            _f("params1", "HDR parameters", "vec4", "HDR range, exposure scaler, luminance-average scaler, luminance-max scaler.",
               components=["HDR range", "Exposure", "Luminance average", "Luminance max"]),
            _f("params2", "Bloom / blur", "vec4", "Brightpass threshold, post power, blur strength, blur amount.",
               components=["Brightpass threshold", "Post power", "Blur strength", "Blur amount"]),
            _f("params3", "Lighting coefficients", "vec4", "Ambient, sun and specular coefficients plus reserved value.",
               components=["Ambient", "Sun", "Specular", "Reserved"]),
        ],
        "columns": ["id", "tonemap", "flags"],
    },
    "party-templates": {
        "label": "Party templates", "filename": "module_party_templates.py", "variable": "party_templates",
        "status": "partial",
        "notes": "Names have semantic controls. Flags, encounter menu, faction, personality and the documented maximum-six troop-stack list remain validated expressions.",
        "fields": [
            _f("id", "ID", "identity", "Stable pt_* source identity."),
            _f("name", "Name", "string", "Party-template display name."),
            _f("flags", "Flags", "expr", "Party/map-icon behavior flags.", bits=True),
            _f("menu", "Encounter menu", "expr", "Menu used when this party is met; 0 uses the default encounter system."),
            _f("faction", "Faction", "expr", "Faction assigned to generated parties."),
            _f("personality", "Personality", "expr", "AI personality expression."),
            _f("stacks", "Troop stacks", "expr", "Up to six (troop, minimum, maximum, optional member flags) stack records."),
        ],
        "columns": ["name", "id", "faction"],
    },
    "parties": {
        "label": "Parties", "filename": "module_parties.py", "variable": "parties",
        "status": "partial", "minFields": 11, "maxFields": 12,
        "notes": "Names, map coordinates and optional direction have semantic controls. Reference/AI fields and troop stacks remain validated expressions.",
        "fields": [
            _f("id", "ID", "identity", "Stable p_* source identity."),
            _f("name", "Name", "string", "Party display name."),
            _f("flags", "Flags", "expr", "Party behavior and map-icon flags.", bits=True),
            _f("menu", "Encounter menu", "expr", "Encounter menu; 0 uses the default system."),
            _f("template", "Party template", "expr", "pt_* template; pt_none means no template."),
            _f("faction", "Faction", "expr", "fac_* faction reference."),
            _f("personality", "Personality", "expr", "Party AI personality."),
            _f("aiBehavior", "AI behavior", "expr", "ai_bhvr_* behavior."),
            _f("aiTarget", "AI target", "expr", "Initial AI target party."),
            _f("coordinates", "Initial coordinates", "vec2", "Initial world-map X and Y coordinates.", components=["X", "Y"], container="tuple"),
            _f("stacks", "Troop stacks", "expr", "List of (troop, count, member flags) stacks."),
            _f("direction", "Direction", "number", "Optional starting direction in degrees.", optional=True),
        ],
        "columns": ["name", "id", "faction"],
    },
    "map-icons": {
        "label": "Map icons", "filename": "module_map_icons.py", "variable": "map_icons",
        "status": "partial", "minFields": 5, "maxFields": 8,
        "notes": "ID, flags, mesh, scale and sound are the documented common prefix and are editable. Optional offsets and custom trigger tails have multiple record shapes and remain source-only.",
        "fields": [
            _f("id", "ID", "identity", "Stable icon_* source identity."),
            _f("flags", "Flags", "expr", "Map-icon behavior flags.", bits=True),
            _f("mesh", "Mesh", "string", "World-map mesh name.", mesh=True),
            _f("scale", "Scale", "number", "World-map icon scale.", min=0),
            _f("sound", "Sound", "expr", "Sound event used by the icon."),
        ],
        "columns": ["id", "mesh", "scale"],
    },
    "scenes": {
        "label": "Scenes", "filename": "module_scenes.py", "variable": "scenes",
        "status": "partial", "minFields": 10, "maxFields": 11,
        "notes": "Indoor mesh/body, movement bounds, water level, terrain code and optional outer terrain are structured. Flags/reference lists remain expressions; .sco layout still belongs to Warband's scene editor.",
        "fields": [
            _f("id", "ID", "identity", "Stable scn_* source identity."),
            _f("flags", "Flags", "expr", "sf_* scene generation/behavior flags.", bits=True),
            _f("mesh", "Indoor mesh", "string", "Indoor scene mesh; use \"none\" for outdoor scenes.", mesh=True),
            _f("body", "Indoor body", "string", "Indoor collision body; use \"none\" for outdoor scenes."),
            _f("minPosition", "Minimum position", "vec2", "Minimum player X/Y movement boundary.", components=["X", "Y"], container="tuple"),
            _f("maxPosition", "Maximum position", "vec2", "Maximum player X/Y movement boundary.", components=["X", "Y"], container="tuple"),
            _f("waterLevel", "Water level", "number", "Scene water height."),
            _f("terrainCode", "Terrain code", "string", "Terrain-generator code for outdoor scenes."),
            _f("relatedScenes", "Related scenes", "expr", "Deprecated directly-accessible scene references."),
            _f("chestTroops", "Chest troops", "expr", "Troops whose inventories are exposed by chest variations."),
            _f("outerTerrain", "Outer terrain", "string", "Optional outer-terrain mesh name.", optional=True),
        ],
        "columns": ["id", "mesh", "waterLevel"],
    },
    "scene-props": {
        "label": "Scene props", "filename": "module_scene_props.py", "variable": "scene_props",
        "status": "partial",
        "notes": "Visual mesh is structured. Flags, physics object and associated trigger operation blocks remain validated expressions.",
        "fields": [
            _f("id", "ID", "identity", "Stable spr_* source identity."),
            _f("flags", "Flags", "expr", "Scene-prop behavior flags.", bits=True),
            _f("mesh", "Mesh", "string", "Visual mesh name.", mesh=True),
            _f("physicsObject", "Physics object", "expr", "Collision/physics object reference; some records use 0."),
            _f("triggers", "Triggers", "expr", "Simple-trigger operation list associated with the prop."),
        ],
        "columns": ["id", "mesh", "physicsObject"],
    },
    "mission-templates": {
        "label": "Mission templates", "filename": "module_mission_templates.py", "variable": "mission_templates",
        "status": "partial",
        "notes": "Mission descriptions are semantic text. Flags/type and spawn/trigger operation lists remain validated expressions.",
        "fields": [
            _f("id", "ID", "identity", "Stable mt_* source identity."),
            _f("flags", "Flags", "expr", "Mission-template flags.", bits=True),
            _f("missionType", "Mission type", "expr", "Default meeting-system type such as charge/charge_with_ally, or -1 for custom missions."),
            _f("description", "Description", "text", "Text describing the mission."),
            _f("spawns", "Spawn records", "expr", "Entry/spawn/alter/AI flags, troop count and optional equipment."),
            _f("triggers", "Triggers", "expr", "Mission trigger operation list."),
        ],
        "columns": ["description", "id", "missionType"],
    },
    "game-menus": {
        "label": "Game menus", "filename": "module_game_menus.py", "variable": "game_menus",
        "status": "partial",
        "notes": "Menu text and mesh-name are structured. Flags, activation operations and nested options remain validated expressions.",
        "fields": [
            _f("id", "ID", "identity", "Stable menu_* source identity."),
            _f("flags", "Flags", "expr", "Game-menu flags; a text-colour expression stays in source.", bits=True),
            _f("text", "Menu text", "text", "Text displayed when the menu opens."),
            _f("mesh", "Mesh", "string", "Documented unused mesh-name field; Native uses \"none\".", mesh=True),
            _f("operations", "Activation operations", "expr", "Operation block run when the menu activates."),
            _f("options", "Menu options", "expr", "Nested option records with id, conditions, text and consequences."),
        ],
        "columns": ["id", "text", "mesh"],
    },
    "presentations": {
        "label": "Presentations", "filename": "module_presentations.py", "variable": "presentations",
        "status": "partial",
        "notes": "Stable presentation records are browsable. Flags, background mesh and trigger operation list remain validated expressions.",
        "fields": [
            _f("id", "ID", "identity", "Stable prsnt_* source identity."),
            _f("flags", "Flags", "expr", "Presentation behavior flags.", bits=True),
            _f("backgroundMesh", "Background mesh", "string", "Background mesh reference.", mesh=True),
            _f("triggers", "Triggers", "expr", "Presentation simple-trigger operation list."),
        ],
        "columns": ["id", "backgroundMesh", "flags"],
    },
    "tableaus": {
        "label": "Tableau materials", "filename": "module_tableau_materials.py", "variable": "tableaus",
        "status": "partial",
        "notes": "Sample material, dimensions and documented mesh bounds are semantic controls. Flags and executable operation block remain expressions.",
        "fields": [
            _f("id", "ID", "identity", "Stable tab_* source identity."),
            _f("flags", "Flags", "expr", "Tableau behavior flags.", bits=True),
            _f("sampleMaterial", "Sample material", "string", "Sample material used by the tableau."),
            _f("width", "Width", "integer", "Generated tableau texture width in pixels.", min=1),
            _f("height", "Height", "integer", "Generated tableau texture height in pixels.", min=1),
            _f("minX", "Mesh min X", "integer", "Mesh minimum X; divided by 1000 by the Module System."),
            _f("minY", "Mesh min Y", "integer", "Mesh minimum Y; divided by 1000 by the Module System."),
            _f("maxX", "Mesh max X", "integer", "Mesh maximum X; divided by 1000 by the Module System."),
            _f("maxY", "Mesh max Y", "integer", "Mesh maximum Y; divided by 1000 by the Module System."),
            _f("operations", "Operations", "expr", "Operation block executed when the tableau is activated."),
        ],
        "columns": ["id", "sampleMaterial", "width"],
    },
    "skins": {
        "label": "Skins", "filename": "module_skins.py", "variable": "skins",
        "status": "partial", "minFields": 15, "maxFields": 18,
        "notes": "Body/calf/hand/head meshes, skeleton and scale are structured. Face/hair/beard/texture/voice lists plus optional blood/constraint expressions remain source expressions.",
        "fields": [
            _f("id", "ID", "identity", "Stable skin identity."),
            _f("flags", "Flags", "expr", "Skin flags; the reference Module System notes this is normally 0.", bits=True),
            _f("bodyMesh", "Body mesh", "string", "Body mesh name.", mesh=True),
            _f("calfMesh", "Calf mesh", "string", "Left calf mesh name.", mesh=True),
            _f("handMesh", "Hand mesh", "string", "Left hand mesh name.", mesh=True),
            _f("headMesh", "Head mesh", "string", "Head mesh name.", mesh=True),
            _f("faceKeys", "Face keys", "expr", "Face morph-key definition/reference."),
            _f("hairMeshes", "Hair meshes", "expr", "Hair mesh list."),
            _f("beardMeshes", "Beard meshes", "expr", "Beard mesh list."),
            _f("hairTextures", "Hair textures", "expr", "Hair texture list."),
            _f("beardTextures", "Beard textures", "expr", "Beard texture list."),
            _f("faceTextures", "Face textures", "expr", "Face texture/color records."),
            _f("voices", "Voices", "expr", "Voice-event/sound mappings."),
            _f("skeleton", "Skeleton", "string", "Skeleton resource name."),
            _f("scale", "Scale", "number", "Skin scale; upstream notes this setting does not fully work."),
            _f("bloodParticles1", "Blood particles 1", "expr", "Optional first blood particle-system reference.", optional=True),
            _f("bloodParticles2", "Blood particles 2", "expr", "Optional second blood particle-system reference.", optional=True),
            _f("faceConstraints", "Face constraints", "expr", "Optional face-key constraint list.", optional=True),
        ],
        "columns": ["id", "bodyMesh", "scale"],
    },
    "particle-systems": {
        "label": "Particle systems", "filename": "module_particle_systems.py", "variable": "particle_systems",
        "status": "partial",
        "notes": "Emission/lifetime/turbulence values, two-key color/alpha/scale curves, emit vectors and rotation controls are semantic. Flags remain a validated expression.",
        "fields": [
            _f("id", "ID", "identity", "Stable psys_* source identity."),
            _f("flags", "Flags", "expr", "Particle-system behavior flags.", bits=True),
            _f("mesh", "Particle mesh", "string", "Mesh rendered for each particle.", mesh=True),
            _f("particlesPerSecond", "Particles / second", "number", "Particles emitted each second.", min=0),
            _f("particleLife", "Particle life", "number", "Particle lifetime in seconds.", min=0),
            _f("damping", "Damping", "number", "Speed lost to friction."),
            _f("gravity", "Gravity", "number", "Gravity strength; negative values float upward."),
            _f("turbulenceSize", "Turbulence size", "number", "Random turbulence size in meters.", min=0),
            _f("turbulenceStrength", "Turbulence strength", "number", "Strength of turbulence."),
            _f("alphaKey1", "Alpha key 1", "vec2", "Curve key (normalized time, magnitude).", components=["Time", "Magnitude"], container="tuple"),
            _f("alphaKey2", "Alpha key 2", "vec2", "Curve key (normalized time, magnitude).", components=["Time", "Magnitude"], container="tuple"),
            _f("redKey1", "Red key 1", "vec2", "Red curve key.", components=["Time", "Magnitude"], container="tuple"),
            _f("redKey2", "Red key 2", "vec2", "Red curve key.", components=["Time", "Magnitude"], container="tuple"),
            _f("greenKey1", "Green key 1", "vec2", "Green curve key.", components=["Time", "Magnitude"], container="tuple"),
            _f("greenKey2", "Green key 2", "vec2", "Green curve key.", components=["Time", "Magnitude"], container="tuple"),
            _f("blueKey1", "Blue key 1", "vec2", "Blue curve key.", components=["Time", "Magnitude"], container="tuple"),
            _f("blueKey2", "Blue key 2", "vec2", "Blue curve key.", components=["Time", "Magnitude"], container="tuple"),
            _f("scaleKey1", "Scale key 1", "vec2", "Scale curve key.", components=["Time", "Magnitude"], container="tuple"),
            _f("scaleKey2", "Scale key 2", "vec2", "Scale curve key.", components=["Time", "Magnitude"], container="tuple"),
            _f("emitBox", "Emit box size", "vec3", "Dimensions of the emission box.", components=["X", "Y", "Z"], container="tuple"),
            _f("emitVelocity", "Emit velocity", "vec3", "Initial particle velocity.", components=["X", "Y", "Z"], container="tuple"),
            _f("emitRandomness", "Direction randomness", "number", "Randomness applied to emission direction."),
            _f("rotationSpeed", "Rotation speed", "number", "Initial rotation speed in degrees per second."),
            _f("rotationDamping", "Rotation damping", "number", "How quickly particle rotation stops.", min=0),
        ],
        "columns": ["id", "mesh", "particlesPerSecond"],
    },
}

SCHEMA_BY_FILENAME = {schema["filename"]: key for key, schema in SCHEMAS.items()}

# Areas the plugin shows as page tabs of their own instead of inside Misc.
# The Data Map names that tab so its open button does not promise a place the
# record no longer lives.
PROMOTED_TABS = {"music": "music", "factions": "factions", "skills": "skills", "sounds": "sounds"}


def _source(path: Path):
    raw = path.read_bytes()
    for encoding in ("utf-8", "cp1254", "latin1"):
        try:
            return raw.decode(encoding), encoding, raw
        except UnicodeDecodeError:
            pass
    return raw.decode("latin1"), "latin1", raw


def _skip_string(text: str, index: int) -> int:
    quote = text[index]
    triple = text.startswith(quote * 3, index)
    delimiter = quote * (3 if triple else 1)
    cursor = index + len(delimiter)
    while cursor < len(text):
        if text[cursor] == "\\":
            cursor += 2
            continue
        if text.startswith(delimiter, cursor):
            return cursor + len(delimiter)
        cursor += 1
    raise ValueError("Unterminated Python string in Module System source")


def _list_start(text: str, variable: str) -> int:
    match = re.search(r"(?m)^[ \t]*" + re.escape(variable) + r"[ \t]*=[ \t]*\[", text)
    if not match:
        raise ValueError(f"Source does not contain {variable} = [...]")
    return text.find("[", match.start(), match.end())


def _record_spans(text: str, variable: str):
    outer = _list_start(text, variable)
    stack = ["["]
    spans = []
    start = None
    pairs = {")": "(", "]": "[", "}": "{"}
    cursor = outer + 1
    while cursor < len(text):
        char = text[cursor]
        if char in "'\"":
            cursor = _skip_string(text, cursor)
            continue
        if char == "#":
            newline = text.find("\n", cursor)
            cursor = len(text) if newline < 0 else newline + 1
            continue
        if char in "([{":
            if len(stack) == 1:
                start = cursor
            stack.append(char)
        elif char in ")]}":
            if not stack or stack[-1] != pairs[char]:
                raise ValueError(f"Unbalanced {variable} record list")
            stack.pop()
            if len(stack) == 1 and start is not None:
                spans.append((start, cursor + 1))
                start = None
            elif not stack:
                return spans
        cursor += 1
    raise ValueError(f"Unterminated {variable} record list")


def _split_fields(text: str, start: int, end: int):
    fields = []
    stack = []
    pairs = {")": "(", "]": "[", "}": "{"}
    cursor = start + 1
    field_start = cursor
    while cursor < end - 1:
        char = text[cursor]
        if char in "'\"":
            cursor = _skip_string(text, cursor)
            continue
        if char == "#":
            newline = text.find("\n", cursor, end)
            cursor = end - 1 if newline < 0 else newline + 1
            continue
        if char in "([{":
            stack.append(char)
        elif char in ")]}":
            if not stack or stack[-1] != pairs[char]:
                raise ValueError("Unbalanced record expression")
            stack.pop()
        elif char == "," and not stack:
            left, right = field_start, cursor
            while left < right and text[left].isspace():
                left += 1
            while right > left and text[right - 1].isspace():
                right -= 1
            if left < right:
                fields.append((left, right))
            field_start = cursor + 1
        cursor += 1
    left, right = field_start, end - 1
    while left < right and text[left].isspace():
        left += 1
    while right > left and text[right - 1].isspace():
        right -= 1
    if left < right:
        fields.append((left, right))
    if stack:
        raise ValueError("Unbalanced record expression")
    return fields


def _decode(expression: str, field: dict):
    kind = field["kind"]
    if kind in {"identity", "string", "text"}:
        value = ast.literal_eval(expression)
        if not isinstance(value, str):
            raise ValueError("expected a string literal")
        return value
    if kind == "integer":
        value = ast.literal_eval(expression)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("expected an integer literal")
        return value
    if kind == "number":
        value = ast.literal_eval(expression)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise ValueError("expected a finite numeric literal")
        return value
    if kind in {"vec2", "vec3", "vec4"}:
        count = int(kind[-1])
        value = ast.literal_eval(expression)
        if not isinstance(value, (list, tuple)) or len(value) != count:
            raise ValueError(f"expected {count} numeric values")
        result = []
        for item in value:
            if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(float(item)):
                raise ValueError(f"expected {count} finite numeric values")
            result.append(item)
        return result
    return expression.strip()


def _literal_record_start(text: str, start: int) -> bool:
    """False when the outer list entry is produced by a helper call/wrapper."""
    cursor = start - 1
    while cursor >= 0 and text[cursor] in " \t":
        cursor -= 1
    return cursor < 0 or text[cursor] in "[,\r\n"


def _records(text: str, schema: dict):
    specs = schema["fields"]
    minimum = int(schema.get("minFields", len(specs)))
    maximum = int(schema.get("maxFields", len(specs)))
    rows = []
    for record_index, (start, end) in enumerate(_record_spans(text, schema["variable"])):
        line = text.count("\n", 0, start) + 1
        if not _literal_record_start(text, start):
            row = {"recordIndex": record_index, "line": line, "_spans": [], "fields": {},
                   "rawFields": {}, "fieldProblems": {}, "presentFields": [],
                   "id": f"record@{line}", "name": f"record@{line}",
                   "problem": "Record is generated by a helper/wrapper expression. Use source editing for this record."}
            rows.append(row)
            continue
        spans = _split_fields(text, start, end)
        raw_fields = [text[a:b] for a, b in spans]
        row = {"recordIndex": record_index, "line": line, "_spans": spans, "fields": {},
               "rawFields": {}, "fieldProblems": {}, "presentFields": []}
        if not minimum <= len(spans) <= maximum:
            row["id"] = f"record@{line}"
            row["name"] = row["id"]
            row["problem"] = (f"Expected {minimum}" + (f"-{maximum}" if maximum != minimum else "")
                              + f" fields; found {len(spans)}. Use source editing for this record.")
            rows.append(row)
            continue
        for index, spec in enumerate(specs):
            if index >= len(spans):
                continue
            key = spec["key"]
            expression = raw_fields[index]
            row["rawFields"][key] = expression
            row["presentFields"].append(key)
            try:
                row["fields"][key] = _decode(expression, spec)
            except Exception as error:
                row["fields"][key] = expression.strip()
                row["fieldProblems"][key] = str(error)
        identity = row["fields"].get("id")
        if not isinstance(identity, str):
            row["id"] = f"record@{line}"
            row["problem"] = "Record ID is not a string literal. Use source editing for this record."
        else:
            row["id"] = identity
        display = row["fields"].get("name")
        # Only a field that names the record becomes its heading. A mesh,
        # resource or file name is a property of the record, not its name; using
        # one put a mesh name in the heading and then printed the real ID under
        # it, so the heading repeated itself on some records and not others.
        for key in ("text", "description", "value"):
            if isinstance(display, str):
                break
            display = row["fields"].get(key)
        row["name"] = display if isinstance(display, str) else row["id"]
        rows.append(row)
    return rows


def _constant_number(expression: str, symbols: dict) -> int:
    """The integer a Module System constant expression reduces to."""
    node = ast.parse(re.sub(r"(?<=[0-9a-fA-F])L\b", "", expression), mode="eval").body

    def value(item):
        if isinstance(item, ast.Constant) and type(item.value) is int:
            return item.value
        if isinstance(item, ast.Name):
            return symbols[item.id]
        if isinstance(item, ast.UnaryOp) and isinstance(item.op, ast.Invert):
            return ~value(item.operand)
        if isinstance(item, ast.BinOp):
            left, right = value(item.left), value(item.right)
            if isinstance(item.op, ast.BitOr):
                return left | right
            if isinstance(item.op, ast.BitAnd):
                return left & right
            if isinstance(item.op, ast.LShift) and 0 <= right <= 256:
                return left << right
            if isinstance(item.op, ast.Add):
                return left + right
        if (isinstance(item, ast.Call) and isinstance(item.func, ast.Name)
                and item.func.id == "level" and len(item.args) == 1):
            return value(item.args[0]) << 32
        raise ValueError("not a fixed integer")

    return value(node)


def header_constants(root, filenames=None) -> dict:
    """Every numeric constant the project's Module System headers define.

    A Module System keeps one ``header_<area>.py`` beside the ``module_*.py``
    files, and that is where ``itp_*``, ``sf_*``, ``mtf_*``, ``imodbits_*`` and
    the rest of the documented constants come from. Reading the project's own
    headers means the editor offers the names the compile step will accept.
    A compiled module ships without headers, and its fields keep source
    controls because there is no finite set to offer.
    """
    root = Path(root)
    pending = []
    paths = ([root / name for name in filenames] if filenames is not None
             else sorted(root.glob("header_*.py")))
    for path in paths:
        if not path.is_file():
            continue
        text, _encoding, _raw = _source(path)
        pending += re.findall(r"(?m)^([A-Za-z_]\w*)\s*=\s*([^\n#]+)", text)
    symbols: dict = {}
    for _ in range(8):
        for key, expression in pending:
            if key in symbols:
                continue
            try:
                symbols[key] = _constant_number(expression.strip(), symbols)
            except (KeyError, ValueError, SyntaxError, TypeError):
                pass
    return symbols


def _single_bits(symbols: dict, prefix: str) -> list[dict]:
    """The named single-bit flags of one prefix, lowest bit first."""
    found = [(name, number) for name, number in symbols.items()
             if name.startswith(prefix) and number > 0 and number & (number - 1) == 0]
    found.sort(key=lambda pair: (pair[1], pair[0]))
    return [{"name": name, "value": number, "label": name[len(prefix):]} for name, number in found]


def _declared_names(path: Path) -> set:
    """The constant names one header file declares."""
    if not path.is_file():
        return set()
    text, _encoding, _raw = _source(path)
    return set(re.findall(r"(?m)^([A-Za-z_]\w*)\s*=", text))


def mesh_choices(root) -> list:
    """The mesh records a project declares, by resource name and by record id.

    A mesh property in one Module System file names a mesh the project
    declares in module_meshes.py, so the editor can offer those names and open
    the record they belong to instead of asking the reader to type one.
    """
    path = Path(root) / "module_meshes.py"
    if not path.is_file():
        return []
    text, _encoding, _raw = _source(path)
    found = []
    for row in _records(text, SCHEMAS["meshes"]):
        if row.get("problem"):
            continue
        resource = str(row["fields"].get("resource") or "").strip()
        for name in sorted({resource, str(row.get("id") or "")} - {""}):
            found.append({"name": name, "id": row.get("id", ""),
                          "recordIndex": row.get("recordIndex"), "label": name})
    return found


def _field_choices(root, schema: dict) -> dict:
    """The finite sets a dataset's fields can choose from, if the project has them."""
    root = Path(root)
    symbols = header_constants(root)
    choices = {}
    area_header = "header_" + schema["filename"][len("module_"):]
    area_names = _declared_names(root / area_header)
    for spec in schema["fields"]:
        if spec.get("mesh"):
            meshes = mesh_choices(root)
            if meshes:
                choices[spec["key"]] = {"kind": "mesh", "meshes": meshes}
            continue
        bits = spec.get("bits")
        if bits:
            if bits is True:
                # The area's own header is the list of flags that belong to that
                # area's records, so a field there offers exactly those.
                flags = [entry for entry in _single_bits(symbols, "")
                         if entry["name"] in area_names]
            else:
                prefixes = [bits] if isinstance(bits, str) else list(bits)
                flags = []
                for prefix in prefixes:
                    flags += _single_bits(symbols, prefix)
            if flags:
                choices[spec["key"]] = {"kind": "bits", "flags": flags}
        enum = spec.get("enum")
        if enum:
            options = [(name, number) for name, number in symbols.items()
                       if name.startswith(enum) and number >= 0]
            options.sort(key=lambda pair: (pair[1], pair[0]))
            if options:
                choices[spec["key"]] = {"kind": "enum",
                                        "options": [{"name": name, "label": name[len(enum):], "value": number}
                                                    for name, number in options]}
    return choices


def _public_schema(schema: dict):
    return {key: value for key, value in schema.items() if key != "variable"}


def dataset_data(root, dataset: str):
    if dataset not in SCHEMAS:
        raise ValueError("Unknown Warband Module System dataset")
    root = Path(root)
    schema = SCHEMAS[dataset]
    path = root / schema["filename"]
    public = _public_schema(schema)
    if not path.is_file():
        return {"dataset": dataset, "available": False, "rows": [], "sha256": "", "schema": public}
    text, encoding, raw = _source(path)
    rows = _records(text, schema)
    seen = {}
    for row in rows:
        if row["id"].startswith("record@"):
            continue
        if row["id"] in seen:
            row["problem"] = f"Duplicate ID {row['id']!r}; repair source before structured editing."
            seen[row["id"]]["problem"] = row["problem"]
        else:
            seen[row["id"]] = row
    for row in rows:
        row.pop("_spans", None)
    return {"dataset": dataset, "available": True, "filename": schema["filename"],
            "choices": _field_choices(root, schema),
            "encoding": encoding, "sha256": hashlib.sha256(raw).hexdigest(),
            "rows": rows, "schema": public}


def _expression(value):
    text = str(value).strip()
    if not text:
        raise ValueError("Expression cannot be empty")
    modern = re.sub(r"(?<=[0-9a-fA-F])L\b", "", text)
    ast.parse(modern, mode="eval")
    return text


def _encode(value, spec: dict):
    kind = spec["kind"]
    if kind in {"string", "text"}:
        return json.dumps(str(value), ensure_ascii=False)
    if kind == "identity":
        raise ValueError("Record IDs are fixed; edit references in source if an ID must change")
    if kind == "integer":
        if isinstance(value, bool):
            raise ValueError("Expected an integer")
        try:
            number = int(value)
            if float(value) != number:
                raise ValueError
        except Exception as error:
            raise ValueError("Expected an integer") from error
        if "min" in spec and number < spec["min"]:
            raise ValueError(f"{spec['label']} must be at least {spec['min']}")
        if "max" in spec and number > spec["max"]:
            raise ValueError(f"{spec['label']} must be at most {spec['max']}")
        return str(number)
    if kind == "number":
        try:
            number = float(value)
        except Exception as error:
            raise ValueError("Expected a number") from error
        if not math.isfinite(number):
            raise ValueError("Expected a finite number")
        if "min" in spec and number < spec["min"]:
            raise ValueError(f"{spec['label']} must be at least {spec['min']}")
        if "max" in spec and number > spec["max"]:
            raise ValueError(f"{spec['label']} must be at most {spec['max']}")
        return str(int(number)) if number.is_integer() else format(number, ".15g")
    if kind in {"vec2", "vec3", "vec4"}:
        count = int(kind[-1])
        if not isinstance(value, (list, tuple)) or len(value) != count:
            raise ValueError(f"{spec['label']} needs {count} numbers")
        rendered = []
        for item in value:
            try:
                number = float(item)
            except Exception as error:
                raise ValueError(f"{spec['label']} needs {count} numbers") from error
            if not math.isfinite(number):
                raise ValueError(f"{spec['label']} needs finite numbers")
            rendered.append(str(int(number)) if number.is_integer() else format(number, ".15g"))
        opening, closing = ("(", ")") if spec.get("container") == "tuple" else ("[", "]")
        return opening + ", ".join(rendered) + closing
    return _expression(value)


def _validate_python(encoded: bytes):
    python27 = Path(r"C:\Python27\python.exe")
    if not python27.is_file():
        return
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as temporary:
        temporary.write(encoded)
        temporary_path = Path(temporary.name)
    try:
        check = subprocess.run(
            [str(python27), "-c", "import sys; compile(open(sys.argv[1],'rb').read(),sys.argv[1],'exec')", str(temporary_path)],
            capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if check.returncode:
            raise ValueError((check.stderr or check.stdout).decode("utf-8", errors="replace").strip())
    finally:
        temporary_path.unlink(missing_ok=True)


def save_dataset(root, dataset: str, expected_sha256: str, edits: list[dict]):
    if dataset not in SCHEMAS:
        raise ValueError("Unknown Warband Module System dataset")
    schema = SCHEMAS[dataset]
    path = Path(root) / schema["filename"]
    with _LOCK:
        text, encoding, raw = _source(path)
        current_sha = hashlib.sha256(raw).hexdigest()
        if current_sha != expected_sha256:
            raise ValueError(f"{schema['filename']} changed; reload before saving")
        records = _records(text, schema)
        identities = [row["id"] for row in records]
        if any(row.get("problem") for row in records):
            raise ValueError("Source contains records that require source repair before structured saving")
        if len(set(identities)) != len(identities):
            raise ValueError("Duplicate record IDs require source repair")
        if len({int(edit["recordIndex"]) for edit in edits}) != len(edits):
            raise ValueError("Send each record only once")
        specs = {field["key"]: field for field in schema["fields"]}
        patches = []
        changed_records = 0
        for edit in edits:
            index = int(edit["recordIndex"])
            if not 0 <= index < len(records):
                raise ValueError("Record no longer exists")
            row = records[index]
            if row["id"] != edit.get("originalId"):
                raise ValueError("Record identity changed; reload before saving")
            row_changed = False
            for key, value in (edit.get("fields") or {}).items():
                spec = specs.get(key)
                if spec is None or key == "id":
                    raise ValueError("Unknown or fixed Module System field")
                field_index = schema["fields"].index(spec)
                if field_index >= len(row["_spans"]):
                    raise ValueError(f"{spec['label']} is not present in this source record")
                replacement = _encode(value, spec)
                a, b = row["_spans"][field_index]
                if text[a:b] == replacement:
                    continue
                patches.append((a, b, replacement))
                row_changed = True
            changed_records += int(row_changed)
        if not patches:
            return {"saved": 0, "sha256": current_sha}
        candidate = text
        for a, b, replacement in sorted(patches, reverse=True):
            candidate = candidate[:a] + replacement + candidate[b:]
        reparsed = _records(candidate, schema)
        if len(reparsed) != len(records) or [row["id"] for row in reparsed] != identities:
            raise ValueError("Save changed record identities or record count")
        if [len(row["_spans"]) for row in reparsed] != [len(row["_spans"]) for row in records]:
            raise ValueError("Save changed Module System field structure")
        if any(ord(char) > 127 for char in candidate) and not re.search(
                r"coding[:=]\s*[-\w.]+", "\n".join(candidate.splitlines()[:2])):
            candidate = f"# coding: {encoding}\n" + candidate
        encoded = candidate.encode(encoding)
        _validate_python(encoded)
        if path.read_bytes() != raw:
            raise ValueError(f"{schema['filename']} changed while validating; reload before saving")
        backup = path.with_name(path.name + ".lexeditor.bak")
        backup.write_bytes(raw)
        fd, temporary_name = tempfile.mkstemp(prefix=f".{path.stem}-", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(encoded)
            os.replace(temporary_name, path)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)
        return {"saved": changed_records, "sha256": hashlib.sha256(encoded).hexdigest(), "backup": str(backup)}
