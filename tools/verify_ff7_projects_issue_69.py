"""Shared mod-project contracts for both Final Fantasy VII products."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import shutil
import sys
import tempfile
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff7.plugin import (  # noqa: E402
    FF7Session, PLUGIN as CURRENT_PLUGIN, seed_project_layout,
)
from games.ff7_2013.plugin import (  # noqa: E402
    FF7LegacySession, PLUGIN as LEGACY_PLUGIN,
)
from games.ff7.kernel import Kernel, resolve_kernel  # noqa: E402
from project_manager import ProjectManager  # noqa: E402


PRODUCTS = (
    (
        CURRENT_PLUGIN,
        Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VII Steam Edition"),
        "LEXEDITOR_FF7_PROJECT",
        "ff7/workingdir/data/lang-en/kernel/kernel.bin",
        FF7Session,
    ),
    (
        LEGACY_PLUGIN,
        Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VII"),
        "LEXEDITOR_FF7_2013_PROJECT",
        "data/lang-en/kernel/KERNEL.BIN",
        FF7LegacySession,
    ),
)


editor = (ROOT / "games" / "ff7" / "editor.html").read_text(encoding="utf-8")
framework = (ROOT / "ui" / "framework.js").read_text(encoding="utf-8")
assert "projectSnapshot:" not in editor, "FF7 bypasses the shared project manager"
for required in ('"New Mod"', '"Find a Mod"', 'callWindow("select_mod_project"'):
    assert required in framework, required

with tempfile.TemporaryDirectory(prefix="lexeditor-ff7-projects-", ignore_cleanup_errors=True) as temp_name:
    temp = Path(temp_name)
    for plugin, game_root, root_env, required_path, session_type in PRODUCTS:
        assert plugin.projects is not None, plugin.plugin_id
        assert plugin.projects.root_env == root_env, plugin.projects
        assert plugin.projects.required_paths == (required_path,), plugin.projects

        product = temp / plugin.plugin_id
        template = product / "template"
        default = product / "default"
        source, relative = resolve_kernel(game_root)
        assert relative.as_posix().casefold() == required_path.casefold(), relative
        seeded = seed_project_layout(game_root, template, default)
        assert seeded["relativePath"].casefold() == required_path.casefold(), seeded
        assert Kernel(template / relative).sha256 == Kernel(source).sha256
        assert Kernel(default / relative).sha256 == Kernel(source).sha256

        test_spec = replace(
            plugin.projects,
            default_root=default,
            template_root=template,
        )
        test_plugin = replace(plugin, projects=test_spec)
        manager = ProjectManager(
            {plugin.plugin_id: test_plugin},
            product / "projects.json",
        )
        initial = manager.snapshot(plugin.plugin_id)
        assert initial["current"] == str(default.resolve()), initial
        assert initial["canCreate"] and initial["projects"][0]["valid"], initial

        created = manager.create(plugin.plugin_id, str(product), "New Mod")
        new_mod = product / "New Mod"
        assert created["current"] == str(new_mod.resolve()), created
        assert Kernel(new_mod / relative).sha256 == Kernel(source).sha256

        found = product / "Found Mod"
        shutil.copytree(template, found)
        selected = manager.select(plugin.plugin_id, str(found))
        assert selected["current"] == str(found.resolve()), selected
        switched = manager.select(plugin.plugin_id, str(new_mod))
        assert switched["current"] == str(new_mod.resolve()), switched
        known = {Path(row["path"]).resolve() for row in switched["projects"]}
        assert new_mod.resolve() in known and found.resolve() in known, switched

        environment = {
            plugin.installation.root_env: str(game_root),
            root_env: str(new_mod),
        }
        with session_type(environment) as session:
            with urllib.request.urlopen(session.url + "api/plugin", timeout=10) as response:
                identity = json.loads(response.read().decode("utf-8"))
            with urllib.request.urlopen(session.url + "api/data", timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))
            assert Path(identity["projectRoot"]).resolve() == new_mod.resolve(), identity
            assert data["usingProject"] is True, data
        assert session.wait_closed(), f"{plugin.plugin_id} project service stayed open"

print("FF7 New Mod, Find a Mod, switching, and both project overlays passed")
