"""The Enemies tab's Bosses subtab: reviewed boss rows, nothing else.

Bosses are NpcParam rows like monsters, kept out of Monsters by the family
allowlist. The Bosses subtab admits reviewed boss families across the live
types bosses fight with: Standard Enemy (0) for the early demons and Smough,
boss type (1) for most, and Gwyndolin alone at the friendly type (2) - he
lists as a boss, not an NPC. Tails, heads, arms and other body parts stay
out, as do merchants, friendly NPCs, test rows and unknown IDs.
"""
import json
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive
from plugins.ds1.formats import FormatError, ItemDocument
from plugins.ds1.monsters import BOSS_FAMILIES, MONSTER_FAMILIES
from plugins.ds1.plugin import DS1Session
from plugins.ds1.store import RELATIVE


IDS = [120000, 223000, 224001, 264000, 527000, 529100, 532000, 502, 999999]
TYPES = {527000: 1, 529100: 2, 532000: 2, 264000: 2}
BOSSES = [223000, 224001, 527000, 532000]


def document():
    return ItemDocument(make_archive(
        table_ids={'NpcParam': IDS},
        field_values={'NpcParam': {row_id: {'npcType': npc_type}
                                   for row_id, npc_type in TYPES.items()}}))


def test_boss_families_and_monster_families_do_not_overlap():
    assert BOSS_FAMILIES and MONSTER_FAMILIES
    assert not (BOSS_FAMILIES & MONSTER_FAMILIES)


def test_bosses_subtab_lists_reviewed_bosses_only():
    doc = document()
    assert [row['id'] for row in doc.list_rows('bosses')] == BOSSES


def test_monsters_and_npcs_tabs_exclude_bosses():
    doc = document()
    assert [row['id'] for row in doc.list_rows('monsters')] == [120000]
    npcs = [row['id'] for row in doc.list_rows('npcs')]
    assert 532000 not in npcs
    assert 264000 in npcs


def test_boss_rows_open_and_edit_like_monsters():
    doc = document()
    for row_id in BOSSES:
        assert doc.read_row('NpcParam', row_id)['fields']
        doc.edit('NpcParam', row_id, 'hp', 500)
        assert doc.value('NpcParam', row_id, 'hp') == 500
    assert doc.attack_references().list(527000)['rows'] == []


def test_tails_test_rows_and_unknown_ids_stay_shut():
    doc = document()
    assert not doc.is_boss(529100)
    assert not doc.is_boss(502)
    assert not doc.is_boss(999999)
    for excluded in (502, 999999):
        with pytest.raises(FormatError, match='not a reviewed'):
            doc.read_row('NpcParam', excluded)
        with pytest.raises(FormatError, match='not a reviewed'):
            doc.edit('NpcParam', excluded, 'hp', 500)


def test_duplicated_boss_stays_a_boss():
    doc = document()
    row = doc.add_row('NpcParam', 527000)
    assert row['name'] == f'Dragonslayer Ornstein ({row["id"]})'
    assert doc.is_boss(row['id'])
    assert row['id'] in [entry['id'] for entry in doc.list_rows('bosses')]


def test_enemy_tabs_list_monsters_then_bosses():
    from plugins.ds1.formats import ENEMY_SUBTABS
    assert [entry[0] for entry in ENEMY_SUBTABS] == ['monsters', 'bosses']


def request_json(session, path, payload=None):
    request = Request(session.url.rstrip("/") + path,
                      data=None if payload is None else json.dumps(payload).encode(),
                      headers={"Content-Type": "application/json"})
    with urlopen(request) as reply:
        return json.load(reply)


def test_service_lists_bosses_and_serves_boss_behaviors(tmp_path):
    game = tmp_path / "game"
    (game / RELATIVE).parent.mkdir(parents=True)
    (game / RELATIVE).write_bytes(make_archive(
        table_ids={"NpcParam": IDS},
        field_values={"NpcParam": {row_id: {"npcType": npc_type}
                                   for row_id, npc_type in TYPES.items()}}))
    session = DS1Session({"LEXEDITOR_DS1_ROOT": str(game), "LEXEDITOR_NO_MOD": "1"})
    try:
        session.start()
        rows = request_json(session, "/api/table?tab=bosses")["rows"]
        assert [row["id"] for row in rows] == BOSSES
        moves = request_json(session, "/api/behaviors?monster=527000")
        assert moves["variation"] == 527000 and "rows" in moves
        attacks = request_json(session, "/api/attacks?monster=527000")
        assert "rows" in attacks
        with pytest.raises(HTTPError):
            request_json(session, "/api/behaviors?monster=502")
    finally:
        session.stop()
