"""Warband model previews stay under their cache limit."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from plugins.warband.model_preview import trim_cache  # noqa: E402


def test_trim_removes_least_recently_used_and_keeps_protected(tmp_path):
    (tmp_path / "textures").mkdir()
    (tmp_path / "item-icons").mkdir()
    icon = tmp_path / "item-icons" / "icon.png"
    icon.write_bytes(b"i" * 5000)
    files = []
    for i in range(6):
        f = tmp_path / f"{i:064x}.json"
        f.write_bytes(b"x" * 1000)
        os.utime(f, (1_000_000 + i, 1_000_000 + i))
        files.append(f)
    newest_protected = files[0]
    removed = trim_cache(tmp_path, limit=3000, protected=(newest_protected,))
    left = sorted(p.name for p in tmp_path.glob("*.json"))
    assert removed == 3
    assert left == sorted([files[0].name, files[4].name, files[5].name])
    assert icon.is_file()
