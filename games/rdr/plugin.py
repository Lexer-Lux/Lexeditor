"""RDR plugin lifecycle for the Lexeditor desktop shell."""

from __future__ import annotations

import json
import hashlib
import struct
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

from plugin_api import GameInstallSpec, GamePlugin, GitHubRepository, ModProjectSpec, PluginFont
from service_session import LocalPluginSession, request_json
from .extractor import ensure_rdr_data
from .paths import LEXEDITOR_ROOT, MOD_ROOT, PLUGIN_ROOT, PROJECT_ROOT, RDR2_FONT_ROOT, check as check_paths


def project_root() -> Path:
    return PROJECT_ROOT


def check() -> list[str]:
    return check_paths()


class RdrSession(LocalPluginSession):
    """One host-owned RDR editor service."""

    def __init__(self, extra_env: dict[str, str] | None = None):
        environment = {"LEXEDITOR_RDR_PROJECT": str(project_root())}
        environment.update(extra_env or {})
        super().__init__(
            module="games.rdr.server",
            plugin_id="rdr",
            app_root=LEXEDITOR_ROOT,
            check=check,
            port_env="LEXEDITOR_RDR_PORT",
            extra_env=environment,
        )


def launch() -> int:
    from desktop_host import run_host
    return run_host({"rdr": PLUGIN}, "rdr")


