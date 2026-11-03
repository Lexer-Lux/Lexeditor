from pathlib import Path

import pytest

import test_chrono_trigger_replacement as fixtures
from plugins.chrono_trigger.scene_data import load_scenes, save_scene


def test_scene_integer_edits_reject_truncation_and_preserve_archive(tmp_path: Path):
    archive, store = fixtures.FreshChronoTriggerTests().fixture(tmp_path)
    original = archive.read_bytes()
    row = load_scenes(store)["rows"][0]
    target = store.project_root / row["path"]
    for value in (1.5, True, float("nan"), float("inf"), "1.5", -1, 65536):
        with pytest.raises(ValueError):
            save_scene(store, row["id"], row["sha256"], {"musicIndex": value})
        assert not target.exists()
        assert archive.read_bytes() == original

    saved = save_scene(store, row["id"], row["sha256"], {"musicIndex": 65535.0})
    assert saved["musicIndex"] == 65535
    assert load_scenes(store)["rows"][0]["musicIndex"] == 65535
    data = target.read_bytes()
    assert data[2:] == store.read(row["path"], "vanilla")[0][2:]
    for value in (2.5, False):
        with pytest.raises(ValueError):
            save_scene(store, row["id"], saved["sha256"], {"musicIndex": value})
        assert target.read_bytes() == data
