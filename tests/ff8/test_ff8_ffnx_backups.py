"""FFNx installs keep the original and latest backups, not every one."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from plugins.ff8.ffnx_manager import prune_backups  # noqa: E402


def _make(root, name):
    folder = root / name
    folder.mkdir(parents=True)
    (folder / "AF3DN.P").write_bytes(b"x")
    return folder


def test_prune_keeps_original_newest_and_state_backup(tmp_path):
    names = [f"202608{day:02d}-120000" for day in range(1, 11)]
    for name in names:
        _make(tmp_path, name)
    manual = _make(tmp_path, "install-before-experiment")
    referenced = tmp_path / names[4]
    removed = prune_backups(tmp_path, keep=referenced)
    left = sorted(p.name for p in tmp_path.iterdir())
    assert left == sorted([names[0], names[4], names[-1], manual.name]), left
    assert len(removed) == 7


def test_prune_is_a_no_op_without_backups(tmp_path):
    assert prune_backups(tmp_path / "missing") == []
    _make(tmp_path, "20260801-120000")
    assert prune_backups(tmp_path) == []
    assert (tmp_path / "20260801-120000").is_dir()
