"""Shots per ATB is editable on Irvine's guns only.

todo: "weapons: shots per atb should be read-only if it's not an irvine gun."
The byte drives Irvine's Shot command; on anyone else's weapon the page shows
it read-only and the writer refuses to change it.
"""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plugins.ff8 import formats, paths  # noqa: E402

VANILLA = paths.BASELINE_ROOT / "main" / "kernel.bin"
pytestmark = pytest.mark.skipif(not VANILLA.is_file(), reason="needs the extracted FF8 baseline")


def owners():
    rows = formats.kernel_rows(5, "vanilla")["rows"]
    return {row["id"]: {field["field"]: field for field in row["fields"]} for row in rows}


def test_only_irvines_guns_offer_shots_per_atb():
    for weapon, fields in owners().items():
        irvine = fields["character_id"]["value"] == formats.IRVINE_CHARACTER_ID
        assert fields["shots_per_atb"]["readonly"] is (not irvine), weapon


def test_the_writer_refuses_shots_on_another_characters_weapon(tmp_path, monkeypatch):
    kernel = tmp_path / "kernel.bin"
    kernel.write_bytes(VANILLA.read_bytes())
    monkeypatch.setattr(formats, "source_path", lambda name, dataset="current": kernel)
    monkeypatch.setattr(formats, "output_path", lambda name: tmp_path / "out.bin")
    by_owner = owners()
    squall = next(weapon for weapon, fields in by_owner.items() if fields["character_id"]["value"] == 0)
    irvine = next(weapon for weapon, fields in by_owner.items()
                  if fields["character_id"]["value"] == formats.IRVINE_CHARACTER_ID)
    with pytest.raises(ValueError, match="Irvine"):
        formats.save_kernel(5, [{"id": squall, "field": "shots_per_atb", "value": 3}])
    assert formats.save_kernel(5, [{"id": irvine, "field": "shots_per_atb", "value": 3}])["saved"] == 1
