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
            module="games.palworld.full_server",
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
    """Exercise package, PalSchema, build and local-test deployment with fixtures."""
    with tempfile.TemporaryDirectory(prefix="lexeditor-palworld-") as temp_name:
        temp = Path(temp_name)
        game = temp / "Palworld"
        (game / "Pal" / "Content" / "Paks").mkdir(parents=True)
        (game / "Palworld.exe").write_bytes(b"")
        workshop = temp / "steamapps" / "workshop" / "content" / "1623730"
        workshop.mkdir(parents=True)
        loader_settings = game / "Mods" / "PalModSettings.ini"
        loader_settings.parent.mkdir(parents=True, exist_ok=True)
        loader_settings.write_text(
            "[PalModSettings]\n"
            "bGlobalEnableMod=True\n"
            f"WorkshopRootDir={workshop}\n"
            "ActiveModList=LexeditorSmoke\n",
            encoding="utf-8",
        )

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
                        "NewSchemaValue": {
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
            "LEXEDITOR_PALWORLD_WORKSHOP_ROOT": str(workshop),
        }) as session:
            identity = request_json(session.url + "api/plugin")
            if identity.get("pluginId") != "palworld" or identity.get("hosted") is not True:
                raise RuntimeError("Palworld service returned the wrong managed identity")
            capabilities = set(identity.get("capabilities", []))
            required = {
                "official-package-info",
                "palschema-raw-patches",
                "palschema-generated-schemas",
                "palschema-add-existing-row-fields",
                "official-package-build",
                "official-local-workshop-deploy",
                "official-loader-state-readonly",
            }
            if not required.issubset(capabilities):
                raise RuntimeError("Palworld service did not advertise the complete authoring/test path")

            loader = request_json(session.url + "api/loader-state")
            if (
                loader.get("readOnly") is not True
                or loader.get("available") is not True
                or loader.get("active") is not True
                or loader.get("listed") is not True
                or loader.get("packageName") != "LexeditorSmoke"
            ):
                raise RuntimeError("Palworld service did not expose the active loader configuration read-only")

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

            fields = request_json(
                session.url + "api/palschema/fields?path=" + quote(relative, safe="")
                + "&table=DT_PalMonsterParameter&row=Kitsunebi"
            )
            new_field = next((row for row in fields.get("fields", []) if row.get("name") == "NewSchemaValue"), None)
            if not new_field or new_field.get("writable") is not True or new_field.get("default") != 0:
                raise RuntimeError("PalSchema service did not expose a safe schema-backed addable field")

            saved_patch = request_json(session.url + "api/palschema/patch/save", {
                "path": relative,
                "sourceSha256": patch["sourceSha256"],
                "edits": [{
                    "table": "DT_PalMonsterParameter",
                    "row": "Kitsunebi",
                    "field": "WorkSuitability_EmitFlame",
                    "value": 4,
                }],
                "adds": [{
                    "table": "DT_PalMonsterParameter",
                    "row": "Kitsunebi",
                    "field": "NewSchemaValue",
                    "value": 7,
                }],
            })
            updated = next(
                row for row in saved_patch.get("records", [])
                if row.get("field") == "WorkSuitability_EmitFlame"
            )
            added = next(
                row for row in saved_patch.get("records", [])
                if row.get("field") == "NewSchemaValue"
            )
            if updated.get("value") != 4 or added.get("value") != 7:
                raise RuntimeError("PalSchema service schema-backed edit/add did not survive readback")
            disk = json.loads(json_patch.read_text("utf-8"))
            disk_row = disk["DT_PalMonsterParameter"]["Kitsunebi"]
            if disk_row["FutureNested"] != {"preserve": [1, 2, 3]}:
                raise RuntimeError("PalSchema edit did not preserve an unmodeled nested property")
            if disk_row["NewSchemaValue"] != 7:
                raise RuntimeError("PalSchema added property did not survive disk readback")
            if not (raw_root / "balance.json.lexeditor.bak").is_file():
                raise RuntimeError("PalSchema changed write did not create a backup")

            build_status = request_json(session.url + "api/build")
            if build_status.get("ready") is not True or build_status.get("built") is not False:
                raise RuntimeError("Palworld clean package build reported the wrong initial state")
            built = request_json(session.url + "api/build/create", {})
            if built.get("built") is not True or built.get("current") is not True:
                raise RuntimeError("Palworld clean official-package snapshot was not built")
            build_root = Path(built["packagePath"])
            built_patch = build_root / "PalSchema" / "LexeditorSmokeBalance" / "raw" / "balance.json"
            if not built_patch.is_file():
                raise RuntimeError("Palworld build did not include the declared PalSchema target")
            if (build_root / "PalSchema" / "LexeditorSmokeBalance" / "raw" / "balance.json.lexeditor.bak").exists():
                raise RuntimeError("Palworld build leaked a Lexeditor recovery backup into the official package")

            local_status = request_json(session.url + "api/workshop")
            if local_status.get("ready") is not True or local_status.get("deployed") is not False:
                raise RuntimeError("Palworld local Workshop deployment reported the wrong initial state")
            deployed = request_json(session.url + "api/workshop/deploy", {})
            folder = str(deployed.get("folder", ""))
            target_path = Path(str(deployed.get("targetPath", "")))
            if (
                deployed.get("deployed") is not True
                or deployed.get("current") is not True
                or len(folder) != 10
                or not folder.isdigit()
                or target_path.parent.resolve() != workshop.resolve()
            ):
                raise RuntimeError("Palworld local Workshop deployment did not use the owned 10-digit test shape")
            if not (target_path / "Info.json").is_file() or not (
                target_path / "PalSchema" / "LexeditorSmokeBalance" / "raw" / "balance.json"
            ).is_file():
                raise RuntimeError("Palworld local Workshop deployment did not copy the clean package")
            if (target_path / ".workshop.json").exists() or (
                target_path / "PalSchema" / "LexeditorSmokeBalance" / "raw" / "balance.json.lexeditor.bak"
            ).exists():
                raise RuntimeError("Palworld local Workshop deployment leaked publishing/recovery metadata")
            removed = request_json(session.url + "api/workshop/remove", {})
            if removed.get("deployed") is not False or target_path.exists():
                raise RuntimeError("Palworld owned local Workshop deployment did not remove cleanly")

            reverted = request_json(session.url + "api/build/revert", {})
            if reverted.get("built") is not False or build_root.exists():
                raise RuntimeError("Palworld clean package build did not revert cleanly")

        if not session.wait_closed():
            raise RuntimeError("Palworld child port is still open after host shutdown")

    return [
        "managed Palworld service identified the selected official package project",
        "read-only PalModSettings state identified the active package without changing activation",
        "official Info.json edit survived save/readback with unknown metadata preserved",
        "PalSchema catalog mirrored official target and non-recursive raw discovery",
        "installed-style generated PalSchema schema supplied scalar field types",
        "generated schema exposed a safe addable property on an already-targeted row",
        "schema-backed PalSchema scalar edit and property addition survived save/readback",
        "clean official-package build included declared targets and excluded Lexeditor backups",
        "Pocketpair-style local test deployment used an owned ten-digit Workshop folder",
        "owned local Workshop deployment removed without touching source/build data",
        "owned package build reverted without touching project sources",
        "Info.json and PalSchema changed writes created recovery backups",
        "PalSchema JSONC patches stayed readable but changed-write disabled",
        "host-owned Palworld child service stopped cleanly",
    ]


PLUGIN = GamePlugin(
    plugin_id="palworld",
    name=DISPLAY_NAME,
    subtitle="Official mod packages",
    description="Author, build and locally test Palworld v0.7+ packages with schema-aware PalSchema patches while installed game data stays read-only.",
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
