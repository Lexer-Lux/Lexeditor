from pathlib import Path

engine=Path('games/terraria/structured_content.py')
text=engine.read_text(encoding='utf-8')

def one(old,new):
    global text
    count=text.count(old)
    if count!=1: raise SystemExit(f'expected one engine anchor, found {count}: {old[:140]!r}')
    text=text.replace(old,new,1)

# New structured families.
one(
    '    "recipe": (\n',
    '    "rarity": (\n'
    '        Field("colorR", "Color red", "int", 255, "COLOR", 0, 255), Field("colorG", "Color green", "int", 255, "COLOR", 0, 255), Field("colorB", "Color blue", "int", 255, "COLOR", 0, 255),\n'
    '    ),\n'
    '    "biome": (\n'
    '        Field("enabled", "Enable biome condition", "bool", False, "ACTIVATION", help="Disabled biomes return false until you intentionally configure and enable them."),\n'
    '        Field("zone", "Vanilla biome condition", "enum", "Any", "ACTIVATION", options=("Any","Forest","Jungle","Snow","Desert","Beach","Dungeon","Corruption","Crimson","Hallow","Glowshroom")),\n'
    '        Field("depth", "Depth condition", "enum", "Any", "ACTIVATION", options=("Any","Sky","Overworld","DirtLayer","RockLayer","Underworld")),\n'
    '        Field("time", "Time condition", "enum", "Any", "ACTIVATION", options=("Any","Day","Night")), Field("hardmode", "Hardmode condition", "enum", "Any", "ACTIVATION", options=("Any","PreHardmode","Hardmode")), Field("rain", "Rain condition", "enum", "Any", "ACTIVATION", options=("Any","Raining","Dry")),\n'
    '        Field("music", "Music ID (-1 inherit)", "int", -1, "SCENE", -1, 100000), Field("priority", "Scene priority", "enum", "BiomeLow", "SCENE", options=("None","BiomeLow","BiomeMedium","BiomeHigh","Environment","Event","BossLow","BossMedium","BossHigh")), Field("mapBackground", "Use bestiary background on map", "bool", True, "SCENE"),\n'
    '        Field("torchItemType", "Biome torch item ID (-1 none)", "int", -1, "ITEMS", -1, 100000), Field("campfireItemType", "Biome campfire item ID (-1 none)", "int", -1, "ITEMS", -1, 100000),\n'
    '        Field("backgroundColorEnabled", "Tint bestiary background", "bool", False, "COLOR"), Field("backgroundR", "Background red", "int", 255, "COLOR", 0, 255), Field("backgroundG", "Background green", "int", 255, "COLOR", 0, 255), Field("backgroundB", "Background blue", "int", 255, "COLOR", 0, 255),\n'
    '    ),\n'
    '    "config": (\n'
    '        Field("scope", "Config scope", "enum", "ClientSide", "CONFIG", options=("ClientSide","ServerSide")), Field("reloadRequired", "All fields require reload", "bool", False, "CONFIG"),\n'
    '        Field("fields", "Config fields", "lines", "", "FIELDS", help="One per line: bool:EnableFeature=true, int:Count=5, float:Scale=1.25, string:Greeting=Hello."),\n'
    '    ),\n'
    '    "command": (\n'
    '        Field("command", "Command text", "text", "example", "COMMAND", help="Without the leading slash and without whitespace."), Field("commandType", "Command context", "enum", "Chat", "COMMAND", options=("Chat","Server","Console","World")), Field("caseSensitive", "Case sensitive arguments", "bool", False, "COMMAND"),\n'
    '        Field("usage", "Usage text (blank = automatic)", "text", "", "HELP"), Field("description", "Description", "text", "", "HELP"), Field("replyText", "Fixed reply text", "text", "", "ACTION"), Field("echoArguments", "Echo arguments", "bool", False, "ACTION"),\n'
    '    ),\n'
    '    "recipe": (\n',
)
one(
    '_LABELS = {"item":"ModItem","npc":"ModNPC","projectile":"ModProjectile","buff":"ModBuff","tile":"ModTile (simple 1×1)","wall":"ModWall","globalItem":"GlobalItem (vanilla modifier)","globalNPC":"GlobalNPC (vanilla modifier)","globalProjectile":"GlobalProjectile (vanilla modifier)","prefix":"ModPrefix","recipe":"Recipe"}\n',
    '_LABELS = {"item":"ModItem","npc":"ModNPC","projectile":"ModProjectile","buff":"ModBuff","tile":"ModTile (simple 1×1)","wall":"ModWall","globalItem":"GlobalItem (vanilla modifier)","globalNPC":"GlobalNPC (vanilla modifier)","globalProjectile":"GlobalProjectile (vanilla modifier)","prefix":"ModPrefix","rarity":"ModRarity","biome":"ModBiome","config":"ModConfig","command":"ModCommand","recipe":"Recipe"}\n',
)

