"""Verify the spreadsheet round trip: export a table, edit it, import it back."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from plugins.ff8 import formats, namedic, paths, wm2field  # noqa: E402


def sheet(text: str) -> tuple[list[str], list[dict]]:
    reader = csv.DictReader(io.StringIO(text))
    return reader.fieldnames or [], list(reader)


def main() -> int:
    listing = formats.table_list()["rows"]
    names = [row["name"] for row in listing]
    assert names == ["items", "names", "wm2field", "weapons", "refine", "shops"], names
    for row in listing:
        assert row["identity"] if "identity" in row else True
        assert row["editable"] and set(row["editable"]).issubset(row["columns"]), row

    project = tempfile.TemporaryDirectory(prefix="lexeditor-tables-", ignore_cleanup_errors=True)
    previous_project, previous_direct = paths.PROJECT_ROOT, paths.DIRECT_ROOT
    try:
        # The project must be isolated before the first read: "current" means the
        # reader's own project when one exists, and a check must not touch it.
        paths.PROJECT_ROOT = Path(project.name)
        paths.DIRECT_ROOT = paths.PROJECT_ROOT / "direct"

        # Export names the identity and every column, and carries a row per record.
        item_export = formats.table_csv("items")
        header, rows = sheet(item_export["text"])
        assert header == ["id", "name", "buyPrice", "sellMultiplier", "sellPrice"], header
        assert len(rows) == item_export["rows"] > 100
        assert rows[0]["id"] == "0"

        # A changed price lands through the item writer, and only that cell moves.
        before = formats.item_rows("current")["rows"]
        edited = rows[:]
        edited[1]["buyPrice"] = str(int(edited[1]["buyPrice"]) + 10)
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(edited)
        result = formats.import_table_csv("items", buffer.getvalue())
        assert result["applied"] == 1 and not result["rejected"], result
        after = formats.item_rows("current")["rows"]
        assert after[1]["buyPrice"] == before[1]["buyPrice"] + 10
        assert [row["buyPrice"] for row in after[2:]] == [row["buyPrice"] for row in before[2:]]
        # Nothing changed is nothing written.
        assert formats.import_table_csv("items", formats.table_csv("items")["text"])["applied"] == 0

        # A refused value names its line and leaves the other rows alone.
        bad = io.StringIO()
        writer = csv.DictWriter(bad, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        for row in edited:
            writer.writerow(row)
        bad.write("")
        text = bad.getvalue().replace(
            f'{"7"},', "7,", 1)
        lines = text.splitlines()
        lines.append("7,Item 7,25,5,6")
        result = formats.import_table_csv("items", "\n".join(lines) + "\n")
        assert result["rejected"], result
        assert any("step" in entry["reason"] or "price" in entry["reason"].lower()
                   for entry in result["rejected"]), result["rejected"]
        assert "no id" in result["rejected"][0]["reason"] or result["applied"] >= 0

        # The name list and the world-to-field table round trip too.
        names_export = formats.table_csv("names")
        _, name_rows = sheet(names_export["text"])
        assert len(name_rows) == 32 and name_rows[0]["id"] == "0"
        names_text = names_export["text"].replace("Galbadia", "Galbadia Test", 1)
        assert formats.import_table_csv("names", names_text)["applied"] == 1
        assert namedic.rows("current")["rows"][0]["text"] == "Galbadia Test"
        assert namedic.rows("current")["rows"][1]["text"] == "Esthar"

        world_export = formats.table_csv("wm2field")
        _, world_rows = sheet(world_export["text"])
        assert len(world_rows) == 72
        world_text = world_export["text"].replace(
            f'{world_rows[0]["id"]},{world_rows[0]["x"]},', f'{world_rows[0]["id"]},-1,', 1)
        result = formats.import_table_csv("wm2field", world_text)
        assert result["applied"] == 1, result
        assert wm2field.rows("current")["rows"][0]["x"] == -1

        # Weapon recipes: a price and an ingredient can be changed together.
        weapon_export = formats.table_csv("weapons")
        weapon_header, weapon_rows_csv = sheet(weapon_export["text"])
        assert weapon_header[:3] == ["id", "name", "upgradePrice"], weapon_header
        assert "item0" in weapon_header and "count3" in weapon_header, weapon_header
        weapons_before = formats.weapon_rows("current")["rows"]
        target = next(index for index, row in enumerate(weapons_before)
                      if row["ingredients"][0]["quantity"] > 0)
        changed_row = weapon_rows_csv[target]
        changed_row["upgradePrice"] = str(int(changed_row["upgradePrice"]) + 10)
        changed_row["count0"] = str(int(changed_row["count0"]) + 1)
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=weapon_header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(weapon_rows_csv)
        result = formats.import_table_csv("weapons", buffer.getvalue())
        assert result["applied"] == 1 and not result["rejected"], result
        weapons_after = formats.weapon_rows("current")["rows"]
        assert weapons_after[target]["upgradePrice"] == \
            weapons_before[target]["upgradePrice"] + 10
        assert weapons_after[target]["ingredients"][0]["quantity"] == \
            weapons_before[target]["ingredients"][0]["quantity"] + 1
        assert weapons_after[target + 1]["ingredients"] == \
            weapons_before[target + 1]["ingredients"]

        # Refine recipes: one recipe's quantities can move together.
        refine_export = formats.table_csv("refine")
        refine_header, refine_csv = sheet(refine_export["text"])
        assert refine_header == ["id", "table", "group", "inputId", "inputQuantity",
                                 "outputId", "outputQuantity", "text"], refine_header
        assert refine_export["rows"] == 377, refine_export["rows"]
        assert refine_csv[0]["id"] == "m000:0"
        target = next(row for row in refine_csv
                      if row["table"] == "m000" and int(row["inputQuantity"]) < 255)
        target["inputQuantity"] = str(int(target["inputQuantity"]) + 1)
        target["outputQuantity"] = str((int(target["outputQuantity"]) + 1) % 256)
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=refine_header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(refine_csv)
        result = formats.import_table_csv("refine", buffer.getvalue())
        assert result["applied"] == 1 and not result["rejected"], result
        landed = next(row for row in formats.refine_rows("current")["rows"]
                      if row["table"] == target["table"]
                      and f"{row['table']}:{row['id']}" == target["id"])
        assert landed["inputQuantity"] == int(target["inputQuantity"])
        assert landed["outputQuantity"] == int(target["outputQuantity"])
        neighbour = next(row for row in formats.refine_rows("current")["rows"]
                         if row["table"] == "m004" and row["id"] == 0)
        assert neighbour["inputQuantity"] == int(next(
            row["inputQuantity"] for row in refine_csv if row["id"] == "m004:0"))

        # Shop inventories: an item and its rare flag can move together.
        shop_export = formats.table_csv("shops")
        shop_header, shop_csv = sheet(shop_export["text"])
        assert shop_header == ["id", "shop", "shopName", "slot", "itemId", "itemName",
                               "rare"], shop_header
        assert len(shop_csv) == shop_export["rows"] == 320, shop_export["rows"]
        assert shop_csv[0]["id"] == "0:0"
        shops_before = {(shop["id"], slot["slot"]): (slot["itemId"], slot["rare"])
                        for shop in formats.shop_rows("current")["rows"]
                        for slot in shop["slots"]}
        shop_csv[0]["itemId"] = str((int(shop_csv[0]["itemId"]) + 1) % 200)
        shop_csv[0]["rare"] = "0" if shop_csv[0]["rare"] == "1" else "1"
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=shop_header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(shop_csv)
        result = formats.import_table_csv("shops", buffer.getvalue())
        assert result["applied"] == 1 and not result["rejected"], result
        shops_after = {(shop["id"], slot["slot"]): (slot["itemId"], slot["rare"])
                       for shop in formats.shop_rows("current")["rows"]
                       for slot in shop["slots"]}
        assert shops_after[(0, 0)] == (int(shop_csv[0]["itemId"]),
                                       shop_csv[0]["rare"] == "1")
        assert [shops_after[key] for key in shops_after if key != (0, 0)] == [
            shops_before[key] for key in shops_before if key != (0, 0)]
        # A rare flag outside 0/1 is refused with the rest landing.
        shop_csv[1]["rare"] = "2"
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=shop_header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(shop_csv)
        result = formats.import_table_csv("shops", buffer.getvalue())
        assert result["applied"] == 0 and len(result["rejected"]) == 1, result
        assert "0 or 1" in result["rejected"][0]["reason"], result["rejected"]

        for bad_name, expected in [("nope", "unknown table"), ("", "unknown table")]:
            try:
                formats.table_csv(bad_name)
            except ValueError as error:
                assert expected in str(error).lower(), error
            else:
                raise AssertionError(f"the table engine accepted {bad_name!r}")
        try:
            formats.import_table_csv("items", "name,buyPrice\nPotion,10\n")
        except ValueError as error:
            assert "id column" in str(error)
        else:
            raise AssertionError("a sheet without the identity column was accepted")
        try:
            formats.import_table_csv("items", "id,buyPrice\n1,10\n")
        except ValueError as error:
            assert "missing" in str(error)
        else:
            raise AssertionError("a sheet missing a column was accepted")
    finally:
        paths.PROJECT_ROOT, paths.DIRECT_ROOT = previous_project, previous_direct
        project.cleanup()
    print(json.dumps({"tables": names, "itemRows": item_export["rows"],
                      "namesRows": 32, "worldRows": 72, "roundTrip": True},
                     ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
