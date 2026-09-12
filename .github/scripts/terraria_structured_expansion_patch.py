from pathlib import Path

engine = Path('games/terraria/structured_content.py')
text = engine.read_text(encoding='utf-8')

def one(old: str, new: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'expected one engine anchor, found {count}: {old[:140]!r}')
    text = text.replace(old, new, 1)

# Deepen existing Item fields.
one(
    '        Field("useTime", "Use time", "int", 0, "USE", 0, 10000), Field("useAnimation", "Use animation", "int", 0, "USE", 0, 10000), Field("autoReuse", "Auto reuse", "bool", False, "USE"), Field("consumable", "Consumable", "bool", False, "USE"), Field("accessory", "Accessory", "bool", False, "USE"), Field("shootSpeed", "Shoot speed", "float", 0.0, "USE", 0, 10000),\n',
    '        Field("useTime", "Use time", "int", 0, "USE", 0, 10000), Field("useAnimation", "Use animation", "int", 0, "USE", 0, 10000), Field("useStyle", "Use style ID", "int", 0, "USE", 0, 1000), Field("useTurn", "Turn while using", "bool", False, "USE"), Field("autoReuse", "Auto reuse", "bool", False, "USE"), Field("channel", "Channel", "bool", False, "USE"), Field("noMelee", "No melee hitbox", "bool", False, "USE"), Field("consumable", "Consumable", "bool", False, "USE"), Field("accessory", "Accessory", "bool", False, "USE"), Field("shootSpeed", "Shoot speed", "float", 0.0, "USE", 0, 10000),\n'
    '        Field("mana", "Mana cost", "int", 0, "CONSUMPTION", 0, 100000), Field("healLife", "Heal life", "int", 0, "CONSUMPTION", 0, 100000), Field("healMana", "Heal mana", "int", 0, "CONSUMPTION", 0, 100000),\n'
    '        Field("pick", "Pickaxe power", "int", 0, "TOOLS", 0, 100000), Field("axe", "Axe power", "int", 0, "TOOLS", 0, 100000), Field("hammer", "Hammer power", "int", 0, "TOOLS", 0, 100000),\n'
    '        Field("ammo", "Ammo category ID", "int", 0, "AMMO / PROJECTILE", 0, 100000), Field("useAmmo", "Consumes ammo category ID", "int", 0, "AMMO / PROJECTILE", 0, 100000), Field("shoot", "Projectile type ID", "int", 0, "AMMO / PROJECTILE", 0, 100000),\n'
    '        Field("createTile", "Places tile ID (-1 none)", "int", -1, "PLACEMENT", -1, 100000), Field("createWall", "Places wall ID (-1 none)", "int", -1, "PLACEMENT", -1, 100000), Field("placeStyle", "Placement style", "int", 0, "PLACEMENT", 0, 100000),\n'
    '        Field("defense", "Accessory defense", "int", 0, "EQUIP", -10000, 100000),\n',
)

# Deepen NPC flags/state.
one(
    '        Field("friendly", "Friendly", "bool", False, "FLAGS"), Field("boss", "Boss", "bool", False, "FLAGS"), Field("noGravity", "No gravity", "bool", False, "FLAGS"), Field("noTileCollide", "No tile collision", "bool", False, "FLAGS"),\n',
    '        Field("friendly", "Friendly", "bool", False, "FLAGS"), Field("townNPC", "Town NPC", "bool", False, "FLAGS"), Field("boss", "Boss", "bool", False, "FLAGS"), Field("dontTakeDamage", "Invulnerable", "bool", False, "FLAGS"), Field("lavaImmune", "Lava immune", "bool", False, "FLAGS"), Field("noGravity", "No gravity", "bool", False, "FLAGS"), Field("noTileCollide", "No tile collision", "bool", False, "FLAGS"), Field("netAlways", "Always network-sync", "bool", False, "FLAGS"),\n'
    '        Field("npcSlots", "Spawn slot cost", "float", 1.0, "SPAWN", 0, 1000), Field("catchItem", "Catch item ID (0 none)", "int", 0, "SPAWN", 0, 100000),\n',
)

