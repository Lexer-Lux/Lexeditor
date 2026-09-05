"""Verify Deling-proved FF8 field encounter MRT/RAT codecs."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8 import field_data, field_encounters  # noqa: E402
from games.ff8.fs_archive import FsArchive  # noqa: E402


def reject(action, phrase: str) -> None:
    try:
        action()
    except ValueError as error:
        assert phrase.casefold() in str(error).casefold(), error
    else:
        raise AssertionError(f"Expected error containing {phrase!r}")


def corpus() -> dict:
    archive = FsArchive(field_data._prefix())
    groups = field_data._outer_groups(archive)
    mrt_count = rat_count = noncanonical_rat = 0
    formations = 0
    sample_mrt = sample_rat = None
    for key, group in groups.items():
        nested = archive.extract(group["entries"][".fs"])
        entries = field_data._memory_entries(
            archive.extract(group["entries"][".fi"]),
            archive.extract(group["entries"][".fl"]),
        )
        for entry in entries:
            name = entry["basename"].casefold()
            if not name.endswith((".mrt", ".rat")):
                continue
            raw = field_data._memory_extract(nested, entries, entry["basename"])
            if name.endswith(".mrt"):
                parsed = field_encounters.read_mrt(raw)
                assert field_encounters.apply_mrt_edits(raw, [])[0] == raw
                mrt_count += 1
                formations += len(parsed["formations"])
                sample_mrt = sample_mrt or (key, raw)
            else:
                parsed = field_encounters.read_rat(raw)
                rat_count += 1
                noncanonical_rat += not parsed["canonical"]
                sample_rat = sample_rat or (key, raw)
    assert mrt_count and rat_count and sample_mrt and sample_rat
    return {
        "mrt": mrt_count,
        "rat": rat_count,
        "formations": formations,
        "noncanonicalRat": noncanonical_rat,
        "sampleMrt": sample_mrt,
        "sampleRat": sample_rat,
    }


def mutations(result: dict) -> dict:
    mrt_key, mrt = result["sampleMrt"]
    values = field_encounters.read_mrt(mrt)["formations"]
    replacement = values[0] + 1 if values[0] < 0xFFFF else values[0] - 1
    changed_mrt, count = field_encounters.apply_mrt_edits(
        mrt, [{"slot": 0, "formation": replacement}])
    assert count == 1 and changed_mrt[2:] == mrt[2:]
    assert field_encounters.read_mrt(changed_mrt)["formations"][0] == replacement

    rat_key, rat = result["sampleRat"]
    rate = field_encounters.read_rat(rat)["rate"]
    replacement_rate = (rate + 1) & 0xFF
    changed_rat, count = field_encounters.apply_rat_edit(rat, replacement_rate)
    assert count == 1 and changed_rat == bytes((replacement_rate,)) * 4

    second = values[1] + 1 if values[1] < 0xFFFF else values[1] - 1
    mod_a = field_encounters.apply_mrt_edits(
        mrt, [{"slot": 0, "formation": replacement}])[0]
    mod_b = field_encounters.apply_mrt_edits(
        mrt, [{"slot": 1, "formation": second}])[0]
    merged, conflicts, reason = field_encounters.merge_mrt(
        mrt, [("A", mod_a), ("B", mod_b)], f"{mrt_key}.mrt")
    assert merged is not None and not conflicts and not reason
    assert field_encounters.read_mrt(merged)["formations"][:2] == [replacement, second]
    collision = field_encounters.apply_mrt_edits(
        mrt, [{"slot": 0, "formation": (replacement + 1) & 0xFFFF}])[0]
    merged, conflicts, reason = field_encounters.merge_mrt(
        mrt, [("A", mod_a), ("B", collision)], f"{mrt_key}.mrt")
    assert merged is not None and len(conflicts) == 1 and not reason
    assert conflicts[0]["winner"] == "B"

    rat_a = field_encounters.apply_rat_edit(rat, replacement_rate)[0]
    rat_b_value = (replacement_rate + 1) & 0xFF
    rat_b = field_encounters.apply_rat_edit(rat, rat_b_value)[0]
    merged_rat, conflicts, reason = field_encounters.merge_rat(
        rat, [("A", rat_a), ("B", rat_b)], f"{rat_key}.rat")
    assert merged_rat == bytes((rat_b_value,)) * 4 and len(conflicts) == 1 and not reason

    reject(lambda: field_encounters.read_mrt(b"\0" * 7), "exactly")
    reject(lambda: field_encounters.read_rat(b"\0" * 3), "exactly")
    reject(lambda: field_encounters.apply_mrt_edits(
        mrt, [{"slot": 4, "formation": 0}]), "invalid")
    reject(lambda: field_encounters.apply_rat_edit(rat, 256), "unsigned")
    unsupported, _, reason = field_encounters.merge_rat(
        rat, [("bad", bytes((1, 2, 1, 1)))], f"{rat_key}.rat")
    assert unsupported is None and "outside" in reason
    return {"mrtSample": mrt_key, "ratSample": rat_key,
            "semanticMerge": True, "rejections": 5}


def main() -> int:
    scanned = corpus()
    checked = mutations(scanned)
    printable = {key: value for key, value in scanned.items()
                 if not key.startswith("sample")}
    print({"corpus": printable, "mutation": checked})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