# Validation for line DSLs and command identifiers.
one(
    '    if kind=="recipe":\n        if out["resultKind"]=="modItem" and not out["resultName"]: raise ValueError("Result mod item class is required")\n        _parse_ingredients(out["ingredients"]); _parse_stations(out["stations"])\n',
    '    if kind=="recipe":\n        if out["resultKind"]=="modItem" and not out["resultName"]: raise ValueError("Result mod item class is required")\n        _parse_ingredients(out["ingredients"]); _parse_stations(out["stations"])\n'
    '    if kind=="config": _parse_config_fields(out["fields"])\n'
    '    if kind=="command":\n'
    '        out["command"]=out["command"].strip()\n'
    '        if not out["command"] or out["command"].startswith("/") or any(ch.isspace() for ch in out["command"]): raise ValueError("Command text must be non-empty, omit the slash, and contain no whitespace")\n'
    '        if any(ch in out[field] for field in ("usage","description","replyText") for ch in "\\r\\n\\x00"): raise ValueError("Command help/reply text must fit on one line")\n',
)

# Helpers for safe generated literals and config DSL.
one(
    'def _b(v): return "true" if v else "false"\n',
    'def _b(v): return "true" if v else "false"\n'
    'def _cs(v): return json.dumps(str(v),ensure_ascii=False)\n',
)
one(
    'def _parse_ingredients(text):\n',
    'def _parse_config_fields(text):\n'
    '    rows=[]\n'
    '    for n,raw in enumerate(text.splitlines(),1):\n'
    '        line=raw.strip()\n'
    '        if not line: continue\n'
    '        if ":" not in line or "=" not in line: raise ValueError(f"Config field line {n} must use type:Name=value")\n'
    '        type_name,rest=line.split(":",1); name,value=rest.split("=",1); type_name=type_name.strip(); name=validate_content_name(name.strip()); value=value.strip()\n'
    '        if type_name=="bool":\n'
    '            if value.casefold() not in {"true","false"}: raise ValueError(f"Config field line {n} bool default must be true or false")\n'
    '            parsed=value.casefold()=="true"\n'
    '        elif type_name=="int":\n'
    '            try: parsed=int(value)\n'
    '            except ValueError as e: raise ValueError(f"Config field line {n} integer default is invalid") from e\n'
    '        elif type_name=="float":\n'
    '            try: parsed=float(value)\n'
    '            except ValueError as e: raise ValueError(f"Config field line {n} float default is invalid") from e\n'
    '            if parsed!=parsed or parsed in (float("inf"),float("-inf")): raise ValueError(f"Config field line {n} float default must be finite")\n'
    '        elif type_name=="string": parsed=value\n'
    '        else: raise ValueError(f"Config field line {n} type must be bool, int, float, or string")\n'
    '        if any(existing[1]==name for existing in rows): raise ValueError(f"Config field name is duplicated: {name}")\n'
    '        rows.append((type_name,name,parsed))\n'
    '    return rows\n\n'
    'def _parse_ingredients(text):\n',
)

