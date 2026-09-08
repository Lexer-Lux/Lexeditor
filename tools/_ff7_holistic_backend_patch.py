from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def replace_once(path,old,new,label):
    text=path.read_text(encoding='utf-8')
    if new in text:return
    if old not in text:raise SystemExit(f'{label}: insertion point changed')
    path.write_text(text.replace(old,new,1),encoding='utf-8')

# Apply semantic metadata to kernel-extra categories too.
path=ROOT/'games/ff7/datasets.py'
replace_once(path,
"""    result.extend(dict(id=key, label=spec['label'], fields=spec['fields'])
                  for key, spec in kernel_extra.EXTRAS.items())""",
"""    result.extend(dict(id=key, label=spec['label'], fields=semantics.apply(key, spec['fields']))
                  for key, spec in kernel_extra.EXTRAS.items())""",
'kernel-extra semantics')

# Expand synthetic section 3/4 fixtures to the documented ranges now exposed.
path=ROOT/'tools/verify_ff7_datasets.py'
replace_once(path,
"""    sections[3] = bytearray(b\"\\xa5\" * (9 * 132 + 700))
    sections[2] = bytearray(b\"\\x5a\" * (0x61C + 2048))
    sections[2][0x61C:0xE1C] = b\"\\xff\" * 2048""",
"""    sections[3] = bytearray(b\"\\xa5\" * 0xB2C)
    sections[2] = bytearray(b\"\\x5a\" * 0xF94)
    sections[2][0x61C:0xE1C] = b\"\\xff\" * 2048""",
'fixture sizes')
replace_once(path,
"""                self.assertEqual(sum(map(len, data[\"records\"].values())), 673)""",
"""                self.assertEqual(sum(map(len, data[\"records\"].values())), 1298)""",
'record count')
insert='''\n    def test_remaining_documented_initial_and_menu_data_round_trip_exact_bytes(self):\n        original = Kernel(self.source)\n        cases = [\n            (\"initialState\", 0, \"gil\", 1234567, 3, 0xB28, 4),\n            (\"initialInventory\", 17, \"amount\", 42, 3, 0x4A8 + 17 * 2, 2),\n            (\"initialMateria\", 11, \"ap\", 0x123456, 3, 0x728 + 11 * 4 + 1, 3),\n            (\"stolenMateria\", 7, \"ap\", 0x654321, 3, 0xA48 + 7 * 4 + 1, 3),\n        ]\n        for category, record_id, field, value, section, offset, size in cases:\n            with self.subTest(category=category, field=field):\n                kernel = Kernel(self.source); rows = kernel.records(category)\n                rows[record_id][\"values\"][field] = value\n                kernel.apply(category, rows)\n                expected = deepcopy(original.sections)\n                expected[section][offset:offset + size] = value.to_bytes(size, \"little\")\n                self.assertEqual(kernel.sections, expected)\n\n        kernel = Kernel(self.source); rows = kernel.records(\"initialInventory\")\n        rows[3][\"values\"].update(item=0x12A, amount=63); kernel.apply(\"initialInventory\", rows)\n        expected = deepcopy(original.sections); packed = 0x12A | (63 << 9); at = 0x4A8 + 3 * 2\n        expected[3][at:at+2] = packed.to_bytes(2, \"little\")\n        self.assertEqual(kernel.sections, expected)\n\n        kernel = Kernel(self.source); rows = kernel.records(\"initialMateria\")\n        rows[4][\"values\"].update(materia=23, ap=0x010203); kernel.apply(\"initialMateria\", rows)\n        expected = deepcopy(original.sections); at = 0x728 + 4 * 4\n        expected[3][at:at+4] = bytes((23, 3, 2, 1))\n        self.assertEqual(kernel.sections, expected)\n\n        kernel = Kernel(self.source); rows = kernel.records(\"magicOrder\")\n        rows[5][\"values\"].update(menuGroup=3, position=17); kernel.apply(\"magicOrder\", rows)\n        expected = deepcopy(original.sections); expected[2][0xF5C + 5] = (3 << 5) | 17\n        self.assertEqual(kernel.sections, expected)\n        self.assertEqual(kernel.records(\"magicOrder\")[5][\"values\"], {\"menuGroup\": 3, \"position\": 17})\n\n'''
replace_once(path,
"""    def test_noop_preserves_all_decoded_bytes(self):\n""",
insert+"""    def test_noop_preserves_all_decoded_bytes(self):\n""",
'new data exact-byte test')

