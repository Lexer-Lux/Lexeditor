"""Structured Terraria content generators/editors with preservation-bounded C# regions."""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from .assets import create_asset
from .content_wizard import default_display_name, placeholder_png, validate_content_name
from .localization import apply_localization_changes
from .source_text import create_source, save_source, source_file_state, source_index

HEADER_PREFIX = "// LEXEDITOR-CONTENT "
BEGIN_MARKER = "    // LEXEDITOR-BEGIN"
END_MARKER = "    // LEXEDITOR-END"
UTF8_BOM = b"\xef\xbb\xbf"

@dataclass(frozen=True)
class Field:
    name: str
    label: str
    type: str
    default: Any
    group: str = "GENERAL"
    minimum: float | int | None = None
    maximum: float | int | None = None
    options: tuple[str, ...] = ()
    help: str = ""

    def public(self) -> dict:
        out = {"name": self.name, "label": self.label, "type": self.type, "default": self.default, "group": self.group, "help": self.help}
        if self.minimum is not None: out["min"] = self.minimum
        if self.maximum is not None: out["max"] = self.maximum
        if self.options: out["options"] = list(self.options)
        return out

_DAMAGE_CLASSES = ("Generic", "Melee", "MeleeNoSpeed", "Ranged", "Magic", "Summon", "SummonMeleeSpeed")

