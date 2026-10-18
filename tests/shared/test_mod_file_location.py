"""The host opens one mod file's location, never an arbitrary path."""
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from core.desktop_host import HostApi


def make_host(project):
    host = HostApi.__new__(HostApi)
    host._plugins = {"ff8": object()}
    host._projects = Mock()
    host._projects.snapshot.return_value = {"current": str(project)}
    return host


def test_mod_file_opens_selected_in_explorer(tmp_path):
    target = tmp_path / "sfx" / "7.ogg"
    target.parent.mkdir()
    target.write_bytes(b"data")
    host = make_host(tmp_path)
    with patch("core.desktop_host.subprocess.Popen") as opened:
        assert host.open_mod_file_location("ff8", "sfx/7.ogg") == {"path": str(target)}
        opened.assert_called_once_with(["explorer.exe", "/select,", str(target)])


def test_mod_file_rejects_escape_and_unknown_plugin(tmp_path):
    host = make_host(tmp_path)
    with pytest.raises(ValueError):
        host.open_mod_file_location("ff8", "../outside.ogg")
    with pytest.raises(ValueError):
        host.open_mod_file_location("nope", "sfx/7.ogg")


def test_mod_file_needs_an_open_project_and_an_existing_file(tmp_path):
    host = make_host("")
    with pytest.raises(RuntimeError):
        host.open_mod_file_location("ff8", "sfx/7.ogg")
    host = make_host(tmp_path)
    with pytest.raises(RuntimeError):
        host.open_mod_file_location("ff8", "sfx/missing.ogg")
