"""G2: cover art fails closed to missing instead of hanging in "loading"."""
from pathlib import Path
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import discover_plugins  # noqa: E402
from cover_art import CoverArtCache  # noqa: E402


def _downloading_plugins():
    plugins = discover_plugins()
    chosen = {pid: p for pid, p in plugins.items() if p.cover_art is None and p.installation is not None}
    assert chosen, "no plugin downloads its cover; pick a fixture"
    return dict(list(chosen.items())[:1])


def test_hung_download_reports_missing_after_deadline(tmp_path):
    release = threading.Event()

    def hang(_url):
        release.wait(30)
        raise OSError("released")

    plugins = _downloading_plugins()
    plugin_id = next(iter(plugins))
    cache = CoverArtCache(plugins, root=tmp_path, fetcher=hang, steam_roots=(), loading_deadline=0.2)
    try:
        assert cache.snapshot(plugin_id)["state"] == "loading"
        time.sleep(0.3)
        state = cache.snapshot(plugin_id)
        assert state["state"] == "missing" and "timed out" in state["error"], state
    finally:
        release.set()
        cache.wait(5)


def test_corrupt_local_steam_capsule_does_not_break_construction(tmp_path):
    plugins = _downloading_plugins()
    plugin_id, plugin = next(iter(plugins.items()))
    spec = plugin.installation
    app_id = spec.art_app_id or spec.steam_app_id
    capsule = tmp_path / "steam" / "appcache" / "librarycache" / str(app_id) / "hash" / "library_capsule.jpg"
    capsule.parent.mkdir(parents=True)
    capsule.write_bytes(b"not a jpeg")
    cache = CoverArtCache(plugins, root=tmp_path / "cache", fetcher=lambda _url: (_ for _ in ()).throw(OSError("offline")),
                          steam_roots=(tmp_path / "steam",))
    assert cache.wait(5)
    assert cache.snapshot(plugin_id)["state"] == "missing"
