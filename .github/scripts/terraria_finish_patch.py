from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one anchor, found {count}")
    return text.replace(old, new, 1)


# Rectangular placeholder PNGs are needed for native tModLoader sprite-sheet shapes such as ModDust.
path = Path("games/terraria/content_wizard.py")
text = path.read_text(encoding="utf-8")
start = text.index("def placeholder_png(")
end = text.index("\n\ndef _localization_target", start)
new_placeholder = '''def placeholder_png(size: int = 16, height: int | None = None) -> bytes:
    """Generate a valid visible checker texture that is intentionally replaceable."""
    width = size
    height = width if height is None else height
    if width < 1 or width > 256 or height < 1 or height > 256:
        raise ValueError("Placeholder texture size is out of range")
    rows = []
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            bright = ((x // 4) + (y // 4)) % 2 == 0
            row.extend((255, 0 if bright else 64, 255, 255))
        rows.append(bytes(row))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        b"\\x89PNG\\r\\n\\x1a\\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", zlib.compress(b"".join(rows), 9))
        + _png_chunk(b"IEND", b"")
    )
'''
text = text[:start] + new_placeholder + text[end:]
path.write_text(text, encoding="utf-8")


# Expand the schema-driven content editor.
path = Path("games/terraria/structured_content.py")
text = path.read_text(encoding="utf-8")

text = replace_once(
    text,
    '        Field("spawnChance", "Constant spawn chance", "float", 0.0, "SPAWN", 0, 1, help="0 leaves natural spawning undefined; positive emits a constant SpawnChance."),\n        Field("lootKind", "Simple loot type", "enum", "none", "LOOT", options=("none", "vanilla", "modItem")),',
    '        Field("spawnChance", "Base spawn chance", "float", 0.0, "SPAWN", 0, 1, help="0 leaves natural spawning undefined; positive enables the structured spawn rules below."),\n'
    '        Field("spawnZone", "Player biome", "enum", "Any", "SPAWN CONDITIONS", options=("Any","Forest","Jungle","Snow","Desert","Beach","Dungeon","Corruption","Crimson","Hallow","Glowshroom")),\n'
    '        Field("spawnDepth", "Depth", "enum", "Any", "SPAWN CONDITIONS", options=("Any","Sky","Overworld","DirtLayer","RockLayer","Underworld")), Field("spawnTime", "Time", "enum", "Any", "SPAWN CONDITIONS", options=("Any","Day","Night")), Field("spawnHardmode", "World mode", "enum", "Any", "SPAWN CONDITIONS", options=("Any","PreHardmode","Hardmode")), Field("spawnRain", "Weather", "enum", "Any", "SPAWN CONDITIONS", options=("Any","Raining","Dry")),\n'
    '        Field("spawnWater", "Spawn tile water", "enum", "Any", "SPAWN CONTEXT", options=("Any","Water","Dry")), Field("spawnSafety", "Player safety", "enum", "Any", "SPAWN CONTEXT", options=("Any","Safe","Unsafe")), Field("spawnTown", "Town state", "enum", "Any", "SPAWN CONTEXT", options=("Any","InTown","OutsideTown")), Field("spawnInvasion", "Invasion state", "enum", "Any", "SPAWN CONTEXT", options=("Any","Invasion","NoInvasion")), Field("spawnSpecial", "Special spawn area", "enum", "Any", "SPAWN CONTEXT", options=("Any","Granite","Marble","DesertCave","SpiderCave","Lihzahrd")),\n'
    '        Field("lootKind", "Primary loot type", "enum", "none", "LOOT", options=("none", "vanilla", "modItem")),',
    "npc spawn schema",
)
text = replace_once(
    text,
    '        Field("lootKind", "Primary loot type", "enum", "none", "LOOT", options=("none", "vanilla", "modItem")), Field("lootItemId", "Vanilla loot item ID", "int", 0, "LOOT", 0, 100000), Field("lootItemName", "Mod loot item class", "identifier", "", "LOOT"), Field("lootChance", "Loot chance denominator", "int", 1, "LOOT", 1, 1_000_000), Field("lootMin", "Loot minimum stack", "int", 1, "LOOT", 1, 9999), Field("lootMax", "Loot maximum stack", "int", 1, "LOOT", 1, 9999),\n',
    '        Field("lootKind", "Primary loot type", "enum", "none", "LOOT", options=("none", "vanilla", "modItem")), Field("lootItemId", "Vanilla loot item ID", "int", 0, "LOOT", 0, 100000), Field("lootItemName", "Mod loot item class", "identifier", "", "LOOT"), Field("lootChance", "Loot chance denominator", "int", 1, "LOOT", 1, 1_000_000), Field("lootMin", "Loot minimum stack", "int", 1, "LOOT", 1, 9999), Field("lootMax", "Loot maximum stack", "int", 1, "LOOT", 1, 9999),\n'
    '        Field("lootRules", "Additional loot rules", "lines", "", "LOOT", help="One per line: vanilla:<id>,<chance denominator>,<min>,<max> or mod:<ClassName>,<chance>,<min>,<max>. Missing numeric columns default to 1."),\n',
    "npc loot rules schema",
)

