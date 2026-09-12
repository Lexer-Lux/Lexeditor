"""FINAL FANTASY VII REMAKE INTERGRADE plugin lifecycle."""

from __future__ import annotations

import struct
import tempfile
from pathlib import Path
from urllib.parse import quote

from plugin_api import GameInstallSpec, GamePlugin, ModProjectSpec
from runtime_bootstrap import user_data_dir
from service_session import LocalPluginSession, request_json

from .tooling import REPAK_TAG, helper_install, helper_status


ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent
USER_ROOT = user_data_dir()
# Lexer's FF7R mod lives outside Lexeditor's own data, beside the other
# per-game mod repositories, so the mod can be worked on without Lexeditor.
DEFAULT_PROJECT = Path(r"C:/FF7RMod")
DISPLAY_NAME = "FINAL FANTASY VII REMAKE INTERGRADE"


def check() -> list[str]:
    # Candidate-specific game files are validated by GameInstallSpec. repak has
    # its own helper status so a missing helper is reported as such, not as a
    # fictitious broken plugin install.
    return []


class FF7RSession(LocalPluginSession):
    def __init__(self, extra_env: dict[str, str] | None = None):
        environment = {
            "LEXEDITOR_FF7R_PROJECT": str(DEFAULT_PROJECT),
        }
        environment.update(extra_env or {})
        super().__init__(
            module="games.ff7r.themed_server",
            plugin_id="ff7r",
            app_root=ROOT,
            check=check,
            port_env="LEXEDITOR_FF7R_PORT",
            extra_env=environment,
        )


def launch() -> int:
    from desktop_host import run_host
    return run_host({"ff7r": PLUGIN}, "ff7r")


def _fstring(value: str) -> bytes:
    encoded = value.encode("utf-8") + b"\0"
    return struct.pack("<i", len(encoded)) + encoded


def _test_package() -> tuple[bytes, bytes]:
    """Generate a proprietary-data-free DataObject for smoke/round-trip checks."""
    names = ["Fixture", "Power", "Enabled", "Mode", "ModeA", "ModeB", "Description", "Values_Array", "RowA"]
    header = bytearray()
    header += struct.pack("<Iii", 0x9E2A83C1, -4, 0)
    header += struct.pack("<i", 0)  # licensee version
    header += struct.pack("<i", 0)  # custom versions
    header += struct.pack("<i", 0)  # header size placeholder
    header += struct.pack("<i", 0)  # empty FString
    header += struct.pack("<i", 0)  # package flags
    counts_offset = len(header)
    header += b"\0" * 24
    names_offset = len(header)
    for name in names:
        header += _fstring(name) + b"\0\0\0\0"
    exports_offset = len(header)
    # One export definition. Only object name/serial fields are semantically used by our reader.
    header += struct.pack("<iiii", 0, 0, 0, 0)
    header += struct.pack("<iI", 0, 0)  # Fixture FName
    header += struct.pack("<Iqq", 0, 0, 0)
    header += b"\0\0\0" + (b"\0" * 16) + struct.pack("<i", 0) + b"\0\1"
    struct.pack_into("<i", header, 20, len(header))
    struct.pack_into("<iiiiii", header, counts_offset,
                     len(names), names_offset, 0, 0, 1, exports_offset)

    name_index = {name: index for index, name in enumerate(names)}
    fname = lambda name: struct.pack("<iI", name_index[name], 0)
    uexp = bytearray(b"\0" * 0x0A)
    uexp += struct.pack("<ii", 1, 5)
    uexp += fname("Power") + struct.pack("<B", 7)
    uexp += fname("Enabled") + struct.pack("<B", 3)
    uexp += fname("Mode") + struct.pack("<B", 11)
    uexp += fname("Description") + struct.pack("<B", 10)
    uexp += fname("Values_Array") + struct.pack("<B", 4)
    uexp += fname("RowA")
    uexp += struct.pack("<i", 42)
    uexp += struct.pack("<B", 1)
    uexp += fname("ModeA")
    uexp += _fstring("$Item_Test")
    uexp += struct.pack("<i3h", 3, 10, 20, 30)
    return bytes(header), bytes(uexp)


