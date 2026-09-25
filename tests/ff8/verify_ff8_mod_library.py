"""Verify that the shared mod library drives the FF8 mod composer.

The shared library and the FF8 composer must agree on one load order. This
check builds two library mods, enables them through the adapter, and reads the
composed runtime back, so "enabled in the library" and "loaded by the game"
cannot drift apart again.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

_TEMP = tempfile.TemporaryDirectory(prefix="lexeditor-ff8-library-")
_ROOTS = Path(_TEMP.name)
os.environ["LEXEDITOR_FF8_RUNTIME_ROOT"] = str(_ROOTS / "runtime" / "active")
os.environ["LEXEDITOR_FF8_DATA_ROOT"] = str(_ROOTS / "game-data")
os.environ["LEXEDITOR_FF8_PROJECT"] = str(_ROOTS / "project")
os.environ["LEXEDITOR_FF8_MODS_ROOT"] = str(_ROOTS / "library-root" / "ff8")

from plugins.ff8.mod_support import Ff8ModAdapter  # noqa: E402
from plugins.ff8 import runtime_layout  # noqa: E402

PROBE = Path("direct/lexeditor/probe.bin")


def write_mod(root: Path, name: str, probe: bytes, extra: bytes = b"") -> Path:
    folder = root / "library" / "ff8" / name
    (folder / PROBE.parent).mkdir(parents=True, exist_ok=True)
    (folder / PROBE).write_bytes(probe)
    (folder / "mod.json").write_text(
        json.dumps({"id": name.lower(), "name": name}), encoding="utf-8")
    if extra:
        (folder / "direct" / f"only-{name.lower()}.bin").write_bytes(extra)
    return folder


def main() -> int:
    library = _ROOTS / "library" / "ff8"
    alpha = write_mod(_ROOTS, "Alpha", b"alpha", extra=b"a")
    beta = write_mod(_ROOTS, "Beta", b"beta", extra=b"b")
    project = _ROOTS / "project"
    (project / PROBE.parent).mkdir(parents=True, exist_ok=True)
    (project / PROBE).write_bytes(b"project")
    game = _ROOTS / "game"
    game.mkdir(parents=True, exist_ok=True)
    runtime = Path(os.environ["LEXEDITOR_FF8_RUNTIME_ROOT"])

    adapter = Ff8ModAdapter()
    adapter.attach_context(project_root=project, library_root=library, game_root=game)

    # A mod folder is accepted when its files are under a source root the
    # composer deploys, and the reason is named when they are not.
    good = adapter.inspect(alpha, [PROBE, Path("mod.json")])
    assert good["valid"], good
    assert good["packages"] == [PROBE.as_posix()], good
    assert good["notDeployed"] == ["mod.json"], good
    bad = _ROOTS / "bad"
    (bad / "sub").mkdir(parents=True, exist_ok=True)
    (bad / "readme.txt").write_text("notes", encoding="utf-8")
    (bad / "setup.exe").write_bytes(b"MZ")
    report = adapter.inspect(bad, [Path("readme.txt"), Path("setup.exe")])
    assert not report["valid"], report
    assert any("not an FF8 mod file" in problem for problem in report["problems"]), report
    assert any("no FF8 game files" in problem for problem in report["problems"]), report
    hext_only = _ROOTS / "hext-only"
    (hext_only / "hext").mkdir(parents=True, exist_ok=True)
    (hext_only / "hext" / "readme.md").write_text("notes", encoding="utf-8")
    assert not adapter.inspect(hext_only, [Path("hext/readme.md")])["valid"]

    # Enabling both mods composes both, and the later mod wins the shared file.
    first = adapter.activate([alpha, beta], game)
    assert first["activated"] == ["Alpha", "Beta"], first
    manifest = runtime_layout.read(runtime)
    assert manifest["mods"], manifest
    enabled = [row["id"] for row in manifest["mods"]]
    assert enabled[0] == "project" and enabled[1:] == ["alpha", "beta"], enabled
    assert (runtime / PROBE).read_bytes() == b"beta"
    assert (runtime / "direct" / "only-beta.bin").read_bytes() == b"b"
    assert (runtime / "direct" / "only-alpha.bin").read_bytes() == b"a"
    assert adapter.active_mod_ids(game) == enabled

    # Disabling one mod through the same call removes it from the runtime.
    adapter.activate([alpha], game)
    assert (runtime / PROBE).read_bytes() == b"alpha"
    assert not (runtime / "direct" / "only-beta.bin").exists()
    assert (runtime / "direct" / "only-alpha.bin").exists()
    stored = json.loads((beta / "mod.json").read_text(encoding="utf-8"))
    assert stored["enabled"] is False, stored
    stored = json.loads((alpha / "mod.json").read_text(encoding="utf-8"))
    assert stored["enabled"] is True, stored
    assert [row["id"] for row in runtime_layout.read(runtime)["mods"]][1:] == ["alpha"]

    # The project row is the lowest priority, and activation writes nothing
    # into the game installation.
    assert (runtime / PROBE).read_bytes() == b"alpha"
    assert sorted(path.name for path in game.iterdir()) == [], \
        "activation wrote into the game installation"

    print("ff8 mod library: inspect, enable, compose and disable verified")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        _TEMP.cleanup()
