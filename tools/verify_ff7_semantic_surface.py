"""Regression contract: FF7 UI exposes game concepts, not storage bytes."""
from __future__ import annotations

from pathlib import Path
import unittest

import verify_ff7_datasets as kernel_fixtures
import verify_ff7_extended as extended_fixtures
from games.ff7 import battle, datasets, extended, semantics, server


class SemanticSurfaceTests(unittest.TestCase):
    def test_core_kernel_categories_are_humanized(self):
        meta={category["id"]:{f["key"]:f for f in category["fields"]} for category in datasets.category_metadata()}
        expected={
            "initialState":{"party1":"enum"},
            "initialInventory":{"item":"inventoryReference"},
            "initialMateria":{"materia":"reference"},
            "stolenMateria":{"materia":"reference"},
            "magicOrder":{"menuGroup":"enum"},
            "commands":{"initialCursorAction":"enum","targetData":"flags"},
            "playerAttacks":{"targetData":"flags","damageCalculationId":"enum","statusChange":"statusChange","statusFlags":"flags","elementFlags":"flags","specialAttackFlags":"flags"},
            "items":{"targetData":"flags","damageCalculationId":"enum","statusChange":"statusChange","statusFlags":"flags","elementFlags":"flags","restrictions":"flags","specialAttackFlags":"flags"},
            "weapons":{"targetData":"flags","damageCalculationId":"enum","growthRate":"enum","equipableBy":"flags","attackElements":"flags","boostedStat1":"enum","materiaSlot1":"enum","restrictions":"flags"},
            "armor":{"elementDamageModifier":"enum","status":"enum","growthRate":"enum","equipableBy":"flags","elementalDefense":"flags","boostedStat1":"enum","materiaSlot1":"enum","restrictions":"flags"},
            "accessories":{"boostedStat1":"enum","specialEffect":"enum","elementalDefense":"flags","statusDefense":"flags","equipableBy":"flags","restrictions":"flags"},
            "characters":{"weaponId":"reference","armorId":"reference","accessoryId":"reference","characterFlags":"enum","rowByte":"enum","learnedLimits":"flags","weaponMateria0":"reference","strengthCurve":"reference","recruitOffsetRaw":"scaled"},
        }
        for category, fields in expected.items():
            for key, kind in fields.items(): self.assertEqual(meta[category][key]["dataType"],kind,(category,key))
        self.assertEqual(next(c for c in meta["characters"]["rowByte"]["choices"] if c["label"]=="Front row")["value"],0xFF)
        self.assertEqual([c["value"] for c in meta["characters"]["characterFlags"]["choices"]],[0x00,0x10,0x20])
        self.assertNotIn("flags",meta["characters"]["characterFlags"])
        self.assertEqual([c["value"] for c in meta["characters"]["storedId"]["choices"]],list(range(11)))
        identity_labels={c["value"]:c["label"] for c in meta["characters"]["storedId"]["choices"]}
        self.assertEqual({i:identity_labels[i] for i in (6,7,9,10)}, {6:"Cait Sith",7:"Vincent",9:"Young Cloud",10:"Sephiroth"})
        party_choices=meta["initialState"]["party1"]["choices"]
        self.assertEqual([c["value"] for c in party_choices],[0xFF,*range(11)])
        self.assertEqual(party_choices[0]["label"],"None")
        self.assertEqual(meta["characters"]["limitAttack11"]["referenceCategory"],"limitBreaks")
        self.assertEqual(meta["characters"]["limitAttack11"]["referenceValueKey"],"gameId")
        self.assertTrue(meta["playerAttacks"]["specialAttackFlags"]["invertBits"])
        for category in ("items","weapons","armor","accessories"):
            self.assertTrue(meta[category]["restrictions"]["invertBits"],category)
            self.assertEqual(meta[category]["restrictions"]["bitWidth"],16,category)
        self.assertTrue(meta["items"]["specialAttackFlags"]["invertBits"])
        self.assertFalse(meta["initialInventory"]["item"]["includeMateria"])
        self.assertEqual([c["value"] for c in meta["weapons"]["materiaSlot1"]["choices"]],[0,1,2,3,5,6,7])

    def test_limit_break_records_expose_stored_game_ids(self):
        obj=object.__new__(extended.ShopExecutable)
        obj.shift=0
        obj.data=bytearray(0x51DCD4 + 71 * 28)
        rows=obj.records("limitBreaks")
        self.assertEqual((rows[0]["id"],rows[0]["gameId"]),(0,128))
        self.assertEqual((rows[-1]["id"],rows[-1]["gameId"]),(70,198))

    def test_limit_text_linking_uses_kernel2_attack_indices(self):
        def side(name, description):
            return {
                "texts":[
                    {"id":9*65536+128,"values":{"text":name}},
                    {"id":1*65536+128,"values":{"text":description}},
                ],
                "limitBreaks":[{"id":0,"gameId":128,"name":"Limit break 0","description":"Executable Limit attack data."}],
            }
        data={"records":side("Braver","Deal damage."),"vanilla":side("Vanilla Braver","Vanilla help.")}
        server._link_limit_text(data)
        self.assertEqual((data["records"]["limitBreaks"][0]["name"],data["records"]["limitBreaks"][0]["description"]),("Braver","Deal damage."))
        self.assertEqual((data["vanilla"]["limitBreaks"][0]["name"],data["vanilla"]["limitBreaks"][0]["description"]),("Vanilla Braver","Vanilla help."))

    def test_limit_save_response_keeps_linked_text(self):
        result={"records":{"limitBreaks":[{"id":0,"gameId":128,"name":"Limit break 0","description":"Executable Limit attack data."}]}}
        extra={"records":{"texts":[
            {"id":9*65536+128,"values":{"text":"Braver"}},
            {"id":1*65536+128,"values":{"text":"Deal damage."}},
        ]}}
        returned=server._link_saved_limit_text(result,extra)
        self.assertIs(returned,result)
        self.assertEqual((result["records"]["limitBreaks"][0]["name"],result["records"]["limitBreaks"][0]["description"]),("Braver","Deal damage."))

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
        self.assertEqual(by["enemies"]["dropRate0"]["dataType"], "enum")
        loot_values={choice["value"] for choice in by["enemies"]["dropRate0"]["choices"]}
        self.assertTrue({0,63,0x81,0xBF} <= loot_values)
        self.assertTrue({64,0x7F,0x80,0xC0}.isdisjoint(loot_values))
        self.assertEqual(by["enemies"]["backMultiplier"]["dataType"], "scaled")
        self.assertEqual(by["enemies"]["backMultiplier"]["displayScale"], 0.125)
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