"""RDR cache rebuilds do not leave old copies behind."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from plugins.rdr.extractor import remove_previous_caches  # noqa: E402


def test_previous_caches_are_removed_and_live_caches_kept(tmp_path):
    for name in ("tune_d11generic", "content"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "keep.xml").write_text("x")
        for stamp in ("20260830T234942Z-8dbd9726", "20260916T115620Z-a64c5c35"):
            old = tmp_path / f"{name}.previous-{stamp}"
            old.mkdir()
            (old / "old.xml").write_text("x")
    (tmp_path / "manifest.json").write_text("{}")
    assert remove_previous_caches(tmp_path) == 4
    assert sorted(p.name for p in tmp_path.iterdir()) == ["content", "manifest.json", "tune_d11generic"]
