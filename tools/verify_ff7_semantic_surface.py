"""Regression contract: FF7 UI exposes game concepts, not storage bytes."""
from __future__ import annotations

from pathlib import Path
import unittest

import verify_ff7_datasets as kernel_fixtures
import verify_ff7_extended as extended_fixtures
from games.ff7 import battle, datasets, extended, semantics


class SemanticSurfaceTests(unittest.TestCase):
    def test_core_kernel_categories_are_humanized(self):
        meta={category["id"]:{f["key"]:f for f in category["fields"]} for category in datasets.category_metadata()}
        expected={
            "items":{"targetData":"flags","damageCalculationId":"enum","statusChange":"statusChange","statusFlags":"flags","elementFlags":"flags"},
            "weapons":{"targetData":"flags","damageCalculationId":"enum","growthRate":"enum","equipableBy":"flags","attackElements":"flags"},
            "armor":{"elementDamageModifier":"enum","status":"enum","growthRate":"enum","equipableBy":"flags","elementalDefense":"flags"},
            "accessories":{"boostedStat1":"enum","specialEffect":"enum","elementalDefense":"flags","statusDefense":"flags","equipableBy":"flags"},
            "characters":{"weaponId":"reference","armorId":"reference","accessoryId":"reference","characterFlags":"flags","rowByte":"enum","learnedLimits":"flags","weaponMateria0":"reference","strengthCurve":"reference","recruitOffsetRaw":"scaled"},
        }
        for category, fields in expected.items():
            for key, kind in fields.items(): self.assertEqual(meta[category][key]["dataType"],kind,(category,key))
        self.assertEqual(next(c for c in meta["characters"]["rowByte"]["choices"] if c["label"]=="Front row")["value"],0xFF)

    def test_extended_categories_are_humanized(self):
        categories={}
        for key, spec in battle.SCENE_CATEGORIES.items(): categories[key]=semantics.apply(key,spec["fields"])
        categories["shops"]=semantics.apply("shops",extended.SHOP_FIELDS)
        from games.ff7 import archives
        categories["fieldEncounters"]=semantics.apply("fieldEncounters",archives.FIELD_FIELDS)
        categories["chocoboRatings"]=semantics.apply("chocoboRatings",archives.CHOCOBO_FIELDS)
        by={key:{f["key"]:f for f in fields} for key,fields in categories.items()}
        self.assertEqual(by["enemies"]["statusImmunity"]["dataType"],"flags")
        self.assertTrue(by["enemies"]["statusImmunity"]["invertBits"])
        self.assertEqual(by["enemies"]["attack0"]["dataType"],"reference")
        self.assertEqual(by["enemyAttacks"]["target"]["dataType"],"flags")
        self.assertEqual(by["enemyAttacks"]["formula"]["dataType"],"enum")
        self.assertEqual(by["enemyAttacks"]["statusChance"]["dataType"],"statusChange")
        self.assertEqual(by["enemyAttacks"]["specialFlags"]["dataType"],"flags")
        self.assertTrue(by["enemyAttacks"]["specialFlags"]["invertBits"])
        self.assertEqual(by["encounters"]["slot0_enemy"]["dataType"],"reference")
        self.assertEqual(by["shops"]["type"]["dataType"],"enum")
        self.assertEqual(by["shops"]["item0"]["dataType"],"shopReference")
        self.assertEqual(by["fieldEncounters"]["enabled"]["dataType"],"boolean")
        self.assertEqual(by["fieldEncounters"]["battle0"]["dataType"],"reference")
        self.assertEqual(by["chocoboRatings"]["rating"]["dataType"],"enum")

    def test_raw_storage_fields_are_quarantined_when_no_mapping_exists(self):
        collections=[
            *(semantics.apply(key,spec["fields"]) for key,spec in battle.SCENE_CATEGORIES.items()),
            semantics.apply("shops",extended.SHOP_FIELDS),
        ]
        suspicious=(" id"," flags"," mask"," byte","camera","animation","layout","arena","cover flags")
        for fields in collections:
            for field in fields:
                if field["dataType"] in {"enum","flags","reference","inventoryReference","shopReference","boolean","statusChange"}: continue
                if any(word in str(field.get("label","")).casefold() for word in suspicious):
                    self.assertTrue(field.get("advanced"),field)
                    self.assertEqual(field.get("group"),"Advanced / engine data",field)

    def test_help_is_semantic_not_generic_storage_filler(self):
        collections=[*(semantics.apply(key,spec["fields"]) for key,spec in battle.SCENE_CATEGORIES.items()),semantics.apply("shops",extended.SHOP_FIELDS)]
        for fields in collections:
            for field in fields:
                self.assertNotIn("Numeric game value",str(field.get("help", "")),field)
        editor=(Path(__file__).resolve().parents[1]/"games/ff7/editor.html").read_text(encoding="utf-8")
        self.assertIn('return "";',editor)
        self.assertNotIn("help:infoHelp(semanticHelp(field))",editor)

    def test_scene_records_expose_reference_identity_without_changing_bytes(self):
        raw=extended_fixtures.scene_fixture(); scene=battle.SceneArchive(raw)
        enemy=scene.records("enemies")[0]; attack=scene.records("enemyAttacks")[0]; formation=scene.records("encounters")[0]
        self.assertEqual((enemy["scene"],enemy["gameId"]),(0,0))
        self.assertEqual((attack["scene"],attack["gameId"]),(0,0))
        self.assertEqual((formation["scene"],formation["gameId"]),(0,0))
        for category in battle.SCENE_CATEGORIES: scene.apply(category,scene.records(category))
        self.assertEqual(scene.to_bytes(),raw)

    def test_status_and_special_flag_storage_remains_exact(self):
        # Logical toggles are a presentation concern. Binary models continue to
        # round-trip the original stored masks exactly, including inverted fields.
        raw=extended_fixtures.scene_fixture(); obj=battle.SceneArchive(raw)
        enemy=obj.records("enemies")[0]["values"]["statusImmunity"]
        attack=obj.records("enemyAttacks")[0]["values"]["specialFlags"]
        self.assertEqual(enemy,int.from_bytes(obj.scenes[0][0x348:0x34C],"little"))
        self.assertEqual(attack,int.from_bytes(obj.scenes[0][0x4C0+26:0x4C0+28],"little"))


if __name__=="__main__": unittest.main(verbosity=2)