text = replace_once(
    text,
    '    "recipe": (\n',
    '    "sceneEffect": (\n'
    '        Field("enabled", "Enable scene condition", "bool", False, "ACTIVATION", help="Disabled scene effects never activate until configured and enabled."), Field("zone", "Player biome", "enum", "Any", "ACTIVATION", options=("Any","Forest","Jungle","Snow","Desert","Beach","Dungeon","Corruption","Crimson","Hallow","Glowshroom")), Field("depth", "Depth", "enum", "Any", "ACTIVATION", options=("Any","Sky","Overworld","DirtLayer","RockLayer","Underworld")), Field("time", "Time", "enum", "Any", "ACTIVATION", options=("Any","Day","Night")), Field("hardmode", "World mode", "enum", "Any", "ACTIVATION", options=("Any","PreHardmode","Hardmode")), Field("rain", "Weather", "enum", "Any", "ACTIVATION", options=("Any","Raining","Dry")),\n'
    '        Field("music", "Music ID (-1 inherit)", "int", -1, "SCENE", -1, 100000), Field("priority", "Scene priority", "enum", "None", "SCENE", options=("None","BiomeLow","BiomeMedium","BiomeHigh","Environment","Event","BossLow","BossMedium","BossHigh")), Field("weight", "Priority weight", "float", 0.5, "SCENE", 0, 1),\n'
    '    ),\n'
    '    "dust": (\n'
    '        Field("updateType", "Copy vanilla dust behavior (-1 none)", "int", -1, "BEHAVIOR", -1, 100000), Field("vanillaUpdate", "Run vanilla dust update", "bool", True, "BEHAVIOR"), Field("midUpdateOwnBehavior", "Handle MidUpdate behavior", "bool", False, "BEHAVIOR"),\n'
    '        Field("noGravity", "No gravity", "bool", False, "SPAWN"), Field("noLight", "Ignore lighting flag", "bool", False, "SPAWN"), Field("fadeIn", "Fade-in value", "float", 0.0, "SPAWN", 0, 1000), Field("scaleMultiplier", "Scale multiplier", "float", 1.0, "SPAWN", 0.01, 1000), Field("velocityMultiplier", "Velocity multiplier", "float", 1.0, "SPAWN", 0, 1000), Field("fullbright", "Draw fullbright", "bool", False, "DRAW"),\n'
    '    ),\n'
    '    "globalBuff": (\n'
    '        Field("targetId", "Target buff ID", "int", 0, "TARGET", 0, 100000), Field("defenseBonus", "Player defense bonus", "int", 0, "PLAYER EFFECT", -10000, 10000), Field("moveSpeedBonus", "Move speed bonus", "float", 0.0, "PLAYER EFFECT", -10, 100), Field("lifeRegenBonus", "Life regen bonus", "int", 0, "PLAYER EFFECT", -100000, 100000), Field("allowCancel", "Allow right-click cancel", "bool", True, "BEHAVIOR"),\n'
    '    ),\n'
    '    "globalTile": (\n'
    '        Field("targetId", "Target tile ID", "int", 0, "TARGET", 0, 100000), Field("allowDrop", "Allow default drop", "bool", True, "BEHAVIOR"), Field("dangerous", "Dangersense override", "enum", "unchanged", "SENSES", options=("unchanged","true","false")), Field("spelunkable", "Spelunker override", "enum", "unchanged", "SENSES", options=("unchanged","true","false")),\n'
    '    ),\n'
    '    "globalWall": (\n'
    '        Field("targetId", "Target wall ID", "int", 0, "TARGET", 0, 100000), Field("allowDefaultDrop", "Allow default drop", "bool", True, "DROP"), Field("dropOverride", "Drop item ID (-1 unchanged)", "int", -1, "DROP", -1, 100000), Field("allowTeleport", "Allow teleport destination", "bool", True, "BEHAVIOR"),\n'
    '    ),\n'
    '    "recipe": (\n',
    "new structured families",
)

