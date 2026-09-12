from __future__ import annotations

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

    def test_native_placeholder_geometry_for_frames_tiles_and_walls(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/"ExampleMod"; root.mkdir()
            npc_values=default_values("npc"); npc_values["frames"]=4
            npc=create_structured_content(root,"npc","FourFrameNPC",npc_values)
            projectile_values=default_values("projectile"); projectile_values["frames"]=3
            projectile=create_structured_content(root,"projectile","ThreeFrameProjectile",projectile_values)
            tile=create_structured_content(root,"tile","BasicBlock",{})
            wall=create_structured_content(root,"wall","BasicWall",{})
            self.assertEqual((npc["texture"]["width"],npc["texture"]["height"]),(16,64))
            self.assertEqual((projectile["texture"]["width"],projectile["texture"]["height"]),(16,48))
            self.assertEqual((tile["texture"]["width"],tile["texture"]["height"]),(288,270))
            self.assertEqual((wall["texture"]["width"],wall["texture"]["height"]),(468,180))

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