# Deepen Projectile networking/immunity/minion fields.
one(
    '        Field("timeLeft", "Lifetime (ticks)", "int", 3600, "MOVEMENT", 1, 10_000_000), Field("tileCollide", "Collide with tiles", "bool", True, "MOVEMENT"), Field("ignoreWater", "Ignore water", "bool", False, "MOVEMENT"), Field("extraUpdates", "Extra updates", "int", 0, "MOVEMENT", 0, 100), Field("aiStyle", "AI style", "int", -1, "AI", -1, 10000), Field("aiType", "Vanilla AI type ID", "int", -1, "AI", -1, 100000),\n',
    '        Field("timeLeft", "Lifetime (ticks)", "int", 3600, "MOVEMENT", 1, 10_000_000), Field("tileCollide", "Collide with tiles", "bool", True, "MOVEMENT"), Field("ignoreWater", "Ignore water", "bool", False, "MOVEMENT"), Field("extraUpdates", "Extra updates", "int", 0, "MOVEMENT", 0, 100), Field("aiStyle", "AI style", "int", -1, "AI", -1, 10000), Field("aiType", "Vanilla AI type ID", "int", -1, "AI", -1, 100000),\n'
    '        Field("usesLocalNPCImmunity", "Per-projectile NPC immunity", "bool", False, "NPC IMMUNITY"), Field("localNPCHitCooldown", "Local hit cooldown (-1 once/NPC)", "int", -1, "NPC IMMUNITY", -1, 100000), Field("usesIDStaticNPCImmunity", "Shared type NPC immunity", "bool", False, "NPC IMMUNITY"), Field("idStaticNPCHitCooldown", "Shared hit cooldown", "int", 10, "NPC IMMUNITY", 1, 100000),\n'
    '        Field("minion", "Minion", "bool", False, "SPECIAL"), Field("minionSlots", "Minion slots", "float", 1.0, "SPECIAL", 0, 1000), Field("netImportant", "Sync to joining players", "bool", False, "SPECIAL"), Field("hide", "Hide normal draw", "bool", False, "SPECIAL"),\n',
)

# Add ModWall, GlobalProjectile and ModPrefix schemas.
one(
    '    "recipe": (\n',
    '    "wall": (\n'
    '        Field("housingSafe", "Counts as housing wall", "bool", True, "WALL"), Field("dustType", "Dust ID", "int", 0, "WALL", -1, 100000),\n'
    '        Field("mapR", "Map red", "int", 180, "MAP", 0, 255), Field("mapG", "Map green", "int", 180, "MAP", 0, 255), Field("mapB", "Map blue", "int", 180, "MAP", 0, 255),\n'
    '        Field("dropKind", "Fallback drop type", "enum", "none", "DROP", options=("none", "vanilla", "modItem")), Field("dropItemId", "Vanilla drop item ID", "int", 0, "DROP", 0, 100000), Field("dropItemName", "Mod drop item class", "identifier", "", "DROP"),\n'
    '    ),\n'
    '    "globalProjectile": (\n'
    '        Field("targetId", "Target vanilla projectile ID", "int", 0, "TARGET", 0, 100000),\n'
    '        Field("friendlyOverride", "Friendly override", "enum", "unchanged", "FLAGS", options=("unchanged", "true", "false")), Field("hostileOverride", "Hostile override", "enum", "unchanged", "FLAGS", options=("unchanged", "true", "false")), Field("tileCollideOverride", "Tile collision override", "enum", "unchanged", "FLAGS", options=("unchanged", "true", "false")),\n'
    '        Field("damageClass", "Damage class override", "enum", "Unchanged", "COMBAT", options=("Unchanged",) + _DAMAGE_CLASSES), Field("penetrateOverride", "Penetration override (-999 unchanged)", "int", -999, "COMBAT", -999, 100000),\n'
    '        Field("timeLeftMultiplier", "Lifetime multiplier", "float", 1.0, "MODIFIERS", 0.01, 1000), Field("scaleMultiplier", "Scale multiplier", "float", 1.0, "MODIFIERS", 0.01, 1000), Field("extraUpdatesAdd", "Extra updates adjustment", "int", 0, "MODIFIERS", -100, 100),\n'
    '    ),\n'
    '    "prefix": (\n'
    '        Field("category", "Prefix category", "enum", "AnyWeapon", "ROLLING", options=("Melee", "Ranged", "Magic", "AnyWeapon", "Accessory", "Custom")), Field("rollChance", "Relative roll chance", "float", 1.0, "ROLLING", 0, 100000), Field("canRoll", "Can roll", "bool", True, "ROLLING"),\n'
    '        Field("damageMult", "Damage multiplier", "float", 1.0, "STATS", 0, 1000), Field("knockBackMult", "Knockback multiplier", "float", 1.0, "STATS", 0, 1000), Field("useTimeMult", "Use-time multiplier", "float", 1.0, "STATS", 0.01, 1000), Field("scaleMult", "Scale multiplier", "float", 1.0, "STATS", 0.01, 1000), Field("shootSpeedMult", "Shoot-speed multiplier", "float", 1.0, "STATS", 0, 1000), Field("manaMult", "Mana-cost multiplier", "float", 1.0, "STATS", 0, 1000), Field("critBonus", "Critical chance bonus", "int", 0, "STATS", -1000, 1000), Field("valueMult", "Value multiplier", "float", 1.0, "VALUE", 0, 1000),\n'
    '    ),\n'
    '    "recipe": (\n',
)

