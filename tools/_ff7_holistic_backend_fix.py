from pathlib import Path

path=Path(__file__).resolve().parents[1]/'tools/verify_ff7_datasets.py'
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
