"""Up-front Hext memory overlaps on the FF8 Mods tab.

Two mods patching the same address still load in order, but the earlier
mod's bytes never take effect. The adapter marks both sides statically,
following the core/memory_conflicts.py pattern the DS1 loader uses.
"""
import json
import struct

from plugins.ff8 import iroj_archive, mod_support, paths, runtime_layout


def _mod(root, mod_id, order, patches=None, native=False, broken=False):
    folder = root / mod_id
    folder.mkdir(parents=True)
    (folder / "mod.json").write_text(json.dumps({
        "id": mod_id, "name": mod_id.title(), "order": order, "enabled": True,
    }), encoding="utf-8")
    for name, text in (patches or {}).items():
        target = folder / "hext" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    if native:
        (folder / "driver.dll").write_bytes(b"MZ")
    if broken:
        target = folder / "hext" / "broken.txt"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"\xff\xfe\x00invalid")
    return folder


def _project(root):
    root.mkdir(parents=True)
    (root / "mod.json").write_text(json.dumps({
        "id": "project", "name": "Project", "order": -1, "enabled": True,
    }), encoding="utf-8")
    return root


def _adapter(project, library, runtime, monkeypatch):
    monkeypatch.setattr(paths, "RUNTIME_ROOT", runtime)
    adapter = mod_support.Ff8ModAdapter()
    adapter.attach_context(project_root=project, library_root=library)
    return adapter


def _archive(path, members):
    encoded = []
    for name, plain in members:
        encoded_name = name.encode("utf-16-le")
        encoded.append((encoded_name, plain))
    records, payload, offset = [], bytearray(), 0
    header_size = 16 + 4 + sum(20 + len(name) for name, _ in encoded)
    offset = header_size
    for encoded_name, plain in encoded:
        record_size = 20 + len(encoded_name)
        records.append(struct.pack("<HH", record_size, len(encoded_name)) + encoded_name
                       + struct.pack("<IqI", 0, offset, len(plain)))
        payload.extend(plain)
        offset += len(plain)
    path.write_bytes(
        struct.pack("<IIIIi", iroj_archive.SIGNATURE, 0x10002, 0, 16, len(records))
        + b"".join(records) + bytes(payload))


def test_overlap_marks_both_sides_last_wins(tmp_path, monkeypatch):
    project = _project(tmp_path / "project")
    library = tmp_path / "mods"
    alpha = _mod(library, "alpha", 0, {"a.txt": "4B1000 = AA BB\n"})
    beta = _mod(library, "beta", 1, {"b.txt": "4B1001 = CC\n"})
    adapter = _adapter(project, library, tmp_path / "runtime", monkeypatch)
    marks = adapter.conflicts([alpha, beta], tmp_path)
    assert marks[str(alpha.resolve())] == [
        "memory 4B1001: Beta changes this too and loads later, "
        "so this mod's change is not used"]
    assert marks[str(beta.resolve())] == ["memory 4B1001: overrides Alpha"]


def test_disjoint_patches_mark_nothing(tmp_path, monkeypatch):
    project = _project(tmp_path / "project")
    library = tmp_path / "mods"
    alpha = _mod(library, "alpha", 0, {"a.txt": "4B1000 = AA\n"})
    beta = _mod(library, "beta", 1, {"b.txt": "4B2000 = BB\n"})
    adapter = _adapter(project, library, tmp_path / "runtime", monkeypatch)
    assert adapter.conflicts([alpha, beta], tmp_path) == {}


def test_native_carrying_mod_is_skipped(tmp_path, monkeypatch):
    project = _project(tmp_path / "project")
    library = tmp_path / "mods"
    alpha = _mod(library, "alpha", 0, {"a.txt": "4B1000 = AA BB\n"})
    beta = _mod(library, "beta", 1, {"b.txt": "4B1001 = CC\n"}, native=True)
    adapter = _adapter(project, library, tmp_path / "runtime", monkeypatch)
    assert adapter.conflicts([alpha, beta], tmp_path) == {}


def test_unreadable_patch_is_left_for_enable_time(tmp_path, monkeypatch):
    project = _project(tmp_path / "project")
    library = tmp_path / "mods"
    alpha = _mod(library, "alpha", 0, {"a.txt": "4B1000 = AA BB\n"})
    beta = _mod(library, "beta", 1, {"b.txt": "4B1001 = CC\n"}, broken=True)
    adapter = _adapter(project, library, tmp_path / "runtime", monkeypatch)
    assert adapter.conflicts([alpha, beta], tmp_path) == {}


def test_non_txt_files_under_hext_do_not_count(tmp_path, monkeypatch):
    project = _project(tmp_path / "project")
    library = tmp_path / "mods"
    alpha = _mod(library, "alpha", 0, {"a.txt": "4B1000 = AA BB\n"})
    beta = _mod(library, "beta", 1, {"notes.bak": "4B1001 = CC\n"})
    adapter = _adapter(project, library, tmp_path / "runtime", monkeypatch)
    assert adapter.conflicts([alpha, beta], tmp_path) == {}


def test_packed_mod_patches_count(tmp_path, monkeypatch):
    project = _project(tmp_path / "project")
    library = tmp_path / "mods"
    library.mkdir(parents=True)
    alpha = _mod(library, "alpha", 0, {"a.txt": "4B1000 = AA BB\n"})
    archive = library / "packed.iroj"
    _archive(archive, [("hext/packed.txt", b"4B1001 = CC\n")])
    adapter = _adapter(project, library, tmp_path / "runtime", monkeypatch)
    marks = adapter.conflicts([alpha, archive], tmp_path)
    assert marks[str(alpha.resolve())] == [
        "memory 4B1001: packed changes this too and loads later, "
        "so this mod's change is not used"]
    assert marks[str(archive.resolve())] == ["memory 4B1001: overrides Alpha"]


def test_file_and_memory_marks_merge(tmp_path, monkeypatch):
    project = _project(tmp_path / "project")
    library = tmp_path / "mods"
    alpha = _mod(library, "alpha", 0, {"a.txt": "4B1000 = AA BB\n"})
    beta = _mod(library, "beta", 1, {"b.txt": "4B1001 = CC\n"})
    runtime = tmp_path / "runtime"
    runtime.mkdir(parents=True)
    (runtime / runtime_layout.COMPOSITION_FILE).write_text(json.dumps({
        "conflicts": [{"path": "direct/shared.bin", "winner": "beta",
                       "claimants": ["alpha", "beta"],
                       "warning": "Only beta's direct/shared.bin is used"}],
    }), encoding="utf-8")
    adapter = _adapter(project, library, runtime, monkeypatch)
    marks = adapter.conflicts([alpha, beta], tmp_path)
    assert marks[str(alpha.resolve())] == [
        "direct/shared.bin: Beta changes this too and loads later, "
        "so this mod's change is not used",
        "memory 4B1001: Beta changes this too and loads later, "
        "so this mod's change is not used"]
    assert marks[str(beta.resolve())] == [
        "direct/shared.bin: overrides Alpha",
        "memory 4B1001: overrides Alpha"]