old_labels = '_LABELS = {"item":"ModItem","npc":"ModNPC","projectile":"ModProjectile","buff":"ModBuff","tile":"ModTile (simple 1×1)","wall":"ModWall","globalItem":"GlobalItem (vanilla modifier)","globalNPC":"GlobalNPC (vanilla modifier)","globalProjectile":"GlobalProjectile (vanilla modifier)","prefix":"ModPrefix","rarity":"ModRarity","biome":"ModBiome","config":"ModConfig","command":"ModCommand","recipe":"Recipe"}\n'
new_labels = '_LABELS = {"item":"ModItem","npc":"ModNPC","projectile":"ModProjectile","buff":"ModBuff","tile":"ModTile (simple 1×1)","wall":"ModWall","globalItem":"GlobalItem (vanilla modifier)","globalNPC":"GlobalNPC (vanilla modifier)","globalProjectile":"GlobalProjectile (vanilla modifier)","prefix":"ModPrefix","rarity":"ModRarity","biome":"ModBiome","config":"ModConfig","command":"ModCommand","sceneEffect":"ModSceneEffect","dust":"ModDust","globalBuff":"GlobalBuff","globalTile":"GlobalTile","globalWall":"GlobalWall","recipe":"Recipe"}\n'
text = replace_once(text, old_labels, new_labels, "labels")

text = replace_once(
    text,
    '        if out["lootKind"]=="modItem" and not out["lootItemName"]: raise ValueError("Mod loot item class is required")\n',
    '        if out["lootKind"]=="modItem" and not out["lootItemName"]: raise ValueError("Mod loot item class is required")\n        _parse_loot_rules(out["lootRules"])\n',
    "loot validation",
)

parser_anchor = 'def _parse_config_fields(text):\n'
parser = '''def _parse_loot_rules(text):
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

'''
text = replace_once(text, parser_anchor, parser + parser_anchor, "loot parser")

# Spawn conditions use only stable 1.4.4 NPCSpawnInfo/Player/Main fields.
spawn_helper = '''def _npc_spawn_condition(v):
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

'''
text = replace_once(text, 'def _render_npc(mod,v):\n', spawn_helper + 'def _render_npc(mod,v):\n', "npc spawn helper")

text = replace_once(
    text,
    '    if v[\'spawnChance\']>0: out += ["",f"public override float SpawnChance(NPCSpawnInfo spawnInfo) => {_f(v[\'spawnChance\'])};"]\n    if v[\'lootKind\']!=\'none\':\n        item=str(v[\'lootItemId\']) if v[\'lootKind\']==\'vanilla\' else f"ModContent.ItemType<global::{mod}.Content.Items.{v[\'lootItemName\']}>()"\n        out += ["","public override void ModifyNPCLoot(NPCLoot npcLoot)","{",f"    npcLoot.Add(ItemDropRule.Common({item}, {v[\'lootChance\']}, {v[\'lootMin\']}, {v[\'lootMax\']}));","}"]\n    return out\n',
    '    if v[\'spawnChance\']>0: out += ["",f"public override float SpawnChance(NPCSpawnInfo spawnInfo) => ({_npc_spawn_condition(v)}) ? {_f(v[\'spawnChance\'])} : 0f;"]\n'
    '    loot=[]\n'
    '    if v[\'lootKind\']!=\'none\':\n'
    '        item=str(v[\'lootItemId\']) if v[\'lootKind\']==\'vanilla\' else f"ModContent.ItemType<global::{mod}.Content.Items.{v[\'lootItemName\']}>()"\n'
    '        loot.append(f"npcLoot.Add(ItemDropRule.Common({item}, {v[\'lootChance\']}, {v[\'lootMin\']}, {v[\'lootMax\']}));")\n'
    '    for kind,value,chance,minimum,maximum in _parse_loot_rules(v[\'lootRules\']):\n'
    '        item=str(value) if kind==\'vanilla\' else f"ModContent.ItemType<global::{mod}.Content.Items.{value}>()"\n'
    '        loot.append(f"npcLoot.Add(ItemDropRule.Common({item}, {chance}, {minimum}, {maximum}));")\n'
    '    if loot: out += ["","public override void ModifyNPCLoot(NPCLoot npcLoot)","{",*("    "+line for line in loot),"}"]\n'
    '    return out\n',
    "npc rendering",
)