# Render the new systems.
one(
    'def _render_recipe(mod,v):\n',
    'def _render_rarity(v):\n'
    '    return [f"public override Color RarityColor => new Color({v[\'colorR\']}, {v[\'colorG\']}, {v[\'colorB\']});"]\n\n'
    'def _biome_condition(v):\n'
    '    if not v["enabled"]: return "false"\n'
    '    zone={"Any":None,"Forest":"player.ZoneForest","Jungle":"player.ZoneJungle","Snow":"player.ZoneSnow","Desert":"player.ZoneDesert","Beach":"player.ZoneBeach","Dungeon":"player.ZoneDungeon","Corruption":"player.ZoneCorrupt","Crimson":"player.ZoneCrimson","Hallow":"player.ZoneHallow","Glowshroom":"player.ZoneGlowshroom"}[v["zone"]]\n'
    '    depth={"Any":None,"Sky":"player.ZoneSkyHeight","Overworld":"player.ZoneOverworldHeight","DirtLayer":"player.ZoneDirtLayerHeight","RockLayer":"player.ZoneRockLayerHeight","Underworld":"player.ZoneUnderworldHeight"}[v["depth"]]\n'
    '    time={"Any":None,"Day":"Main.dayTime","Night":"!Main.dayTime"}[v["time"]]\n'
    '    hardmode={"Any":None,"PreHardmode":"!Main.hardMode","Hardmode":"Main.hardMode"}[v["hardmode"]]\n'
    '    rain={"Any":None,"Raining":"Main.raining","Dry":"!Main.raining"}[v["rain"]]\n'
    '    parts=[part for part in (zone,depth,time,hardmode,rain) if part]\n'
    '    parts.append("AdditionalCondition(player)")\n'
    '    return " && ".join(parts)\n\n'
    'def _render_biome(v):\n'
    '    out=[f"public override int Music => {v[\'music\']};",f"public override SceneEffectPriority Priority => SceneEffectPriority.{v[\'priority\']};",f"public override int BiomeTorchItemType => {v[\'torchItemType\']};",f"public override int BiomeCampfireItemType => {v[\'campfireItemType\']};"]\n'
    '    if v["mapBackground"]: out.append("public override string MapBackground => BackgroundPath;")\n'
    '    if v["backgroundColorEnabled"]: out.append(f"public override Color? BackgroundColor => new Color({v[\'backgroundR\']}, {v[\'backgroundG\']}, {v[\'backgroundB\']});")\n'
    '    out += ["",f"public override bool IsBiomeActive(Player player) => {_biome_condition(v)};"]\n'
    '    return out\n\n'
    'def _config_literal(type_name,value):\n'
    '    if type_name=="bool": return _b(value)\n'
    '    if type_name=="int": return str(value)\n'
    '    if type_name=="float": return _f(value)\n'
    '    return _cs(value)\n\n'
    'def _render_config(v):\n'
    '    out=[f"public override ConfigScope Mode => ConfigScope.{v[\'scope\']};"]\n'
    '    for type_name,name,value in _parse_config_fields(v["fields"]):\n'
    '        cs_type={"bool":"bool","int":"int","float":"float","string":"string"}[type_name]; literal=_config_literal(type_name,value)\n'
    '        out += [""]\n'
    '        if v["reloadRequired"]: out.append("[ReloadRequired]")\n'
    '        out += [f"[DefaultValue({literal})]",f"public {cs_type} {name} {{ get; set; }} = {literal};"]\n'
    '    return out\n\n'
    'def _render_command(v):\n'
    '    out=[f"public override string Command => {_cs(v[\'command\'])};",f"public override CommandType Type => CommandType.{v[\'commandType\']};",f"public override bool IsCaseSensitive => {_b(v[\'caseSensitive\'])};"]\n'
    '    if v["usage"]: out.append(f"public override string Usage => {_cs(v[\'usage\'])};")\n'
    '    if v["description"]: out.append(f"public override string Description => {_cs(v[\'description\'])};")\n'
    '    out += ["","public override void Action(CommandCaller caller, string input, string[] args)","{"]\n'
    '    if v["replyText"]: out.append(f"    caller.Reply({_cs(v[\'replyText\'])});")\n'
    '    if v["echoArguments"]: out.append("    caller.Reply(string.Join(\" \", args));")\n'
    '    out.append("    CustomAction(caller, input, args);")\n'
    '    out += ["}"]; return out\n\n'
    'def _render_recipe(mod,v):\n',
)