def _test_text_package() -> tuple[bytes, bytes]:
    """Generate a proprietary-data-free FF7R Resident_TxtRes pair."""
    from .textresource import (
        TEXT_NAME_COUNT_OFFSET,
        TEXT_NAME_MAP_OFFSET,
        TEXT_SERIAL_SIZE_FROM_END,
        UNREAL_SIGNATURE,
    )

    names = ["ACTOR", "EMOTION"]
    uasset = bytearray(320)
    uasset[:4] = UNREAL_SIGNATURE
    struct.pack_into("<I", uasset, TEXT_NAME_COUNT_OFFSET, len(names))
    cursor = TEXT_NAME_MAP_OFFSET
    for name in names:
        encoded = _fstring(name) + b"\0\0\0\0"
        uasset[cursor:cursor + len(encoded)] = encoded
        cursor += len(encoded)

    uexp = bytearray(b"\x00\x03")
    uexp += _fstring("US")
    uexp += struct.pack("<iI", 0, 2)
    uexp += _fstring("$Item_Test") + _fstring("Buster Sword") + struct.pack("<I", 0)
    uexp += _fstring("$Line_Test") + _fstring("Hello") + struct.pack("<I", 1)
    uexp += struct.pack("<Ii", 0, 0) + _fstring("Cloud")
    uexp += UNREAL_SIGNATURE
    struct.pack_into("<i", uasset, len(uasset) - TEXT_SERIAL_SIZE_FROM_END,
                     len(uexp) - len(UNREAL_SIGNATURE))
    return bytes(uasset), bytes(uexp)


def smoke() -> list[str]:
    from .dataobject import DataObjectPackage
    from .textresource import TextResourcePackage

    uasset, uexp = _test_package()
    package = DataObjectPackage.from_bytes(uasset, uexp)
    package.apply_edits([
        {"entry": 0, "property": "Power", "value": 73},
        {"entry": 0, "property": "Enabled", "value": False},
        {"entry": 0, "property": "Mode", "value": "ModeB"},
        {"entry": 0, "property": "Values_Array", "index": 1, "value": 12},
    ])
    reread = DataObjectPackage.from_bytes(uasset, bytes(package.uexp_bytes))
    if reread.entries[0].values["Power"] != 73 or reread.entries[0].values["Enabled"] is not False:
        raise RuntimeError("FF7R generated DataObject edit failed binary readback")
    if (reread.entries[0].values["Mode"] != "ModeB"
            or reread.entries[0].values["Values_Array"] != [10, 12, 30]
            or reread.entries[0].values["Description"] != "$Item_Test"):
        raise RuntimeError("FF7R generated DataObject edit did not preserve fixed/read-only values")

    text_uasset, text_uexp = _test_text_package()
    text_package = TextResourcePackage.from_bytes(text_uasset, text_uexp)
    text_package.apply_edits([{"entry": 0, "text": "A much longer Buster Sword name"}])
    text_reread = TextResourcePackage.from_bytes(
        bytes(text_package.uasset_bytes), bytes(text_package.uexp_bytes))
    if text_reread.entries[0].text != "A much longer Buster Sword name":
        raise RuntimeError("FF7R generated text-resource edit failed binary readback")

    with tempfile.TemporaryDirectory(prefix="lexeditor-ff7r-") as temp_name:
        temp = Path(temp_name)
        fixture = temp / "fixture"
        data_source = fixture / "End" / "Content" / "GameContents" / "DataObject" / "Resident"
        data_source.mkdir(parents=True)
        (data_source / "Equipment.uasset").write_bytes(uasset)
        (data_source / "Equipment.uexp").write_bytes(uexp)
        text_source = fixture / "End" / "Content" / "GameContents" / "Text" / "US"
        text_source.mkdir(parents=True)
        (text_source / "Resident_TxtRes.uasset").write_bytes(text_uasset)
        (text_source / "Resident_TxtRes.uexp").write_bytes(text_uexp)

        game = temp / "game"
        (game / "End" / "Content" / "Paks").mkdir(parents=True)
        project = temp / "project"
        with FF7RSession({
            "LEXEDITOR_FF7R_ROOT": str(game),
            "LEXEDITOR_FF7R_DATA_ROOT": str(temp / "data"),
            "LEXEDITOR_FF7R_PROJECT": str(project),
            "LEXEDITOR_FF7R_TEST_DATAOBJECTS": str(fixture),
        }) as session:
            identity = request_json(session.url + "api/plugin")
            if identity.get("pluginId") != "ff7r" or identity.get("hosted") is not True:
                raise RuntimeError("FF7R service returned the wrong managed identity")
            if "text-resource" not in identity.get("capabilities", []):
                raise RuntimeError("FF7R service did not advertise text-resource editing")

            catalog = request_json(session.url + "api/catalog")
            if len(catalog.get("assets", [])) != 1 or len(catalog.get("textAssets", [])) != 1:
                raise RuntimeError("FF7R fixture catalog did not expose gameplay and text resources")

            asset = catalog["assets"][0]["asset"]
            data = request_json(session.url + "api/data?asset=" + quote(asset, safe=""))
            if data.get("textLookup", {}).get("$Item_Test") != "Buster Sword":
                raise RuntimeError("FF7R gameplay data did not resolve its installed Resident text ID")
            result = request_json(session.url + "api/save", {
                "asset": asset,
                "sourceSha256": data["sourceSha256"],
                "activeSha256": data["activeSha256"],
                "edits": [{"entry": 0, "property": "Power", "value": 99}],
            })
            if result.get("saved") != 1:
                raise RuntimeError("FF7R service did not save one generated gameplay edit")
            saved = request_json(session.url + "api/data?asset=" + quote(asset, safe=""))
            if saved["records"][0]["values"]["Power"] != 99 or not saved.get("usingProject"):
                raise RuntimeError("FF7R gameplay service save did not survive readback")

            text_asset = catalog["textAssets"][0]["asset"]
            text = request_json(session.url + "api/text?asset=" + quote(text_asset, safe=""))
            text_result = request_json(session.url + "api/text/save", {
                "asset": text_asset,
                "sourceUassetSha256": text["sourceUassetSha256"],
                "sourceUexpSha256": text["sourceUexpSha256"],
                "activeUassetSha256": text["activeUassetSha256"],
                "activeUexpSha256": text["activeUexpSha256"],
                "edits": [{"entry": 0, "text": "Lexeditor テスト Sword"}],
            })
            if text_result.get("saved") != 1:
                raise RuntimeError("FF7R service did not save one generated text edit")
            saved_text = request_json(session.url + "api/text?asset=" + quote(text_asset, safe=""))
            if saved_text["records"][0]["text"] != "Lexeditor テスト Sword" or not saved_text.get("usingProject"):
                raise RuntimeError("FF7R text service save did not survive variable-length UTF-16 readback")
        if not session.wait_closed():
            raise RuntimeError("FF7R child port is still open after host shutdown")
    return [
        "generated FF7R DataObject parser/write round-trip passed",
        "installed-style Resident text IDs resolve without bundled game strings",
        "generated FF7R variable-length text resource round-trip passed",
        "managed service saved/read back gameplay and UTF-16 text project overlays",
        "host-owned FF7R child service stopped cleanly",
    ]