SCHEMAS: dict[str, tuple[Field, ...]] = {
    "item": (
        Field("width", "Width", "int", 20, "HITBOX", 1, 2000), Field("height", "Height", "int", 20, "HITBOX", 1, 2000),
        Field("maxStack", "Max stack", "int", 1, "INVENTORY", 1, 9999), Field("value", "Value (copper)", "int", 0, "INVENTORY", 0, 2_000_000_000), Field("rare", "Rarity ID", "int", 0, "INVENTORY", -13, 100),
        Field("damage", "Damage", "int", 0, "COMBAT", 0, 1_000_000), Field("damageClass", "Damage class", "enum", "Generic", "COMBAT", options=_DAMAGE_CLASSES), Field("knockBack", "Knockback", "float", 0.0, "COMBAT", 0, 1000), Field("crit", "Bonus crit", "int", 0, "COMBAT", -100, 1000),
        Field("useTime", "Use time", "int", 0, "USE", 0, 10000), Field("useAnimation", "Use animation", "int", 0, "USE", 0, 10000), Field("useStyle", "Use style ID", "int", 0, "USE", 0, 1000), Field("useTurn", "Turn while using", "bool", False, "USE"), Field("autoReuse", "Auto reuse", "bool", False, "USE"), Field("channel", "Channel", "bool", False, "USE"), Field("noMelee", "No melee hitbox", "bool", False, "USE"), Field("consumable", "Consumable", "bool", False, "USE"), Field("accessory", "Accessory", "bool", False, "USE"), Field("shootSpeed", "Shoot speed", "float", 0.0, "USE", 0, 10000),
        Field("mana", "Mana cost", "int", 0, "CONSUMPTION", 0, 100000), Field("healLife", "Heal life", "int", 0, "CONSUMPTION", 0, 100000), Field("healMana", "Heal mana", "int", 0, "CONSUMPTION", 0, 100000),
        Field("pick", "Pickaxe power", "int", 0, "TOOLS", 0, 100000), Field("axe", "Axe power", "int", 0, "TOOLS", 0, 100000), Field("hammer", "Hammer power", "int", 0, "TOOLS", 0, 100000),
        Field("ammo", "Ammo category ID", "int", 0, "AMMO / PROJECTILE", 0, 100000), Field("useAmmo", "Consumes ammo category ID", "int", 0, "AMMO / PROJECTILE", 0, 100000), Field("shoot", "Projectile type ID", "int", 0, "AMMO / PROJECTILE", 0, 100000),
        Field("createTile", "Places tile ID (-1 none)", "int", -1, "PLACEMENT", -1, 100000), Field("createWall", "Places wall ID (-1 none)", "int", -1, "PLACEMENT", -1, 100000), Field("placeStyle", "Placement style", "int", 0, "PLACEMENT", 0, 100000),
        Field("defense", "Accessory defense", "int", 0, "EQUIP", -10000, 100000),
    ),
    "npc": (
        Field("width", "Width", "int", 18, "HITBOX", 1, 4000), Field("height", "Height", "int", 40, "HITBOX", 1, 4000),
        Field("lifeMax", "Max life", "int", 100, "COMBAT", 1, 2_000_000_000), Field("damage", "Contact damage", "int", 10, "COMBAT", 0, 1_000_000), Field("defense", "Defense", "int", 0, "COMBAT", -10000, 100000), Field("knockBackResist", "Knockback resistance", "float", 0.5, "COMBAT", 0, 100), Field("value", "Coin value", "float", 0.0, "COMBAT", 0, 2_000_000_000),
        Field("scale", "Scale", "float", 1.0, "VISUAL", 0.01, 100), Field("frames", "Sprite frames", "int", 1, "VISUAL", 1, 1000),
        Field("aiStyle", "AI style", "int", -1, "AI", -1, 10000), Field("aiType", "Vanilla AI type ID", "int", -1, "AI", -1, 100000), Field("animationType", "Vanilla animation type ID", "int", -1, "AI", -1, 100000),
        Field("friendly", "Friendly", "bool", False, "FLAGS"), Field("townNPC", "Town NPC", "bool", False, "FLAGS"), Field("boss", "Boss", "bool", False, "FLAGS"), Field("dontTakeDamage", "Invulnerable", "bool", False, "FLAGS"), Field("lavaImmune", "Lava immune", "bool", False, "FLAGS"), Field("noGravity", "No gravity", "bool", False, "FLAGS"), Field("noTileCollide", "No tile collision", "bool", False, "FLAGS"), Field("netAlways", "Always network-sync", "bool", False, "FLAGS"),
        Field("npcSlots", "Spawn slot cost", "float", 1.0, "SPAWN", 0, 1000), Field("catchItem", "Catch item ID (0 none)", "int", 0, "SPAWN", 0, 100000),
        Field("spawnChance", "Base spawn chance", "float", 0.0, "SPAWN", 0, 1, help="0 leaves natural spawning undefined; positive enables the structured spawn rules below."),
        Field("spawnZone", "Player biome", "enum", "Any", "SPAWN CONDITIONS", options=("Any","Forest","Jungle","Snow","Desert","Beach","Dungeon","Corruption","Crimson","Hallow","Glowshroom")),
        Field("spawnDepth", "Depth", "enum", "Any", "SPAWN CONDITIONS", options=("Any","Sky","Overworld","DirtLayer","RockLayer","Underworld")), Field("spawnTime", "Time", "enum", "Any", "SPAWN CONDITIONS", options=("Any","Day","Night")), Field("spawnHardmode", "World mode", "enum", "Any", "SPAWN CONDITIONS", options=("Any","PreHardmode","Hardmode")), Field("spawnRain", "Weather", "enum", "Any", "SPAWN CONDITIONS", options=("Any","Raining","Dry")),
        Field("spawnWater", "Spawn tile water", "enum", "Any", "SPAWN CONTEXT", options=("Any","Water","Dry")), Field("spawnSafety", "Player safety", "enum", "Any", "SPAWN CONTEXT", options=("Any","Safe","Unsafe")), Field("spawnTown", "Town state", "enum", "Any", "SPAWN CONTEXT", options=("Any","InTown","OutsideTown")), Field("spawnInvasion", "Invasion state", "enum", "Any", "SPAWN CONTEXT", options=("Any","Invasion","NoInvasion")), Field("spawnSpecial", "Special spawn area", "enum", "Any", "SPAWN CONTEXT", options=("Any","Granite","Marble","DesertCave","SpiderCave","Lihzahrd")),
        Field("lootKind", "Primary loot type", "enum", "none", "LOOT", options=("none", "vanilla", "modItem")), Field("lootItemId", "Vanilla loot item ID", "int", 0, "LOOT", 0, 100000), Field("lootItemName", "Mod loot item class", "identifier", "", "LOOT"), Field("lootChance", "Loot chance denominator", "int", 1, "LOOT", 1, 1_000_000), Field("lootMin", "Loot minimum stack", "int", 1, "LOOT", 1, 9999), Field("lootMax", "Loot maximum stack", "int", 1, "LOOT", 1, 9999),
        Field("lootRules", "Additional loot rules", "lines", "", "LOOT", help="One per line: vanilla:<id>,<chance denominator>,<min>,<max> or mod:<ClassName>,<chance>,<min>,<max>. Missing numeric columns default to 1."),
    ),
    "projectile": (
        Field("width", "Width", "int", 8, "HITBOX", 1, 4000), Field("height", "Height", "int", 8, "HITBOX", 1, 4000), Field("frames", "Sprite frames", "int", 1, "VISUAL", 1, 1000), Field("scale", "Scale", "float", 1.0, "VISUAL", 0.01, 100), Field("alpha", "Alpha", "int", 0, "VISUAL", 0, 255), Field("light", "Light", "float", 0.0, "VISUAL", 0, 10),
        Field("friendly", "Friendly", "bool", True, "COMBAT"), Field("hostile", "Hostile", "bool", False, "COMBAT"), Field("damageClass", "Damage class", "enum", "Generic", "COMBAT", options=_DAMAGE_CLASSES), Field("penetrate", "Penetration", "int", 1, "COMBAT", -1, 100000), Field("ownerHitCheck", "Owner line-of-sight check", "bool", False, "COMBAT"),
        Field("timeLeft", "Lifetime (ticks)", "int", 3600, "MOVEMENT", 1, 10_000_000), Field("tileCollide", "Collide with tiles", "bool", True, "MOVEMENT"), Field("ignoreWater", "Ignore water", "bool", False, "MOVEMENT"), Field("extraUpdates", "Extra updates", "int", 0, "MOVEMENT", 0, 100), Field("aiStyle", "AI style", "int", -1, "AI", -1, 10000), Field("aiType", "Vanilla AI type ID", "int", -1, "AI", -1, 100000),
        Field("usesLocalNPCImmunity", "Per-projectile NPC immunity", "bool", False, "NPC IMMUNITY"), Field("localNPCHitCooldown", "Local hit cooldown (-1 once/NPC)", "int", -1, "NPC IMMUNITY", -1, 100000), Field("usesIDStaticNPCImmunity", "Shared type NPC immunity", "bool", False, "NPC IMMUNITY"), Field("idStaticNPCHitCooldown", "Shared hit cooldown", "int", 10, "NPC IMMUNITY", 1, 100000),
        Field("minion", "Minion", "bool", False, "SPECIAL"), Field("minionSlots", "Minion slots", "float", 1.0, "SPECIAL", 0, 1000), Field("netImportant", "Sync to joining players", "bool", False, "SPECIAL"), Field("hide", "Hide normal draw", "bool", False, "SPECIAL"),
    ),
    "buff": (
        Field("debuff", "Debuff", "bool", False, "FLAGS"), Field("noTimeDisplay", "Hide time display", "bool", False, "FLAGS"), Field("pvpBuff", "PvP buff", "bool", False, "FLAGS"), Field("vanityPet", "Vanity pet", "bool", False, "FLAGS"), Field("lightPet", "Light pet", "bool", False, "FLAGS"),
        Field("defenseBonus", "Player defense bonus", "int", 0, "PLAYER EFFECT", -10000, 10000), Field("moveSpeedBonus", "Move speed bonus", "float", 0.0, "PLAYER EFFECT", -10, 100), Field("lifeRegenBonus", "Life regen bonus", "int", 0, "PLAYER EFFECT", -100000, 100000),
    ),
    "tile": (
        Field("solid", "Solid", "bool", True, "TILE"), Field("mergeDirt", "Merge with dirt", "bool", True, "TILE"), Field("blockLight", "Block light", "bool", True, "TILE"), Field("lighted", "Emits/uses light", "bool", False, "TILE"),
        Field("dustType", "Dust ID", "int", 0, "HARVEST", -1, 100000), Field("mineResist", "Mine resistance", "float", 1.0, "HARVEST", 0.01, 100000), Field("minPick", "Minimum pick power", "int", 0, "HARVEST", 0, 100000),
        Field("mapR", "Map red", "int", 180, "MAP", 0, 255), Field("mapG", "Map green", "int", 180, "MAP", 0, 255), Field("mapB", "Map blue", "int", 180, "MAP", 0, 255),
        Field("dropKind", "Fallback drop type", "enum", "none", "DROP", options=("none", "vanilla", "modItem")), Field("dropItemId", "Vanilla drop item ID", "int", 0, "DROP", 0, 100000), Field("dropItemName", "Mod drop item class", "identifier", "", "DROP"),
    ),
    "globalItem": (
        Field("targetId", "Target vanilla item ID", "int", 0, "TARGET", 0, 100000), Field("damageMultiplier", "Damage multiplier", "float", 1.0, "MODIFIERS", 0, 1000), Field("knockBackMultiplier", "Knockback multiplier", "float", 1.0, "MODIFIERS", 0, 1000), Field("valueMultiplier", "Value multiplier", "float", 1.0, "MODIFIERS", 0, 1000), Field("maxStackOverride", "Max stack override (-1 unchanged)", "int", -1, "OVERRIDES", -1, 9999), Field("rareOverride", "Rarity override (-999 unchanged)", "int", -999, "OVERRIDES", -999, 100),
    ),
    "globalNPC": (
        Field("targetId", "Target vanilla NPC ID", "int", 0, "TARGET", 0, 100000), Field("lifeMultiplier", "Life multiplier", "float", 1.0, "MODIFIERS", 0.01, 1000), Field("damageMultiplier", "Damage multiplier", "float", 1.0, "MODIFIERS", 0, 1000), Field("defenseAdd", "Defense adjustment", "int", 0, "MODIFIERS", -100000, 100000), Field("valueMultiplier", "Value multiplier", "float", 1.0, "MODIFIERS", 0, 1000), Field("knockBackMultiplier", "Knockback resistance multiplier", "float", 1.0, "MODIFIERS", 0, 1000), Field("scaleMultiplier", "Scale multiplier", "float", 1.0, "MODIFIERS", 0.01, 1000),
    ),
    "wall": (
        Field("housingSafe", "Counts as housing wall", "bool", True, "WALL"), Field("dustType", "Dust ID", "int", 0, "WALL", -1, 100000),
        Field("mapR", "Map red", "int", 180, "MAP", 0, 255), Field("mapG", "Map green", "int", 180, "MAP", 0, 255), Field("mapB", "Map blue", "int", 180, "MAP", 0, 255),
        Field("dropKind", "Fallback drop type", "enum", "none", "DROP", options=("none", "vanilla", "modItem")), Field("dropItemId", "Vanilla drop item ID", "int", 0, "DROP", 0, 100000), Field("dropItemName", "Mod drop item class", "identifier", "", "DROP"),
    ),
    "globalProjectile": (
        Field("targetId", "Target vanilla projectile ID", "int", 0, "TARGET", 0, 100000),
        Field("friendlyOverride", "Friendly override", "enum", "unchanged", "FLAGS", options=("unchanged", "true", "false")), Field("hostileOverride", "Hostile override", "enum", "unchanged", "FLAGS", options=("unchanged", "true", "false")), Field("tileCollideOverride", "Tile collision override", "enum", "unchanged", "FLAGS", options=("unchanged", "true", "false")),
        Field("damageClass", "Damage class override", "enum", "Unchanged", "COMBAT", options=("Unchanged",) + _DAMAGE_CLASSES), Field("penetrateOverride", "Penetration override (-999 unchanged)", "int", -999, "COMBAT", -999, 100000),
        Field("timeLeftMultiplier", "Lifetime multiplier", "float", 1.0, "MODIFIERS", 0.01, 1000), Field("scaleMultiplier", "Scale multiplier", "float", 1.0, "MODIFIERS", 0.01, 1000), Field("extraUpdatesAdd", "Extra updates adjustment", "int", 0, "MODIFIERS", -100, 100),
    ),
    "prefix": (
        Field("category", "Prefix category", "enum", "AnyWeapon", "ROLLING", options=("Melee", "Ranged", "Magic", "AnyWeapon", "Accessory", "Custom")), Field("rollChance", "Relative roll chance", "float", 1.0, "ROLLING", 0, 100000), Field("canRoll", "Can roll", "bool", True, "ROLLING"),
        Field("damageMult", "Damage multiplier", "float", 1.0, "STATS", 0, 1000), Field("knockBackMult", "Knockback multiplier", "float", 1.0, "STATS", 0, 1000), Field("useTimeMult", "Use-time multiplier", "float", 1.0, "STATS", 0.01, 1000), Field("scaleMult", "Scale multiplier", "float", 1.0, "STATS", 0.01, 1000), Field("shootSpeedMult", "Shoot-speed multiplier", "float", 1.0, "STATS", 0, 1000), Field("manaMult", "Mana-cost multiplier", "float", 1.0, "STATS", 0, 1000), Field("critBonus", "Critical chance bonus", "int", 0, "STATS", -1000, 1000), Field("valueMult", "Value multiplier", "float", 1.0, "VALUE", 0, 1000),
    ),
    "rarity": (
        Field("colorR", "Color red", "int", 255, "COLOR", 0, 255), Field("colorG", "Color green", "int", 255, "COLOR", 0, 255), Field("colorB", "Color blue", "int", 255, "COLOR", 0, 255),
    ),
    "biome": (
        Field("enabled", "Enable biome condition", "bool", False, "ACTIVATION", help="Disabled biomes return false until you intentionally configure and enable them."),
        Field("zone", "Vanilla biome condition", "enum", "Any", "ACTIVATION", options=("Any","Forest","Jungle","Snow","Desert","Beach","Dungeon","Corruption","Crimson","Hallow","Glowshroom")),
        Field("depth", "Depth condition", "enum", "Any", "ACTIVATION", options=("Any","Sky","Overworld","DirtLayer","RockLayer","Underworld")),
        Field("time", "Time condition", "enum", "Any", "ACTIVATION", options=("Any","Day","Night")), Field("hardmode", "Hardmode condition", "enum", "Any", "ACTIVATION", options=("Any","PreHardmode","Hardmode")), Field("rain", "Rain condition", "enum", "Any", "ACTIVATION", options=("Any","Raining","Dry")),
        Field("music", "Music ID (-1 inherit)", "int", -1, "SCENE", -1, 100000), Field("priority", "Scene priority", "enum", "BiomeLow", "SCENE", options=("None","BiomeLow","BiomeMedium","BiomeHigh","Environment","Event","BossLow","BossMedium","BossHigh")), Field("mapBackground", "Use bestiary background on map", "bool", True, "SCENE"),
        Field("torchItemType", "Biome torch item ID (-1 none)", "int", -1, "ITEMS", -1, 100000), Field("campfireItemType", "Biome campfire item ID (-1 none)", "int", -1, "ITEMS", -1, 100000),
        Field("backgroundColorEnabled", "Tint bestiary background", "bool", False, "COLOR"), Field("backgroundR", "Background red", "int", 255, "COLOR", 0, 255), Field("backgroundG", "Background green", "int", 255, "COLOR", 0, 255), Field("backgroundB", "Background blue", "int", 255, "COLOR", 0, 255),
    ),
    "config": (
        Field("scope", "Config scope", "enum", "ClientSide", "CONFIG", options=("ClientSide","ServerSide")), Field("reloadRequired", "All fields require reload", "bool", False, "CONFIG"),
        Field("fields", "Config fields", "lines", "", "FIELDS", help="One per line: bool:EnableFeature=true, int:Count=5, float:Scale=1.25, string:Greeting=Hello."),
    ),
    "command": (
        Field("command", "Command text", "text", "example", "COMMAND", help="Without the leading slash and without whitespace."), Field("commandType", "Command context", "enum", "Chat", "COMMAND", options=("Chat","Server","Console","World")), Field("caseSensitive", "Case sensitive arguments", "bool", False, "COMMAND"),
        Field("usage", "Usage text (blank = automatic)", "text", "", "HELP"), Field("description", "Description", "text", "", "HELP"), Field("replyText", "Fixed reply text", "text", "", "ACTION"), Field("echoArguments", "Echo arguments", "bool", False, "ACTION"),
    ),
    "sceneEffect": (
        Field("enabled", "Enable scene condition", "bool", False, "ACTIVATION", help="Disabled scene effects never activate until configured and enabled."), Field("zone", "Player biome", "enum", "Any", "ACTIVATION", options=("Any","Forest","Jungle","Snow","Desert","Beach","Dungeon","Corruption","Crimson","Hallow","Glowshroom")), Field("depth", "Depth", "enum", "Any", "ACTIVATION", options=("Any","Sky","Overworld","DirtLayer","RockLayer","Underworld")), Field("time", "Time", "enum", "Any", "ACTIVATION", options=("Any","Day","Night")), Field("hardmode", "World mode", "enum", "Any", "ACTIVATION", options=("Any","PreHardmode","Hardmode")), Field("rain", "Weather", "enum", "Any", "ACTIVATION", options=("Any","Raining","Dry")),
        Field("music", "Music ID (-1 inherit)", "int", -1, "SCENE", -1, 100000), Field("priority", "Scene priority", "enum", "None", "SCENE", options=("None","BiomeLow","BiomeMedium","BiomeHigh","Environment","Event","BossLow","BossMedium","BossHigh")), Field("weight", "Priority weight", "float", 0.5, "SCENE", 0, 1),
    ),
    "dust": (
        Field("updateType", "Copy vanilla dust behavior (-1 none)", "int", -1, "BEHAVIOR", -1, 100000), Field("vanillaUpdate", "Run vanilla dust update", "bool", True, "BEHAVIOR"), Field("midUpdateOwnBehavior", "Handle MidUpdate behavior", "bool", False, "BEHAVIOR"),
        Field("noGravity", "No gravity", "bool", False, "SPAWN"), Field("noLight", "Ignore lighting flag", "bool", False, "SPAWN"), Field("fadeIn", "Fade-in value", "float", 0.0, "SPAWN", 0, 1000), Field("scaleMultiplier", "Scale multiplier", "float", 1.0, "SPAWN", 0.01, 1000), Field("velocityMultiplier", "Velocity multiplier", "float", 1.0, "SPAWN", 0, 1000), Field("fullbright", "Draw fullbright", "bool", False, "DRAW"),
    ),
    "globalBuff": (
        Field("targetId", "Target buff ID", "int", 0, "TARGET", 0, 100000), Field("defenseBonus", "Player defense bonus", "int", 0, "PLAYER EFFECT", -10000, 10000), Field("moveSpeedBonus", "Move speed bonus", "float", 0.0, "PLAYER EFFECT", -10, 100), Field("lifeRegenBonus", "Life regen bonus", "int", 0, "PLAYER EFFECT", -100000, 100000), Field("allowCancel", "Allow right-click cancel", "bool", True, "BEHAVIOR"),
    ),
    "globalTile": (
        Field("targetId", "Target tile ID", "int", 0, "TARGET", 0, 100000), Field("allowDrop", "Allow default drop", "bool", True, "BEHAVIOR"), Field("dangerous", "Dangersense override", "enum", "unchanged", "SENSES", options=("unchanged","true","false")), Field("spelunkable", "Spelunker override", "enum", "unchanged", "SENSES", options=("unchanged","true","false")),
    ),
    "globalWall": (
        Field("targetId", "Target wall ID", "int", 0, "TARGET", 0, 100000), Field("allowDefaultDrop", "Allow default drop", "bool", True, "DROP"), Field("dropOverride", "Drop item ID (-1 unchanged)", "int", -1, "DROP", -1, 100000), Field("allowTeleport", "Allow teleport destination", "bool", True, "BEHAVIOR"),
    ),
    "recipe": (
        Field("resultKind", "Result type", "enum", "modItem", "RESULT", options=("modItem", "vanilla")), Field("resultName", "Result mod item class", "identifier", "", "RESULT"), Field("resultId", "Result vanilla item ID", "int", 0, "RESULT", 0, 100000), Field("resultStack", "Result stack", "int", 1, "RESULT", 1, 9999),
        Field("ingredients", "Ingredients", "lines", "", "RECIPE", help="One per line: vanilla:<id>=<stack> or mod:<ClassName>=<stack>."), Field("stations", "Crafting stations", "lines", "", "RECIPE", help="One per line: vanilla:<tileId> or mod:<TileClassName>."),
    ),
}

