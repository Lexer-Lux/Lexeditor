"""Static and round-trip contract for Lexeditor issue 21."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import discover_plugins  # noqa: E402
from games.ff8 import paths  # noqa: E402
from games.ff8.plugin import FF8Session  # noqa: E402
from service_session import request_json  # noqa: E402


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def post(session: FF8Session, endpoint: str, payload: dict) -> dict:
    return request_json(session.url + endpoint, payload)


def main() -> int:
    plugin = discover_plugins().get("ff8")
    assert plugin is not None and plugin.name == "Final Fantasy 8"
    assert plugin.installation and plugin.installation.steam_app_id == "39150"
    assert not plugin.check()

    html = (ROOT / "games" / "ff8" / "editor.html").read_text(encoding="utf-8")
    for required in ("/shared/framework.css", "/shared/framework.js", "pagedListDetail",
                     "LexeditorUI.dataMap", '["characters","Characters"]',
                     'type:"text",inputmode:"decimal"', 'search:{key:`ff8-${view}`',
                     '@font-face{font-family:"FF8 Menu"',
                     "linear-gradient(135deg,#747474,#555"):
        assert required in html, f"FF8 editor is missing {required}"
    assert 'value:gfCompatibilityFormat(field.value)' in html
    assert "gf-compat-sign" not in html, "GF Compatibility restored the detached plus-sign overlay"

    lzs_source = ROOT / "games" / "ff8" / "vendor" / "ff8ue" / "lzs.py"
    assert digest(lzs_source) == "eb0fa352685f9ef6b7ce3c2d9f8f70cfc289d23551449175d9aa1ed2eaf3e8f6"
    baseline_files = [
        paths.BASELINE_ROOT / "main" / "kernel.bin",
        paths.BASELINE_ROOT / "menu" / "price.bin",
        paths.BASELINE_ROOT / "menu" / "shop.bin",
        paths.BASELINE_ROOT / "menu" / "mwepon.bin",
        paths.BASELINE_ROOT / "menu" / "sysfnt.tex",
        paths.BASELINE_ROOT / "menu" / "sysfnt.tdw",
    ]
    before = {path: digest(path) for path in baseline_files}

    with tempfile.TemporaryDirectory(prefix="lexeditor-ff8-contract-", ignore_cleanup_errors=True) as project:
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project}) as session:
            with urlopen(session.url + "assets/ff8-menu.ttf", timeout=5) as response:
                assert response.headers.get_content_type() in {
                    "font/ttf", "application/octet-stream", "application/x-font-ttf"
                }
                assert len(response.read()) > 10_000
            items = request_json(session.url + "api/items")
            item = items["rows"][1]
            next_price = 20 if item["buyPrice"] != 20 else 30
            assert post(session, "api/items/save", {"edits": [{
                "id": item["id"], "buyPrice": next_price,
                "sellMultiplier": item["sellMultiplier"],
            }]})["saved"] == 1

            shops = request_json(session.url + "api/shops")
            slot = shops["rows"][0]["slots"][0]
            assert post(session, "api/shops/save", {"edits": [{
                "shopId": 0, "slot": 0, "itemId": slot["itemId"], "rare": not slot["rare"],
            }]})["saved"] == 1

            weapons = request_json(session.url + "api/weapons")
            weapon = weapons["rows"][0]
            next_weapon_price = 20 if weapon["upgradePrice"] != 20 else 30
            assert post(session, "api/weapons/save", {"edits": [{
                "id": 0, "upgradePrice": next_weapon_price,
                "ingredients": weapon["ingredients"], "fields": [],
            }]})["saved"] == 1

            for section in (2, 3, 7):
                records = request_json(session.url + f"api/kernel?section={section}")["rows"]
                candidate = next(
                    (field for row in records for field in row["fields"]
                     if field["mask"] is None and field["maximum"] > 1), None
                )
                assert candidate is not None
                row = next(row for row in records if candidate in row["fields"])
                value = candidate["value"] + 1 if candidate["value"] < candidate["maximum"] else candidate["value"] - 1
                assert post(session, "api/kernel/save", {
                    "section": section,
                    "edits": [{"id": row["id"], "field": candidate["field"], "value": value}],
                })["saved"] == 1

            output = Path(project) / "direct"
            assert (output / "kernel.bin").is_file()
            assert (output / "menu" / "price.bin").is_file()
            assert (output / "menu" / "shop.bin").is_file()
            assert (output / "menu" / "mwepon.bin").is_file()
            assert request_json(session.url + "api/items")["rows"][1]["buyPrice"] == next_price

    assert all(digest(path) == expected for path, expected in before.items())
    print(json.dumps({
        "plugin": "ff8",
        "roundTrips": ["price.bin", "shop.bin", "mwepon.bin", "kernel.bin sections 2, 3, and 7"],
        "baselineUnchanged": True,
        "copiedSourceVerified": True,
        "installedMenuFontGenerated": True,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
