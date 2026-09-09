from games.ff7r import theme
from games.ff7r.plugin import FF7RSession
from games.ff7r.themed_server import themed_editor_html
from service_session import request_json


def test_theme_fallback_is_proprietary_free_and_semantically_complete(tmp_path):
    game = tmp_path / "game"
    (game / "End" / "Content" / "Paks").mkdir(parents=True)
    data = tmp_path / "data"

    payload = theme.theme_payload(game, data, scan=True)

    assert payload["themeName"] == "ff7r"
    assert payload["assetMode"] == "fallback"
    assert payload["font"]["available"] is False
    assert payload["theme"]["accent"] == "#36b6ee"
    assert payload["theme"]["ff7r-background-image"] == "none"
    assert [row["slot"] for row in payload["sounds"]["rows"]] == list(theme.SOUND_SLOTS)
    assert not any(row["available"] for row in payload["sounds"]["rows"])


def test_installed_browser_ready_assets_are_copied_only_to_private_cache(tmp_path, monkeypatch):
    game = tmp_path / "game"
    paks = game / "End" / "Content" / "Paks"
    paks.mkdir(parents=True)
    pak = paks / "pakchunk0_s00-WindowsNoEditor.pak"
    pak.write_bytes(b"fixture")
    data = tmp_path / "data"

    entries = [
        "End/Content/GameContents/Menu/Resident/Font/SystemFontNormal.ttf",
        "End/Content/GameContents/Menu/Resident/Texture/MenuBackground.png",
        "End/Content/GameContents/Menu/Resident/Texture/MenuPanel.png",
        "End/Content/GameContents/Menu/Sound/MenuConfirm.wav",
        "End/Content/GameContents/Menu/Sound/MenuCancel.wav",
        "End/Content/GameContents/Menu/Sound/MenuCursor.wav",
        "End/Content/GameContents/Menu/Sound/MenuOpen.wav",
        "End/Content/GameContents/Menu/Sound/MenuClose.wav",
        "End/Content/GameContents/Menu/Sound/MenuSave.wav",
        # Cooked sources are reported for decoding, never served as web assets.
        "End/Content/GameContents/Menu/Resident/Font/SystemFontNormal.uasset",
        "End/Content/GameContents/Menu/Resident/Texture/T_MenuWindow.uasset",
    ]
    payloads = {entry: ("PAYLOAD:" + entry).encode() for entry in entries}
    monkeypatch.setattr(theme, "installed_paks", lambda _root: [pak])
    monkeypatch.setattr(theme, "list_pak", lambda _pak: entries)
    monkeypatch.setattr(theme, "get_file", lambda _pak, internal: payloads[internal])

    payload = theme.theme_payload(game, data, scan=True)

    assert payload["assetMode"] == "installed"
    assert payload["font"]["available"] is True
    assert payload["font"]["url"] == "/theme-assets/font.ttf"
    assert payload["textures"]["background"] == "/theme-assets/background.png"
    assert payload["textures"]["panel"] == "/theme-assets/panel.png"
    assert payload["sounds"]["available"] == len(theme.SOUND_SLOTS)
    assert all(row["url"].startswith("/theme-assets/sounds/") for row in payload["sounds"]["rows"])
    assert payload["font"]["cookedSourceCount"] == 1
    assert payload["textures"]["cookedSourceCount"] == 1

    root = theme.theme_cache_root(data)
    assert (root / "font.ttf").read_bytes() == payloads[entries[0]]
    assert not any(path.suffix in theme.COOKED_EXTENSIONS for path in root.rglob("*"))


def test_theme_asset_resolver_is_allowlisted_and_rejects_traversal(tmp_path):
    data = tmp_path / "data"
    root = theme.theme_cache_root(data)
    (root / "sounds").mkdir(parents=True)
    font = root / "font.woff2"
    font.write_bytes(b"font")
    confirm = root / "sounds" / "confirm.ogg"
    confirm.write_bytes(b"sound")
    secret = root / "secret.txt"
    secret.write_text("nope", encoding="utf-8")

    assert theme.theme_asset_file(data, "font.woff2") == font.resolve()
    assert theme.theme_asset_file(data, "sounds/confirm.ogg") == confirm.resolve()
    assert theme.theme_asset_file(data, "../secret.txt") is None
    assert theme.theme_asset_file(data, "sounds/../../secret.txt") is None
    assert theme.theme_asset_file(data, "secret.txt") is None
    assert theme.theme_asset_file(data, "sounds/not-a-slot.ogg") is None


def test_themed_server_injects_one_ff7r_style_and_script_without_editing_document_source():
    html = themed_editor_html()

    assert html.count('/theme/ff7r.css') == 1
    assert html.count('/theme/ff7r.js') == 1
    assert html.index('/shared/framework.css') < html.index('/theme/ff7r.css')
    assert html.index('/shared/framework.js') < html.index('/theme/ff7r.js')


def test_managed_ff7r_service_exposes_fallback_theme_contract(tmp_path):
    game = tmp_path / "game"
    (game / "End" / "Content" / "Paks").mkdir(parents=True)
    data = tmp_path / "data"
    project = tmp_path / "project"

    with FF7RSession({
        "LEXEDITOR_FF7R_ROOT": str(game),
        "LEXEDITOR_FF7R_DATA_ROOT": str(data),
        "LEXEDITOR_FF7R_PROJECT": str(project),
    }) as session:
        payload = request_json(session.url + "api/theme?scan=1")
        assert payload["themeName"] == "ff7r"
        assert payload["assetMode"] == "fallback"
        assert payload["bitmapFont"]["available"] is False
        assert [row["slot"] for row in payload["sounds"]["rows"]] == list(theme.SOUND_SLOTS)