_LABELS = {"item":"ModItem","npc":"ModNPC","projectile":"ModProjectile","buff":"ModBuff","tile":"ModTile (simple 1×1)","wall":"ModWall","globalItem":"GlobalItem (vanilla modifier)","globalNPC":"GlobalNPC (vanilla modifier)","globalProjectile":"GlobalProjectile (vanilla modifier)","prefix":"ModPrefix","rarity":"ModRarity","biome":"ModBiome","config":"ModConfig","command":"ModCommand","sceneEffect":"ModSceneEffect","dust":"ModDust","globalBuff":"GlobalBuff","globalTile":"GlobalTile","globalWall":"GlobalWall","recipe":"Recipe"}

def schemas_public() -> dict:
    return {"kinds":[{"kind":k,"label":_LABELS[k],"fields":[f.public() for f in v]} for k,v in SCHEMAS.items()]}

def default_values(kind: str) -> dict[str, Any]:
    if kind not in SCHEMAS: raise ValueError(f"Unsupported structured content kind: {kind}")
    return {f.name:f.default for f in SCHEMAS[kind]}

def _num(value: object, field: Field, integer: bool):
    if isinstance(value, bool): raise ValueError(f"{field.label} must be numeric")
    try: out = int(value) if integer else float(value)
    except (TypeError,ValueError) as e: raise ValueError(f"{field.label} must be numeric") from e
    if integer and isinstance(value,float) and not value.is_integer(): raise ValueError(f"{field.label} must be an integer")
    if field.minimum is not None and out < field.minimum: raise ValueError(f"{field.label} must be at least {field.minimum}")
    if field.maximum is not None and out > field.maximum: raise ValueError(f"{field.label} must be at most {field.maximum}")
    return out

