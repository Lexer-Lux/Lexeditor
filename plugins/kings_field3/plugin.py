"""King's Field III native settings and source mods."""
from pathlib import Path
import tempfile
from core.plugin_api import GamePlugin
from core.plugin_manifest import install_spec, plugin_defaults
from core.service_session import LocalPluginSession
from core.native_source_mods import NativeSourceModAdapter
from core.native_port_settings import updated_ini
from .model import MODEL

ROOT = Path(__file__).resolve().parents[2]


def check() -> list[str]:
    return []


class KingsField3Session(LocalPluginSession):
    def __init__(self, extra_env=None):
        super().__init__(module="plugins.kings_field3.server", plugin_id="kings-field3",
                         app_root=ROOT, check=check, extra_env=extra_env)


def launch() -> int:
    from core.desktop_host import run_host
    return run_host({MODEL.descriptor["id"]: PLUGIN}, MODEL.descriptor["id"])


def smoke() -> list[str]:
    with tempfile.TemporaryDirectory(prefix="lexeditor-kf3-smoke-") as name:
        root = Path(name)
        raw = b"[RecompOne]\nkf3.renderdistance=16\nkf3.renderdistance.fade=4.5\nunknown=keep\n"
        (root / "interface.ini").write_bytes(raw)
        fields = {field["key"]: field["value"] for field in MODEL.preferences(root)["fields"]}
        if fields["kf3.renderdistance"] != 16 or fields["kf3.renderdistance.fade"] is not True:
            return ["Native distance settings did not decode"]
        if updated_ini(raw, {}) != raw:
            return ["Unchanged preferences did not preserve their bytes"]
    return []


PLUGIN = GamePlugin(**plugin_defaults(__file__), check=check, launch=launch,
                    cover_art=ROOT / "assets" / "covers" / "kf3.png",
                    smoke=smoke,
                    installation=install_spec(__file__), session_factory=KingsField3Session,
                    mod_adapter=NativeSourceModAdapter(MODEL))
