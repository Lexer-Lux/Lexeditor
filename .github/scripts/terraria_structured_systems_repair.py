from pathlib import Path

path = Path('.github/scripts/terraria_structured_systems_patch.py')
text = path.read_text(encoding='utf-8')
old = '\\n}}\\n'
new = '\\n}\\n'
count = text.count(old)
if count != 2:
    raise SystemExit(f'expected two render-source closing-brace escapes, found {count}')
path.write_text(text.replace(old, new), encoding='utf-8')
