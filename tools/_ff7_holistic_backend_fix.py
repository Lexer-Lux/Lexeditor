from pathlib import Path

path=Path(__file__).resolve().parents[1]/'tools/verify_ff7_datasets.py'
text=path.read_text(encoding='utf-8')
old='''            ("initialInventory", 17, "amount", 42, 3, 0x4A8 + 17 * 2, 2),\n'''
if old in text:
    text=text.replace(old,'',1)
old='''            expected = {"characters", "growthCurves", "growthBonuses", "characterAI"} if section == 2 else {"characters"}\n'''
new='''            expected = {"characters", "growthCurves", "growthBonuses", "characterAI", "magicOrder"} if section == 2 else {"characters"}\n'''
if new not in text:
    if old not in text: raise SystemExit('truncated-section expectation insertion point changed')
    text=text.replace(old,new,1)
path.write_text(text,encoding='utf-8')
