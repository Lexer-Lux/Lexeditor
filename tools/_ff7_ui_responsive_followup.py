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
old="get_by_role('tab',name='Growth curves',exact=True)"
new="get_by_role('tab',name='Curves',exact=True)"
if tests.count(old)!=2: raise SystemExit(f'Growth curves rendered assertion count {tests.count(old)}')
rendered.write_text(tests.replace(old,new),encoding='utf-8')
