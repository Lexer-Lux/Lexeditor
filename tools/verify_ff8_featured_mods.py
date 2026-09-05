"""Verify featured FF8 release discovery, safe install, update, delete, and API."""

from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import struct
import sys
import tempfile
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8 import featured_mods, iroj_archive, paths, runtime_layout, server  # noqa: E402


def archive_bytes(mod_id: str, name: str, payload: bytes) -> bytes:
    members = [
        ("mod.xml", f"<ModInfo><ID>{mod_id}</ID><Name>{name}</Name></ModInfo>".encode()),
        ("direct/test.bin", payload),
    ]
    directory_size = 4 + sum(20 + len(member.encode("utf-16-le")) for member, _ in members)
    offset = 16 + directory_size
    records = []
    data = bytearray()
    for member, value in members:
        encoded = member.encode("utf-16-le")
        records.append(struct.pack("<HH", 20 + len(encoded), len(encoded)) + encoded
                       + struct.pack("<IqI", 0, offset, len(value)))
        data.extend(value)
        offset += len(value)
    return struct.pack("<IIIIi", iroj_archive.SIGNATURE, 0x10002, 0, 16, len(records)) \
        + b"".join(records) + data


def source_catalog(path: Path) -> None:
    path.write_text(json.dumps([{
        "id": "featured-test", "name": "Featured Test", "featured": True,
        "source": {
            "repository": "https://github.com/Example/FeaturedTest",
            "releaseFeed": "https://api.github.com/repos/Example/FeaturedTest/releases/latest",
            "assetPattern": "*.iroj",
        },
    }]), encoding="utf-8")


