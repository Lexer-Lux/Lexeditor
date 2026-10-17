"""Compare vendored effect metadata against independently pinned source facts."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

METADATA = Path(__file__).resolve().parents[2] / "plugins/ds1/metadata"
SOURCE = json.loads((METADATA / "EFFECT_SOURCE.json").read_text("utf-8"))


def projection(relative, text):
    if relative.startswith("defs/"):
        root = ET.fromstring(text)
        return {
            "header": {key: root.findtext(key) for key in
                       ("ParamType", "Unk06", "BigEndian", "Unicode", "Version")},
            "fields": [{"Def": node.attrib["Def"],
                        **{key: node.findtext(key) for key in ("Minimum", "Maximum", "Enum")}}
                       for node in root.findall("Fields/Field")],
        }
    if relative.startswith("meta/"):
        return {node.tag: dict(node.attrib) for node in ET.fromstring(text).find("Field")}
    value = json.loads(text)
    if relative.startswith("annotations/"):
        return {field["Field"]: {key: field[key] for key in ("Name", "Description")}
                for field in value["Fields"]}
    if relative.startswith("row_names/"):
        return {str(row["ID"]): row["Entries"][0] for row in value["Entries"] if row["Entries"]}
    return {str(row["Key"]): next((name["Text"] for name in row.get("Names", [])
                                  if name["Language"] == "English"), str(row["Key"]))
            for row in value["Options"]}


@pytest.mark.parametrize("relative", sorted(SOURCE["files"]))
def test_effect_metadata_matches_pinned_source(relative):
    value = projection(relative, (METADATA / relative).read_text("utf-8-sig"))
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode()
    actual = hashlib.sha256(encoded).hexdigest()
    assert actual == SOURCE["files"][relative]["semanticSha256"], (relative, actual)