def validate_values(kind: str, values: object) -> dict[str, Any]:
    if kind not in SCHEMAS: raise ValueError(f"Unsupported structured content kind: {kind}")
    if not isinstance(values, dict): raise ValueError("Structured content values must be an object")
    fields={f.name:f for f in SCHEMAS[kind]}; unknown=set(values)-set(fields)
    if unknown: raise ValueError("Unknown structured content fields: "+", ".join(sorted(unknown)))
    out=default_values(kind); out.update(values)
    for name,field in fields.items():
        value=out[name]
        if field.type=="int": out[name]=_num(value,field,True)
        elif field.type=="float": out[name]=_num(value,field,False)
        elif field.type=="bool":
            if not isinstance(value,bool): raise ValueError(f"{field.label} must be true or false")
        elif field.type=="enum":
            if not isinstance(value,str) or value not in field.options: raise ValueError(f"{field.label} must be one of: {', '.join(field.options)}")
        elif field.type=="identifier": out[name]="" if value in ("",None) else validate_content_name(value)
        elif field.type in {"text","lines"}:
            if not isinstance(value,str) or "\x00" in value: raise ValueError(f"{field.label} must be text")
        else: raise ValueError(f"Unsupported structured field type: {field.type}")
    if kind=="npc":
        if out["lootMin"]>out["lootMax"]: raise ValueError("Loot minimum stack cannot exceed maximum stack")
        if out["lootKind"]=="modItem" and not out["lootItemName"]: raise ValueError("Mod loot item class is required")
        _parse_loot_rules(out["lootRules"])
    if kind in {"tile","wall"} and out["dropKind"]=="modItem" and not out["dropItemName"]: raise ValueError("Mod drop item class is required")
    if kind=="projectile" and out["usesLocalNPCImmunity"] and out["usesIDStaticNPCImmunity"]: raise ValueError("Projectile cannot use local and shared ID-static NPC immunity at the same time")
    if kind=="recipe":
        if out["resultKind"]=="modItem" and not out["resultName"]: raise ValueError("Result mod item class is required")
        _parse_ingredients(out["ingredients"]); _parse_stations(out["stations"])
    if kind=="config": _parse_config_fields(out["fields"])
    if kind=="command":
        out["command"]=out["command"].strip()
        if not out["command"] or out["command"].startswith("/") or any(ch.isspace() for ch in out["command"]): raise ValueError("Command text must be non-empty, omit the slash, and contain no whitespace")
        if any(ch in out[field] for field in ("usage","description","replyText") for ch in "\r\n\x00"): raise ValueError("Command help/reply text must fit on one line")
    return out

def _b(v): return "true" if v else "false"
def _cs(v): return json.dumps(str(v),ensure_ascii=False)
def _f(v): return f"{int(v)}f" if v==int(v) else f"{v:.8g}f"
def _meta(kind,name,values): return HEADER_PREFIX+json.dumps({"version":1,"kind":kind,"name":name,"values":values},sort_keys=True,separators=(",",":"))
def _managed(lines): return "\n".join([BEGIN_MARKER,*(("    "+x) if x else "" for x in lines),END_MARKER])

def _render_item(v):
    return ["public override void SetDefaults()","{",f"    Item.width = {v['width']};",f"    Item.height = {v['height']};",f"    Item.maxStack = {v['maxStack']};",f"    Item.value = {v['value']};",f"    Item.rare = {v['rare']};",f"    Item.damage = {v['damage']};",f"    Item.DamageType = DamageClass.{v['damageClass']};",f"    Item.knockBack = {_f(v['knockBack'])};",f"    Item.crit = {v['crit']};",f"    Item.defense = {v['defense']};",f"    Item.useTime = {v['useTime']};",f"    Item.useAnimation = {v['useAnimation']};",f"    Item.useStyle = {v['useStyle']};",f"    Item.useTurn = {_b(v['useTurn'])};",f"    Item.autoReuse = {_b(v['autoReuse'])};",f"    Item.channel = {_b(v['channel'])};",f"    Item.noMelee = {_b(v['noMelee'])};",f"    Item.consumable = {_b(v['consumable'])};",f"    Item.accessory = {_b(v['accessory'])};",f"    Item.shootSpeed = {_f(v['shootSpeed'])};",f"    Item.mana = {v['mana']};",f"    Item.healLife = {v['healLife']};",f"    Item.healMana = {v['healMana']};",f"    Item.pick = {v['pick']};",f"    Item.axe = {v['axe']};",f"    Item.hammer = {v['hammer']};",f"    Item.ammo = {v['ammo']};",f"    Item.useAmmo = {v['useAmmo']};",f"    Item.shoot = {v['shoot']};",f"    Item.createTile = {v['createTile']};",f"    Item.createWall = {v['createWall']};",f"    Item.placeStyle = {v['placeStyle']};","}"]

def _npc_spawn_condition(v):
    zone={"Any":None,"Forest":"spawnInfo.Player.ZoneForest","Jungle":"spawnInfo.Player.ZoneJungle","Snow":"spawnInfo.Player.ZoneSnow","Desert":"spawnInfo.Player.ZoneDesert","Beach":"spawnInfo.Player.ZoneBeach","Dungeon":"spawnInfo.Player.ZoneDungeon","Corruption":"spawnInfo.Player.ZoneCorrupt","Crimson":"spawnInfo.Player.ZoneCrimson","Hallow":"spawnInfo.Player.ZoneHallow","Glowshroom":"spawnInfo.Player.ZoneGlowshroom"}[v["spawnZone"]]
    depth={"Any":None,"Sky":"spawnInfo.Sky","Overworld":"spawnInfo.Player.ZoneOverworldHeight","DirtLayer":"spawnInfo.Player.ZoneDirtLayerHeight","RockLayer":"spawnInfo.Player.ZoneRockLayerHeight","Underworld":"spawnInfo.Player.ZoneUnderworldHeight"}[v["spawnDepth"]]
    time={"Any":None,"Day":"Main.dayTime","Night":"!Main.dayTime"}[v["spawnTime"]]
    hardmode={"Any":None,"PreHardmode":"!Main.hardMode","Hardmode":"Main.hardMode"}[v["spawnHardmode"]]
    rain={"Any":None,"Raining":"Main.raining","Dry":"!Main.raining"}[v["spawnRain"]]
    water={"Any":None,"Water":"spawnInfo.Water","Dry":"!spawnInfo.Water"}[v["spawnWater"]]
    safety={"Any":None,"Safe":"spawnInfo.PlayerSafe","Unsafe":"!spawnInfo.PlayerSafe"}[v["spawnSafety"]]
    town={"Any":None,"InTown":"spawnInfo.PlayerInTown","OutsideTown":"!spawnInfo.PlayerInTown"}[v["spawnTown"]]
    invasion={"Any":None,"Invasion":"spawnInfo.Invasion","NoInvasion":"!spawnInfo.Invasion"}[v["spawnInvasion"]]
    special={"Any":None,"Granite":"spawnInfo.Granite","Marble":"spawnInfo.Marble","DesertCave":"spawnInfo.DesertCave","SpiderCave":"spawnInfo.SpiderCave","Lihzahrd":"spawnInfo.Lihzahrd"}[v["spawnSpecial"]]
    return " && ".join(part for part in (zone,depth,time,hardmode,rain,water,safety,town,invasion,special) if part) or "true"

def _render_npc(mod,v):
    out=[]
    if v['frames']!=1: out += ["public override void SetStaticDefaults()","{",f"    Main.npcFrameCount[Type] = {v['frames']};","}",""]
    out += ["public override void SetDefaults()","{",f"    NPC.width = {v['width']};",f"    NPC.height = {v['height']};",f"    NPC.lifeMax = {v['lifeMax']};",f"    NPC.damage = {v['damage']};",f"    NPC.defense = {v['defense']};",f"    NPC.knockBackResist = {_f(v['knockBackResist'])};",f"    NPC.value = {_f(v['value'])};",f"    NPC.scale = {_f(v['scale'])};",f"    NPC.aiStyle = {v['aiStyle']};",f"    NPC.npcSlots = {_f(v['npcSlots'])};",f"    NPC.catchItem = {v['catchItem']};",f"    NPC.friendly = {_b(v['friendly'])};",f"    NPC.townNPC = {_b(v['townNPC'])};",f"    NPC.boss = {_b(v['boss'])};",f"    NPC.dontTakeDamage = {_b(v['dontTakeDamage'])};",f"    NPC.lavaImmune = {_b(v['lavaImmune'])};",f"    NPC.noGravity = {_b(v['noGravity'])};",f"    NPC.noTileCollide = {_b(v['noTileCollide'])};",f"    NPC.netAlways = {_b(v['netAlways'])};"]
    if v['aiType']>=0: out.append(f"    AIType = {v['aiType']};")
    if v['animationType']>=0: out.append(f"    AnimationType = {v['animationType']};")
    out += ["}"]
    if v['spawnChance']>0:
        condition=_npc_spawn_condition(v)
        spawn=f"public override float SpawnChance(NPCSpawnInfo spawnInfo) => {_f(v['spawnChance'])};" if condition=='true' else f"public override float SpawnChance(NPCSpawnInfo spawnInfo) => ({condition}) ? {_f(v['spawnChance'])} : 0f;"
        out += ["",spawn]
    loot=[]
    if v['lootKind']!='none':
        item=str(v['lootItemId']) if v['lootKind']=='vanilla' else f"ModContent.ItemType<global::{mod}.Content.Items.{v['lootItemName']}>()"
        loot.append(f"npcLoot.Add(ItemDropRule.Common({item}, {v['lootChance']}, {v['lootMin']}, {v['lootMax']}));")
    for kind,value,chance,minimum,maximum in _parse_loot_rules(v['lootRules']):
        item=str(value) if kind=='vanilla' else f"ModContent.ItemType<global::{mod}.Content.Items.{value}>()"
        loot.append(f"npcLoot.Add(ItemDropRule.Common({item}, {chance}, {minimum}, {maximum}));")
    if loot: out += ["","public override void ModifyNPCLoot(NPCLoot npcLoot)","{",*("    "+line for line in loot),"}"]
    return out