def release(payload: bytes, version: str = "v1", *, digest: bool = True,
            url: str = "https://github.com/Example/FeaturedTest/releases/download/v1/featured-test.iroj") -> dict:
    asset = {"name": "featured-test.iroj", "browser_download_url": url,
             "size": len(payload)}
    if digest:
        asset["digest"] = f"sha256:{sha256(payload).hexdigest()}"
    return {"id": 101, "tag_name": version, "html_url":
            f"https://github.com/Example/FeaturedTest/releases/tag/{version}",
            "draft": False, "prerelease": False, "assets": [asset]}


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="lexeditor-featured-mod-") as temp_name:
        root = Path(temp_name)
        project, mods, runtime = root / "project", root / "mods", root / "runtime"
        (project / "direct").mkdir(parents=True)
        (project / "mod.json").write_text(json.dumps({
            "id": "editable", "name": "Editable", "enabled": False, "order": 0,
        }), encoding="utf-8")
        catalog_path = root / "featured.json"
        source_catalog(catalog_path)
        first = archive_bytes("featured-test", "Featured Test", b"one")

        calls = []
        def fetch_json(url: str) -> dict:
            calls.append(url)
            return release(first)

        def fetch_file(url: str, destination: Path, size: int, digest: str) -> str:
            assert size == len(first) and digest == sha256(first).hexdigest()
            destination.write_bytes(first)
            return sha256(first).hexdigest()

        installed = featured_mods.install_latest(
            "featured-test", project, mods, catalog_path, fetch_json, fetch_file)
        assert installed["featured"] is True and installed["version"] == "v1"
        assert installed["source"]["repository"] == "https://github.com/Example/FeaturedTest"
        assert calls == ["https://api.github.com/repos/Example/FeaturedTest/releases/latest"]
        assert iroj_archive.Archive(Path(installed["path"])).read("direct/test.bin") == b"one"

        runtime_layout.configure(
            project, mods, ["editable", "featured-test"],
            {"editable": False, "featured-test": True})
        second = archive_bytes("featured-test", "Featured Test", b"two")
        def fetch_second(_url: str) -> dict:
            return release(second, "v2")
        def download_second(_url: str, destination: Path, _size: int, _digest: str) -> str:
            destination.write_bytes(second)
            return sha256(second).hexdigest()
        updated = featured_mods.install_latest(
            "featured-test", project, mods, catalog_path, fetch_second, download_second)
        assert updated["enabled"] is True and updated["order"] == 1 and updated["version"] == "v2"
        assert iroj_archive.Archive(Path(updated["path"])).read("direct/test.bin") == b"two"

        # Force the final metadata swap to fail after the old archive has moved.
        # The old archive and its sidecar must both return intact.
        third = archive_bytes("featured-test", "Featured Test", b"three")
        old_archive = Path(updated["path"]).read_bytes()
        old_sidecar_path = Path(updated["path"]).with_name(
            Path(updated["path"]).name + runtime_layout.IROJ_STATE_SUFFIX)
        old_sidecar = old_sidecar_path.read_bytes()
        original_replace = Path.replace
        def fail_state_swap(self: Path, target: Path):
            if self.name.endswith(".json.tmp") and str(target).endswith(runtime_layout.IROJ_STATE_SUFFIX):
                raise OSError("simulated metadata swap failure")
            return original_replace(self, target)
        def fetch_third(_url: str) -> dict:
            return release(third, "v3")
        def download_third(_url: str, destination: Path, _size: int, _digest: str) -> str:
            destination.write_bytes(third)
            return sha256(third).hexdigest()
        try:
            Path.replace = fail_state_swap
            try:
                featured_mods.install_latest(
                    "featured-test", project, mods, catalog_path, fetch_third, download_third)
            except OSError as error:
                assert "simulated" in str(error)
            else:
                raise AssertionError("The simulated atomic replacement failure did not occur")
        finally:
            Path.replace = original_replace
        assert Path(updated["path"]).read_bytes() == old_archive
        assert old_sidecar_path.read_bytes() == old_sidecar

        old_bytes = Path(updated["path"]).read_bytes()
        wrong = archive_bytes("somebody-else", "Wrong", b"bad")
        def fetch_wrong(_url: str) -> dict:
            return release(wrong, "v3")
        def download_wrong(_url: str, destination: Path, _size: int, _digest: str) -> str:
            destination.write_bytes(wrong)
            return sha256(wrong).hexdigest()
        try:
            featured_mods.install_latest(
                "featured-test", project, mods, catalog_path, fetch_wrong, download_wrong)
        except RuntimeError as error:
            assert "identity" in str(error)
        else:
            raise AssertionError("A featured package with the wrong identity was installed")
        assert Path(updated["path"]).read_bytes() == old_bytes

        try:
            featured_mods.latest_release(
                featured_mods.catalog(catalog_path)[0], lambda _url: release(first, digest=False))
        except RuntimeError as error:
            assert "SHA-256" in str(error)
        else:
            raise AssertionError("An unsigned featured release was accepted")
        try:
            featured_mods.latest_release(
                featured_mods.catalog(catalog_path)[0],
                lambda _url: release(first, url="https://example.com/steal.iroj"))
        except ValueError as error:
            assert "host is not allowed" in str(error)
        else:
            raise AssertionError("An untrusted featured download host was accepted")

        bad_catalog = root / "bad-featured.json"
        bad_catalog.write_text(json.dumps([{
            "id": "bad", "name": "Bad", "featured": True,
            "source": "http://127.0.0.1/private",
        }]), encoding="utf-8")
        try:
            featured_mods.catalog(bad_catalog)
        except ValueError as error:
            assert "HTTPS" in str(error)
        else:
            raise AssertionError("An unsafe featured source URL was accepted")

        original_urlopen = featured_mods.urlopen
        try:
            featured_mods.urlopen = lambda *_args, **_kwargs: (_ for _ in ()).throw(
                HTTPError("url", 404, "Not Found", {}, BytesIO()))
            try:
                featured_mods._fetch_json(
                    "https://api.github.com/repos/Example/FeaturedTest/releases/latest")
            except RuntimeError as error:
                assert "private or have no published release" in str(error)
            else:
                raise AssertionError("A missing/private release did not give a clear error")
        finally:
            featured_mods.urlopen = original_urlopen

        unrelated = mods / "do-not-delete.txt"
        unrelated.write_text("keep", encoding="utf-8")
        removed = runtime_layout.delete_mod(project, mods, "featured-test")
        assert removed["id"] == "featured-test" and unrelated.read_text() == "keep"
        assert [row["id"] for row in runtime_layout.catalog(project, mods)] == ["editable"]
        empty = runtime_layout.compose(project, runtime, [])
        assert empty["fileCount"] == 0 and (runtime / runtime_layout.COMPOSITION_FILE).is_file()
        try:
            runtime_layout.delete_mod(project, mods, "editable")
        except ValueError as error:
            assert "selected editable" in str(error)
        else:
            raise AssertionError("The selected project could be deleted")

        # Exercise the public API with an isolated fake installer. The service
        # still performs its normal catalog refresh and composition.
        api_mod = mods / "api-featured"
        old_paths = paths.PROJECT_ROOT, paths.MODS_ROOT, paths.RUNTIME_ROOT, paths.BASELINE_ROOT
        old_installer = server.featured_mods.install_latest
        paths.PROJECT_ROOT, paths.MODS_ROOT, paths.RUNTIME_ROOT, paths.BASELINE_ROOT = \
            project, mods, runtime, root / "baseline"
        def api_install(mod_id: str, _project: Path, _mods: Path) -> dict:
            assert mod_id == "lexers-mod-for-ff8"
            (api_mod / "direct").mkdir(parents=True)
            (api_mod / "direct" / "api.bin").write_bytes(b"api")
            (api_mod / "mod.json").write_text(json.dumps({
                "id": mod_id, "name": "Lexer's Mod for FF8", "featured": True,
                "enabled": False, "order": 1,
            }), encoding="utf-8")
            return next(row for row in runtime_layout.catalog(project, mods)
                        if row["id"] == mod_id)
        server.featured_mods.install_latest = api_install
        service = server.create_server(0)
        thread = threading.Thread(target=service.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{service.server_address[1]}"
        try:
            with urlopen(f"{base}/api/mods/featured") as response:
                available = json.loads(response.read())
            assert available["rows"][0]["id"] == "lexers-mod-for-ff8"
            request = Request(f"{base}/api/mods/featured/install",
                              data=b'{"id":"lexers-mod-for-ff8"}', method="POST",
                              headers={"Content-Type": "application/json"})
            with urlopen(request) as response:
                payload = json.loads(response.read())
            assert payload["installed"]["featured"] is True
            request = Request(f"{base}/api/mods/lexers-mod-for-ff8", method="DELETE")
            with urlopen(request) as response:
                deleted = json.loads(response.read())
            assert deleted["deleted"]["id"] == "lexers-mod-for-ff8"
            assert not api_mod.exists() and unrelated.is_file()
        finally:
            service.shutdown(); service.server_close(); thread.join(timeout=5)
            server.featured_mods.install_latest = old_installer
            paths.PROJECT_ROOT, paths.MODS_ROOT, paths.RUNTIME_ROOT, paths.BASELINE_ROOT = old_paths

    print("FF8 featured mod source, secure release, atomic update, delete, and API passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
