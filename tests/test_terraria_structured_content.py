from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from games.terraria.structured_content import (
    BEGIN_MARKER,
    END_MARKER,
    create_structured_content,
    default_values,
    render_structured_source,
    schemas_public,
    structured_content_index,
    structured_content_state,
    update_structured_content,
    validate_values,
)
from games.terraria.source_text import save_source, source_file_state
from games.terraria.localization import parse_localization_text


class TerrariaStructuredContentTests(unittest.TestCase):
    def test_schema_exposes_major_content_families(self):
        kinds = {row["kind"] for row in schemas_public()["kinds"]}
        self.assertEqual(
            kinds,
            {"item", "npc", "projectile", "buff", "tile", "wall", "globalItem", "globalNPC", "globalProjectile", "prefix", "rarity", "biome", "config", "command", "recipe"},
        )
        npc_fields = {row["name"] for row in next(row for row in schemas_public()["kinds"] if row["kind"] == "npc")["fields"]}
        self.assertTrue({"lifeMax", "damage", "defense", "aiStyle", "spawnChance", "lootKind"}.issubset(npc_fields))

    def test_npc_renderer_includes_stats_ai_spawn_and_loot(self):
        values = default_values("npc")
        values.update({
            "lifeMax": 450,
            "damage": 37,
            "defense": 12,
            "frames": 4,
            "aiStyle": 3,
            "aiType": 3,
            "animationType": 3,
            "spawnChance": 0.08,
            "lootKind": "vanilla",
            "lootItemId": 22,
            "lootChance": 5,
            "lootMin": 1,
            "lootMax": 3,
        })
        source = render_structured_source("ExampleMod", "npc", "ExampleEnemy", values)
        self.assertIn("public sealed class ExampleEnemy : ModNPC", source)
        self.assertIn("NPC.lifeMax = 450;", source)
        self.assertIn("NPC.damage = 37;", source)
        self.assertIn("NPC.defense = 12;", source)
        self.assertIn("Main.npcFrameCount[Type] = 4;", source)
        self.assertIn("NPC.aiStyle = 3;", source)
        self.assertIn("AIType = 3;", source)
        self.assertIn("AnimationType = 3;", source)
        self.assertIn("SpawnChance(NPCSpawnInfo spawnInfo) => 0.08f;", source)
        self.assertIn("ItemDropRule.Common(22, 5, 1, 3)", source)
        self.assertIn(BEGIN_MARKER, source)
        self.assertIn(END_MARKER, source)

    def test_projectile_buff_tile_and_globals_generate_current_api_shapes(self):
        projectile = default_values("projectile")
        projectile.update({"damageClass": "Ranged", "penetrate": -1, "tileCollide": False, "aiType": 1})
        projectile_source = render_structured_source("ExampleMod", "projectile", "Bolt", projectile)
        self.assertIn("Projectile.DamageType = DamageClass.Ranged;", projectile_source)
        self.assertIn("Projectile.penetrate = -1;", projectile_source)
        self.assertIn("Projectile.tileCollide = false;", projectile_source)
        self.assertIn("AIType = 1;", projectile_source)

        buff = default_values("buff")
        buff.update({"debuff": True, "defenseBonus": -8, "moveSpeedBonus": -0.1})
        buff_source = render_structured_source("ExampleMod", "buff", "SlowCurse", buff)
        self.assertIn("Main.debuff[Type] = true;", buff_source)
        self.assertIn("player.statDefense += -8;", buff_source)
        self.assertIn("player.moveSpeed += -0.1f;", buff_source)

        tile = default_values("tile")
        tile.update({"minPick": 65, "mineResist": 2.5, "dropKind": "modItem", "dropItemName": "ExampleBlock"})
        tile_source = render_structured_source("ExampleMod", "tile", "ExampleTile", tile)
        self.assertIn("MineResist = 2.5f;", tile_source)
        self.assertIn("MinPick = 65;", tile_source)
        self.assertIn("CreateMapEntryName()", tile_source)
        self.assertIn("ModContent.ItemType<global::ExampleMod.Content.Items.ExampleBlock>()", tile_source)

        global_item = default_values("globalItem")
        global_item.update({"targetId": 42, "damageMultiplier": 1.5, "maxStackOverride": 99})
        global_item_source = render_structured_source("ExampleMod", "globalItem", "BuffVanillaItem", global_item)
        self.assertIn("entity.type == 42", global_item_source)
        self.assertIn("entity.damage * 1.5f", global_item_source)
        self.assertIn("entity.maxStack = 99;", global_item_source)

        global_npc = default_values("globalNPC")
        global_npc.update({"targetId": 50, "lifeMultiplier": 2.0, "defenseAdd": 7})
        global_npc_source = render_structured_source("ExampleMod", "globalNPC", "BuffVanillaNPC", global_npc)
        self.assertIn("entity.type == 50", global_npc_source)
        self.assertIn("entity.lifeMax * 2f", global_npc_source)
        self.assertIn("entity.defense += 7;", global_npc_source)

    def test_recipe_renderer_uses_strict_mod_and_vanilla_references(self):
        values = default_values("recipe")
        values.update({
            "resultName": "ExampleSword",
            "resultStack": 2,
            "ingredients": "vanilla:9=10\nmod:ExampleBar=4",
            "stations": "vanilla:18\nmod:ExampleWorkbench",
        })
        source = render_structured_source("ExampleMod", "recipe", "ExampleSwordRecipe", values)
        self.assertIn("Recipe.Create(ModContent.ItemType<global::ExampleMod.Content.Items.ExampleSword>(), 2)", source)
        self.assertIn("recipe.AddIngredient(9, 10);", source)
        self.assertIn("ExampleMod.Content.Items.ExampleBar", source)
        self.assertIn("recipe.AddTile(18);", source)
        self.assertIn("ExampleMod.Content.Tiles.ExampleWorkbench", source)
        self.assertIn("recipe.Register();", source)

        with self.assertRaisesRegex(ValueError, "Ingredient line 1"):
            validate_values("recipe", {"resultName": "ExampleSword", "ingredients": "raw csharp()"})

    def test_structured_update_only_replaces_managed_region(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "ExampleMod"
            root.mkdir()
            created = create_structured_content(root, "npc", "Enemy", {"lifeMax": 100}, "Enemy")
            state = source_file_state(root, created["path"])
            custom = state["text"].replace("\n}\n", "\n\n    public override void AI()\n    {\n        NPC.TargetClosest();\n    }\n}\n")
            custom_state = save_source(root, state["path"], custom, state["sha256"])

            changed_values = dict(created["values"])
            changed_values["lifeMax"] = 777
            updated = update_structured_content(root, created["path"], changed_values, custom_state["sha256"])
            text = source_file_state(root, created["path"])["text"]
            self.assertIn("NPC.lifeMax = 777;", text)
            self.assertIn("public override void AI()", text)
            self.assertIn("NPC.TargetClosest();", text)
            self.assertEqual(updated["values"]["lifeMax"], 777)

            with self.assertRaisesRegex(ValueError, "changed outside Lexeditor"):
                update_structured_content(root, created["path"], changed_values, custom_state["sha256"])

    def test_create_npc_writes_source_texture_localization_and_index(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "ExampleMod"
            root.mkdir()
            result = create_structured_content(root, "npc", "CaveBug", {"lifeMax": 250}, "Cave Bug")
            self.assertEqual(result["path"], "Content/NPCs/CaveBug.cs")
            self.assertEqual(result["texture"]["path"], "Content/NPCs/CaveBug.png")
            self.assertTrue((root / result["path"]).is_file())
            self.assertTrue((root / result["texture"]["path"]).is_file())
            values = {entry.key: entry.value for entry in parse_localization_text((root / "Localization/en-US.hjson").read_text(encoding="utf-8")).entries}
            self.assertEqual(values["Mods.ExampleMod.NPCs.CaveBug.DisplayName"], "Cave Bug")
            index = structured_content_index(root)
            self.assertEqual(index["files"], [{"path": "Content/NPCs/CaveBug.cs", "kind": "npc", "name": "CaveBug", "editable": True}])
            reopened = structured_content_state(root, result["path"])
            self.assertEqual(reopened["values"]["lifeMax"], 250)

    def test_recipe_and_global_modifier_create_without_fake_assets_or_localization(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "ExampleMod"
            root.mkdir()
            recipe = create_structured_content(root, "recipe", "WoodRecipe", {"resultKind": "vanilla", "resultId": 9})
            global_item = create_structured_content(root, "globalItem", "WoodModifier", {"targetId": 9, "valueMultiplier": 2})
            self.assertIsNone(recipe["texture"])
            self.assertIsNone(recipe["localizationPath"])
            self.assertIsNone(global_item["texture"])
            self.assertFalse((root / "Localization").exists())

    def test_validation_rejects_ambiguous_or_unsafe_values(self):
        with self.assertRaisesRegex(ValueError, "minimum stack"):
            validate_values("npc", {"lootMin": 5, "lootMax": 1})
        with self.assertRaisesRegex(ValueError, "Mod loot item class"):
            validate_values("npc", {"lootKind": "modItem"})
        with self.assertRaisesRegex(ValueError, "Unknown structured content fields"):
            validate_values("item", {"rawCode": "Item.damage = 999999;"})
        with self.assertRaisesRegex(ValueError, "Damage class"):
            validate_values("item", {"damageClass": "TotallyRealDamageClass"})


if __name__ == "__main__":
    unittest.main()