one(
    '_LABELS = {"item":"ModItem","npc":"ModNPC","projectile":"ModProjectile","buff":"ModBuff","tile":"ModTile (simple 1×1)","globalItem":"GlobalItem (vanilla modifier)","globalNPC":"GlobalNPC (vanilla modifier)","recipe":"Recipe"}\n',
    '_LABELS = {"item":"ModItem","npc":"ModNPC","projectile":"ModProjectile","buff":"ModBuff","tile":"ModTile (simple 1×1)","wall":"ModWall","globalItem":"GlobalItem (vanilla modifier)","globalNPC":"GlobalNPC (vanilla modifier)","globalProjectile":"GlobalProjectile (vanilla modifier)","prefix":"ModPrefix","recipe":"Recipe"}\n',
)

one(
    '    if kind=="tile" and out["dropKind"]=="modItem" and not out["dropItemName"]: raise ValueError("Mod drop item class is required")\n',
    '    if kind in {"tile","wall"} and out["dropKind"]=="modItem" and not out["dropItemName"]: raise ValueError("Mod drop item class is required")\n'
    '    if kind=="projectile" and out["usesLocalNPCImmunity"] and out["usesIDStaticNPCImmunity"]: raise ValueError("Projectile cannot use local and shared ID-static NPC immunity at the same time")\n',
)

