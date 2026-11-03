import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from core.desktop_host import HostApi


def make_host(tmp, projects):
    host = HostApi.__new__(HostApi)
    host._plugins = {"ds1": Mock()}
    host._projects = Mock()
    host._projects.snapshot.return_value = {"projects": projects}
    host._settings = Mock()
    host._settings.snapshot.return_value = {"modLibraryPath": str(Path(tmp) / "lib")}
    host._settings.path = Path(tmp) / "settings.json"
    return host


def test_library_mod_never_edited_opens():
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp) / "lib" / "ds1" / "later-game-ammunition"
        folder.mkdir(parents=True)
        host = make_host(tmp, [{"path": str(Path(tmp) / "projects" / "armor-rework")}])
        with patch("os.startfile", create=True) as opened:
            result = host.open_mod_folder("ds1", str(folder))
        assert result["opened"] is True
        opened.assert_called_once_with(str(folder.resolve()))


def test_project_outside_library_still_opens():
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp) / "projects" / "armor-rework"
        project.mkdir(parents=True)
        host = make_host(tmp, [{"path": str(project)}])
        with patch("os.startfile", create=True) as opened:
            assert host.open_mod_folder("ds1", str(project))["opened"] is True
        opened.assert_called_once()


def test_foreign_folder_stays_rejected():
    with tempfile.TemporaryDirectory() as tmp:
        foreign = Path(tmp) / "elsewhere"
        foreign.mkdir()
        host = make_host(tmp, [])
        try:
            with patch("os.startfile", create=True):
                host.open_mod_folder("ds1", str(foreign))
        except ValueError as error:
            assert "not one of this plugin's mods" in str(error)
        else:
            raise AssertionError("foreign folder opened")
