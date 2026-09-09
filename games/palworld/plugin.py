"""Palworld official mod-package plugin lifecycle."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from urllib.parse import quote

from plugin_api import GameInstallSpec, GamePlugin, ModProjectSpec
from runtime_bootstrap import user_data_dir
from service_session import LocalPluginSession, request_json

from .package import default_info


ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent
DEFAULT_PROJECT = user_data_dir() / "projects" / "palworld"
DISPLAY_NAME = "Palworld"


def check() -> list[str]:
    # GameInstallSpec validates the selected installation. PalSchema support is
    # package-authoring support and does not silently install UE4SS/PalSchema.
    return []


class PalworldSession(LocalPluginSession):
    def __init__(self, extra_env: dict[str, str] | None = None):
        environment = {"LEXEDITOR_PALWORLD_PROJECT": str(DEFAULT_PROJECT)}
        environment.update(extra_env or {})
        super().__init__(
            module="games.palworld.server",
            plugin_id="palworld",
            app_root=ROOT,
            check=check,
            port_env="LEXEDITOR_PALWORLD_PORT",
            extra_env=environment,
        )


def launch() -> int:
    from desktop_host import run_host
    return run_host({"palworld": PLUGIN}, "palworld")


def smoke() -> list[str]:
    """Exercise package + PalSchema service paths without installed game data."""
    with tempfile.TemporaryDirectory(prefix="lexeditor-palworld-") as temp_name:
        temp = Path(temp_name)
        game = temp / "Palworld"
        (game / "Pal" / "Content" / "Paks").mkdir(parents=True)
        (game / "Palworld.exe").write_bytes(b"")

        # Synthetic stand-in for the JSON schemas generated locally by PalSchema.
        schema_root = game / "Mods" / "NativeMods" / "UE4SS" / "Mods" / "PalSchema" / "schemas"
        (schema_root / "raw").mkdir(parents=True)
        (schema_root / "raw" / "DT_PalMonsterParameter.schema.json").write_text(
            json.dumps({
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "properties": {
                        "WorkSuitability_EmitFlame": {
                            "type": "integer",
                            "description": "IntProperty",
                        },
                        "FutureNested": {
                            "type": "object",
                            "description": "StructProperty",
                            "properties": {},
                        },
                    },
                },
            }, indent=2) + "\n",
            encoding="utf-8",
        )
        (schema_root / "enums.schema.json").write_text(
            json.dumps({"definitions": {}}, indent=2) + "\n", encoding="utf-8"
        )

        project = temp / "project"
        project.mkdir()
        fixture = default_info("LexeditorSmoke")
        fixture["FuturePocketpairField"] = {"preserve": True}
        fixture["Dependencies"] = ["PalSchema"]
        fixture["Tags"] = ["PalSchema"]
        fixture["InstallRule"] = [{"Type": "PalSchema", "Targets": ["./PalSchema/"]}]
        (project / "Info.json").write_text(
            json.dumps(fixture, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        raw_root = project / "PalSchema" / "LexeditorSmokeBalance" / "raw"
        raw_root.mkdir(parents=True)
        json_patch = raw_root / "balance.json"
        json_patch.write_text(
            json.dumps({
                "DT_PalMonsterParameter": {
                    "Kitsunebi": {
                        "WorkSuitability_EmitFlame": 3,
                        "FutureNested": {"preserve": [1, 2, 3]},
                    }
                }
            }, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        jsonc_patch = raw_root / "commented.jsonc"
        jsonc_patch.write_text(
            '// preserve this comment\n{"DT_Test":{"Row":{"Value":1}}}\n',
            encoding="utf-8",
        )
        nested = raw_root / "nested"
        nested.mkdir()
        (nested / "ignored.json").write_text(
            '{"DT_Test":{"Row":{"Value":9}}}\n', encoding="utf-8"
        )

        with PalworldSession({
            "LEXEDITOR_PALWORLD_ROOT": str(game),
            "LEXEDITOR_PALWORLD_PROJECT": str(project),
        }) as session:
            identity = request_json(session.url + "api/plugin")
            if identity.get("pluginId") != "palworld" or identity.get("hosted") is not True:
                raise RuntimeError("Palworld service returned the wrong managed identity")
            capabilities = identity.get("capabilities", [])
            required = {"official-package-info", "palschema-raw-patches", "palschema-generated-schemas"}
            if not required.issubset(set(capabilities)):
                raise RuntimeError("Palworld service did not advertise package + schema-aware PalSchema editing")

            info = request_json(session.url + "api/info")
            if info.get("data", {}).get("PackageName") != "LexeditorSmoke":
                raise RuntimeError("Palworld service did not read the selected project Info.json")
            result = request_json(session.url + "api/info/save", {
                "sourceSha256": info["sourceSha256"],
                "changes": {"Version": "0.2.0", "DebugMode": False},
            })
            if result.get("data", {}).get("Version") != "0.2.0":
                raise RuntimeError("Palworld service Info.json edit did not survive readback")
            reread = request_json(session.url + "api/info")
            if reread.get("data", {}).get("FuturePocketpairField") != {"preserve": True}:
                raise RuntimeError("Palworld service did not preserve unknown Info.json metadata")
            if not (project / "Info.json.lexeditor.bak").is_file():
                raise RuntimeError("Palworld service changed Info.json without a backup")

            catalog = request_json(session.url + "api/palschema/catalog")
            patches = catalog.get("patches", [])
            if catalog.get("schemaAvailable") is not True:
                raise RuntimeError("PalSchema service did not detect generated runtime schemas")
            if [row.get("name") for row in patches] != ["balance.json", "commented.jsonc"]:
                raise RuntimeError("PalSchema catalog did not mirror direct raw-folder discovery")
            if [row.get("writable") for row in patches] != [True, False]:
                raise RuntimeError("PalSchema catalog did not keep JSONC writes read-only")

            relative = patches[0]["path"]
            patch = request_json(
                session.url + "api/palschema/patch?path=" + quote(relative, safe="")
            )
            target = next(
                row for row in patch.get("records", [])
                if row.get("table") == "DT_PalMonsterParameter"
                and row.get("row") == "Kitsunebi"
                and row.get("field") == "WorkSuitability_EmitFlame"
            )
            if (
                target.get("value") != 3
                or target.get("writable") is not True
                or target.get("schemaState") != "matched"
                or target.get("schemaType") != "integer"
            ):
                raise RuntimeError("PalSchema service did not apply generated schema metadata to the scalar field")

            saved_patch = request_json(session.url + "api/palschema/patch/save", {
                "path": relative,
                "sourceSha256": patch["sourceSha256"],
                "edits": [{
                    "table": "DT_PalMonsterParameter",
                    "row": "Kitsunebi",
                    "field": "WorkSuitability_EmitFlame",
                    "value": 4,
                }],
            })
            updated = next(
                row for row in saved_patch.get("records", [])
                if row.get("field") == "WorkSuitability_EmitFlame"
            )
            if updated.get("value") != 4:
                raise RuntimeError("PalSchema service schema-backed scalar edit did not survive readback")
            disk = json.loads(json_patch.read_text("utf-8"))
            if disk["DT_PalMonsterParameter"]["Kitsunebi"]["FutureNested"] != {"preserve": [1, 2, 3]}:
                raise RuntimeError("PalSchema edit did not preserve an unmodeled nested property")
            if not (raw_root / "balance.json.lexeditor.bak").is_file():
                raise RuntimeError("PalSchema changed write did not create a backup")

        if not session.wait_closed():
            raise RuntimeError("Palworld child port is still open after host shutdown")

    return [
        "managed Palworld service identified the selected official package project",
        "official Info.json edit survived save/readback with unknown metadata preserved",
        "PalSchema catalog mirrored official target and non-recursive raw discovery",
        "installed-style generated PalSchema schema supplied the scalar field type",
        "schema-backed PalSchema scalar edit survived save/readback while nested data was preserved",
        "Info.json and PalSchema changed writes created recovery backups",
        "PalSchema JSONC patches stayed readable but changed-write disabled",
        "host-owned Palworld child service stopped cleanly",
    ]


PLUGIN = GamePlugin(
    plugin_id="palworld",
    name=DISPLAY_NAME,
    subtitle="Official mod packages",
    description="Create Palworld v0.7+ packages and schema-aware PalSchema raw DataTable patches while installed game data stays read-only.",
    accent="#55c7d9",
    check=check,
    launch=launch,
    smoke=smoke,
    session_factory=PalworldSession,
    process_names=("Palworld.exe", "Palworld-Win64-Shipping.exe"),
    projects=ModProjectSpec(
        root_env="LEXEDITOR_PALWORLD_PROJECT",
        default_root=DEFAULT_PROJECT,
        required_paths=("Info.json",),
        template_root=PLUGIN_ROOT / "template",
    ),
    installation=GameInstallSpec(
        root_env="LEXEDITOR_PALWORLD_ROOT",
        required_paths=("Palworld.exe", "Pal/Content/Paks"),
        steam_app_id="1623730",
        install_dir_names=("Palworld",),
        default_roots=(Path(r"C:\Program Files (x86)\Steam\steamapps\common\Palworld"),),
        launch_path="Palworld.exe",
    ),
)