def _render_projectile(v):
    out=[]
    if v['frames']!=1: out += ["public override void SetStaticDefaults()","{",f"    Main.projFrames[Type] = {v['frames']};","}",""]
    out += ["public override void SetDefaults()","{",f"    Projectile.width = {v['width']};",f"    Projectile.height = {v['height']};",f"    Projectile.scale = {_f(v['scale'])};",f"    Projectile.alpha = {v['alpha']};",f"    Projectile.light = {_f(v['light'])};",f"    Projectile.friendly = {_b(v['friendly'])};",f"    Projectile.hostile = {_b(v['hostile'])};",f"    Projectile.DamageType = DamageClass.{v['damageClass']};",f"    Projectile.penetrate = {v['penetrate']};",f"    Projectile.timeLeft = {v['timeLeft']};",f"    Projectile.tileCollide = {_b(v['tileCollide'])};",f"    Projectile.ignoreWater = {_b(v['ignoreWater'])};",f"    Projectile.extraUpdates = {v['extraUpdates']};",f"    Projectile.aiStyle = {v['aiStyle']};",f"    Projectile.ownerHitCheck = {_b(v['ownerHitCheck'])};"]
    if v['aiType']>=0: out.append(f"    AIType = {v['aiType']};")
    out += [f"    Projectile.netImportant = {_b(v['netImportant'])};",f"    Projectile.hide = {_b(v['hide'])};"]
    if v['usesLocalNPCImmunity']:
        out += ["    Projectile.usesLocalNPCImmunity = true;",f"    Projectile.localNPCHitCooldown = {v['localNPCHitCooldown']};"]
    if v['usesIDStaticNPCImmunity']:
        out += ["    Projectile.usesIDStaticNPCImmunity = true;",f"    Projectile.idStaticNPCHitCooldown = {v['idStaticNPCHitCooldown']};"]
    if v['minion']:
        out += ["    Projectile.minion = true;",f"    Projectile.minionSlots = {_f(v['minionSlots'])};"]
    out += ["}"]; return out

def _render_buff(v):
    out=["public override void SetStaticDefaults()","{",f"    Main.debuff[Type] = {_b(v['debuff'])};",f"    Main.buffNoTimeDisplay[Type] = {_b(v['noTimeDisplay'])};",f"    Main.pvpBuff[Type] = {_b(v['pvpBuff'])};",f"    Main.vanityPet[Type] = {_b(v['vanityPet'])};",f"    Main.lightPet[Type] = {_b(v['lightPet'])};","}"]
    if v['defenseBonus'] or v['moveSpeedBonus'] or v['lifeRegenBonus']:
        out += ["","public override void Update(Player player, ref int buffIndex)","{"]
        if v['defenseBonus']: out.append(f"    player.statDefense += {v['defenseBonus']};")
        if v['moveSpeedBonus']: out.append(f"    player.moveSpeed += {_f(v['moveSpeedBonus'])};")
        if v['lifeRegenBonus']: out.append(f"    player.lifeRegen += {v['lifeRegenBonus']};")
        out += ["}"]
    return out

def _render_tile(mod,v):
    out=["public override void SetStaticDefaults()","{",f"    Main.tileSolid[Type] = {_b(v['solid'])};",f"    Main.tileMergeDirt[Type] = {_b(v['mergeDirt'])};",f"    Main.tileBlockLight[Type] = {_b(v['blockLight'])};",f"    Main.tileLighted[Type] = {_b(v['lighted'])};",f"    DustType = {v['dustType']};",f"    MineResist = {_f(v['mineResist'])};",f"    MinPick = {v['minPick']};",f"    AddMapEntry(new Color({v['mapR']}, {v['mapG']}, {v['mapB']}), CreateMapEntryName());"]
    if v['dropKind']=='vanilla': out.append(f"    RegisterItemDrop({v['dropItemId']});")
    elif v['dropKind']=='modItem': out.append(f"    RegisterItemDrop(ModContent.ItemType<global::{mod}.Content.Items.{v['dropItemName']}>());")
    out += ["}"]; return out

def _render_global_item(v):
    out=[f"public override bool AppliesToEntity(Item entity, bool lateInstantiation) => entity.type == {v['targetId']};","","public override void SetDefaults(Item entity)","{"]
    if v['damageMultiplier']!=1: out.append(f"    entity.damage = (int)(entity.damage * {_f(v['damageMultiplier'])});")
    if v['knockBackMultiplier']!=1: out.append(f"    entity.knockBack *= {_f(v['knockBackMultiplier'])};")
    if v['valueMultiplier']!=1: out.append(f"    entity.value = (int)(entity.value * {_f(v['valueMultiplier'])});")
    if v['maxStackOverride']>=0: out.append(f"    entity.maxStack = {v['maxStackOverride']};")
    if v['rareOverride']!=-999: out.append(f"    entity.rare = {v['rareOverride']};")
    out += ["}"]; return out

def _render_global_npc(v):
    out=[f"public override bool AppliesToEntity(NPC entity, bool lateInstantiation) => entity.type == {v['targetId']};","","public override void SetDefaults(NPC entity)","{"]
    if v['lifeMultiplier']!=1: out.append(f"    entity.lifeMax = (int)(entity.lifeMax * {_f(v['lifeMultiplier'])});")
    if v['damageMultiplier']!=1: out.append(f"    entity.damage = (int)(entity.damage * {_f(v['damageMultiplier'])});")
    if v['defenseAdd']: out.append(f"    entity.defense += {v['defenseAdd']};")
    if v['valueMultiplier']!=1: out.append(f"    entity.value *= {_f(v['valueMultiplier'])};")
    if v['knockBackMultiplier']!=1: out.append(f"    entity.knockBackResist *= {_f(v['knockBackMultiplier'])};")
    if v['scaleMultiplier']!=1: out.append(f"    entity.scale *= {_f(v['scaleMultiplier'])};")
    out += ["}"]; return out

def _render_wall(mod,v):
    out=["public override void SetStaticDefaults()","{",f"    Main.wallHouse[Type] = {_b(v['housingSafe'])};",f"    DustType = {v['dustType']};",f"    AddMapEntry(new Color({v['mapR']}, {v['mapG']}, {v['mapB']}), CreateMapEntryName());"]
    if v['dropKind']=='vanilla': out.append(f"    RegisterItemDrop({v['dropItemId']});")
    elif v['dropKind']=='modItem': out.append(f"    RegisterItemDrop(ModContent.ItemType<global::{mod}.Content.Items.{v['dropItemName']}>());")
    out += ["}"]; return out

def _render_global_projectile(v):
    out=[f"public override bool AppliesToEntity(Projectile entity, bool lateInstantiation) => entity.type == {v['targetId']};","","public override void SetDefaults(Projectile entity)","{"]
    if v['friendlyOverride']!='unchanged': out.append(f"    entity.friendly = {v['friendlyOverride']};")
    if v['hostileOverride']!='unchanged': out.append(f"    entity.hostile = {v['hostileOverride']};")
    if v['tileCollideOverride']!='unchanged': out.append(f"    entity.tileCollide = {v['tileCollideOverride']};")
    if v['damageClass']!='Unchanged': out.append(f"    entity.DamageType = DamageClass.{v['damageClass']};")
    if v['penetrateOverride']!=-999: out.append(f"    entity.penetrate = {v['penetrateOverride']};")
    if v['timeLeftMultiplier']!=1: out.append(f"    entity.timeLeft = (int)(entity.timeLeft * {_f(v['timeLeftMultiplier'])});")
    if v['scaleMultiplier']!=1: out.append(f"    entity.scale *= {_f(v['scaleMultiplier'])};")
    if v['extraUpdatesAdd']: out.append(f"    entity.extraUpdates += {v['extraUpdatesAdd']};")
    out += ["}"]; return out

def _render_prefix(v):
    out=[f"public override PrefixCategory Category => PrefixCategory.{v['category']};",f"public override float RollChance(Item item) => {_f(v['rollChance'])};",f"public override bool CanRoll(Item item) => {_b(v['canRoll'])};","","public override void SetStats(ref float damageMult, ref float knockbackMult, ref float useTimeMult, ref float scaleMult, ref float shootSpeedMult, ref float manaMult, ref int critBonus)","{",f"    damageMult *= {_f(v['damageMult'])};",f"    knockbackMult *= {_f(v['knockBackMult'])};",f"    useTimeMult *= {_f(v['useTimeMult'])};",f"    scaleMult *= {_f(v['scaleMult'])};",f"    shootSpeedMult *= {_f(v['shootSpeedMult'])};",f"    manaMult *= {_f(v['manaMult'])};",f"    critBonus += {v['critBonus']};","}"]
    if v['valueMult']!=1: out += ["","public override void ModifyValue(ref float valueMult)","{",f"    valueMult *= {_f(v['valueMult'])};","}"]
    return out