def smoke() -> list[str]:
    """Exercise identity, UI, and a temporary project save/readback."""
    with tempfile.TemporaryDirectory(prefix="lexeditor-rdr-") as temp_name:
        root = Path(temp_name)
        project = root / "project"
        mod = project / "mod"
        data = root / "data"
        prepared = data / "tune_d11generic" / "tune" / "ai"
        inventory_root = data / "content" / "content" / "init" / "inventory"
        gringo_raw_root = data / "gringores-unpacked" / "gringores"
        gringo_packed_root = data / "gringores" / "gringores"
        mod.mkdir(parents=True)
        prepared.mkdir(parents=True)
        inventory_root.mkdir(parents=True)
        gringo_raw_root.mkdir(parents=True)
        gringo_packed_root.mkdir(parents=True)
        source = prepared / "motives.xml"
        source.write_text("<?xml version=\"1.0\"?><motives><value>vanilla</value></motives>\n", encoding="utf-8")
        inventory = inventory_root / "inventory.xml"
        inventory_source = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<invManager><Types><!--keep-comment--><Item type="invGringoType">'
            '<Name content="ascii">TEST_ITEM</Name><FriendlyName content="ascii">Test item</FriendlyName>'
            '<MaxItemCount value="5"/><Unsupported keep="yes"><Nested value="untouched"/></Unsupported>'
            '</Item></Types></invManager>\n'
        )
        inventory.write_text(inventory_source, encoding="utf-8")
        dlc_inventory = inventory_root / "dlc_inventory.xml"
        dlc_inventory.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<invManagerDLC><Types><Item type="invGringoType">'
            '<Name content="ascii">DLC_TEST_ITEM</Name><FriendlyName content="ascii">DLC test</FriendlyName>'
            '<MaxItemCount value="1"/></Item></Types></invManagerDLC>\n',
            encoding="utf-8",
        )
        shop_raw = bytearray(4096)
        def u32(offset: int, value: int) -> None:
            struct.pack_into("<I", shop_raw, offset, value)
        u32(16, 0x50000080)
        u32(20, 0x00010001)
        u32(24, 0x50000084)
        u32(28, 0x00010001)
        u32(0x80, 0x12345678)
        u32(0x84, 0x50000100)
        u32(0x88, 0x50000160)
        u32(0x8C, 0x50000180)
        for index, offset in enumerate((0x1C0, 0x1CC, 0x1D8, 0x1EC)):
            u32(0x90 + index * 4, 0x50000000 | offset)
        u32(0x100 + 32, 0x50000300)
        u32(0x100 + 40, 0x50000088)
        u32(0x100 + 44, 0x00010001)
        u32(0x160, 0xD6F7F3F1)
        u32(0x160 + 8, 0x1C51E604)
        u32(0x160 + 16, 0x5000008C)
        u32(0x160 + 20, 0x00010001)
        u32(0x180, 0xB16C14A8)
        u32(0x180 + 16, 0x50000090)
        u32(0x180 + 20, 0x00040004)
        u32(0x1C0, 0x3EED2FB8)
        u32(0x1C4, 0xDE02D359)
        u32(0x1C8, 0x50000380)
        u32(0x1CC, 0x178DF99A)
        u32(0x1D0, 0x65E7F789)
        struct.pack_into("<f", shop_raw, 0x1D4, 1.25)
        u32(0x1D8, 0x7EB41668)
        u32(0x1DC, 0x7EBD2697)
        u32(0x1E4, 2)
        u32(0x1EC, 0x7EB41668)
        u32(0x1F0, 0x7992CBA6)
        u32(0x1F8, 10)
        shop_script = (
            b"content\\scripting\\gringo\\GringoBrains\\GringoBrainScripts\\Shopkeeper_Brain\0"
        )
        shop_item = b"ITEM_TEST_SHOP\0"
        shop_raw[0x300:0x300 + len(shop_script)] = shop_script
        shop_raw[0x380:0x380 + len(shop_item)] = shop_item
        (gringo_raw_root / "smoke.wgd").write_bytes(shop_raw)
        (gringo_packed_root / "smoke.wgd").write_bytes(b"RSC85 smoke fixture")
        settings_file = project / "LexerRDR.ini"
        settings_file.write_bytes(
            b"; keep comment\r\n[WeaponRadial]\r\nEnabled=true\r\n"
            b"TimeScale = 0.25 ; keep inline\r\nUnknownKey=keep\r\n"
        )
        loot_file = project / "LexerRDR.loot.json"
        # Synthetic contract values, never the user's private runtime configuration.
        from tools.rdr_test_support import loot_document as synthetic_loot_document
        loot_document = synthetic_loot_document()
        loot_file.write_text(json.dumps(loot_document, indent=2) + "\n", encoding="utf-8")
        with RdrSession({
            "LEXEDITOR_RDR_PROJECT": str(project),
            "LEXEDITOR_RDR_MOD_ROOT": str(mod),
            "LEXEDITOR_RDR_EXTRACT_ROOT": str(data),
            "LEXEDITOR_RDR_SETTINGS": str(settings_file),
            "LEXEDITOR_RDR_LOOT": str(loot_file),
            "RDR_GAME_ROOT": str(root / "game"),
            "LEXEDITOR_RDR_OPEN_URL_DRY_RUN": "1",
        }) as session:
            identity = request_json(session.url + "api/plugin")
            if identity.get("pluginId") != "rdr" or identity.get("windowHost") != "webview2":
                raise RuntimeError("RDR plugin returned the wrong managed identity")
            if Path(identity["projectRoot"]).resolve() != project:
                raise RuntimeError("RDR plugin reported the wrong project root")
            with urllib.request.urlopen(session.url, timeout=10) as response:
                html = response.read().decode("utf-8")
            if ('id="lexeditor-shell"' not in html or
                    '/shared/framework.js' not in html or
                    "Lexeditor - RDR" not in html):
                raise RuntimeError("RDR plugin did not serve the managed editor interface")
            if '{id:"files",label:"Files"}' in html or 'help:()=>navigate("datamap")' not in html:
                raise RuntimeError("RDR editor exposed a Files tab or omitted the Data Map button")
            data_map = request_json(session.url + "api/data-map")
            if (data_map.get("contract") != "Lexeditor.data-map"
                    or len(data_map.get("rows", [])) < 3000):
                raise RuntimeError("RDR Data Map did not expose the generated archive coverage")
            files = request_json(session.url + "api/files")
            if not any(row["path"] == "tune/ai/motives.xml" for row in files.get("rows", [])):
                raise RuntimeError("RDR plugin did not list prepared tuning data")
            query = urllib.parse.urlencode({"path": "tune/ai/motives.xml"})
            original = request_json(session.url + "api/file?" + query)
            if original.get("source") != "vanilla":
                raise RuntimeError("RDR plugin did not read the prepared vanilla file")
            changed = "<?xml version=\"1.0\"?><motives><value>project</value></motives>\n"
            saved = request_json(session.url + "api/file/save", {
                "path": "tune/ai/motives.xml",
                "text": changed,
                "encoding": "utf-8",
            })
            if saved.get("saved") != 1:
                raise RuntimeError("RDR plugin did not save one project override")
            reread = request_json(session.url + "api/file?" + query)
            if reread.get("source") != "project" or reread.get("text") != changed:
                raise RuntimeError("RDR project override did not read back")
            if source.read_text(encoding="utf-8").find("vanilla") < 0:
                raise RuntimeError("RDR save changed the prepared vanilla file")
            items = request_json(session.url + "api/items")
            item = next((row for row in items.get("rows", []) if row.get("name") == "TEST_ITEM"), None)
            if item is None:
                raise RuntimeError("RDR Items API did not expose the prepared base item")
            max_count = next((field for field in item.get("fields", [])
                              if field.get("field") == "MaxItemCount"), None)
            if max_count is None or max_count.get("control") != "number" or max_count.get("step") != 1:
                raise RuntimeError("RDR Items API did not expose the typed MaxItemCount control")
            shops = request_json(session.url + "api/shops")
            shop = next((row for row in shops.get("rows", [])
                         if row.get("name") == "ITEM_TEST_SHOP"), None)
            if (shop is None or shop.get("priceModifier") != 1.25
                    or shop.get("quantityPerPurchase") != 2
                    or shop.get("totalAvailableQuantity") != 10):
                raise RuntimeError("RDR Shops API did not decode the ShopInventory fixture")
            missions = request_json(session.url + "api/missions")
            if len(missions.get("missions", [])) != 57:
                raise RuntimeError("RDR Missions API did not expose all 57 resolved Story missions")
            reward_limits = missions.get("limits", {}).get("rewards", {})
            if (reward_limits.get("cash", {}).get("minimum") != 0
                    or reward_limits.get("fame", {}).get("minimum") != 0
                    or reward_limits.get("honor", {}).get("minimum") != -999999):
                raise RuntimeError("RDR Missions API exposed incorrect per-reward bounds")
            source_hashes = {
                str(PLUGIN_ROOT / "missions.generated.json"):
                hashlib.sha256((PLUGIN_ROOT / "missions.generated.json").read_bytes()).hexdigest()
            }
            mission_result = request_json(session.url + "api/missions/save", {
                "schemaVersion": 1,
                "contract": "LexerRDR.mission-rewards",
                "overrides": [{"id": 2, "rewards": {"cash": 321, "honor": -25}}],
            })
            if mission_result.get("saved") != 2:
                raise RuntimeError("RDR Missions API did not save two changed reward fields")
            mission_file = project / "LexerRDR.missions.json"
            mission_override = json.loads(mission_file.read_text(encoding="utf-8"))
            if mission_override.get("overrides") != [{"id": 2, "rewards": {"cash": 321, "honor": -25}}]:
                raise RuntimeError("RDR Missions save did not keep only changed reward fields")
            missions_after = request_json(session.url + "api/missions")
            mission_two = next(row for row in missions_after["missions"] if row["id"] == 2)
            if mission_two["rewards"]["cash"] != 321 or mission_two["rewards"]["honor"] != -25:
                raise RuntimeError("RDR Missions override did not read back")
            if any(hashlib.sha256(Path(source).read_bytes()).hexdigest() != digest
                   for source, digest in source_hashes.items()):
                raise RuntimeError("RDR Missions save changed the read-only generated reward table")
            dashboard = request_json(session.url + "api/dashboard")
            if dashboard.get("redHook", {}).get("installed"):
                raise RuntimeError("RDR plugin did not report the missing RedHook prerequisite")
            redhook = request_json(session.url + "api/redhook/open", {})
            if not redhook.get("dryRun") or redhook.get("opened"):
                raise RuntimeError("RDR RedHook link check did not stay in smoke-test mode")
            (root / "game").mkdir(parents=True, exist_ok=True)
            (root / "game" / "RedHook.dll").write_bytes(b"smoke")
            (root / "game" / "winmm.dll").write_bytes(b"smoke")
            redhook_ini = root / "game" / "RedHook.ini"
            redhook_ini.write_bytes(
                b"[RedHook]\r\nSkipIntroLogos=false ; keep inline\r\nInternalConsole=true\r\n"
            )
            configured = request_json(session.url + "api/redhook/configure", {})
            if configured.get("changed") != 1 or not configured.get(
                    "skipIntroLogos", {}).get("enabled"):
                raise RuntimeError("RDR plugin did not enable RedHook startup-logo skipping")
            if (b"SkipIntroLogos=true ; keep inline\r\n" not in redhook_ini.read_bytes()
                    or not redhook_ini.with_name("RedHook.ini.lexeditor.bak").is_file()):
                raise RuntimeError("RDR plugin did not preserve or back up RedHook.ini")
            item_result = request_json(session.url + "api/item/save", {
                "source": item["source"],
                "index": item["index"],
                "expectedName": item["name"],
                "edits": [{"field": "MaxItemCount", "value": "9"}],
            })
            if item_result.get("saved") != 1:
                raise RuntimeError("RDR Items API did not save one field")
            item_override = mod / "content" / "content" / "init" / "inventory" / "inventory.xml"
            item_text = item_override.read_text(encoding="utf-8")
            if ('MaxItemCount value="9"' not in item_text or '<!--keep-comment-->' not in item_text or
                    'Unsupported keep="yes"' not in item_text or 'Nested value="untouched"' not in item_text):
                raise RuntimeError("RDR Items save dropped an unsupported XML value or comment")
            if inventory.read_text(encoding="utf-8") != inventory_source:
                raise RuntimeError("RDR Items save changed the prepared inventory XML")
            settings = request_json(session.url + "api/settings")
            if not settings.get("available"):
                raise RuntimeError("RDR Settings API did not expose LexerRDR.ini")
            settings_result = request_json(session.url + "api/settings/save", {
                "edits": [{"section": "WeaponRadial", "key": "TimeScale", "value": "0.5"}],
            })
            if settings_result.get("saved") != 1:
                raise RuntimeError("RDR Settings API did not save one value")
            settings_bytes = settings_file.read_bytes()
            if (b"TimeScale = 0.5 ; keep inline\r\n" not in settings_bytes or
                    b"; keep comment\r\n" not in settings_bytes or b"UnknownKey=keep\r\n" not in settings_bytes):
                raise RuntimeError("RDR Settings save did not preserve comments, keys, or line endings")
            loot = request_json(session.url + "api/loot")
            if loot.get("label") != "ASI override":
                raise RuntimeError("RDR Loot API did not identify the ASI-owned project format")
            loot["document"]["corpseBonusItem"]["chancePercent"] = 11
            loot_result = request_json(session.url + "api/loot/save", {"document": loot["document"]})
            if loot_result.get("saved") != 1:
                raise RuntimeError("RDR Loot API did not save the ASI override")
            if json.loads(loot_file.read_text(encoding="utf-8"))["corpseBonusItem"]["chancePercent"] != 11:
                raise RuntimeError("RDR Loot ASI override did not read back")
        if not session.process or session.process.poll() is None:
            raise RuntimeError("RDR child service still runs after shutdown")
        if not session.wait_closed():
            raise RuntimeError("RDR child port is still open after shutdown")
    return [
        "RDR plugin identity and WebView2 host confirmed",
        "managed RDR interface and prepared file list served",
        "Files tab removed and generated Data Map exposed through the shared help button",
        "item, shop, mission, settings, and loot controls use schema-appropriate input types",
        "temporary project override saved and read back",
        "prepared vanilla source remained unchanged",
        "inventory field saved while comments and unsupported XML stayed intact",
        "ShopInventory item, price, purchase quantity, and stock decoded",
        "57 Story missions exposed with bounded cash, fame, and honor controls",
        "mission reward override saved only changed fields and left base sources unchanged",
        "missing RedHook notice and official-link action confirmed without opening a browser",
        "RedHook startup-logo setting enabled with a byte-preserving backup",
        "LexerRDR.ini saved atomically with comments and unknown keys intact",
        "schema-versioned loot ASI override saved and read back",
        "host-owned child service stopped cleanly",
    ]


