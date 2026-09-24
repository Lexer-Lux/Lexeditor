"""G7: per-game mod trees default to Documents and migrate loss-free.

ff7, ff7-2013 and ff8 kept editable mods under AppData. Their defaults now
resolve under Documents/Mods, the environment overrides still win, and a
one-time verified copy moves existing trees (registry paths remapped, the
AppData source kept as recovery). Caches and settings stay in AppData.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core import mod_library
from core.mod_library import (
    default_user_library_root,
    legacy_appdata_library_root,
    migrate_appdata_user_data,
)
from core.project_manager import ProjectManager


@pytest.fixture
def fake_homes(monkeypatch, tmp_path):
    local = tmp_path / "Local"
    docs = tmp_path / "Docs"
    (local / "Lexeditor").mkdir(parents=True)
    docs.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setattr(mod_library, "documents_folder", lambda: docs)
    for name in ("LEXEDITOR_FF7_PROJECT", "LEXEDITOR_FF7_2013_PROJECT",
                 "LEXEDITOR_FF8_MODS_ROOT", "LEXEDITOR_SKIP_USER_DATA_MIGRATION"):
        monkeypatch.delenv(name, raising=False)
    return local, docs


def test_default_library_prefers_documents_then_appdata(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    monkeypatch.setattr(mod_library, "documents_folder", lambda: tmp_path / "Docs")
    assert default_user_library_root() == tmp_path / "Docs" / "Mods"

    def missing():
        raise OSError("no Documents")

    monkeypatch.setattr(mod_library, "documents_folder", missing)
    assert default_user_library_root() == legacy_appdata_library_root()


def test_migration_moves_verified_tree_and_remaps_registry(fake_homes, tmp_path):
    local, docs = fake_homes
    old_tree = local / "Lexeditor" / "mods" / "ff7"
    (old_tree / "My Mod" / "data").mkdir(parents=True)
    (old_tree / "Second").mkdir()
    (old_tree / "My Mod" / "data" / "kernel.bin").write_bytes(b"kernel-bytes")
    (old_tree / "My Mod" / "notes.txt").write_text("keep me", encoding="utf-8")
    (old_tree / "Second" / "mod.json").write_text("{}", encoding="utf-8")
    registry = tmp_path / "projects.json"
    registry.write_text(json.dumps({
        "ff7": {"current": str(old_tree / "My Mod"),
                "known": [str(old_tree / "My Mod"), str(old_tree / "Second")],
                "forgotten": []},
        "ff8": {"current": "C:\\FF8Mod", "known": ["C:\\FF8Mod"], "forgotten": []},
    }), encoding="utf-8")
    projects = ProjectManager({}, path=registry)

    report = migrate_appdata_user_data(projects, local / "Lexeditor")
    assert [move["game"] for move in report["moved"]] == ["ff7"]
    assert report["moved"][0]["files"] == 3
    new_tree = docs / "Mods" / "ff7"
    assert (new_tree / "My Mod" / "data" / "kernel.bin").read_bytes() == b"kernel-bytes"
    assert (new_tree / "Second" / "mod.json").read_text(encoding="utf-8") == "{}"
    # Loss-free: the AppData source stays as recovery.
    assert (old_tree / "My Mod" / "data" / "kernel.bin").read_bytes() == b"kernel-bytes"
    payload = json.loads(registry.read_text(encoding="utf-8"))
    assert payload["ff7"]["current"] == str(new_tree / "My Mod")
    assert payload["ff7"]["known"] == [str(new_tree / "My Mod"), str(new_tree / "Second")]
    assert payload["ff8"]["current"] == "C:\\FF8Mod"
    journal = json.loads((local / "Lexeditor" / "user-data-migration.json").read_text(encoding="utf-8"))
    assert journal["moves"]["ff7"]["phase"] == "done"
    assert journal["moves"]["ff7"]["files"] == 3
    # Second run is a no-op.
    again = migrate_appdata_user_data(projects, local / "Lexeditor")
    assert again["moved"] == []
    assert ("ff7", "already migrated") in [(s["game"], s["reason"]) for s in again["skipped"]]


def test_migration_skips_override_settled_and_missing(monkeypatch, fake_homes, tmp_path):
    local, docs = fake_homes
    (local / "Lexeditor" / "mods" / "ff7" / "My Mod").mkdir(parents=True)
    (local / "Lexeditor" / "mods" / "ff7" / "My Mod" / "a.txt").write_text("a", encoding="utf-8")
    (local / "Lexeditor" / "mods" / "ff8" / "some-mod").mkdir(parents=True)
    (local / "Lexeditor" / "mods" / "ff8" / "some-mod" / "b.txt").write_text("b", encoding="utf-8")
    (docs / "Mods" / "ff8" / "settled-mod").mkdir(parents=True)
    (docs / "Mods" / "ff8" / "settled-mod" / "c.txt").write_text("c", encoding="utf-8")
    monkeypatch.setenv("LEXEDITOR_FF7_PROJECT", str(tmp_path / "elsewhere"))
    report = migrate_appdata_user_data(None, local / "Lexeditor")
    assert report["moved"] == []
    reasons = {s["game"]: s["reason"] for s in report["skipped"]}
    assert reasons["ff7"] == "environment override set"
    assert reasons["ff8"] == "Documents copy already settled"
    assert reasons["ff7-2013"] == "nothing to migrate"
    assert not (docs / "Mods" / "ff7").exists()
    journal = json.loads((local / "Lexeditor" / "user-data-migration.json").read_text(encoding="utf-8"))
    assert journal["moves"]["ff8"]["phase"] == "settled"


def _scrubbed_env(extra=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith("LEXEDITOR_")}
    env.update(extra or {})
    return env


def test_plugin_defaults_use_documents_and_keep_overrides():
    script = ("from plugins.ff7 import paths as ff7_paths;"
              "from plugins.ff8 import paths as ff8_paths;"
              "from plugins.ff7_2013 import plugin as legacy;"
              "print(ff7_paths.PROJECT_ROOT);print(ff8_paths.MODS_ROOT);"
              "print(legacy.DEFAULT_PROJECT)")
    clean = subprocess.run([sys.executable, "-c", script], cwd=ROOT, capture_output=True,
                           text=True, env=_scrubbed_env(), timeout=120)
    assert clean.returncode == 0, clean.stderr[-500:]
    roots = clean.stdout.splitlines()
    assert roots[0].replace("\\", "/").endswith("Documents/Mods/ff7/My Mod"), roots
    assert roots[1].replace("\\", "/").endswith("Documents/Mods/ff8"), roots
    assert roots[2].replace("\\", "/").endswith("Documents/Mods/ff7-2013/My Mod"), roots
    assert "AppData" not in clean.stdout and "Lexeditor/mods" not in clean.stdout.replace("\\", "/")
    override = subprocess.run(
        [sys.executable, "-c", script], cwd=ROOT, capture_output=True, text=True,
        env=_scrubbed_env({"LEXEDITOR_FF7_PROJECT": "C:/custom/ff7",
                           "LEXEDITOR_FF8_MODS_ROOT": "C:/custom/ff8mods",
                           "LEXEDITOR_FF7_2013_PROJECT": "C:/custom/legacy"}), timeout=120)
    assert override.returncode == 0, override.stderr[-500:]
    assert [line.replace("\\", "/") for line in override.stdout.splitlines()] == [
        "C:/custom/ff7", "C:/custom/ff8mods", "C:/custom/legacy"]