# Add semantic metadata for the newly surfaced data and improve two weak enemy values.
path=ROOT/'games/ff7/semantics.py'
replace_once(path,
"""COMMAND_ACTIONS = (\n    (0x00, \"Perform command using target data\"), (0x01, \"Magic menu\"),\n    (0x02, \"Summon menu\"), (0x03, \"Item menu\"), (0x04, \"Enemy Skill menu\"),\n    (0x05, \"Throw menu\"), (0x06, \"Limit menu\"),\n    (0x07, \"Enable target selection via cursor\"), (0x08, \"W-Magic menu\"),\n    (0x09, \"W-Summon menu\"), (0x0A, \"W-Item menu\"), (0x0B, \"Coin menu\"),\n    (0xFF, \"No initial cursor action\"),\n)""",
"""COMMAND_ACTIONS = (\n    (0x00, \"Perform command using target data\"), (0x01, \"Magic menu\"),\n    (0x02, \"Summon menu\"), (0x03, \"Item menu\"), (0x04, \"Enemy Skill menu\"),\n    (0x05, \"Throw menu\"), (0x06, \"Limit menu\"),\n    (0x07, \"Enable target selection via cursor\"), (0x08, \"W-Magic menu\"),\n    (0x09, \"W-Summon menu\"), (0x0A, \"W-Item menu\"), (0x0B, \"Coin menu\"),\n    (0xFF, \"No initial cursor action\"),\n)\nMAGIC_MENU_GROUPS = ((0, \"Restore\"), (1, \"Attack\"), (2, \"Indirect\"), (3, \"Special\"), (0xFF, \"Not listed\"))""",
'magic menu groups')
replace_once(path,
"""CORE = {\n    \"commands\": {""",
"""CORE = {\n    \"initialState\": {\n        \"party1\": reference(\"characters\", label=\"Party member 1\", empty=255, help=\"First character placed in the party when a new save is initialized.\"),\n        \"party2\": reference(\"characters\", label=\"Party member 2\", empty=255, help=\"Second character placed in the party when a new save is initialized.\"),\n        \"party3\": reference(\"characters\", label=\"Party member 3\", empty=255, help=\"Third character placed in the party when a new save is initialized.\"),\n        \"gil\": _field(label=\"Starting gil\", group=\"Starting resources\", help=\"Gil copied into a newly initialized save. Existing saves are not changed.\"),\n    },\n    \"initialInventory\": {\n        \"item\": _field(label=\"Item / equipment\", dataType=\"inventoryReference\", emptyValue=0x1FF, includeMateria=False, group=\"Starting inventory\", help=\"Item or equipment stored in this new-game inventory slot. 511 means empty.\"),\n        \"amount\": _field(label=\"Quantity\", group=\"Starting inventory\", help=\"Initial quantity in this packed inventory slot (0–127).\"),\n    },\n    \"initialMateria\": {\n        \"materia\": reference(\"materia\", label=\"Materia\", empty=255, help=\"Materia stored in this initial stock slot; 255 means empty.\"),\n        \"ap\": _field(label=\"AP\", group=\"Starting Materia\", help=\"AP already accumulated on this initial Materia instance.\"),\n    },\n    \"stolenMateria\": {\n        \"materia\": reference(\"materia\", label=\"Materia\", empty=255, help=\"Materia in Yuffie's temporary stolen-Materia inventory for the Wutai sequence.\"),\n        \"ap\": _field(label=\"AP\", group=\"Stolen Materia\", help=\"AP retained on this temporary stolen-Materia instance.\"),\n    },\n    \"magicOrder\": {\n        \"menuGroup\": _field(label=\"Magic-menu section\", dataType=\"enum\", choices=choices(*MAGIC_MENU_GROUPS), group=\"Menu placement\", help=\"Which Magic submenu section contains this player spell: Restore, Attack, Indirect or Special. Not listed stores 0xFF.\"),\n        \"position\": _field(label=\"Position within section\", group=\"Menu placement\", help=\"Zero-based position inside the selected Magic submenu section.\"),\n    },\n    \"growthCurves\": {\n        **{f\"gradient{i}\": _field(label=\"Gradient\", group=f\"Levels {bracket}\", help=\"Slope/coefficient used by this level bracket's growth formula.\") for i, bracket in enumerate((\"2–11\",\"12–21\",\"22–31\",\"32–41\",\"42–51\",\"52–61\",\"62–81\",\"82–99\"))},\n        **{f\"base{i}\": _field(label=\"Base\", group=f\"Levels {bracket}\", help=\"Base/intercept used by this level bracket. Experience curves store this byte but do not use it in the EXP formula.\") for i, bracket in enumerate((\"2–11\",\"12–21\",\"22–31\",\"32–41\",\"42–51\",\"52–61\",\"62–81\",\"82–99\"))},\n    },\n    \"growthBonuses\": {\n        **{f\"bonus{i}\": _field(label=f\"Difference bracket {i}\", group=\"Randomized level gain\", help=\"Result/factor selected when the growth calculation lands in difference bracket %d.\" % i) for i in range(12)},\n    },\n    \"commands\": {""",
'new categories semantics')
replace_once(path,
"""        \"morph\": _field(label=\"Morph reward\", dataType=\"inventoryReference\", emptyValue=65535, group=\"Rewards\", help=\"Global item/equipment rewarded by Morph; 65535 means none.\"),\n        \"statusImmunity\":""",
"""        \"morph\": _field(label=\"Morph reward\", dataType=\"inventoryReference\", emptyValue=65535, group=\"Rewards\", help=\"Global item/equipment rewarded by Morph; 65535 means none.\"),\n        \"backMultiplier\": _field(label=\"Back-attack damage multiplier\", dataType=\"scaled\", displayScale=0.125, group=\"Stats / rewards\", help=\"Damage multiplier when this enemy is struck from behind. The stored byte is measured in eighths.\"),\n        \"statusImmunity\":""",
'enemy back multiplier')
replace_once(path,
"""        **{f\"dropRate{i}\": _field(label=f\"Loot slot {i+1} rate\", group=\"Loot\", help=\"Drop/steal probability parameter expressed as x/63 by Scarlet. 0xFF is also used with an empty item slot.\") for i in range(4)},""",
"""        **{f\"dropRate{i}\": _field(label=f\"Loot slot {i+1} method / chance\", dataType=\"lootRate\", group=\"Loot\", help=\"Values below 0x80 are drops; values from 0x80 are steals. The low seven bits are the chance parameter expressed as x/63.\") for i in range(4)},""",
'loot rate semantics')