PLUGIN = GamePlugin(
    plugin_id="rdr",
    name="Red Dead Redemption",
    subtitle="RDR",
    description="Edit RDR tuning, weapons, vehicles, AI, effects, population, and more.",
    accent="#a92b20",
    check=check,
    launch=launch,
    smoke=smoke,
    session_factory=RdrSession,
    github=GitHubRepository(
        full_name="Lexer-Lux/Lexers-Mod-For-RDR",
        authorized_logins=("Lexer-Lux",),
    ),
    projects=ModProjectSpec(
        root_env="LEXEDITOR_RDR_MOD_ROOT",
        default_root=MOD_ROOT,
        required_paths=(),
        template_root=MOD_ROOT,
    ),
    installation=GameInstallSpec(
        root_env="RDR_GAME_ROOT",
        data_env="LEXEDITOR_RDR_EXTRACT_ROOT",
        required_paths=("RDR.exe", "game/tune_d11generic.rpf", "game/content.rpf", "game/mapres.rpf"),
        steam_app_id="2668510",
        install_dir_names=("Red Dead Redemption",),
        default_roots=(
            Path(r"C:\Program Files (x86)\Steam\steamapps\common\Red Dead Redemption"),
            Path(r"D:\SteamLibrary\steamapps\common\Red Dead Redemption"),
        ),
        prepare=ensure_rdr_data,
    ),
    fonts=(
        PluginFont(
            font_id="redemption",
            name="Redemption",
            destination=PLUGIN_ROOT / "assets" / "fonts" / "Redemption.woff",
            source_url="https://media-rockstargames-com.akamaized.net/mfe6/prod/__common/fonts/d83fe1be4c1e7239c409db49a3850103.woff",
            sha256="a2e7903be5ebbad46801787c5dcb5964603ea4123aca0543786ae640c412fc3e",
            file_format="woff",
            alternatives=(RDR2_FONT_ROOT / "Redemption.ttf",),
        ),
        PluginFont(
            font_id="rdr-lino",
            name="RDR Lino",
            destination=PLUGIN_ROOT / "assets" / "fonts" / "RDRLino-Regular.rockstar.woff2",
            source_url="https://media-rockstargames-com.akamaized.net/mfe6/prod/__common/fonts/593253ebb2f8260c4005859f87ed4ca3.woff2",
            sha256="70ee112972cd7687782551044f872b10b1b787879dcb56b531c5e8977493fc08",
            file_format="woff2",
            alternatives=(RDR2_FONT_ROOT / "RDRLino-Regular.woff2",),
        ),
    ),
)