def _parse_loot_rules(text):
    rows=[]
    for n,raw in enumerate(text.splitlines(),1):
        line=raw.strip()
        if not line: continue
        parts=[part.strip() for part in line.split(',')]
        if len(parts)>4 or ':' not in parts[0]: raise ValueError(f"Loot rule line {n} must use kind:value[,chance[,min[,max]]]")
        kind,value=(part.strip() for part in parts[0].split(':',1))
        if kind=='vanilla':
            try: value=int(value)
            except ValueError as e: raise ValueError(f"Loot rule line {n} vanilla ID is invalid") from e
            if value<0: raise ValueError(f"Loot rule line {n} vanilla ID is invalid")
        elif kind=='mod': value=validate_content_name(value)
        else: raise ValueError(f"Loot rule line {n} must start with vanilla: or mod:")
        numbers=[]
        for i,default in enumerate((1,1,1),1):
            if len(parts)>i and parts[i]:
                try: number=int(parts[i])
                except ValueError as e: raise ValueError(f"Loot rule line {n} numeric column is invalid") from e
            else: number=default
            numbers.append(number)
        chance,minimum,maximum=numbers
        if chance<1: raise ValueError(f"Loot rule line {n} chance denominator must be at least 1")
        if minimum<1 or maximum<minimum or maximum>9999: raise ValueError(f"Loot rule line {n} stack range is invalid")
        rows.append((kind,value,chance,minimum,maximum))
    return rows

def _parse_config_fields(text):
    rows=[]
    for n,raw in enumerate(text.splitlines(),1):
        line=raw.strip()
        if not line: continue
        if ":" not in line or "=" not in line: raise ValueError(f"Config field line {n} must use type:Name=value")
        type_name,rest=line.split(":",1); name,value=rest.split("=",1); type_name=type_name.strip(); name=validate_content_name(name.strip()); value=value.strip()
        if type_name=="bool":
            if value.casefold() not in {"true","false"}: raise ValueError(f"Config field line {n} bool default must be true or false")
            parsed=value.casefold()=="true"
        elif type_name=="int":
            try: parsed=int(value)
            except ValueError as e: raise ValueError(f"Config field line {n} integer default is invalid") from e
        elif type_name=="float":
            try: parsed=float(value)
            except ValueError as e: raise ValueError(f"Config field line {n} float default is invalid") from e
            if parsed!=parsed or parsed in (float("inf"),float("-inf")): raise ValueError(f"Config field line {n} float default must be finite")
        elif type_name=="string": parsed=value
        else: raise ValueError(f"Config field line {n} type must be bool, int, float, or string")
        if any(existing[1]==name for existing in rows): raise ValueError(f"Config field name is duplicated: {name}")
        rows.append((type_name,name,parsed))
    return rows

def _parse_ingredients(text):
    rows=[]
    for n,raw in enumerate(text.splitlines(),1):
        line=raw.strip()
        if not line: continue
        if '=' in line:
            left,stack_text=line.rsplit('=',1)
            try: stack=int(stack_text.strip())
            except ValueError as e: raise ValueError(f"Ingredient line {n} has an invalid stack") from e
        else: left,stack=line,1
        if not 1<=stack<=9999: raise ValueError(f"Ingredient line {n} stack is out of range")
        if ':' not in left: raise ValueError(f"Ingredient line {n} must start with vanilla: or mod:")
        kind,value=(x.strip() for x in left.split(':',1))
        if kind=='vanilla':
            try: value=int(value)
            except ValueError as e: raise ValueError(f"Ingredient line {n} vanilla ID is invalid") from e
            if value<0: raise ValueError(f"Ingredient line {n} vanilla ID is invalid")
        elif kind=='mod': value=validate_content_name(value)
        else: raise ValueError(f"Ingredient line {n} must start with vanilla: or mod:")
        rows.append((kind,value,stack))
    return rows

def _parse_stations(text):
    rows=[]
    for n,raw in enumerate(text.splitlines(),1):
        line=raw.strip()
        if not line: continue
        if ':' not in line: raise ValueError(f"Station line {n} must start with vanilla: or mod:")
        kind,value=(x.strip() for x in line.split(':',1))
        if kind=='vanilla':
            try: value=int(value)
            except ValueError as e: raise ValueError(f"Station line {n} vanilla tile ID is invalid") from e
            if value<0: raise ValueError(f"Station line {n} vanilla tile ID is invalid")
        elif kind=='mod': value=validate_content_name(value)
        else: raise ValueError(f"Station line {n} must start with vanilla: or mod:")
        rows.append((kind,value))
    return rows

def _scene_effect_condition(v):
    if not v["enabled"]: return "false"
    zone={"Any":None,"Forest":"player.ZoneForest","Jungle":"player.ZoneJungle","Snow":"player.ZoneSnow","Desert":"player.ZoneDesert","Beach":"player.ZoneBeach","Dungeon":"player.ZoneDungeon","Corruption":"player.ZoneCorrupt","Crimson":"player.ZoneCrimson","Hallow":"player.ZoneHallow","Glowshroom":"player.ZoneGlowshroom"}[v["zone"]]
    depth={"Any":None,"Sky":"player.ZoneSkyHeight","Overworld":"player.ZoneOverworldHeight","DirtLayer":"player.ZoneDirtLayerHeight","RockLayer":"player.ZoneRockLayerHeight","Underworld":"player.ZoneUnderworldHeight"}[v["depth"]]
    time={"Any":None,"Day":"Main.dayTime","Night":"!Main.dayTime"}[v["time"]]
    hardmode={"Any":None,"PreHardmode":"!Main.hardMode","Hardmode":"Main.hardMode"}[v["hardmode"]]
    rain={"Any":None,"Raining":"Main.raining","Dry":"!Main.raining"}[v["rain"]]
    parts=[part for part in (zone,depth,time,hardmode,rain) if part]
    parts.append("AdditionalCondition(player)")
    return " && ".join(parts)

def _render_scene_effect(v):
    return [f"public override int Music => {v['music']};",f"public override SceneEffectPriority Priority => SceneEffectPriority.{v['priority']};",f"public override float GetWeight(Player player) => {_f(v['weight'])};","",f"public override bool IsSceneEffectActive(Player player) => {_scene_effect_condition(v)};"]

def _render_dust(v):
    out=[]
    if v['updateType']>=0: out += ["public override void SetStaticDefaults()","{",f"    UpdateType = {v['updateType']};","}"]
    spawn=v['noGravity'] or v['noLight'] or v['fadeIn']!=0 or v['scaleMultiplier']!=1 or v['velocityMultiplier']!=1
    if spawn:
        if out: out.append("")
        out += ["public override void OnSpawn(Dust dust)","{"]
        if v['noGravity']: out.append("    dust.noGravity = true;")
        if v['noLight']: out.append("    dust.noLight = true;")
        if v['fadeIn']!=0: out.append(f"    dust.fadeIn = {_f(v['fadeIn'])};")
        if v['scaleMultiplier']!=1: out.append(f"    dust.scale *= {_f(v['scaleMultiplier'])};")
        if v['velocityMultiplier']!=1: out.append(f"    dust.velocity *= {_f(v['velocityMultiplier'])};")
        out += ["}"]
    if not v['vanillaUpdate']: out += ([""] if out else []) + ["public override bool Update(Dust dust) => false;"]
    if v['midUpdateOwnBehavior']: out += ([""] if out else []) + ["public override bool MidUpdate(Dust dust) => true;"]
    if v['fullbright']: out += ([""] if out else []) + ["public override Color? GetAlpha(Dust dust, Color lightColor) => Color.White;"]
    return out

def _render_global_buff(v):
    out=[]
    if v['defenseBonus'] or v['moveSpeedBonus'] or v['lifeRegenBonus']:
        out += ["public override void Update(int type, Player player, ref int buffIndex)","{",f"    if (type != {v['targetId']}) return;"]
        if v['defenseBonus']: out.append(f"    player.statDefense += {v['defenseBonus']};")
        if v['moveSpeedBonus']: out.append(f"    player.moveSpeed += {_f(v['moveSpeedBonus'])};")
        if v['lifeRegenBonus']: out.append(f"    player.lifeRegen += {v['lifeRegenBonus']};")
        out += ["}"]
    if not v['allowCancel']: out += ([""] if out else []) + [f"public override bool RightClick(int type, int buffIndex) => type != {v['targetId']};"]
    return out

def _render_global_tile(v):
    out=[f"public override bool CanDrop(int i, int j, int type) => type != {v['targetId']} || {_b(v['allowDrop'])};"]
    if v['dangerous']!='unchanged': out += ["", "public override bool? IsTileDangerous(int i, int j, int type, Player player)", "{", f"    if (type != {v['targetId']}) return null;", f"    return {v['dangerous']};", "}"]
    if v['spelunkable']!='unchanged': out += ["", "public override bool? IsTileSpelunkable(int i, int j, int type)", "{", f"    if (type != {v['targetId']}) return null;", f"    return {v['spelunkable']};", "}"]
    return out

def _render_global_wall(v):
    out=["public override bool Drop(int i, int j, int type, ref int dropType)","{",f"    if (type != {v['targetId']}) return true;"]
    if v['dropOverride']>=0: out.append(f"    dropType = {v['dropOverride']};")
    out += [f"    return {_b(v['allowDefaultDrop'])};","}"]
    if not v['allowTeleport']: out += ["",f"public override bool CanBeTeleportedTo(int i, int j, int type, Player player, string context) => type != {v['targetId']};"]
    return out