# Deepen renderers.
one(
    'def _render_item(v):\n    return ["public override void SetDefaults()","{",f"    Item.width = {v[\'width\']};",f"    Item.height = {v[\'height\']};",f"    Item.maxStack = {v[\'maxStack\']};",f"    Item.value = {v[\'value\']};",f"    Item.rare = {v[\'rare\']};",f"    Item.damage = {v[\'damage\']};",f"    Item.DamageType = DamageClass.{v[\'damageClass\']};",f"    Item.knockBack = {_f(v[\'knockBack\'])};",f"    Item.crit = {v[\'crit\']};",f"    Item.useTime = {v[\'useTime\']};",f"    Item.useAnimation = {v[\'useAnimation\']};",f"    Item.autoReuse = {_b(v[\'autoReuse\'])};",f"    Item.consumable = {_b(v[\'consumable\'])};",f"    Item.accessory = {_b(v[\'accessory\'])};",f"    Item.shootSpeed = {_f(v[\'shootSpeed\'])};","}"]\n',
    'def _render_item(v):\n'
    '    return ["public override void SetDefaults()","{",f"    Item.width = {v[\'width\']};",f"    Item.height = {v[\'height\']};",f"    Item.maxStack = {v[\'maxStack\']};",f"    Item.value = {v[\'value\']};",f"    Item.rare = {v[\'rare\']};",f"    Item.damage = {v[\'damage\']};",f"    Item.DamageType = DamageClass.{v[\'damageClass\']};",f"    Item.knockBack = {_f(v[\'knockBack\'])};",f"    Item.crit = {v[\'crit\']};",f"    Item.defense = {v[\'defense\']};",f"    Item.useTime = {v[\'useTime\']};",f"    Item.useAnimation = {v[\'useAnimation\']};",f"    Item.useStyle = {v[\'useStyle\']};",f"    Item.useTurn = {_b(v[\'useTurn\'])};",f"    Item.autoReuse = {_b(v[\'autoReuse\'])};",f"    Item.channel = {_b(v[\'channel\'])};",f"    Item.noMelee = {_b(v[\'noMelee\'])};",f"    Item.consumable = {_b(v[\'consumable\'])};",f"    Item.accessory = {_b(v[\'accessory\'])};",f"    Item.shootSpeed = {_f(v[\'shootSpeed\'])};",f"    Item.mana = {v[\'mana\']};",f"    Item.healLife = {v[\'healLife\']};",f"    Item.healMana = {v[\'healMana\']};",f"    Item.pick = {v[\'pick\']};",f"    Item.axe = {v[\'axe\']};",f"    Item.hammer = {v[\'hammer\']};",f"    Item.ammo = {v[\'ammo\']};",f"    Item.useAmmo = {v[\'useAmmo\']};",f"    Item.shoot = {v[\'shoot\']};",f"    Item.createTile = {v[\'createTile\']};",f"    Item.createWall = {v[\'createWall\']};",f"    Item.placeStyle = {v[\'placeStyle\']};","}"]\n',
)

one(
    '    out += ["public override void SetDefaults()","{",f"    NPC.width = {v[\'width\']};",f"    NPC.height = {v[\'height\']};",f"    NPC.lifeMax = {v[\'lifeMax\']};",f"    NPC.damage = {v[\'damage\']};",f"    NPC.defense = {v[\'defense\']};",f"    NPC.knockBackResist = {_f(v[\'knockBackResist\'])};",f"    NPC.value = {_f(v[\'value\'])};",f"    NPC.scale = {_f(v[\'scale\'])};",f"    NPC.aiStyle = {v[\'aiStyle\']};",f"    NPC.friendly = {_b(v[\'friendly\'])};",f"    NPC.boss = {_b(v[\'boss\'])};",f"    NPC.noGravity = {_b(v[\'noGravity\'])};",f"    NPC.noTileCollide = {_b(v[\'noTileCollide\'])};"]\n',
    '    out += ["public override void SetDefaults()","{",f"    NPC.width = {v[\'width\']};",f"    NPC.height = {v[\'height\']};",f"    NPC.lifeMax = {v[\'lifeMax\']};",f"    NPC.damage = {v[\'damage\']};",f"    NPC.defense = {v[\'defense\']};",f"    NPC.knockBackResist = {_f(v[\'knockBackResist\'])};",f"    NPC.value = {_f(v[\'value\'])};",f"    NPC.scale = {_f(v[\'scale\'])};",f"    NPC.aiStyle = {v[\'aiStyle\']};",f"    NPC.npcSlots = {_f(v[\'npcSlots\'])};",f"    NPC.catchItem = {v[\'catchItem\']};",f"    NPC.friendly = {_b(v[\'friendly\'])};",f"    NPC.townNPC = {_b(v[\'townNPC\'])};",f"    NPC.boss = {_b(v[\'boss\'])};",f"    NPC.dontTakeDamage = {_b(v[\'dontTakeDamage\'])};",f"    NPC.lavaImmune = {_b(v[\'lavaImmune\'])};",f"    NPC.noGravity = {_b(v[\'noGravity\'])};",f"    NPC.noTileCollide = {_b(v[\'noTileCollide\'])};",f"    NPC.netAlways = {_b(v[\'netAlways\'])};"]\n',
)