one(
    "    return {'item':lambda:_render_item(v),'npc':lambda:_render_npc(mod,v),'projectile':lambda:_render_projectile(v),'buff':lambda:_render_buff(v),'tile':lambda:_render_tile(mod,v),'wall':lambda:_render_wall(mod,v),'globalItem':lambda:_render_global_item(v),'globalNPC':lambda:_render_global_npc(v),'globalProjectile':lambda:_render_global_projectile(v),'prefix':lambda:_render_prefix(v),'recipe':lambda:_render_recipe(mod,v)}[kind]()\n",
    "    return {'item':lambda:_render_item(v),'npc':lambda:_render_npc(mod,v),'projectile':lambda:_render_projectile(v),'buff':lambda:_render_buff(v),'tile':lambda:_render_tile(mod,v),'wall':lambda:_render_wall(mod,v),'globalItem':lambda:_render_global_item(v),'globalNPC':lambda:_render_global_npc(v),'globalProjectile':lambda:_render_global_projectile(v),'prefix':lambda:_render_prefix(v),'rarity':lambda:_render_rarity(v),'biome':lambda:_render_biome(v),'config':lambda:_render_config(v),'command':lambda:_render_command(v),'recipe':lambda:_render_recipe(mod,v)}[kind]()\n",
)

# Paths/base classes/usings.
one(
    "        'prefix':(f\"Content/Prefixes/{name}.cs\",'ModPrefix',('Terraria','Terraria.ModLoader')),\n",
    "        'prefix':(f\"Content/Prefixes/{name}.cs\",'ModPrefix',('Terraria','Terraria.ModLoader')),\n"
    "        'rarity':(f\"Content/Rarities/{name}.cs\",'ModRarity',('Microsoft.Xna.Framework','Terraria.ModLoader')),\n"
    "        'biome':(f\"Content/Biomes/{name}.cs\",'ModBiome',('Microsoft.Xna.Framework','Terraria','Terraria.ModLoader')),\n"
    "        'config':(f\"Common/Configs/{name}.cs\",'ModConfig',('System.ComponentModel','Terraria.ModLoader.Config')),\n"
    "        'command':(f\"Common/Commands/{name}.cs\",'ModCommand',('Terraria.ModLoader',)),\n",
)
one(
    "    return {'item':f'{mod}.Content.Items','npc':f'{mod}.Content.NPCs','projectile':f'{mod}.Content.Projectiles','buff':f'{mod}.Content.Buffs','tile':f'{mod}.Content.Tiles','wall':f'{mod}.Content.Walls','globalItem':f'{mod}.Common.GlobalItems','globalNPC':f'{mod}.Common.GlobalNPCs','globalProjectile':f'{mod}.Common.GlobalProjectiles','prefix':f'{mod}.Content.Prefixes','recipe':f'{mod}.Common.Recipes'}[kind]\n",
    "    return {'item':f'{mod}.Content.Items','npc':f'{mod}.Content.NPCs','projectile':f'{mod}.Content.Projectiles','buff':f'{mod}.Content.Buffs','tile':f'{mod}.Content.Tiles','wall':f'{mod}.Content.Walls','globalItem':f'{mod}.Common.GlobalItems','globalNPC':f'{mod}.Common.GlobalNPCs','globalProjectile':f'{mod}.Common.GlobalProjectiles','prefix':f'{mod}.Content.Prefixes','rarity':f'{mod}.Content.Rarities','biome':f'{mod}.Content.Biomes','config':f'{mod}.Common.Configs','command':f'{mod}.Common.Commands','recipe':f'{mod}.Common.Recipes'}[kind]\n",
)

