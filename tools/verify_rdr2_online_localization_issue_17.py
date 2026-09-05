"""Focused contract for RDR2 Online item-name resolution."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.rdr2 import extractor, server  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    localization_entry = next(
        (entry for entry in extractor.ENTRIES
         if entry.output == "localization/american_global.json"), None)
    require(localization_entry is not None, "startup extraction omits Online localization")
    require(localization_entry.archive == "update_3.rpf", "wrong localization archive")
    require(localization_entry.entry == "x64/data/lang/american_rel.rpf",
            "wrong English localization archive entry")
    require(localization_entry.chain == ("global.yldb",), "global.yldb chain is missing")
    require(localization_entry.kind == "text-json", "localization is not decoded to JSON")

    with tempfile.TemporaryDirectory(prefix="lexeditor-online-localization-", ignore_cleanup_errors=True) as name:
        temporary = Path(name)
        catalog = temporary / server.CATALOG_FILE
        online = temporary / "american_global.json"
        story = temporary / "story.json"
        overrides = temporary / server.LOCALIZATION_FILE

        direct_key = "ONLINE_DIRECT_LABEL"
        direct_hash = f"0x{server.joaat(direct_key):08X}"
        story.write_text(json.dumps({"STORY_LABEL": "Story item"}), encoding="utf-8")
        online.write_text(json.dumps({
            direct_hash: "Direct Online item",
            "0x00153557": "Webster Gun Belt",
            "0x5DE85D64": "Irish Whiskey Bottle",
            "0xA76A7C7B": "A precious bottle of whiskey.",
        }), encoding="utf-8")
        overrides.write_text(
            "[LEXEDITOR OVERRIDES]\n\nONLINE_ALT_LABEL = Custom bottle name\n",
            encoding="utf-8",
        )
        catalog.write_text("""<root><catalog><items>
          <item key="DIRECT"><ui><key>ONLINE_DIRECT_LABEL</key><description />
            <localization /></ui></item>
          <item key="HASHED"><ui><key>0x00153557</key><description />
            <localization /></ui></item>
          <item key="ALT"><ui><key>ONLINE_ALT_LABEL</key><description>ONLINE_ALT_DESC</description>
            <localization>
              <item><type>LABEL_TYPE_ALT_NAME</type><values><item>0x5DE85D64</item></values></item>
              <item><type>LABEL_TYPE_ALT_DESC</type><values><item>0xA76A7C7B</item></values></item>
            </localization></ui></item>
        </items></catalog></root>""", encoding="utf-8")

        old_dataset = server.DATASETS["mine"]
        old_online = server.ONLINE_LOCALIZATION_FILE
        old_story = server.VANILLA_LOCALIZATION_FILE
        try:
            server.DATASETS["mine"] = {"dir": temporary, "readonly": False}
            server.ONLINE_LOCALIZATION_FILE = online
            server.VANILLA_LOCALIZATION_FILE = story
            result = server.get_localization("mine")
        finally:
            server.DATASETS["mine"] = old_dataset
            server.ONLINE_LOCALIZATION_FILE = old_online
            server.VANILLA_LOCALIZATION_FILE = old_story

        require(result["values"][direct_key] == "Direct Online item",
                "symbolic Online labels do not resolve through their hash")
        require(result["values"]["0x00153557"] == "Webster Gun Belt",
                "hashed Online labels do not resolve directly")
        require(result["vanilla"]["ONLINE_ALT_LABEL"] == "Irish Whiskey Bottle",
                "alternate Online name was not exposed as the baseline")
        require(result["vanilla"]["ONLINE_ALT_DESC"] == "A precious bottle of whiskey.",
                "alternate Online description was not exposed as the baseline")
        require(result["values"]["ONLINE_ALT_LABEL"] == "Custom bottle name",
                "the editable strings.gxt2 override did not remain authoritative")

    print("PASS: installed Online text, direct hashes, alternate labels, and overrides are covered")


if __name__ == "__main__":
    main()
