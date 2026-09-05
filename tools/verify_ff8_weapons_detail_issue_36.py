"""Focused contract for the FF8 Weapons detail pane (GitHub #36)."""

from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8 import paths  # noqa: E402
from games.ff8.plugin import FF8Session  # noqa: E402
from service_session import request_json  # noqa: E402


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def post(session: FF8Session, endpoint: str, payload: dict) -> dict:
    return request_json(session.url + endpoint, payload)


def main() -> int:
    html = (ROOT / "games" / "ff8" / "editor.html").read_text(encoding="utf-8")
    weapon_start = html.index("function weaponDetail(row,prefs)")
    weapon_end = html.index("function renderKernel", weapon_start)
    weapon_source = html[weapon_start:weapon_end]

    assert 'detailSection({className:"weapon-section weapon-data",title:"DATA"' in weapon_source
    assert 'detailSection({className:"weapon-section weapon-cost",title:"COST"' in weapon_source
    assert "return sharedDetail(row,prefs" in weapon_source
    assert weapon_source.index('"DATA"') < weapon_source.index('"COST"')
    assert '"INGREDIENTS"' not in weapon_source
    assert 'el("thead"' not in weapon_source
    cost_start = weapon_source.index('className:"weapon-section weapon-cost"')
    assert weapon_source.index('label:"PRICE"', cost_start) < weapon_source.index("...ingredients", cost_start)
    assert '"Upgrade price"' not in weapon_source
    assert 'fieldSourceControl(field,"weapons",row.id,{internal:true})' in weapon_source
    assert 'sourceControl(itemSearchControl(ingredient.itemId' in weapon_source
    assert 'ingredient.itemId===0?null:sourceControl(numberControl(ingredient.quantity,1,255,1' in weapon_source
    assert 'detailField({className:"weapon-ingredient-row"' in weapon_source
    assert "itemSelectControl(ingredient.itemId" not in weapon_source
    assert 'type:"items"' in html and 'prompt,target:()=>navigate("items")' in html
    assert "fieldGroups(" not in weapon_source
    assert 'el("details"' not in weapon_source
    assert ".weapon-detail" in html and "overflow:hidden" in html

    baseline = {
        path: digest(path)
        for path in (
            paths.BASELINE_ROOT / "menu" / "mwepon.bin",
            paths.BASELINE_ROOT / "main" / "kernel.bin",
        )
    }
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff8-weapons-36-", ignore_cleanup_errors=True) as project:
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project}) as session:
            weapon = request_json(session.url + "api/weapons")["rows"][0]
            price = 20 if weapon["upgradePrice"] != 20 else 30
            ingredients = [dict(value) for value in weapon["ingredients"]]
            ingredients[0]["quantity"] = (ingredients[0]["quantity"] + 1) % 256
            field = next(value for value in weapon["fields"] if value["field"] == "attack_power")
            field_value = field["value"] + 1 if field["value"] < field["maximum"] else field["value"] - 1
            result = post(session, "api/weapons/save", {"edits": [{
                "id": weapon["id"],
                "upgradePrice": price,
                "ingredients": ingredients,
                "fields": [{"field": field["field"], "value": field_value}],
            }]})
            assert result["saved"] == 1
            reread = request_json(session.url + "api/weapons")["rows"][0]
            assert reread["upgradePrice"] == price
            assert reread["ingredients"][0]["quantity"] == ingredients[0]["quantity"]
            assert next(value for value in reread["fields"] if value["field"] == "attack_power")["value"] == field_value

    assert all(digest(path) == expected for path, expected in baseline.items())
    print("FF8 Weapons detail and save/readback contracts passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
