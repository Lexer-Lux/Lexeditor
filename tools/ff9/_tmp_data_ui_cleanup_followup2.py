from pathlib import Path

p = Path("tests/ff9_editor.test.cjs")
s = p.read_text(encoding="utf-8")
old = '''test('catalog-driven views expose every character dataset', async () => {\n  const e = await editor();\n  e.run('state.catalog=[{key:"characters",tab:"characters"},{key:"character-parameters",tab:"characters"},{key:"default-equipment",tab:"characters"},{key:"leveling",tab:"characters"},{key:"world-weather",tab:"world"}]');\n  assert.deepEqual(Array.from(e.run('choices("characters")')), ['characters','character-parameters','default-equipment','leveling']);\n  assert.deepEqual(Array.from(e.run('choices("world")')), ['world-weather']);\n});\n'''
new = '''test('catalog-driven views combine character implementation tables behind conceptual navigation', async () => {\n  const e = await editor();\n  e.run('state.catalog=[{key:"characters",tab:"characters"},{key:"character-parameters",tab:"characters"},{key:"default-equipment",tab:"characters"},{key:"leveling",tab:"characters"},{key:"world-weather",tab:"world"}]');\n  assert.deepEqual(Array.from(e.run('choices("characters")')), ['characters','leveling']);\n  assert.deepEqual(Array.from(e.run('choices("world")')), ['world-weather']);\n});\n'''
if old not in s:
    raise SystemExit("obsolete character-subtab test anchor missing")
p.write_text(s.replace(old, new, 1), encoding="utf-8")