one(
    '    if v[\'aiType\']>=0: out.append(f"    AIType = {v[\'aiType\']};")\n    out += ["}"]; return out\n\ndef _render_buff(v):\n',
    '    if v[\'aiType\']>=0: out.append(f"    AIType = {v[\'aiType\']};")\n'
    '    out += [f"    Projectile.netImportant = {_b(v[\'netImportant\'])};",f"    Projectile.hide = {_b(v[\'hide\'])};"]\n'
    '    if v[\'usesLocalNPCImmunity\']:\n        out += ["    Projectile.usesLocalNPCImmunity = true;",f"    Projectile.localNPCHitCooldown = {v[\'localNPCHitCooldown\']};"]\n'
    '    if v[\'usesIDStaticNPCImmunity\']:\n        out += ["    Projectile.usesIDStaticNPCImmunity = true;",f"    Projectile.idStaticNPCHitCooldown = {v[\'idStaticNPCHitCooldown\']};"]\n'
    '    if v[\'minion\']:\n        out += ["    Projectile.minion = true;",f"    Projectile.minionSlots = {_f(v[\'minionSlots\'])};"]\n'
    '    out += ["}"]; return out\n\ndef _render_buff(v):\n',
)

# New family renderers.
one(
    'def _parse_ingredients(text):\n',
    'def _render_wall(mod,v):\n'
    '    out=["public override void SetStaticDefaults()","{",f"    Main.wallHouse[Type] = {_b(v[\'housingSafe\'])};",f"    DustType = {v[\'dustType\']};",f"    AddMapEntry(new Color({v[\'mapR\']}, {v[\'mapG\']}, {v[\'mapB\']}), CreateMapEntryName());"]\n'
    '    if v[\'dropKind\']==\'vanilla\': out.append(f"    RegisterItemDrop({v[\'dropItemId\']});")\n'
    '    elif v[\'dropKind\']==\'modItem\': out.append(f"    RegisterItemDrop(ModContent.ItemType<global::{mod}.Content.Items.{v[\'dropItemName\']}>());")\n'
    '    out += ["}"]; return out\n\n'
    'def _render_global_projectile(v):\n'
    '    out=[f"public override bool AppliesToEntity(Projectile entity, bool lateInstantiation) => entity.type == {v[\'targetId\']};","","public override void SetDefaults(Projectile entity)","{"]\n'
    '    if v[\'friendlyOverride\']!=\'unchanged\': out.append(f"    entity.friendly = {v[\'friendlyOverride\']};")\n'
    '    if v[\'hostileOverride\']!=\'unchanged\': out.append(f"    entity.hostile = {v[\'hostileOverride\']};")\n'
    '    if v[\'tileCollideOverride\']!=\'unchanged\': out.append(f"    entity.tileCollide = {v[\'tileCollideOverride\']};")\n'
    '    if v[\'damageClass\']!=\'Unchanged\': out.append(f"    entity.DamageType = DamageClass.{v[\'damageClass\']};")\n'
    '    if v[\'penetrateOverride\']!=-999: out.append(f"    entity.penetrate = {v[\'penetrateOverride\']};")\n'
    '    if v[\'timeLeftMultiplier\']!=1: out.append(f"    entity.timeLeft = (int)(entity.timeLeft * {_f(v[\'timeLeftMultiplier\'])});")\n'
    '    if v[\'scaleMultiplier\']!=1: out.append(f"    entity.scale *= {_f(v[\'scaleMultiplier\'])};")\n'
    '    if v[\'extraUpdatesAdd\']: out.append(f"    entity.extraUpdates += {v[\'extraUpdatesAdd\']};")\n'
    '    out += ["}"]; return out\n\n'
    'def _render_prefix(v):\n'
    '    out=[f"public override PrefixCategory Category => PrefixCategory.{v[\'category\']};",f"public override float RollChance(Item item) => {_f(v[\'rollChance\'])};",f"public override bool CanRoll(Item item) => {_b(v[\'canRoll\'])};","","public override void SetStats(ref float damageMult, ref float knockbackMult, ref float useTimeMult, ref float scaleMult, ref float shootSpeedMult, ref float manaMult, ref int critBonus)","{",f"    damageMult *= {_f(v[\'damageMult\'])};",f"    knockbackMult *= {_f(v[\'knockBackMult\'])};",f"    useTimeMult *= {_f(v[\'useTimeMult\'])};",f"    scaleMult *= {_f(v[\'scaleMult\'])};",f"    shootSpeedMult *= {_f(v[\'shootSpeedMult\'])};",f"    manaMult *= {_f(v[\'manaMult\'])};",f"    critBonus += {v[\'critBonus\']};","}"]\n'
    '    if v[\'valueMult\']!=1: out += ["","public override void ModifyValue(ref float valueMult)","{",f"    valueMult *= {_f(v[\'valueMult\'])};","}"]\n'
    '    return out\n\n'
    'def _parse_ingredients(text):\n',
)

