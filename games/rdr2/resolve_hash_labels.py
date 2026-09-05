"""Resolve hashed catalog identifiers using a local candidate-string corpus.

Expected corpus: _downloads/RDR2-Unhashed-Strings/*.txt. The corpus remains
gitignored; only exact joaat matches are written to this plugin's labels.json.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import server
from paths import PROJECT_ROOT

CORPUS = PROJECT_ROOT / "_downloads" / "RDR2-Unhashed-Strings"
FILES = ["MemberNames.txt", "DataLines.txt", "ArchiveItems.txt"]


def joaat(value):
    h = 0
    for char in value.lower().encode("latin-1", "ignore"):
        h = (h + char) & 0xFFFFFFFF
        h = (h + (h << 10)) & 0xFFFFFFFF
        h ^= h >> 6
    h = (h + (h << 3)) & 0xFFFFFFFF
    h ^= h >> 11
    return (h + (h << 15)) & 0xFFFFFFFF


catalog = server.get_catalog("mine")
shops = server.get_shops("mine")["shops"]
scopes = {
    "items": {item["key"] for item in catalog["items"] if item["key"].startswith("0x")},
    "effects": {effect["key"] for effect in catalog["effects"] if effect["key"].startswith("0x")},
    "catalogueMenus": {
        key
        for shop in shops
        for category in shop.get("catalogueCategories", [])
        for key in category.get("path", [])
        if key.startswith("0x")
    },
}
targets = {int(key[2:], 16): key for keys in scopes.values() for key in keys}
resolved = {}
for filename in FILES:
    with (CORPUS / filename).open(encoding="utf-8-sig", errors="ignore") as source:
        for line in source:
            candidate = line.strip()
            if candidate:
                hashed = joaat(candidate)
                if hashed in targets and hashed not in resolved:
                    resolved[hashed] = candidate

labels = server.get_labels()
for scope, keys in scopes.items():
    output = labels.setdefault(scope, {})
    for hashed, candidate in resolved.items():
        key = targets[hashed]
        if key in keys:
            output.setdefault(key, candidate)
server.LABELS_FILE.write_text(json.dumps(labels, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"Resolved {len(resolved)} of {len(targets)} hashed catalog identifiers.")
