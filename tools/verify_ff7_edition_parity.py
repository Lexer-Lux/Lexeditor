"""Enforce one FF7 editing implementation across the supported Steam editions."""
from __future__ import annotations

import json
from pathlib import Path
import re
import sys
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff7.plugin import DISPLAY_NAME, FF7Session, kernel_save_payload
from games.ff7_2013.plugin import FF7LegacySession, PLUGIN as LEGACY_PLUGIN
from service_session import request_json

import verify_ff7_completion as complete
import verify_ff7_datasets as fixtures
import verify_ff7_extended as extended


LEGACY_ROOT = ROOT / "games" / "ff7_2013"
EXPECTED_CURRENT = "Final Fantasy 7 (Completely Pointless 2026 Re-Release That Really Should Have Just Been A Patch)"
EXPECTED_LEGACY = "Final Fantasy 7 (Original)"


def post_json(url: str, payload: dict) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def install_fixture(root: Path, prefix: str, launcher: str) -> None:
    kernel = root / f"{prefix}data/lang-en/kernel/KERNEL.BIN"
    fixtures.write_kernel(kernel)
    sources = {
        f"{prefix}data/battle/scene.bin": extended.scene_fixture(),
        f"{prefix}data/lang-en/kernel/kernel2.bin": extended.text_fixture(),
        f"{prefix}data/field/flevel.lgp": complete.lgp_fixture([
            ("maplist", b"list"), ("field1", complete.field_fixture()),
        ]),
        f"{prefix}data/wm/world_us.lgp": complete.lgp_fixture([
            ("enc_w.bin", complete.world_fixture()), ("other", b"opaque"),
        ]),
        "ff7_en.exe": extended.exe_fixture(),
        "FFNx.toml": fixtures.CONFIG,
    }
    for relative, data in sources.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    launcher_path = root / launcher
    if not launcher_path.exists():
        launcher_path.write_bytes(b"fixture")


def normalized_map(payload: dict) -> dict:
    return {
        row["target"]: {
            "controls": row["controls"],
            "coverage": row["coverage"],
            "openable": row["openable"],
        }
        for row in payload["rows"]
    }


def normalized_html(html: str) -> str:
    html = re.sub(r"<title>.*?</title>", "<title>EDITION</title>", html, count=1)
    return re.sub(
        r"<script>window\.__lexeditorPlugin=.*?</script>",
        "<script>EDITION_IDENTITY</script>",
        html,
        count=1,
    )


def save_one_weapon(session_url: str, data: dict) -> bytes:
    payload = kernel_save_payload(data)
    current = payload["records"]["weapons"][0]["values"]["attackStrength"]
    payload["records"]["weapons"][0]["values"]["attackStrength"] = 1 if current == 255 else current + 1
    saved = post_json(session_url + "api/save", payload)
    return Path(saved["path"]).read_bytes()


def verify_structure() -> None:
    allowed = {"__init__.py", "plugin.py", "__pycache__"}
    extras = sorted(path.name for path in LEGACY_ROOT.iterdir() if path.name not in allowed)
    if extras:
        raise AssertionError(
            "ff7_2013 must remain an edition adapter, not a second editor implementation: "
            + ", ".join(extras)
        )
    source = (LEGACY_ROOT / "plugin.py").read_text(encoding="utf-8")
    required = (
        'SHARED_PLUGIN_ROOT = LEXEDITOR_ROOT / "games" / "ff7"',
        'module="games.ff7.server"',
        "from games.ff7.plugin import prepare_product, kernel_save_payload",
        "from games.ff7.kernel import Kernel, resolve_kernel",
    )
    missing = [text for text in required if text not in source]
    if missing:
        raise AssertionError("FF7 2013 stopped delegating to the shared FF7 implementation: " + repr(missing))
    if DISPLAY_NAME != EXPECTED_CURRENT or LEGACY_PLUGIN.name != EXPECTED_LEGACY:
        raise AssertionError("FF7 edition display names drifted from the requested names")


def verify_runtime_parity() -> None:
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff7-parity-") as temp_name:
        base = Path(temp_name)
        current_root, legacy_root = base / "current", base / "legacy"
        install_fixture(current_root, "ff7/workingdir/", "FFVII_LAUNCHER.exe")
        install_fixture(legacy_root, "", "ff7_en.exe")

        current_env = {
            "LEXEDITOR_FF7_ROOT": str(current_root),
            "LEXEDITOR_FF7_DATA_ROOT": str(base / "data-current"),
            "LEXEDITOR_FF7_PROJECT": str(base / "project-current"),
        }
        legacy_env = {
            "LEXEDITOR_FF7_ROOT": str(legacy_root),
            "LEXEDITOR_FF7_DATA_ROOT": str(base / "data-legacy"),
            "LEXEDITOR_FF7_PROJECT": str(base / "project-legacy"),
        }
        with FF7Session(current_env) as current, FF7LegacySession(legacy_env) as legacy:
            current_identity = request_json(current.url + "api/plugin")
            legacy_identity = request_json(legacy.url + "api/plugin")
            if current_identity["name"] != EXPECTED_CURRENT or legacy_identity["name"] != EXPECTED_LEGACY:
                raise AssertionError("FF7 HTTP identity names do not match the plugin cards")
            if current_identity["capabilities"] != legacy_identity["capabilities"]:
                raise AssertionError("FF7 editions expose different editor capabilities")
            if current_identity["editorRoot"] != legacy_identity["editorRoot"]:
                raise AssertionError("FF7 editions no longer use the same editor root")

            current_data = request_json(current.url + "api/data")
            legacy_data = request_json(legacy.url + "api/data")
            if current_data["categories"] != legacy_data["categories"]:
                raise AssertionError("FF7 editions expose different editor categories/fields")
            if current_data["records"] != legacy_data["records"]:
                raise AssertionError("Equivalent FF7 edition fixtures decode to different editable records")
            if set(current_data["errors"]) != set(legacy_data["errors"]):
                raise AssertionError("Equivalent FF7 edition fixtures expose different availability")

            current_map = normalized_map(request_json(current.url + "api/datamap"))
            legacy_map = normalized_map(request_json(legacy.url + "api/datamap"))
            if current_map != legacy_map:
                raise AssertionError("FF7 Data Map/editor surface differs by edition")

            with urllib.request.urlopen(current.url, timeout=10) as response:
                current_html = response.read().decode("utf-8")
            with urllib.request.urlopen(legacy.url, timeout=10) as response:
                legacy_html = response.read().decode("utf-8")
            if normalized_html(current_html) != normalized_html(legacy_html):
                raise AssertionError("FF7 editions are not serving the same editor UI")
            if f"<title>Lexeditor - {EXPECTED_CURRENT}</title>" not in current_html:
                raise AssertionError("2026 FF7 editor title does not use the requested name")
            if f"<title>Lexeditor - {EXPECTED_LEGACY}</title>" not in legacy_html:
                raise AssertionError("Original FF7 editor title does not use the requested name")

            if save_one_weapon(current.url, current_data) != save_one_weapon(legacy.url, legacy_data):
                raise AssertionError("The same FF7 edit serializes differently between editions")

        if not current.wait_closed() or not legacy.wait_closed():
            raise AssertionError("An FF7 parity-test child service stayed open")


def main() -> None:
    verify_structure()
    verify_runtime_parity()
    print("FF7 edition parity: shared UI, datasets, capabilities and binary save output verified")


if __name__ == "__main__":
    main()