# Preserved custom hooks for managed types whose common advanced logic can't be represented safely as scalar fields.
one(
    'def render_structured_source(mod_name,kind,name,values):\n    mod_name=validate_content_name(mod_name); name=validate_content_name(name); v=validate_values(kind,values); _,base,usings=_kind_spec(kind,name)\n    return \'\'.join(f"using {x};\\n" for x in usings)+"\\n"+_meta(kind,name,v)+"\\n"+f"namespace {_namespace(mod_name,kind)};\\n\\npublic sealed class {name} : {base}\\n{{\\n"+_managed(_render_region(mod_name,kind,v))+"\\n}}\\n"\n',
    'def _custom_tail(kind):\n'
    '    if kind=="biome": return "    private bool AdditionalCondition(Player player) => true;"\n'
    '    if kind=="command": return "    private void CustomAction(CommandCaller caller, string input, string[] args)\\n    {\\n    }"\n'
    '    return ""\n\n'
    'def render_structured_source(mod_name,kind,name,values):\n'
    '    mod_name=validate_content_name(mod_name); name=validate_content_name(name); v=validate_values(kind,values); _,base,usings=_kind_spec(kind,name)\n'
    '    tail=_custom_tail(kind); suffix=("\\n\\n"+tail if tail else "")\n'
    '    return \'\'.join(f"using {x};\\n" for x in usings)+"\\n"+_meta(kind,name,v)+"\\n"+f"namespace {_namespace(mod_name,kind)};\\n\\npublic sealed class {name} : {base}\\n{{\\n"+_managed(_render_region(mod_name,kind,v))+suffix+"\\n}}\\n"\n',
)

# Localization for biome DisplayName.
one(
    "    if kind=='prefix': return {f\"Mods.{mod}.Prefixes.{name}.DisplayName\":display}\n",
    "    if kind=='prefix': return {f\"Mods.{mod}.Prefixes.{name}.DisplayName\":display}\n"
    "    if kind=='biome': return {f\"Mods.{mod}.Biomes.{name}.DisplayName\":display}\n",
)

# Generalize generated assets so biomes get their two required default-path images without breaking existing texture contracts.
one(
    "    needs_texture=kind in {'item','npc','projectile','buff','tile','wall'}; texture_relative=source_relative[:-3]+'.png'; texture_target=project/texture_relative\n    if needs_texture and texture_target.exists(): raise ValueError(f\"Asset file already exists: {texture_relative}\")\n",
    "    primary_texture=kind in {'item','npc','projectile','buff','tile','wall'}\n"
    "    asset_specs=[]\n"
    "    if primary_texture: asset_specs.append((source_relative[:-3]+'.png',32 if kind=='buff' else 16))\n"
    "    if kind=='biome': asset_specs += [(f'Content/Biomes/{name}_Icon.png',30),(f'Content/Biomes/{name}_Background.png',64)]\n"
    "    for asset_relative,_size in asset_specs:\n"
    "        if (project/asset_relative).exists(): raise ValueError(f\"Asset file already exists: {asset_relative}\")\n",
)
one(
    "    loc_target=project/'Localization'/'en-US.hjson'; creates=_loc_plan(mod,kind,name,display,desc); loc_existed=loc_target.is_file(); loc_original=loc_target.read_bytes() if loc_existed else b''; loc_written=src_written=tex_written=False; texture_state=None\n",
    "    loc_target=project/'Localization'/'en-US.hjson'; creates=_loc_plan(mod,kind,name,display,desc); loc_existed=loc_target.is_file(); loc_original=loc_target.read_bytes() if loc_existed else b''; loc_written=src_written=False; created_assets=[]; texture_state=None\n",
)
one(
    "        if needs_texture:\n            texture_state=create_asset(project,texture_relative,placeholder_png(32 if kind=='buff' else 16)); tex_written=True\n",
    "        for asset_relative,size in asset_specs:\n            created_assets.append(create_asset(project,asset_relative,placeholder_png(size)))\n        if primary_texture and created_assets: texture_state=created_assets[0]\n",
)
one(
    "        if tex_written: texture_target.unlink(missing_ok=True)\n",
    "        for asset in reversed(created_assets): (project/asset['path']).unlink(missing_ok=True)\n",
)
one(
    "    result=structured_content_state(project,source_relative); result.update({'displayName':display,'description':desc,'texture':texture_state,'localizationPath':'Localization/en-US.hjson' if creates else None,'localizationKeys':list(creates)}); return result\n",
    "    result=structured_content_state(project,source_relative); result.update({'displayName':display,'description':desc,'texture':texture_state,'assets':created_assets,'localizationPath':'Localization/en-US.hjson' if creates else None,'localizationKeys':list(creates)}); return result\n",
)