one(
    "    return {'item':lambda:_render_item(v),'npc':lambda:_render_npc(mod,v),'projectile':lambda:_render_projectile(v),'buff':lambda:_render_buff(v),'tile':lambda:_render_tile(mod,v),'globalItem':lambda:_render_global_item(v),'globalNPC':lambda:_render_global_npc(v),'recipe':lambda:_render_recipe(mod,v)}[kind]()\n",
    "    return {'item':lambda:_render_item(v),'npc':lambda:_render_npc(mod,v),'projectile':lambda:_render_projectile(v),'buff':lambda:_render_buff(v),'tile':lambda:_render_tile(mod,v),'wall':lambda:_render_wall(mod,v),'globalItem':lambda:_render_global_item(v),'globalNPC':lambda:_render_global_npc(v),'globalProjectile':lambda:_render_global_projectile(v),'prefix':lambda:_render_prefix(v),'recipe':lambda:_render_recipe(mod,v)}[kind]()\n",
)

one(
    "        'tile':(f\"Content/Tiles/{name}.cs\",'ModTile',('Microsoft.Xna.Framework','Terraria','Terraria.ModLoader')),\n",
    "        'tile':(f\"Content/Tiles/{name}.cs\",'ModTile',('Microsoft.Xna.Framework','Terraria','Terraria.ModLoader')),\n"
    "        'wall':(f\"Content/Walls/{name}.cs\",'ModWall',('Microsoft.Xna.Framework','Terraria','Terraria.ModLoader')),\n",
)
one(
    "        'globalNPC':(f\"Common/GlobalNPCs/{name}.cs\",'GlobalNPC',('Terraria','Terraria.ModLoader')),\n",
    "        'globalNPC':(f\"Common/GlobalNPCs/{name}.cs\",'GlobalNPC',('Terraria','Terraria.ModLoader')),\n"
    "        'globalProjectile':(f\"Common/GlobalProjectiles/{name}.cs\",'GlobalProjectile',('Terraria','Terraria.ModLoader')),\n"
    "        'prefix':(f\"Content/Prefixes/{name}.cs\",'ModPrefix',('Terraria','Terraria.ModLoader')),\n",
)
one(
    "    return {'item':f'{mod}.Content.Items','npc':f'{mod}.Content.NPCs','projectile':f'{mod}.Content.Projectiles','buff':f'{mod}.Content.Buffs','tile':f'{mod}.Content.Tiles','globalItem':f'{mod}.Common.GlobalItems','globalNPC':f'{mod}.Common.GlobalNPCs','recipe':f'{mod}.Common.Recipes'}[kind]\n",
    "    return {'item':f'{mod}.Content.Items','npc':f'{mod}.Content.NPCs','projectile':f'{mod}.Content.Projectiles','buff':f'{mod}.Content.Buffs','tile':f'{mod}.Content.Tiles','wall':f'{mod}.Content.Walls','globalItem':f'{mod}.Common.GlobalItems','globalNPC':f'{mod}.Common.GlobalNPCs','globalProjectile':f'{mod}.Common.GlobalProjectiles','prefix':f'{mod}.Content.Prefixes','recipe':f'{mod}.Common.Recipes'}[kind]\n",
)