def _render_rarity(v):
    return [f"public override Color RarityColor => new Color({v['colorR']}, {v['colorG']}, {v['colorB']});"]

def _biome_condition(v):
    if not v["enabled"]: return "false"
    zone={"Any":None,"Forest":"player.ZoneForest","Jungle":"player.ZoneJungle","Snow":"player.ZoneSnow","Desert":"player.ZoneDesert","Beach":"player.ZoneBeach","Dungeon":"player.ZoneDungeon","Corruption":"player.ZoneCorrupt","Crimson":"player.ZoneCrimson","Hallow":"player.ZoneHallow","Glowshroom":"player.ZoneGlowshroom"}[v["zone"]]
    depth={"Any":None,"Sky":"player.ZoneSkyHeight","Overworld":"player.ZoneOverworldHeight","DirtLayer":"player.ZoneDirtLayerHeight","RockLayer":"player.ZoneRockLayerHeight","Underworld":"player.ZoneUnderworldHeight"}[v["depth"]]
    time={"Any":None,"Day":"Main.dayTime","Night":"!Main.dayTime"}[v["time"]]
    hardmode={"Any":None,"PreHardmode":"!Main.hardMode","Hardmode":"Main.hardMode"}[v["hardmode"]]
    rain={"Any":None,"Raining":"Main.raining","Dry":"!Main.raining"}[v["rain"]]
    parts=[part for part in (zone,depth,time,hardmode,rain) if part]
    parts.append("AdditionalCondition(player)")
    return " && ".join(parts)

def _render_biome(v):
    out=[f"public override int Music => {v['music']};",f"public override SceneEffectPriority Priority => SceneEffectPriority.{v['priority']};",f"public override int BiomeTorchItemType => {v['torchItemType']};",f"public override int BiomeCampfireItemType => {v['campfireItemType']};"]
    if v["mapBackground"]: out.append("public override string MapBackground => BackgroundPath;")
    if v["backgroundColorEnabled"]: out.append(f"public override Color? BackgroundColor => new Color({v['backgroundR']}, {v['backgroundG']}, {v['backgroundB']});")
    out += ["",f"public override bool IsBiomeActive(Player player) => {_biome_condition(v)};"]
    return out

def _config_literal(type_name,value):
    if type_name=="bool": return _b(value)
    if type_name=="int": return str(value)
    if type_name=="float": return _f(value)
    return _cs(value)

def _render_config(v):
    out=[f"public override ConfigScope Mode => ConfigScope.{v['scope']};"]
    for type_name,name,value in _parse_config_fields(v["fields"]):
        cs_type={"bool":"bool","int":"int","float":"float","string":"string"}[type_name]; literal=_config_literal(type_name,value)
        out += [""]
        if v["reloadRequired"]: out.append("[ReloadRequired]")
        out += [f"[DefaultValue({literal})]",f"public {cs_type} {name} {{ get; set; }} = {literal};"]
    return out

def _render_command(v):
    out=[f"public override string Command => {_cs(v['command'])};",f"public override CommandType Type => CommandType.{v['commandType']};",f"public override bool IsCaseSensitive => {_b(v['caseSensitive'])};"]
    if v["usage"]: out.append(f"public override string Usage => {_cs(v['usage'])};")
    if v["description"]: out.append(f"public override string Description => {_cs(v['description'])};")
    out += ["","public override void Action(CommandCaller caller, string input, string[] args)","{"]
    if v["replyText"]: out.append(f"    caller.Reply({_cs(v['replyText'])});")
    if v["echoArguments"]: out.append('    caller.Reply(string.Join(" ", args));')
    out.append("    CustomAction(caller, input, args);")
    out += ["}"]; return out

def _render_recipe(mod,v):
    result=str(v['resultId']) if v['resultKind']=='vanilla' else f"ModContent.ItemType<global::{mod}.Content.Items.{v['resultName']}>()"
    out=["public override void AddRecipes()","{",f"    Recipe recipe = Recipe.Create({result}, {v['resultStack']});"]
    for kind,value,stack in _parse_ingredients(v['ingredients']):
        item=str(value) if kind=='vanilla' else f"ModContent.ItemType<global::{mod}.Content.Items.{value}>()"
        out.append(f"    recipe.AddIngredient({item}, {stack});")
    for kind,value in _parse_stations(v['stations']):
        tile=str(value) if kind=='vanilla' else f"ModContent.TileType<global::{mod}.Content.Tiles.{value}>()"
        out.append(f"    recipe.AddTile({tile});")
    out += ["    recipe.Register();","}"]; return out

def _render_region(mod,kind,v):
    return {'item':lambda:_render_item(v),'npc':lambda:_render_npc(mod,v),'projectile':lambda:_render_projectile(v),'buff':lambda:_render_buff(v),'tile':lambda:_render_tile(mod,v),'wall':lambda:_render_wall(mod,v),'globalItem':lambda:_render_global_item(v),'globalNPC':lambda:_render_global_npc(v),'globalProjectile':lambda:_render_global_projectile(v),'prefix':lambda:_render_prefix(v),'rarity':lambda:_render_rarity(v),'biome':lambda:_render_biome(v),'config':lambda:_render_config(v),'command':lambda:_render_command(v),'sceneEffect':lambda:_render_scene_effect(v),'dust':lambda:_render_dust(v),'globalBuff':lambda:_render_global_buff(v),'globalTile':lambda:_render_global_tile(v),'globalWall':lambda:_render_global_wall(v),'recipe':lambda:_render_recipe(mod,v)}[kind]()

def _kind_spec(kind,name):
    return {
        'item':(f"Content/Items/{name}.cs",'ModItem',('Terraria','Terraria.ModLoader')),
        'npc':(f"Content/NPCs/{name}.cs",'ModNPC',('Terraria','Terraria.GameContent.ItemDropRules','Terraria.ModLoader')),
        'projectile':(f"Content/Projectiles/{name}.cs",'ModProjectile',('Terraria','Terraria.ModLoader')),
        'buff':(f"Content/Buffs/{name}.cs",'ModBuff',('Terraria','Terraria.ModLoader')),
        'tile':(f"Content/Tiles/{name}.cs",'ModTile',('Microsoft.Xna.Framework','Terraria','Terraria.ModLoader')),
        'wall':(f"Content/Walls/{name}.cs",'ModWall',('Microsoft.Xna.Framework','Terraria','Terraria.ModLoader')),
        'globalItem':(f"Common/GlobalItems/{name}.cs",'GlobalItem',('Terraria','Terraria.ModLoader')),
        'globalNPC':(f"Common/GlobalNPCs/{name}.cs",'GlobalNPC',('Terraria','Terraria.ModLoader')),
        'globalProjectile':(f"Common/GlobalProjectiles/{name}.cs",'GlobalProjectile',('Terraria','Terraria.ModLoader')),
        'prefix':(f"Content/Prefixes/{name}.cs",'ModPrefix',('Terraria','Terraria.ModLoader')),
        'rarity':(f"Content/Rarities/{name}.cs",'ModRarity',('Microsoft.Xna.Framework','Terraria.ModLoader')),
        'biome':(f"Content/Biomes/{name}.cs",'ModBiome',('Microsoft.Xna.Framework','Terraria','Terraria.ModLoader')),
        'config':(f"Common/Configs/{name}.cs",'ModConfig',('System.ComponentModel','Terraria.ModLoader.Config')),
        'command':(f"Common/Commands/{name}.cs",'ModCommand',('Terraria.ModLoader',)),
        'sceneEffect':(f"Content/SceneEffects/{name}.cs",'ModSceneEffect',('Terraria','Terraria.ModLoader')),
        'dust':(f"Content/Dusts/{name}.cs",'ModDust',('Microsoft.Xna.Framework','Terraria','Terraria.ModLoader')),
        'globalBuff':(f"Common/GlobalBuffs/{name}.cs",'GlobalBuff',('Terraria','Terraria.ModLoader')),
        'globalTile':(f"Common/GlobalTiles/{name}.cs",'GlobalTile',('Terraria','Terraria.ModLoader')),
        'globalWall':(f"Common/GlobalWalls/{name}.cs",'GlobalWall',('Terraria','Terraria.ModLoader')),
        'recipe':(f"Common/Recipes/{name}.cs",'ModSystem',('Terraria','Terraria.ModLoader')),
    }[kind]

def _namespace(mod,kind):
    return {'item':f'{mod}.Content.Items','npc':f'{mod}.Content.NPCs','projectile':f'{mod}.Content.Projectiles','buff':f'{mod}.Content.Buffs','tile':f'{mod}.Content.Tiles','wall':f'{mod}.Content.Walls','globalItem':f'{mod}.Common.GlobalItems','globalNPC':f'{mod}.Common.GlobalNPCs','globalProjectile':f'{mod}.Common.GlobalProjectiles','prefix':f'{mod}.Content.Prefixes','rarity':f'{mod}.Content.Rarities','biome':f'{mod}.Content.Biomes','config':f'{mod}.Common.Configs','command':f'{mod}.Common.Commands','sceneEffect':f'{mod}.Content.SceneEffects','dust':f'{mod}.Content.Dusts','globalBuff':f'{mod}.Common.GlobalBuffs','globalTile':f'{mod}.Common.GlobalTiles','globalWall':f'{mod}.Common.GlobalWalls','recipe':f'{mod}.Common.Recipes'}[kind]

