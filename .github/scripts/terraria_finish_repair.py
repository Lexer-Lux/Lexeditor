from pathlib import Path

# Preserve the legacy compact SpawnChance output when no structured filters are selected.
path = Path("games/terraria/structured_content.py")
text = path.read_text(encoding="utf-8")
old = "    if v['spawnChance']>0: out += [\"\",f\"public override float SpawnChance(NPCSpawnInfo spawnInfo) => ({_npc_spawn_condition(v)}) ? {_f(v['spawnChance'])} : 0f;\"]\n"
new = "    if v['spawnChance']>0:\n        condition=_npc_spawn_condition(v)\n        spawn=f\"public override float SpawnChance(NPCSpawnInfo spawnInfo) => {_f(v['spawnChance'])};\" if condition=='true' else f\"public override float SpawnChance(NPCSpawnInfo spawnInfo) => ({condition}) ? {_f(v['spawnChance'])} : 0f;\"\n        out += [\"\",spawn]\n"
if text.count(old) != 1:
    raise SystemExit(f"spawn compatibility anchor count: {text.count(old)}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")

# Extend the established exact schema regression to cover the five new families.
path = Path("tests/test_terraria_structured_content.py")
text = path.read_text(encoding="utf-8")
old = '{"item", "npc", "projectile", "buff", "tile", "wall", "globalItem", "globalNPC", "globalProjectile", "prefix", "rarity", "biome", "config", "command", "recipe"},'
new = '{"item", "npc", "projectile", "buff", "tile", "wall", "globalItem", "globalNPC", "globalProjectile", "prefix", "rarity", "biome", "config", "command", "sceneEffect", "dust", "globalBuff", "globalTile", "globalWall", "recipe"},'
if text.count(old) != 1:
    raise SystemExit(f"schema regression anchor count: {text.count(old)}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