# Semantic-surface assertions for the newly surfaced concepts.
path=ROOT/'tools/verify_ff7_semantic_surface.py'
replace_once(path,
"""            \"commands\":{\"initialCursorAction\":\"enum\",\"targetData\":\"flags\"},""",
"""            \"initialState\":{\"party1\":\"reference\"},\n            \"initialInventory\":{\"item\":\"inventoryReference\"},\n            \"initialMateria\":{\"materia\":\"reference\"},\n            \"stolenMateria\":{\"materia\":\"reference\"},\n            \"magicOrder\":{\"menuGroup\":\"enum\"},\n            \"commands\":{\"initialCursorAction\":\"enum\",\"targetData\":\"flags\"},""",
'new semantic assertions')
replace_once(path,
"""        self.assertTrue(meta[\"items\"][\"specialAttackFlags\"][\"invertBits\"])""",
"""        self.assertTrue(meta[\"items\"][\"specialAttackFlags\"][\"invertBits\"])\n        self.assertFalse(meta[\"initialInventory\"][\"item\"][\"includeMateria\"])\n        self.assertEqual(meta[\"enemies\"][\"dropRate0\"][\"dataType\"], \"lootRate\")\n        self.assertEqual(meta[\"enemies\"][\"backMultiplier\"][\"displayScale\"], 0.125)""",
'new semantic values')