engine.write_text(text,encoding='utf-8')

# Biomes have a localized DisplayName in the generic create header.
editor=Path('games/terraria/editor.html'); ui=editor.read_text(encoding='utf-8')
old='  function localizedContentKind(kind){return ["item","npc","projectile","buff","tile","wall","prefix"].includes(kind)}\n'
new='  function localizedContentKind(kind){return ["item","npc","projectile","buff","tile","wall","prefix","biome"].includes(kind)}\n'
if ui.count(old)!=1: raise SystemExit('localized content UI anchor missing')
editor.write_text(ui.replace(old,new,1),encoding='utf-8')

# Expand exact-kind regression and add systems tests.
test=Path('tests/test_terraria_structured_content.py'); t=test.read_text(encoding='utf-8')
old='            {"item", "npc", "projectile", "buff", "tile", "wall", "globalItem", "globalNPC", "globalProjectile", "prefix", "recipe"},\n'
new='            {"item", "npc", "projectile", "buff", "tile", "wall", "globalItem", "globalNPC", "globalProjectile", "prefix", "rarity", "biome", "config", "command", "recipe"},\n'
if t.count(old)!=1: raise SystemExit('systems kind test anchor missing')
test.write_text(t.replace(old,new,1),encoding='utf-8')

Path('tests/test_terraria_structured_systems.py').write_text(r'''from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from games.terraria.localization import parse_localization_text
from games.terraria.source_text import source_file_state
from games.terraria.structured_content import create_structured_content, default_values, render_structured_source, update_structured_content, validate_values


class TerrariaStructuredSystemsTests(unittest.TestCase):
    def test_rarity_color(self):
        source=render_structured_source("ExampleMod","rarity","Electric",{"colorR":12,"colorG":200,"colorB":240})
        self.assertIn("public sealed class Electric : ModRarity",source)
        self.assertIn("RarityColor => new Color(12, 200, 240)",source)

    def test_biome_is_disabled_by_default_and_generates_safe_conditions(self):
        source=render_structured_source("ExampleMod","biome","StormForest",{})
        self.assertIn("IsBiomeActive(Player player) => false;",source)
        values=default_values("biome")
        values.update({"enabled":True,"zone":"Jungle","depth":"Overworld","time":"Night","hardmode":"Hardmode","rain":"Raining","music":42,"priority":"BiomeMedium","torchItemType":8,"campfireItemType":9,"backgroundColorEnabled":True,"backgroundR":10,"backgroundG":20,"backgroundB":30})
        source=render_structured_source("ExampleMod","biome","StormForest",values)
        self.assertIn("Music => 42;",source)
        self.assertIn("SceneEffectPriority.BiomeMedium",source)
        self.assertIn("player.ZoneJungle",source)
        self.assertIn("player.ZoneOverworldHeight",source)
        self.assertIn("!Main.dayTime",source)
        self.assertIn("Main.hardMode",source)
        self.assertIn("Main.raining",source)
        self.assertIn("AdditionalCondition(player)",source)
        self.assertIn("private bool AdditionalCondition(Player player) => true;",source)

    def test_biome_creation_writes_icon_background_and_display_name(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/"ExampleMod"; root.mkdir()
            result=create_structured_content(root,"biome","StormForest",{},"Storm Forest","")
            self.assertIsNone(result["texture"])
            self.assertEqual({asset["path"] for asset in result["assets"]},{"Content/Biomes/StormForest_Icon.png","Content/Biomes/StormForest_Background.png"})
            self.assertEqual((root/"Content/Biomes/StormForest_Icon.png").read_bytes()[16:20],(30).to_bytes(4,"big"))
            values={entry.key:entry.value for entry in parse_localization_text((root/"Localization/en-US.hjson").read_text(encoding="utf-8")).entries}
            self.assertEqual(values["Mods.ExampleMod.Biomes.StormForest.DisplayName"],"Storm Forest")

    def test_config_typed_field_dsl(self):
        values={"scope":"ServerSide","reloadRequired":True,"fields":"bool:EnableFeature=true\nint:Count=5\nfloat:Scale=1.25\nstring:Greeting=Howdy"}
        source=render_structured_source("ExampleMod","config","GameplayConfig",values)
        self.assertIn("public sealed class GameplayConfig : ModConfig",source)
        self.assertIn("ConfigScope.ServerSide",source)
        self.assertEqual(source.count("[ReloadRequired]"),4)
        self.assertIn("[DefaultValue(true)]",source)
        self.assertIn("public int Count { get; set; } = 5;",source)
        self.assertIn("public float Scale { get; set; } = 1.25f;",source)
        self.assertIn('public string Greeting { get; set; } = "Howdy";',source)
        with self.assertRaisesRegex(ValueError,"duplicated"):
            validate_values("config",{"fields":"bool:Same=true\nint:Same=2"})
        with self.assertRaisesRegex(ValueError,"type must be"):
            validate_values("config",{"fields":"vector:Position=1"})

    def test_command_safe_metadata_and_preserved_custom_hook(self):
        values={"command":"hello","commandType":"World","caseSensitive":True,"usage":"/hello [name]","description":"Say hello","replyText":"Hello!","echoArguments":True}
        source=render_structured_source("ExampleMod","command","HelloCommand",values)
        self.assertIn('Command => "hello";',source)
        self.assertIn("CommandType.World",source)
        self.assertIn('Usage => "/hello [name]";',source)
        self.assertIn('caller.Reply("Hello!");',source)
        self.assertIn('caller.Reply(string.Join(" ", args));',source)
        self.assertIn("CustomAction(caller, input, args);",source)
        self.assertIn("private void CustomAction",source)
        with self.assertRaisesRegex(ValueError,"omit the slash"):
            validate_values("command",{"command":"/bad command"})

    def test_command_custom_hook_survives_structured_save(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/"ExampleMod"; root.mkdir()
            created=create_structured_content(root,"command","PingCommand",{"command":"ping","replyText":"pong"})
            state=source_file_state(root,created["path"])
            customized=state["text"].replace("    {\n    }\n}","    {\n        caller.Reply(\"custom\");\n    }\n}")
            (root/created["path"]).write_text(customized,encoding="utf-8")
            external=source_file_state(root,created["path"])
            values=dict(created["values"]); values["replyText"]="PONG"
            update_structured_content(root,created["path"],values,external["sha256"])
            final=source_file_state(root,created["path"])["text"]
            self.assertIn('caller.Reply("PONG");',final)
            self.assertIn('caller.Reply("custom");',final)


if __name__ == "__main__":
    unittest.main()
''',encoding='utf-8')
