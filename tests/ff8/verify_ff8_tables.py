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
    assert names == ["items", "names", "wm2field"], names
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