one(
    "    if kind=='tile': return {f\"Mods.{mod}.Tiles.{name}.MapEntry\":display}\n",
    "    if kind=='tile': return {f\"Mods.{mod}.Tiles.{name}.MapEntry\":display}\n"
    "    if kind=='wall': return {f\"Mods.{mod}.Walls.{name}.MapEntry\":display}\n"
    "    if kind=='prefix': return {f\"Mods.{mod}.Prefixes.{name}.DisplayName\":display}\n",
)
one(
    "    needs_texture=kind in {'item','npc','projectile','buff','tile'}; texture_relative=source_relative[:-3]+'.png'; texture_target=project/texture_relative\n",
    "    needs_texture=kind in {'item','npc','projectile','buff','tile','wall'}; texture_relative=source_relative[:-3]+'.png'; texture_target=project/texture_relative\n",
)

engine.write_text(text, encoding='utf-8')

# Dynamic UI only needs to know that walls and prefixes have a localized display/map name.
editor = Path('games/terraria/editor.html')
ui = editor.read_text(encoding='utf-8')
old='  function localizedContentKind(kind){return ["item","npc","projectile","buff","tile"].includes(kind)}\n'
new='  function localizedContentKind(kind){return ["item","npc","projectile","buff","tile","wall","prefix"].includes(kind)}\n'
if ui.count(old)!=1: raise SystemExit('localizedContentKind UI anchor missing')
editor.write_text(ui.replace(old,new,1),encoding='utf-8')

# Expand the existing exact-kind regression.
test = Path('tests/test_terraria_structured_content.py')
t = test.read_text(encoding='utf-8')
old='            {"item", "npc", "projectile", "buff", "tile", "globalItem", "globalNPC", "recipe"},\n'
new='            {"item", "npc", "projectile", "buff", "tile", "wall", "globalItem", "globalNPC", "globalProjectile", "prefix", "recipe"},\n'
if t.count(old)!=1: raise SystemExit('schema-kind test anchor missing')
test.write_text(t.replace(old,new,1),encoding='utf-8')