# Additional safe managed families.
render_anchor = 'def _render_rarity(v):\n'
new_renderers = '''def _scene_effect_condition(v):
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

'''
text = replace_once(text, render_anchor, new_renderers + render_anchor, "new renderers")

old_region = "    return {'item':lambda:_render_item(v),'npc':lambda:_render_npc(mod,v),'projectile':lambda:_render_projectile(v),'buff':lambda:_render_buff(v),'tile':lambda:_render_tile(mod,v),'wall':lambda:_render_wall(mod,v),'globalItem':lambda:_render_global_item(v),'globalNPC':lambda:_render_global_npc(v),'globalProjectile':lambda:_render_global_projectile(v),'prefix':lambda:_render_prefix(v),'rarity':lambda:_render_rarity(v),'biome':lambda:_render_biome(v),'config':lambda:_render_config(v),'command':lambda:_render_command(v),'recipe':lambda:_render_recipe(mod,v)}[kind]()\n"
new_region = "    return {'item':lambda:_render_item(v),'npc':lambda:_render_npc(mod,v),'projectile':lambda:_render_projectile(v),'buff':lambda:_render_buff(v),'tile':lambda:_render_tile(mod,v),'wall':lambda:_render_wall(mod,v),'globalItem':lambda:_render_global_item(v),'globalNPC':lambda:_render_global_npc(v),'globalProjectile':lambda:_render_global_projectile(v),'prefix':lambda:_render_prefix(v),'rarity':lambda:_render_rarity(v),'biome':lambda:_render_biome(v),'config':lambda:_render_config(v),'command':lambda:_render_command(v),'sceneEffect':lambda:_render_scene_effect(v),'dust':lambda:_render_dust(v),'globalBuff':lambda:_render_global_buff(v),'globalTile':lambda:_render_global_tile(v),'globalWall':lambda:_render_global_wall(v),'recipe':lambda:_render_recipe(mod,v)}[kind]()\n"
text = replace_once(text, old_region, new_region, "render dispatch")