def _custom_tail(kind):
    if kind in {"biome","sceneEffect"}: return "    private bool AdditionalCondition(Player player) => true;"
    if kind=="command": return "    private void CustomAction(CommandCaller caller, string input, string[] args)\n    {\n    }"
    return ""

def render_structured_source(mod_name,kind,name,values):
    mod_name=validate_content_name(mod_name); name=validate_content_name(name); v=validate_values(kind,values); _,base,usings=_kind_spec(kind,name)
    tail=_custom_tail(kind); suffix=("\n\n"+tail if tail else "")
    return ''.join(f"using {x};\n" for x in usings)+"\n"+_meta(kind,name,v)+"\n"+f"namespace {_namespace(mod_name,kind)};\n\npublic sealed class {name} : {base}\n{{\n"+_managed(_render_region(mod_name,kind,v))+suffix+"\n}\n"

def _parse_header(text):
    hits=[]
    for i,line in enumerate(text.splitlines()):
        if line.startswith(HEADER_PREFIX): hits.append((i,line[len(HEADER_PREFIX):]))
    if len(hits)!=1: raise ValueError("Lexeditor structured-content metadata is missing or ambiguous")
    try: payload=json.loads(hits[0][1])
    except json.JSONDecodeError as e: raise ValueError("Lexeditor structured-content metadata is malformed") from e
    if not isinstance(payload,dict): raise ValueError("Lexeditor structured-content metadata is malformed")
    return hits[0][0],payload

def _bounds(lines):
    b=[i for i,x in enumerate(lines) if x==BEGIN_MARKER]; e=[i for i,x in enumerate(lines) if x==END_MARKER]
    if len(b)!=1 or len(e)!=1 or b[0]>=e[0]: raise ValueError("Lexeditor managed source region is missing or ambiguous")
    return b[0],e[0]

def structured_content_state(root,relative):
    state=source_file_state(Path(root).resolve(),relative); _,m=_parse_header(state['text']); kind=m.get('kind'); name=m.get('name')
    if m.get('version')!=1 or kind not in SCHEMAS or not isinstance(name,str): raise ValueError("Lexeditor structured-content metadata is unsupported")
    validate_content_name(name); v=validate_values(kind,m.get('values')); _bounds(state['text'].splitlines())
    return {'path':state['path'],'sha256':state['sha256'],'kind':kind,'name':name,'values':v,'schema':[f.public() for f in SCHEMAS[kind]],'editable':True}

def structured_content_index(root):
    project=Path(root).resolve(); files=[]
    for row in source_index(project)['files']:
        if row.get('error'): continue
        try: state=structured_content_state(project,row['path'])
        except (OSError,ValueError): continue
        files.append({'path':state['path'],'kind':state['kind'],'name':state['name'],'editable':True})
    files.sort(key=lambda x:(x['kind'].casefold(),x['name'].casefold()))
    return {'root':str(project),'schemas':schemas_public()['kinds'],'files':files}

def update_structured_content(root,relative,values,expected_sha256):
    project=Path(root).resolve(); state=source_file_state(project,relative)
    if state['sha256']!=expected_sha256: raise ValueError(f"{state['path']} changed outside Lexeditor; reload before saving")
    _,m=_parse_header(state['text']); kind=m.get('kind'); name=m.get('name')
    if kind not in SCHEMAS or not isinstance(name,str): raise ValueError("Lexeditor structured-content metadata is unsupported")
    v=validate_values(kind,values); mod=validate_content_name(project.name); lines=state['text'].splitlines(); h=[i for i,x in enumerate(lines) if x.startswith(HEADER_PREFIX)][0]; b,e=_bounds(lines)
    lines[h]=_meta(kind,name,v); managed=_managed(_render_region(mod,kind,v)).splitlines(); changed='\n'.join(lines[:b]+managed+lines[e+1:])+('\n' if state['text'].endswith(('\n','\r')) else '')
    saved=save_source(project,state['path'],changed,expected_sha256); return structured_content_state(project,saved['path'])

def _loc_plan(mod,kind,name,display,desc):
    if kind=='item':
        out={f"Mods.{mod}.Items.{name}.DisplayName":display}
        if desc: out[f"Mods.{mod}.Items.{name}.Tooltip"]=desc
        return out
    if kind=='npc': return {f"Mods.{mod}.NPCs.{name}.DisplayName":display}
    if kind=='projectile': return {f"Mods.{mod}.Projectiles.{name}.DisplayName":display}
    if kind=='buff': return {f"Mods.{mod}.Buffs.{name}.DisplayName":display,f"Mods.{mod}.Buffs.{name}.Description":desc}
    if kind=='tile': return {f"Mods.{mod}.Tiles.{name}.MapEntry":display}
    if kind=='wall': return {f"Mods.{mod}.Walls.{name}.MapEntry":display}
    if kind=='prefix': return {f"Mods.{mod}.Prefixes.{name}.DisplayName":display}
    if kind=='biome': return {f"Mods.{mod}.Biomes.{name}.DisplayName":display}
    return {}

def _initial_loc(mod): return f"# tModLoader may add generated localization entries here after build/reload.\nMods: {{\n\t{mod}: {{\n\t}}\n}}\n"
def _atomic(target,data):
    temp=None
    try:
        with tempfile.NamedTemporaryFile('wb',dir=target.parent,prefix='.lexeditor-structured-',delete=False) as h:
            h.write(data); h.flush(); os.fsync(h.fileno()); temp=Path(h.name)
        os.replace(temp,target); temp=None
    finally:
        if temp is not None: temp.unlink(missing_ok=True)

def create_structured_content(root,kind,name,values,display_name='',description=''):
    project=Path(root).resolve()
    if not project.is_dir(): raise ValueError("Terraria source project does not exist")
    if not isinstance(kind,str) or kind not in SCHEMAS: raise ValueError("Unsupported structured content kind")
    mod=validate_content_name(project.name); name=validate_content_name(name)
    if not isinstance(display_name,str) or any(c in display_name for c in '\r\n\x00'): raise ValueError("Display name must fit on one line")
    if not isinstance(description,str) or any(c in description for c in '\r\n\x00'): raise ValueError("Description must fit on one line")
    display=display_name.strip() or default_display_name(name); desc=description.strip(); v=validate_values(kind,values); source_relative,_,_=_kind_spec(kind,name); source_target=project/source_relative
    if source_target.exists(): raise ValueError(f"C# source file already exists: {source_relative}")
    primary_texture=kind in {'item','npc','projectile','buff','tile','wall','dust'}
    asset_specs=[]
    if kind=='dust': asset_specs.append((source_relative[:-3]+'.png',10,30))
    elif primary_texture:
        size=32 if kind=='buff' else 16; asset_specs.append((source_relative[:-3]+'.png',size,size))
    if kind=='biome': asset_specs += [(f'Content/Biomes/{name}_Icon.png',30,30),(f'Content/Biomes/{name}_Background.png',64,64)]
    for asset_relative,_width,_height in asset_specs:
        if (project/asset_relative).exists(): raise ValueError(f"Asset file already exists: {asset_relative}")
    loc_target=project/'Localization'/'en-US.hjson'; creates=_loc_plan(mod,kind,name,display,desc); loc_existed=loc_target.is_file(); loc_original=loc_target.read_bytes() if loc_existed else b''; loc_written=src_written=False; created_assets=[]; texture_state=None
    if creates:
        loc_target.parent.mkdir(parents=True,exist_ok=True)
        if loc_existed:
            try: loc_text=loc_original.decode('utf-8-sig')
            except UnicodeDecodeError as e: raise ValueError("Localization/en-US.hjson is not UTF-8 text") from e
            bom=loc_original.startswith(UTF8_BOM)
        else: loc_text=_initial_loc(mod); bom=False
        changed=apply_localization_changes(loc_text,{},creates); loc_bytes=(UTF8_BOM if bom else b'')+changed.encode('utf-8')
    try:
        source_state=create_source(project,source_relative,render_structured_source(mod,kind,name,v)); src_written=True
        for asset_relative,width,height in asset_specs:
            created_assets.append(create_asset(project,asset_relative,placeholder_png(width,height)))
        if primary_texture and created_assets: texture_state=created_assets[0]
        if creates:
            if loc_existed: _atomic(loc_target,loc_bytes)
            else:
                with loc_target.open('xb') as h: h.write(loc_bytes); h.flush(); os.fsync(h.fileno())
            loc_written=True
    except Exception:
        if loc_written:
            if loc_existed: _atomic(loc_target,loc_original)
            else: loc_target.unlink(missing_ok=True)
        for asset in reversed(created_assets): (project/asset['path']).unlink(missing_ok=True)
        if src_written: source_target.unlink(missing_ok=True)
        raise
    result=structured_content_state(project,source_relative); result.update({'displayName':display,'description':desc,'texture':texture_state,'assets':created_assets,'localizationPath':'Localization/en-US.hjson' if creates else None,'localizationKeys':list(creates)}); return result