Path('tests/test_terraria_structured_content_expansion.py').write_text(r'''from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from games.terraria.localization import parse_localization_text
from games.terraria.structured_content import create_structured_content, default_values, render_structured_source, validate_values


class TerrariaStructuredContentExpansionTests(unittest.TestCase):
    def test_item_exposes_tools_ammo_healing_placement_and_use_fields(self):
        values=default_values("item")
        values.update({"useStyle":1,"useTurn":True,"noMelee":True,"channel":True,"mana":8,"healLife":20,"pick":55,"axe":15,"hammer":35,"ammo":40,"useAmmo":40,"shoot":14,"createTile":1,"createWall":2,"placeStyle":3,"defense":4})
        source=render_structured_source("ExampleMod","item","UtilityItem",values)
        for expected in (
            "Item.useStyle = 1;","Item.useTurn = true;","Item.noMelee = true;","Item.channel = true;","Item.mana = 8;","Item.healLife = 20;","Item.pick = 55;","Item.axe = 15;","Item.hammer = 35;","Item.ammo = 40;","Item.useAmmo = 40;","Item.shoot = 14;","Item.createTile = 1;","Item.createWall = 2;","Item.placeStyle = 3;","Item.defense = 4;"
        ):
            self.assertIn(expected,source)

    def test_npc_exposes_town_spawn_slot_and_safety_flags(self):
        values=default_values("npc")
        values.update({"townNPC":True,"dontTakeDamage":True,"lavaImmune":True,"netAlways":True,"npcSlots":2.5,"catchItem":2673})
        source=render_structured_source("ExampleMod","npc","TownCritter",values)
        self.assertIn("NPC.townNPC = true;",source)
        self.assertIn("NPC.dontTakeDamage = true;",source)
        self.assertIn("NPC.lavaImmune = true;",source)
        self.assertIn("NPC.netAlways = true;",source)
        self.assertIn("NPC.npcSlots = 2.5f;",source)
        self.assertIn("NPC.catchItem = 2673;",source)

    def test_projectile_immunity_minion_and_network_fields(self):
        values=default_values("projectile")
        values.update({"usesLocalNPCImmunity":True,"localNPCHitCooldown":20,"minion":True,"minionSlots":1.5,"netImportant":True,"hide":True})
        source=render_structured_source("ExampleMod","projectile","MinionShot",values)
        self.assertIn("Projectile.usesLocalNPCImmunity = true;",source)
        self.assertIn("Projectile.localNPCHitCooldown = 20;",source)
        self.assertIn("Projectile.minion = true;",source)
        self.assertIn("Projectile.minionSlots = 1.5f;",source)
        self.assertIn("Projectile.netImportant = true;",source)
        self.assertIn("Projectile.hide = true;",source)
        with self.assertRaisesRegex(ValueError,"cannot use local and shared"):
            validate_values("projectile",{"usesLocalNPCImmunity":True,"usesIDStaticNPCImmunity":True})

    def test_modwall_generates_map_housing_dust_and_drop(self):
        values=default_values("wall")
        values.update({"housingSafe":False,"dustType":7,"mapR":12,"mapG":34,"mapB":56,"dropKind":"modItem","dropItemName":"ExampleWallItem"})
        source=render_structured_source("ExampleMod","wall","ExampleWall",values)
        self.assertIn("public sealed class ExampleWall : ModWall",source)
        self.assertIn("Main.wallHouse[Type] = false;",source)
        self.assertIn("DustType = 7;",source)
        self.assertIn("new Color(12, 34, 56)",source)
        self.assertIn("ExampleMod.Content.Items.ExampleWallItem",source)

    def test_global_projectile_is_target_filtered_and_tri_state(self):
        values=default_values("globalProjectile")
        values.update({"targetId":14,"friendlyOverride":"true","tileCollideOverride":"false","damageClass":"Ranged","penetrateOverride":5,"timeLeftMultiplier":0.5,"scaleMultiplier":1.25,"extraUpdatesAdd":1})
        source=render_structured_source("ExampleMod","globalProjectile","ArrowTweaks",values)
        self.assertIn("entity.type == 14",source)
        self.assertIn("entity.friendly = true;",source)
        self.assertNotIn("entity.hostile =",source)
        self.assertIn("entity.tileCollide = false;",source)
        self.assertIn("entity.DamageType = DamageClass.Ranged;",source)
        self.assertIn("entity.penetrate = 5;",source)
        self.assertIn("entity.timeLeft = (int)(entity.timeLeft * 0.5f);",source)
        self.assertIn("entity.scale *= 1.25f;",source)
        self.assertIn("entity.extraUpdates += 1;",source)

    def test_prefix_uses_current_category_setstats_and_value_hooks(self):
        values=default_values("prefix")
        values.update({"category":"Magic","rollChance":2.5,"damageMult":1.2,"useTimeMult":0.9,"manaMult":0.8,"critBonus":4,"valueMult":1.3})
        source=render_structured_source("ExampleMod","prefix","Arcane",values)
        self.assertIn("public sealed class Arcane : ModPrefix",source)
        self.assertIn("PrefixCategory.Magic",source)
        self.assertIn("RollChance(Item item) => 2.5f",source)
        self.assertIn("damageMult *= 1.2f;",source)
        self.assertIn("useTimeMult *= 0.9f;",source)
        self.assertIn("manaMult *= 0.8f;",source)
        self.assertIn("critBonus += 4;",source)
        self.assertIn("valueMult *= 1.3f;",source)

    def test_wall_and_prefix_creation_create_only_expected_resources(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/"ExampleMod"; root.mkdir()
            wall=create_structured_content(root,"wall","StoneWall",{},"Stone Wall","")
            prefix=create_structured_content(root,"prefix","HeavyPrefix",{},"Heavy","")
            self.assertIsNotNone(wall["texture"])
            self.assertTrue((root/"Content/Walls/StoneWall.png").is_file())
            self.assertIsNone(prefix["texture"])
            values={entry.key:entry.value for entry in parse_localization_text((root/"Localization/en-US.hjson").read_text(encoding="utf-8")).entries}
            self.assertEqual(values["Mods.ExampleMod.Walls.StoneWall.MapEntry"],"Stone Wall")
            self.assertEqual(values["Mods.ExampleMod.Prefixes.HeavyPrefix.DisplayName"],"Heavy")


if __name__ == "__main__":
    unittest.main()
''',encoding='utf-8')
