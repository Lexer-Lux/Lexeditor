"""Build LEXEDITOR's vanilla localization subset from an OpenIV text export."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET

try:
    from .paths import PLUGIN_ROOT, PROJECT_ROOT
except ImportError:
    from paths import PLUGIN_ROOT, PROJECT_ROOT

SOURCE = PROJECT_ROOT / "_downloads/extract/localization/update_txt/global.txt"
OUTPUT = PLUGIN_ROOT / "vanilla_localization.json"


def parse_strings(path):
    values = {}
    for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if " = " in raw and not raw.lstrip().startswith("#"):
            key, value = raw.split(" = ", 1)
            key = key.strip()
            if key:
                values[key.upper()] = value
    return values


wanted = set()
catalog = ET.parse(PROJECT_ROOT / "datasets/vanilla/catalog_sp.ymt").getroot()
for item in catalog.findall("./catalog/items/item"):
    ui = item.find("ui")
    if ui is not None:
        for tag in ("key", "description"):
            value = ui.findtext(tag, "").strip()
            if value:
                wanted.add(value)

for filename in ("challenges_sp.meta", "goals_sp.meta"):
    root = ET.parse(PROJECT_ROOT / "datasets/vanilla" / filename).getroot()
    for node in root.iter():
        if isinstance(node.tag, str) and "label" in node.tag.lower() and node.text:
            wanted.add(node.text.strip())

weapons = ET.parse(PROJECT_ROOT / "datasets/vanilla/weapons.ymt").getroot()
for item in weapons.iter("Item"):
    if item.get("type") in {"CWeaponInfo", "CAmmoInfo"}:
        value = item.findtext("Name", "").strip()
        if value:
            wanted.add(value)

all_values = parse_strings(SOURCE)
subset = {key: all_values[key.upper()] for key in sorted(wanted) if key.upper() in all_values}
OUTPUT.write_text(json.dumps(subset, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"wrote {len(subset):,}/{len(wanted):,} referenced labels to {OUTPUT}")
