"""Records made by Lexeditor's create actions carry the created-in-mod pen.

todo: "Warband: created records (e.g. troops from the template copy) still get
no created-in-mod pen; the server has no 'created' flag yet." The create
endpoints note each new id in the project's ledger, and the lists mark rows
whose id is in it.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plugins.warband import server  # noqa: E402
from plugins.warband.troop_editor import create_troop, troop_data  # noqa: E402
from test_warband_troop_editor import SOURCE  # noqa: E402


def test_created_troop_is_noted_and_marked(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "CREATED_LEDGER", tmp_path / ".lexeditor-created.json")
    (tmp_path / "module_troops.py").write_text(SOURCE, encoding="utf-8")
    data = troop_data(tmp_path)
    server.note_created("troops", create_troop(tmp_path, data["sha256"], 0, "soldier", "new_soldier",
                                               "New soldier", "New soldiers"))
    marked = server.mark_created("troops", troop_data(tmp_path))
    flags = {row["id"]: row.get("created", False) for row in marked["rows"]}
    assert flags["new_soldier"] is True and flags["soldier"] is False
    # Other kinds keep their own ids.
    assert server.created_ids("items") == set()


def test_ledger_keeps_each_id_once_and_ignores_failed_creates(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "CREATED_LEDGER", tmp_path / ".lexeditor-created.json")
    server.note_created("items", {"created": "itm_new"})
    server.note_created("items", {"created": "itm_new"})
    server.note_created("items", {"saved": 0})
    assert server.created_ids("items") == {"itm_new"}


def test_a_broken_ledger_marks_nothing(tmp_path, monkeypatch):
    ledger = tmp_path / ".lexeditor-created.json"
    ledger.write_text("not json", encoding="utf-8")
    monkeypatch.setattr(server, "CREATED_LEDGER", ledger)
    payload = {"rows": [{"id": "a"}]}
    assert server.mark_created("troops", payload) == {"rows": [{"id": "a"}]}
