from pathlib import Path

path = Path('.github/scripts/terraria_structured_systems_patch.py')
text = path.read_text(encoding='utf-8')
start_marker = '# Preserved custom hooks for managed types whose common advanced logic can\'t be represented safely as scalar fields.\n'
end_marker = '# Localization for biome DisplayName.\n'
start = text.index(start_marker)
end = text.index(end_marker, start)
block = text[start:end]
count = block.count('}}')
if count != 2:
    raise SystemExit(f'expected exactly two doubled closing braces in render-source patch block, found {count}')
text = text[:start] + block.replace('}}', '}') + text[end:]
path.write_text(text, encoding='utf-8')
