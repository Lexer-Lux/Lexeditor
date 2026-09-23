from __future__ import annotations

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
