"""Registration-only contract; fixtures never touch an installed game."""
import sys
import tempfile
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app import discover_plugins
from core.game_installation import GameInstallationManager
from plugins.ds1.plugin import DS1Session, PLUGIN


def test_ds1_detection_and_read_only_service():
    assert discover_plugins()["ds1"] is PLUGIN
    assert PLUGIN.projects is not None and PLUGIN.mod_adapter is None
    with tempfile.TemporaryDirectory(prefix="lexeditor-ds1-") as temporary:
        root = Path(temporary)
        manager = GameInstallationManager({"ds1": PLUGIN}, root / "locations.json",
                                          root / "data", auto_scan=False)
        assert manager._validate(PLUGIN, root)
        # A different Dark Souls edition must not pass detection.
        (root / "DARKSOULS.exe").touch()
        (root / "param").mkdir()
        (root / "map").mkdir()
        assert manager._validate(PLUGIN, root)
        (root / "DarkSoulsRemastered.exe").touch()
        assert manager._validate(PLUGIN, root) == []
        before = sorted(str(p.relative_to(root)) for p in root.rglob("*"))
        session = DS1Session({"LEXEDITOR_DS1_ROOT": str(root)})
        try:
            assert session.start()["pluginId"] == "ds1"
            for route in ("/", "/editor.js", "/shared/framework.css"):
                with urlopen(session.url.rstrip("/") + route) as reply:
                    assert reply.status == 200
            try:
                urlopen(Request(session.url.rstrip("/") + "/api/save", data=b"{}"))
                raise AssertionError("The registration service accepted a write")
            except HTTPError as error:
                assert error.code == 403
        finally:
            session.stop()
        assert session.wait_closed()
        assert sorted(str(p.relative_to(root)) for p in root.rglob("*")) == before
