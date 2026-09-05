"""Offline cache and source contract for Lexeditor issue 22."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import sys
import tempfile

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import discover_plugins  # noqa: E402
from cover_art import CoverArtCache  # noqa: E402


def jpeg() -> bytes:
    stream = BytesIO()
    Image.new("RGB", (600, 900), "#39445b").save(stream, format="JPEG")
    return stream.getvalue()


def main() -> int:
    plugins = discover_plugins()
    chooser = (ROOT / "ui" / "chooser.html").read_text(encoding="utf-8")
    desktop = (ROOT / "desktop_host.py").read_text(encoding="utf-8")

    for required in (
        "aspect-ratio:2/3", 'class="state-indicator"',
        'class="game-hover"', 'class="game-action-icon"', 'class="game-folder-button"',
        'plugin.coverArt?.state==="loading"', 'LexeditorUI.openGameFolder',
        'class="game-version"', 'plugin.gameVersion', '#00000078',
        'existing=new Map', 'updateCard(card,plugin)', '"added":"Ready"',
        '"warning":"Broken"', '"not-added":"Absent"',
        'actionSymbols', 'class="state-label"', '✍️', '🛠️', '🔍',
        'id="home-github"', 'id="home-twitter"', 'class="twitter-bird"',
        'class="twitter-x"', 'open_home_link(target)', '--lex-chooser-menu-height',
        'mainMenuHeightPercent',
        'absentGameDesaturationPercent', 'state-not-added .game-cover',
        '"not-added":"✕"', 'class="game-name"', 'restart_lexeditor()',
    ):
        assert required in chooser, f"the main menu is missing {required}"
    assert 'class="game-caption"' not in chooser
    assert "Click to open" not in chooser and "Click to repair" not in chooser
    assert "Choose a game" not in chooser
    assert "game-shade" not in chooser and "linear-gradient(to bottom" not in chooser
    assert ("overflow:visible" in chooser and "--lex-game-row-gap:52px" in chooser
            and "bottom:calc(100% + 3px)" in chooser
            and "background:transparent" in chooser
            and "box-shadow:none" in chooser), \
        "the hovered game name must use the transparent row gap above the cover"
    assert "translateY(calc(-100% - 7px))" not in chooser, \
        "the old content-sized title translation must not return"
    game_hover_rule = chooser[chooser.index(".game:hover"):chooser.index(".state-added")]
    assert "outline:" not in game_hover_rule, "hover must not draw a second card outline"
    assert "border-radius:10px" not in chooser, "box art must keep square corners"
    assert "games.replaceChildren" not in chooser, "scan refresh remounts every game card"
    assert 'class="font-control"' not in chooser, "font status belongs in the game Info page"
    assert 'class="hover-path"' not in chooser, "the full game path must not cover the box art"
    assert '"gameVersion": game_version(' in desktop
    assert '"github": "https://github.com/Lexer-Lux/Lexeditor"' in desktop
    assert '"twitter": "https://twitter.com/LexerLux"' in desktop
    assert "HOME_LINKS.get(key)" in desktop, "Home links must use the host allowlist"
    assert plugins["blank"].cover_art.name == "blank-game-cover.png"

    with tempfile.TemporaryDirectory(prefix="lexeditor-cover-contract-", ignore_cleanup_errors=True) as temp:
        cache = CoverArtCache(
            plugins, root=Path(temp), fetcher=lambda _url: jpeg(), auto_download=True,
            steam_roots=(),
        )
        assert cache.wait(10), "cover-art workers did not finish"
        for plugin_id in plugins:
            state = cache.snapshot(plugin_id)
            assert state["state"] == "ready", state
            path = Path(state["uri"].removeprefix("file:///"))
            expected_size = (1024, 1536) if plugin_id == "blank" else (600, 900)
            assert path.is_file() and (state["width"], state["height"]) == expected_size

    def offline(_url: str) -> bytes:
        raise OSError("offline")

    with tempfile.TemporaryDirectory(prefix="lexeditor-cover-offline-", ignore_cleanup_errors=True) as temp:
        cache = CoverArtCache(
            plugins, root=Path(temp), fetcher=offline, auto_download=True,
            steam_roots=(),
        )
        assert cache.wait(10), "offline cover-art workers did not finish"
        assert cache.snapshot("blank")["state"] == "ready"
        assert all(cache.snapshot(plugin_id)["state"] == "missing"
                   for plugin_id in plugins if plugin_id != "blank")

    with tempfile.TemporaryDirectory(prefix="lexeditor-local-steam-art-", ignore_cleanup_errors=True) as temp:
        root = Path(temp)
        capsule = root / "appcache" / "librarycache" / "3837340" / "hash" / "library_capsule.jpg"
        capsule.parent.mkdir(parents=True)
        capsule.write_bytes(jpeg())
        calls = []
        cache = CoverArtCache(
            {"ff7": plugins["ff7"]}, root=root / "private",
            fetcher=lambda url: calls.append(url) or offline(url), auto_download=True,
            steam_roots=(root,),
        )
        assert cache.wait(10)
        state = cache.snapshot("ff7")
        assert state["state"] == "ready" and state["width"] == 600 and not calls, state

    print("Main-menu box-art cache, offline fallback, status, and font contracts passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