text = replace_once(
    text,
    "        'command':(f\"Common/Commands/{name}.cs\",'ModCommand',('Terraria.ModLoader',)),\n        'recipe':",
    "        'command':(f\"Common/Commands/{name}.cs\",'ModCommand',('Terraria.ModLoader',)),\n        'sceneEffect':(f\"Content/SceneEffects/{name}.cs\",'ModSceneEffect',('Terraria','Terraria.ModLoader')),\n        'dust':(f\"Content/Dusts/{name}.cs\",'ModDust',('Microsoft.Xna.Framework','Terraria','Terraria.ModLoader')),\n        'globalBuff':(f\"Common/GlobalBuffs/{name}.cs\",'GlobalBuff',('Terraria','Terraria.ModLoader')),\n        'globalTile':(f\"Common/GlobalTiles/{name}.cs\",'GlobalTile',('Terraria','Terraria.ModLoader')),\n        'globalWall':(f\"Common/GlobalWalls/{name}.cs\",'GlobalWall',('Terraria','Terraria.ModLoader')),\n        'recipe':",
    "kind specs",
)
old_namespace = "    return {'item':f'{mod}.Content.Items','npc':f'{mod}.Content.NPCs','projectile':f'{mod}.Content.Projectiles','buff':f'{mod}.Content.Buffs','tile':f'{mod}.Content.Tiles','wall':f'{mod}.Content.Walls','globalItem':f'{mod}.Common.GlobalItems','globalNPC':f'{mod}.Common.GlobalNPCs','globalProjectile':f'{mod}.Common.GlobalProjectiles','prefix':f'{mod}.Content.Prefixes','rarity':f'{mod}.Content.Rarities','biome':f'{mod}.Content.Biomes','config':f'{mod}.Common.Configs','command':f'{mod}.Common.Commands','recipe':f'{mod}.Common.Recipes'}[kind]\n"
new_namespace = "    return {'item':f'{mod}.Content.Items','npc':f'{mod}.Content.NPCs','projectile':f'{mod}.Content.Projectiles','buff':f'{mod}.Content.Buffs','tile':f'{mod}.Content.Tiles','wall':f'{mod}.Content.Walls','globalItem':f'{mod}.Common.GlobalItems','globalNPC':f'{mod}.Common.GlobalNPCs','globalProjectile':f'{mod}.Common.GlobalProjectiles','prefix':f'{mod}.Content.Prefixes','rarity':f'{mod}.Content.Rarities','biome':f'{mod}.Content.Biomes','config':f'{mod}.Common.Configs','command':f'{mod}.Common.Commands','sceneEffect':f'{mod}.Content.SceneEffects','dust':f'{mod}.Content.Dusts','globalBuff':f'{mod}.Common.GlobalBuffs','globalTile':f'{mod}.Common.GlobalTiles','globalWall':f'{mod}.Common.GlobalWalls','recipe':f'{mod}.Common.Recipes'}[kind]\n"
text = replace_once(text, old_namespace, new_namespace, "namespaces")
text = replace_once(text, '    if kind=="biome": return "    private bool AdditionalCondition(Player player) => true;"\n', '    if kind in {"biome","sceneEffect"}: return "    private bool AdditionalCondition(Player player) => true;"\n', "custom condition hook")

old_assets = '''    primary_texture=kind in {'item','npc','projectile','buff','tile','wall'}
    asset_specs=[]
    if primary_texture: asset_specs.append((source_relative[:-3]+'.png',32 if kind=='buff' else 16))
    if kind=='biome': asset_specs += [(f'Content/Biomes/{name}_Icon.png',30),(f'Content/Biomes/{name}_Background.png',64)]
    for asset_relative,_size in asset_specs:
        if (project/asset_relative).exists(): raise ValueError(f"Asset file already exists: {asset_relative}")
'''
new_assets = '''    primary_texture=kind in {'item','npc','projectile','buff','tile','wall','dust'}
    asset_specs=[]
    if kind=='dust': asset_specs.append((source_relative[:-3]+'.png',10,30))
    elif primary_texture:
        size=32 if kind=='buff' else 16; asset_specs.append((source_relative[:-3]+'.png',size,size))
    if kind=='biome': asset_specs += [(f'Content/Biomes/{name}_Icon.png',30,30),(f'Content/Biomes/{name}_Background.png',64,64)]
    for asset_relative,_width,_height in asset_specs:
        if (project/asset_relative).exists(): raise ValueError(f"Asset file already exists: {asset_relative}")
'''
text = replace_once(text, old_assets, new_assets, "asset specs")
text = replace_once(text, '        for asset_relative,size in asset_specs:\n            created_assets.append(create_asset(project,asset_relative,placeholder_png(size)))\n', '        for asset_relative,width,height in asset_specs:\n            created_assets.append(create_asset(project,asset_relative,placeholder_png(width,height)))\n', "asset creation")

path.write_text(text, encoding="utf-8")


# tModLoader treats JSON null enabled state as an empty enabled set.
path = Path("games/terraria/server.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    '    if not isinstance(payload, list) or any(not isinstance(value, str) for value in payload):\n        state["enabledStateValid"] = False\n        state["enabledStateError"] = "tModLoader enabled.json must contain a JSON array of mod names"\n        return state\n    state["enabled"] = selected.name in set(payload)\n',
    '    if payload is None:\n        payload = []\n    elif not isinstance(payload, list) or any(not isinstance(value, str) for value in payload):\n        state["enabledStateValid"] = False\n        state["enabledStateError"] = "tModLoader enabled.json must contain a JSON array of mod names or null"\n        return state\n    state["enabled"] = selected.name in set(payload)\n',
    "enabled null parity",
)
path.write_text(text, encoding="utf-8")


