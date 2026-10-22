"""Map geometry survives between sessions in a bounded disk cache.

Parsing FLVER and decoding textures costs seconds per map, so textured
geometry is cached on disk: one geometry file per model plus
content-addressed PNGs shared across models and maps. Entries are
keyed by file stamp (a rebuilt mod recomputes), the cache is capped
in size with oldest-first eviction, and a corrupt entry recomputes
instead of failing the map.
"""
import base64
import io
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from flver_fixture import build_flver
from msb_fixture import build_msb
from tpf_fixture import make_dds_rgba, make_tpf
from plugins.ds1.map_store import MapStore
from plugins.ds1.msb import MAP_DIR
from plugins.ds1 import viewport

MAP = "test.msb"


def setup(tmp_path, models=(("m10piece", 0),)):
    game = tmp_path / "game"
    (game / MAP_DIR).mkdir(parents=True, exist_ok=True)
    parts = tuple(("piece", 0, index, min(index, len(models) - 1), None)
                  for index in range(len(models)))
    (game / MAP_DIR / MAP).write_bytes(build_msb(parts=parts, models=models))
    folder = game / "map" / "test"
    folder.mkdir(parents=True, exist_ok=True)
    for name, _mtype in models:
        stem = "tex_" + name
        (folder / (name + ".flver")).write_bytes(build_flver(tex_name=stem))
        red = make_dds_rgba(4, 4, [(255, 0, 0, 255)] * 16)
        (folder / (name + ".tpf")).write_bytes(make_tpf([(stem, red)]))
    return MapStore(game, None, True)


def isolate(tmp_path, monkeypatch):
    """A private disk cache, with the module's incremental totals reset."""
    monkeypatch.setenv(viewport.MAP_CACHE_ENV, str(tmp_path / "cache"))
    monkeypatch.setattr(viewport, "_disk_size", None)
    monkeypatch.setattr(viewport, "_pruned", False)
    viewport._cached_map.cache_clear()
    return tmp_path / "cache"


def geometry(store, name="m10piece"):
    model = next(entry for entry in store.get(MAP).models if entry["name"] == name)
    return viewport.model_geometry(store.game_root, None, MAP, model)


def test_disk_cache_serves_repeat_geometry(tmp_path, monkeypatch):
    cache = isolate(tmp_path, monkeypatch)
    store = setup(tmp_path)
    first = geometry(store)
    assert first["textures"], "the textured fixture must serve a PNG"
    assert sorted(path.suffix for path in cache.rglob("*") if path.is_file())
    viewport._cached_map.cache_clear()
    calls = []
    real_doc, real_read = viewport.FlverDocument, viewport._read_flver
    monkeypatch.setattr(viewport, "FlverDocument", lambda raw: calls.append(1) or real_doc(raw))
    monkeypatch.setattr(viewport, "_read_flver", lambda *args: calls.append(1) or real_read(*args))
    second = geometry(store)
    assert second == first
    assert not calls, "a disk hit must not re-read or re-parse the model"
    from PIL import Image
    png = base64.b64decode(second["textures"]["tex_m10piece"])
    with Image.open(io.BytesIO(png)) as image:
        assert image.getpixel((0, 0))[:3] == (255, 0, 0)


def test_disk_cache_miss_after_rebuild(tmp_path, monkeypatch):
    isolate(tmp_path, monkeypatch)
    store = setup(tmp_path)
    first = geometry(store)
    (tmp_path / "game" / "map" / "test" / "m10piece.flver").write_bytes(
        build_flver(tex_name="tex_m10piece", mesh_count=0))
    viewport._cached_map.cache_clear()
    calls = []
    real = viewport.FlverDocument
    monkeypatch.setattr(viewport, "FlverDocument", lambda raw: calls.append(1) or real(raw))
    second = geometry(store)
    assert calls, "a changed model file must recompute"
    assert second["meshes"] == [] and first["meshes"] != []


def test_disk_cache_evicts_oldest_under_cap(tmp_path, monkeypatch):
    cache = isolate(tmp_path, monkeypatch)
    monkeypatch.setattr(viewport, "_disk_cap", lambda: 2000)
    old = {"meshes": [{"blob": "x" * 1000}], "notes": [], "textures": {"t": b"y" * 500}}
    new = {"meshes": [{"blob": "z" * 1000}], "notes": [], "textures": {"t": b"w" * 500}}
    viewport._disk_write("a" * 32, old)
    for path in cache.rglob("*"):
        if path.is_file():
            stat = path.stat()
            os.utime(path, (stat.st_atime - 60, stat.st_mtime - 60))
    # The second entry pushes the tiny cache over its cap; the aged
    # entry's files go first while the newest survives.
    viewport._disk_write("b" * 32, new)
    left = sorted(path.name for path in cache.rglob("geom/*.json"))
    assert left == ["b" * 32 + ".json"]
    assert viewport._disk_read("b" * 32) == new
    assert viewport._disk_read("a" * 32) is None


def test_disk_cache_corruption_recomputes(tmp_path, monkeypatch):
    isolate(tmp_path, monkeypatch)
    store = setup(tmp_path)
    first = geometry(store)
    for path in (tmp_path / "cache").rglob("*.json"):
        path.write_bytes(b"{not json")
    viewport._cached_map.cache_clear()
    calls = []
    real = viewport.FlverDocument
    monkeypatch.setattr(viewport, "FlverDocument", lambda raw: calls.append(1) or real(raw))
    assert geometry(store) == first
    assert calls, "a corrupt entry must recompute"


def test_disk_cache_off_disables_writes(tmp_path, monkeypatch):
    monkeypatch.setenv(viewport.MAP_CACHE_ENV, "off")
    monkeypatch.setattr(viewport, "_disk_size", None)
    monkeypatch.setattr(viewport, "_pruned", False)
    viewport._cached_map.cache_clear()
    store = setup(tmp_path)
    assert geometry(store)["textures"]
    assert not (tmp_path / "cache").exists()


def test_pipeline_digest_covers_geometry_readers():
    # Every reader that shapes cached geometry must feed the
    # pipeline digest: a fix in any of them (like the lightmap-UV
    # fix in flver.py) moves the cache directory, so entries
    # written by the old readers are recomputed, never served.
    assert {'viewport.py', 'flver.py', 'assets.py', 'bhf.py',
            'formats.py'} <= set(viewport._PIPELINE_FILES)
    for leaf in viewport._PIPELINE_FILES:
        assert (Path(viewport.__file__).parent / leaf).is_file()


def test_reader_change_orphans_old_cache(tmp_path, monkeypatch):
    cache = isolate(tmp_path, monkeypatch)
    store = setup(tmp_path)
    first = geometry(store)
    assert first['meshes']
    old_dirs = [path for path in cache.iterdir() if path.is_dir()]
    assert len(old_dirs) == 1
    # A reader change moves the digest; the old directory's
    # entries are never read again, and are pruned away.
    monkeypatch.setattr(viewport, '_pipeline_digest', '0' * 16)
    monkeypatch.setattr(viewport, '_pruned', False)
    monkeypatch.setattr(viewport, '_disk_size', None)
    viewport._cached_map.cache_clear()
    calls = []
    real = viewport.FlverDocument
    monkeypatch.setattr(viewport, 'FlverDocument', lambda raw: calls.append(1) or real(raw))
    assert geometry(store) == first
    assert calls, 'a reader change must recompute cached geometry'
    assert [path for path in cache.iterdir() if path.is_dir()] != old_dirs
