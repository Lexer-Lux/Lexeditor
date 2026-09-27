"""A mod copy of an enemy file changes its model only when a model section differs.

Lexer, 2026-09-27: Griever, Abadon and Anacondaur read as replaced models in
a mod that only edits their stats. The stats and AI sections live in the same
battle file, so only the model sections decide.
"""
import struct

from plugins.ff8 import assets


def _dat(sections):
    count = len(sections)
    header = 4 + (count + 1) * 4
    offsets, at = [], header
    for body in sections:
        offsets.append(at)
        at += len(body)
    offsets.append(at)
    return struct.pack(f"<I{count + 1}I", count, *offsets) + b"".join(sections)


def _sections(stats=b"stats", geometry=b"mesh"):
    parts = [b"skel", geometry, b"anim", b"dyn", b"seq", b"cam", stats, b"ai", b"snd", b"bank", b"tex"]
    return parts


def _digest(tmp_path, name, data):
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    stat = path.stat()
    return assets._model_parts_digest(str(path), stat.st_size, stat.st_mtime_ns)


def test_a_stats_edit_is_not_a_changed_model(tmp_path):
    shipped = _digest(tmp_path / "a", "c0m001.dat", _dat(_sections()))
    stats_only = _digest(tmp_path / "b", "c0m001.dat", _dat(_sections(stats=b"STATS EDITED")))
    assert shipped == stats_only


def test_a_new_mesh_is_a_changed_model(tmp_path):
    shipped = _digest(tmp_path / "a", "c0m001.dat", _dat(_sections()))
    remeshed = _digest(tmp_path / "b", "c0m001.dat", _dat(_sections(geometry=b"new mesh")))
    assert shipped != remeshed