# Let absent build booleans be intentionally added rather than shown as permanently read-only.
path = Path("games/terraria/editor.html")
text = path.read_text(encoding="utf-8")
old_bool = '''  function boolControl(key){
    if(!(key in current.values))return readonlyField("Not declared in build.txt");
    return el("input",{type:"checkbox",checked:!!current.values[key],disabled:!current.editable,onchange:event=>setValue(key,event.target.checked)});
  }
'''
new_bool = '''  function boolControl(key){
    const declared=key in current.values;
    const checkbox=el("input",{type:"checkbox",checked:declared?!!current.values[key]:false,disabled:!current.editable,onchange:event=>setValue(key,event.target.checked)});
    if(declared)return checkbox;
    return el("span",{class:"terraria-build-row"},checkbox,el("span",{class:"terraria-build-path"},"Not declared — check to add"));
  }
'''
text = replace_once(text, old_bool, new_bool, "boolean control")
text = replace_once(
    text,
    '        detailField({label:"INCLUDE SOURCE",control:boolControl("includeSource"),dataType:"BOOL"}),\n',
    '        detailField({label:"INCLUDE SOURCE",control:boolControl("includeSource"),dataType:"BOOL"}),\n        detailField({label:"NO COMPILE",control:boolControl("noCompile"),dataType:"BOOL"}),\n        detailField({label:"PLAYABLE ON PREVIEW",control:boolControl("playableOnPreview"),dataType:"BOOL"}),\n        detailField({label:"TRANSLATION MOD",control:boolControl("translationMod"),dataType:"BOOL"}),\n',
    "boolean fields",
)
path.write_text(text, encoding="utf-8")


