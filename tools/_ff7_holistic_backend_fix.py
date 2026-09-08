from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

path=ROOT/'tools/verify_ff7_datasets.py'
text=path.read_text(encoding='utf-8')
old='''            ("initialInventory", 17, "amount", 42, 3, 0x4A8 + 17 * 2, 2),\n'''
if old in text:
    text=text.replace(old,'',1)
old='''            expected = {"characters", "growthCurves", "growthBonuses", "characterAI"} if section == 2 else {"characters"}\n'''
intermediate='''            expected = {"characters", "growthCurves", "growthBonuses", "characterAI", "magicOrder"} if section == 2 else {"characters"}\n'''
new='''            expected = ({"characters", "growthCurves", "growthBonuses", "characterAI", "magicOrder"} if section == 2 else
                        {"characters", "initialState", "initialInventory", "initialMateria", "stolenMateria"})\n'''
if new not in text:
    if intermediate in text:
        text=text.replace(intermediate,new,1)
    elif old in text:
        text=text.replace(old,new,1)
    else:
        raise SystemExit('truncated-section expectation insertion point changed')
path.write_text(text,encoding='utf-8')

path=ROOT/'tools/verify_ff7_semantic_surface.py'
text=path.read_text(encoding='utf-8')
wrong='''        self.assertFalse(meta["initialInventory"]["item"]["includeMateria"])
        self.assertEqual(meta["enemies"]["dropRate0"]["dataType"], "lootRate")
        self.assertEqual(meta["enemies"]["backMultiplier"]["displayScale"], 0.125)
'''
right='''        self.assertFalse(meta["initialInventory"]["item"]["includeMateria"])
'''
if wrong in text:
    text=text.replace(wrong,right,1)
anchor='''        self.assertTrue(by["enemyAttacks"]["specialFlags"]["invertBits"])
'''
expanded='''        self.assertTrue(by["enemyAttacks"]["specialFlags"]["invertBits"])
        self.assertEqual(by["enemies"]["dropRate0"]["dataType"], "lootRate")
        self.assertEqual(by["enemies"]["backMultiplier"]["dataType"], "scaled")
        self.assertEqual(by["enemies"]["backMultiplier"]["displayScale"], 0.125)
'''
if expanded not in text:
    if anchor not in text: raise SystemExit('extended semantic assertion insertion point changed')
    text=text.replace(anchor,expanded,1)
path.write_text(text,encoding='utf-8')
