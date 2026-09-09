"""Small follow-up for the responsive FF7 one-shot before verification."""
from pathlib import Path

root=Path(__file__).resolve().parents[1]
editor=root/'games/ff7/editor.html'
text=editor.read_text(encoding='utf-8')
old='formationAI:"Formation AI",fieldEncounters:"Field"'
new='formationAI:"AI",fieldEncounters:"Field"'
if text.count(old)!=1: raise SystemExit(f'encounter subtab marker count {text.count(old)}')
editor.write_text(text.replace(old,new),encoding='utf-8')

rendered=root/'tools/verify_ff7_rendered.py'
tests=rendered.read_text(encoding='utf-8')
renames={
    "get_by_role('tab',name='Growth curves',exact=True)":"get_by_role('tab',name='Curves',exact=True)",
    "get_by_role('tab',name='Growth bonuses',exact=True)":"get_by_role('tab',name='Bonuses',exact=True)",
    "get_by_role('tab',name='Field encounters',exact=True)":"get_by_role('tab',name='Field',exact=True)",
}
expected={"Growth curves":3,"Growth bonuses":1,"Field encounters":1}
for old,new in renames.items():
    label=old.split("name='")[1].split("'")[0]
    count=tests.count(old)
    if count!=expected[label]: raise SystemExit(f'{label} rendered assertion count {count}')
    tests=tests.replace(old,new)
rendered.write_text(tests,encoding='utf-8')