PLUGIN = GamePlugin(
    plugin_id="ff7r",
    name=DISPLAY_NAME,
    subtitle="FF7 Remake",
    description="Edit FF7 Remake gameplay DataObjects and localized text, then build project overlays as mod PAKs.",
    accent="#1d6fb8",
    check=check,
    launch=launch,
    smoke=smoke,
    session_factory=FF7RSession,
    process_names=("ff7remake_.exe",),
    helper_name="repak",
    helper_status=helper_status,
    helper_install=helper_install,
    helper_pinned=REPAK_TAG,
    projects=ModProjectSpec(
        root_env="LEXEDITOR_FF7R_PROJECT",
        default_root=DEFAULT_PROJECT,
        required_paths=(),
        template_root=PLUGIN_ROOT / "_no_project_template",
        content_types=(
            ("DataObject tables", (".uasset", ".uexp")),
            ("Packaged archives", (".pak", ".ucas", ".utoc")),
            ("Textures", (".ubulk", ".dds", ".png")),
            ("Audio", (".bnk", ".wem")),
            ("ReShade presets", (".ini", ".fx")),
        ),
    ),
    installation=GameInstallSpec(
        root_env="LEXEDITOR_FF7R_ROOT",
        data_env="LEXEDITOR_FF7R_DATA_ROOT",
        required_paths=(
            "End/Binaries/Win64/ff7remake_.exe",
            "End/Content/Paks",
        ),
        steam_app_id="1462040",
        install_dir_names=("FINAL FANTASY VII REMAKE", "FFVIIRemakeIntergrade"),
        default_roots=(
            Path(r"C:\Program Files (x86)\Steam\steamapps\common\FINAL FANTASY VII REMAKE"),
            Path(r"C:\Program Files\Epic Games\FFVIIRemakeIntergrade"),
        ),
        launch_path="End/Binaries/Win64/ff7remake_.exe",
    ),
)
