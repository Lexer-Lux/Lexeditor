import pytest

import test_ffx_x2_ffx2_jobs as fixtures
from plugins.ffx_x2 import ffx2_jobs


def test_job_pairs_reject_fractional_ids_and_preserve_other_bytes(tmp_path):
    source = tmp_path / "jobs.bin"
    original = fixtures._fixture()
    source.write_bytes(original)
    for field in ("slot", "requirementId", "abilityId"):
        for value in (1.5, True, float("nan"), float("inf"), "1.5"):
            pair = {"slot": 0, "requirementId": 10, "abilityId": 20, field: value}
            with pytest.raises(ffx2_jobs.FFX2JobError):
                ffx2_jobs.apply_edits(source.read_bytes(), [{"id": 0, "abilities": [pair]}])
            assert source.read_bytes() == original

    edited = ffx2_jobs.apply_edits(original, [{"id": 0, "abilities": [{
        "slot": 0, "requirementId": 0.0, "abilityId": "65535",
    }]}])
    source.write_bytes(edited)
    pair = ffx2_jobs.payload(source.read_bytes())["rows"][0]["abilities"][0]
    assert pair == {"requirementId": 0, "abilityId": 65535}
    offset = 0x20 + ffx2_jobs.ABILITY_OFFSET
    assert edited[:offset] == original[:offset]
    assert edited[offset + 4:] == original[offset + 4:]
