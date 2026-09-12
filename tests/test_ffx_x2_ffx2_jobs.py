from __future__ import annotations

import struct

import pytest

from games.ffx_x2 import ffx2_jobs


def _fixture(record_size: int = ffx2_jobs.RECORD_SIZE) -> bytes:
    header = bytearray(0x20)
    records = bytearray(record_size * 2)
    struct.pack_into("<IIII", header, 0x0C, 0, 1, record_size, len(records))
    for record_id in range(2):
        start = record_id * record_size
        if record_size >= ffx2_jobs.RECORD_SIZE:
            struct.pack_into("<HHHH", records, start, 0x10 + record_id, 0x20 + record_id,
                             0x30 + record_id, 0x40 + record_id)
            records[start + 0x0B] = 7 + record_id
            struct.pack_into("<H", records, start + 0x0C, 0x3000 + record_id)
            records[start + 0x0E:start + 0x3C] = bytes((0x80 + i + record_id) & 0xFF for i in range(0x2E))
            for slot in range(ffx2_jobs.ABILITY_COUNT):
                offset = start + ffx2_jobs.ABILITY_OFFSET + slot * 4
                struct.pack_into("<HH", records, offset, 0x4000 + slot + record_id,
                                 0x5000 + slot + record_id)
            records[start + 0x7C:start + record_size] = bytes(
                (0x30 + i + record_id) & 0xFF for i in range(record_size - 0x7C)
            )
    return bytes(header + records + b"opaque-job-strings")


def test_job_payload_exposes_only_proved_tree_metadata():
    data = _fixture()
    payload = ffx2_jobs.payload(data)

    assert payload["minIndex"] == 0
    assert payload["maxIndex"] == 1
    assert payload["recordSize"] == 0xE4
    assert payload["abilityCount"] == 16
    assert payload["abilityOffset"] == 0x3C
    assert len(payload["rows"]) == 2
    row = payload["rows"][1]
    assert row["nameOffset"] == 0x11
    assert row["nameKey"] == 0x21
    assert row["icon"] == 8
    assert row["berserkAction"] == 0x3001
    assert row["abilities"][0] == {"requirementId": 0x4001, "abilityId": 0x5001}
    assert row["abilities"][15] == {"requirementId": 0x4010, "abilityId": 0x5010}
    assert "growth" not in row
    assert "weapons" not in row
    assert "creature" not in row


def test_job_edit_changes_only_selected_requirement_and_ability_pair():
    before = _fixture()
    after = ffx2_jobs.apply_edits(before, [{
        "id": 1,
        "abilities": [{"slot": 3, "requirementId": 0x1234, "abilityId": 0xABCD}],
    }])

    record = 0x20 + ffx2_jobs.RECORD_SIZE
    changed = {index for index, (left, right) in enumerate(zip(before, after)) if left != right}
    expected = set(range(
        record + ffx2_jobs.ABILITY_OFFSET + 3 * 4,
        record + ffx2_jobs.ABILITY_OFFSET + 3 * 4 + 4,
    ))
    assert changed <= expected
    assert changed
    assert after[:record + ffx2_jobs.ABILITY_OFFSET] == before[:record + ffx2_jobs.ABILITY_OFFSET]
    assert after[record + 0x7C:] == before[record + 0x7C:]
    row = ffx2_jobs.parse_jobs(after)[1]
    assert row.abilities[3].requirement_id == 0x1234
    assert row.abilities[3].ability_id == 0xABCD


def test_job_edit_can_change_multiple_slots_without_touching_opaque_data():
    before = _fixture()
    after = ffx2_jobs.apply_edits(before, [{
        "id": 0,
        "abilities": [
            {"slot": 0, "requirementId": 0, "abilityId": 0x2222},
            {"slot": 15, "requirementId": 0x3333, "abilityId": 0x4444},
        ],
    }])
    record_end = 0x20 + ffx2_jobs.RECORD_SIZE
    assert after[0x20 + 0x0E:0x20 + 0x3C] == before[0x20 + 0x0E:0x20 + 0x3C]
    assert after[0x20 + 0x7C:record_end] == before[0x20 + 0x7C:record_end]
    assert after[0x20 + ffx2_jobs.RECORD_SIZE:] == before[0x20 + ffx2_jobs.RECORD_SIZE:]


@pytest.mark.parametrize("edit,match", [
    ({"id": 0, "abilities": [{"slot": 16, "requirementId": 1, "abilityId": 2}]}, "slot"),
    ({"id": 0, "abilities": [{"slot": 0, "requirementId": -1, "abilityId": 2}]}, "Required"),
    ({"id": 0, "abilities": [{"slot": 0, "requirementId": 1, "abilityId": 65536}]}, "Ability ID"),
    ({"id": 0, "abilities": []}, "at least one"),
    ({"id": 0, "abilities": [{"slot": 0, "requirementId": 1, "abilityId": 2}], "price": 3}, "only id"),
])
def test_job_edits_fail_closed(edit, match):
    with pytest.raises(ffx2_jobs.FFX2JobError, match=match):
        ffx2_jobs.apply_edits(_fixture(), [edit])


def test_job_edits_reject_duplicate_records_and_slots():
    with pytest.raises(ffx2_jobs.FFX2JobError, match="Duplicate dressphere edit"):
        ffx2_jobs.apply_edits(_fixture(), [
            {"id": 0, "abilities": [{"slot": 0, "requirementId": 1, "abilityId": 2}]},
            {"id": 0, "abilities": [{"slot": 1, "requirementId": 3, "abilityId": 4}]},
        ])
    with pytest.raises(ffx2_jobs.FFX2JobError, match="Duplicate ability slot"):
        ffx2_jobs.apply_edits(_fixture(), [{
            "id": 0,
            "abilities": [
                {"slot": 2, "requirementId": 1, "abilityId": 2},
                {"slot": 2, "requirementId": 3, "abilityId": 4},
            ],
        }])


def test_job_parser_rejects_wrong_record_size():
    with pytest.raises(ffx2_jobs.FFX2JobError, match="0xE4-byte"):
        ffx2_jobs.payload(_fixture(0xE0))