# Regression coverage for the final structured pass and the two fidelity fixes.
Path("tests/test_terraria_structured_finish.py").write_text(r'''from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

from games.terraria import server
from games.terraria.structured_content import (
    create_structured_content,
    default_values,
    render_structured_source,
    schemas_public,
    validate_values,
)


class TerrariaStructuredFinishTests(unittest.TestCase):
    def test_new_safe_managed_families_are_exposed(self):
        kinds={row["kind"] for row in schemas_public()["kinds"]}
        self.assertTrue({"sceneEffect","dust","globalBuff","globalTile","globalWall"}.issubset(kinds))
        self.assertEqual(len(kinds),20)

    def test_scene_effect_conditions_and_custom_hook(self):
        values=default_values("sceneEffect")
        values.update({"enabled":True,"zone":"Jungle","time":"Night","hardmode":"Hardmode","music":12,"priority":"Event","weight":0.75})
        source=render_structured_source("ExampleMod","sceneEffect","StormScene",values)
        self.assertIn("public sealed class StormScene : ModSceneEffect",source)
        self.assertIn("player.ZoneJungle",source)
        self.assertIn("!Main.dayTime",source)
        self.assertIn("Main.hardMode",source)
        self.assertIn("SceneEffectPriority.Event",source)
        self.assertIn("GetWeight(Player player) => 0.75f",source)
        self.assertIn("AdditionalCondition(player)",source)
        self.assertIn("private bool AdditionalCondition(Player player) => true;",source)

    def test_dust_generation_and_native_sprite_sheet_placeholder(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/"ExampleMod"; root.mkdir()
            values=default_values("dust")
            values.update({"updateType":6,"noGravity":True,"noLight":True,"fadeIn":1.5,"scaleMultiplier":1.25,"velocityMultiplier":0.5,"vanillaUpdate":False,"midUpdateOwnBehavior":True,"fullbright":True})
            result=create_structured_content(root,"dust","SparkDust",values)
            self.assertEqual(result["path"],"Content/Dusts/SparkDust.cs")
            self.assertEqual((result["texture"]["width"],result["texture"]["height"]),(10,30))
            source=(root/result["path"]).read_text(encoding="utf-8")
            self.assertIn("public sealed class SparkDust : ModDust",source)
            self.assertIn("UpdateType = 6",source)
            self.assertIn("dust.noGravity = true",source)
            self.assertIn("dust.velocity *= 0.5f",source)
            self.assertIn("Update(Dust dust) => false",source)
            self.assertIn("GetAlpha(Dust dust, Color lightColor) => Color.White",source)

    def test_global_buff_tile_and_wall_are_target_bounded(self):
        buff=default_values("globalBuff"); buff.update({"targetId":24,"defenseBonus":8,"moveSpeedBonus":0.1,"allowCancel":False})
        buff_source=render_structured_source("ExampleMod","globalBuff","BuffRules",buff)
        self.assertIn("if (type != 24) return;",buff_source)
        self.assertIn("player.statDefense += 8",buff_source)
        self.assertIn("type != 24;",buff_source)
        tile=default_values("globalTile"); tile.update({"targetId":7,"allowDrop":False,"dangerous":"true","spelunkable":"false"})
        tile_source=render_structured_source("ExampleMod","globalTile","TileRules",tile)
        self.assertIn("type != 7 || false",tile_source)
        self.assertIn("return true;",tile_source)
        self.assertIn("return false;",tile_source)
        wall=default_values("globalWall"); wall.update({"targetId":3,"dropOverride":9,"allowTeleport":False})
        wall_source=render_structured_source("ExampleMod","globalWall","WallRules",wall)
        self.assertIn("if (type != 3) return true",wall_source)
        self.assertIn("dropType = 9",wall_source)
        self.assertIn("type != 3;",wall_source)

    def test_npc_spawn_filters_and_multiple_loot_rules(self):
        values=default_values("npc")
        values.update({
            "spawnChance":0.2,"spawnZone":"Jungle","spawnTime":"Night","spawnWater":"Dry","spawnSafety":"Unsafe","spawnSpecial":"Granite",
            "lootRules":"vanilla:71,3,2,5\nmod:Gem,4,1,2",
        })
        source=render_structured_source("ExampleMod","npc","JungleThing",values)
        self.assertIn("spawnInfo.Player.ZoneJungle",source)
        self.assertIn("!Main.dayTime",source)
        self.assertIn("!spawnInfo.Water",source)
        self.assertIn("!spawnInfo.PlayerSafe",source)
        self.assertIn("spawnInfo.Granite",source)
        self.assertIn("ItemDropRule.Common(71, 3, 2, 5)",source)
        self.assertIn("ModContent.ItemType<global::ExampleMod.Content.Items.Gem>()",source)
        with self.assertRaisesRegex(ValueError,"stack range"):
            bad=default_values("npc"); bad["lootRules"]="vanilla:1,2,5,3"; validate_values("npc",bad)

    def test_enabled_json_null_matches_empty_native_state(self):
        previous_project=os.environ.get("LEXEDITOR_TERRARIA_PROJECT")
        previous_save=server.TMODLOADER_SAVE_ROOT
        try:
            with tempfile.TemporaryDirectory() as directory:
                save=Path(directory); project=save/"ModSources"/"ExampleMod"; project.mkdir(parents=True)
                os.environ["LEXEDITOR_TERRARIA_PROJECT"]=str(project); server.TMODLOADER_SAVE_ROOT=save
                mods=save/"Mods"; mods.mkdir(); (mods/"enabled.json").write_text("null",encoding="utf-8")
                state=server.local_mod_state()
                self.assertTrue(state["enabledStateExists"])
                self.assertTrue(state["enabledStateValid"])
                self.assertFalse(state["enabled"])
                self.assertEqual(state["enabledStateError"],"")
        finally:
            server.TMODLOADER_SAVE_ROOT=previous_save
            if previous_project is None: os.environ.pop("LEXEDITOR_TERRARIA_PROJECT",None)
            else: os.environ["LEXEDITOR_TERRARIA_PROJECT"]=previous_project

    def test_absent_build_booleans_are_addable_in_editor(self):
        html=Path("games/terraria/editor.html").read_text(encoding="utf-8")
        self.assertIn("Not declared — check to add",html)
        self.assertIn('boolControl("noCompile")',html)
        self.assertIn('boolControl("playableOnPreview")',html)
        self.assertIn('boolControl("translationMod")',html)


if __name__ == "__main__":
    unittest.main()
''',encoding="utf-8")
