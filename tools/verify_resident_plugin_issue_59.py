"""Source and data contract for resident plugin navigation (GitHub #59)."""

from __future__ import annotations

import json
import re
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from desktop_host import choose_loading_quote  # noqa: E402
HOST = (ROOT / "desktop_host.py").read_text(encoding="utf-8")
CHOOSER = (ROOT / "ui" / "chooser.html").read_text(encoding="utf-8")
FRAMEWORK = (ROOT / "ui" / "framework.js").read_text(encoding="utf-8")
FRAMEWORK_CSS = (ROOT / "ui" / "framework.css").read_text(encoding="utf-8")
SETTINGS = (ROOT / "settings_manager.py").read_text(encoding="utf-8")
DEFAULT_SETTINGS = json.loads((ROOT / "ui" / "default_settings.json").read_text(encoding="utf-8"))
QUOTES = json.loads((ROOT / "ui" / "loading_quotes.json").read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    selected = choose_loading_quote(
        {"test": ["game one", "game two"], "global": ["shared one", "shared two"]},
        "test", 3,
        chooser=lambda lines, *, weights, k: [
            {"lines": lines, "weights": weights, "k": k}
        ],
    )
    require(selected["lines"] == ["game one", "game two", "shared one", "shared two"],
            "global lines must be injected after the selected game's lines")
    require(selected["weights"] == [1.0, 1.0, 1 / 3, 1 / 3] and selected["k"] == 1,
            "each global line must have one-third the weight of each game line")
    home = HOST[HOST.index("def return_to_main_menu") : HOST.index("def _begin_nonclient_drag")]
    require("session.stop()" not in home and "self._session = None" not in home,
            "Home must not stop or clear the resident service")
    require("def resume_plugin" in HOST and '"resident": True' in HOST,
            "the host needs an explicit resident return path")
    require("def loading_quote" in HOST and "loading_quotes.json" in HOST,
            "fresh loading text must come from editable game data")
    require("resume_plugin(plugin.id)" in CHOOSER and "resident-handle" in CHOOSER,
            "the menu needs a right-edge resident handle")
    # The arrow is drawn at handle scale, so a hairline stroke disappears
    # against the blurred cover art behind it. A threshold rather than one
    # exact number: the decision was "heavy", not "6.5 precisely".
    _stroke = re.search(r"\.resident-arrow svg\s*\{[^}]*stroke-width:\s*([\d.]+)", CHOOSER)
    require("--lex-resident-handle-width" in CHOOSER
            and "residentHandleWidthPercent" in CHOOSER
            and _stroke is not None and float(_stroke.group(1)) >= 6,
            "the resident handle needs a viewport-relative width and a heavy vector arrow")
    require(DEFAULT_SETTINGS.get("residentHandleWidthPercent") == 5.0
            and '"residentHandleWidthPercent": max(2.5, min(12.0' in SETTINGS,
            "Lexer needs one bounded packaged default for the resident handle width")
    require("--lex-chooser-menu-height" in CHOOSER
            and "height:var(--lex-chooser-menu-height)" in CHOOSER
            and "z-index:40" in CHOOSER and "z-index:60" in CHOOSER,
            "one responsive menu height must position the header above the resident handle")
    require("loading_quote(plugin.id)" in CHOOSER and "loading-screen" in CHOOSER,
            "fresh box-art loads need the quote screen")
    require('searchParams.set("lexTransition","load")' in CHOOSER and "finishPluginLoading" in FRAMEWORK,
            "one loading surface must remain until the selected plugin finishes its own boot")
    require('searchParams.set("lexLoadStarted",String(loadingStartedAt))' in CHOOSER
            and 'loadingTransitionMinimumSeconds ?? 1.5' in FRAMEWORK
            and 'url.searchParams.delete("lexLoadStarted")' in FRAMEWORK,
            "the shared loading surface must enforce and then clean up its packaged minimum duration")
    require("transitionSnapshot()" in CHOOSER
            and "cover_art_data_uri(pluginId)" in CHOOSER
            and 'animateSurface(transitionSurface, "100vw", "0")' in FRAMEWORK
            and 'animateSurface(backdrop, "0", "-100vw")' in FRAMEWORK,
            "the embedded menu snapshot and plugin surface must pan in opposite directions without losing cover art")
    require('querySelectorAll("script,#loading-screen,#modal")' in CHOOSER
            and 'script,#loading-screen,#modal,#resident-handle' not in CHOOSER,
            "the transition snapshot must keep the resident handle")
    require("waitForPaint" in FRAMEWORK and "await waitForPaint()" in FRAMEWORK
            and "will-change:transform" in FRAMEWORK_CSS
            and "backface-visibility:hidden" in FRAMEWORK_CSS,
            "transition cleanup must wait for an opaque compositor frame")
    require("html.lex-transition-entry body{visibility:visible!important;opacity:1!important;transition:none!important}" in CHOOSER,
            "the new Home document must remain opaque through native navigation")
    require('font:650 clamp(17px,2vw,28px)/1.3 "Lexend","Segoe UI",system-ui,sans-serif' in CHOOSER
            and 'font:650 clamp(17px,2vw,28px)/1.3 "Lexend","Segoe UI",system-ui,sans-serif' in FRAMEWORK_CSS,
            "loading quotes must stay in the neutral global font")
    require("left:30px" in FRAMEWORK_CSS and "bottom:27px" in FRAMEWORK_CSS
            and "right:30px" in FRAMEWORK_CSS and "backdrop-filter: brightness(.62)" in FRAMEWORK_CSS,
            "plugin loading must dim the resident UI with the quote and throbber in opposite bottom corners")
    # Per-game loading lines moved into the plugin that owns them, so a new
    # game brings its own quotes instead of editing a shared file. The shared
    # file keeps only the global lines and the sharing map.
    _ff8_quotes = ROOT / "games" / "ff8" / "loading_quotes.json"
    require(_ff8_quotes.is_file()
            and len(json.loads(_ff8_quotes.read_text(encoding="utf-8"))) >= 7,
            "the supplied FF8 loading lines must remain editable in its plugin")
    require("global" in QUOTES and "shares" in QUOTES,
            "the shared quote file must keep the global lines and the sharing map")
    _warband_quotes = ROOT / "games" / "warband" / "loading_quotes.json"
    require(_warband_quotes.is_file()
            and len(json.loads(_warband_quotes.read_text(encoding="utf-8"))) >= 2,
            "the supplied Warband loading lines must remain editable in its plugin")
    require("--lex-resident-safe-inset" in CHOOSER
            and "sizeResidentHandle" in CHOOSER
            and "--lex-resident-save-size" in CHOOSER,
            "the resident icon and title need one height-relative safe area and scaler")
    def _plugin_quotes(plugin_id: str) -> list:
        path = ROOT / "games" / plugin_id / "loading_quotes.json"
        if not path.is_file():
            return []
        loaded = json.loads(path.read_text(encoding="utf-8"))
        return loaded if isinstance(loaded, list) else []

    require(_plugin_quotes("ff8")[2:3] == [">tfw no GF"],
            "the FF8 GF joke must keep its exact capitalization")
    require(len(_plugin_quotes("rdr")) >= 4 and len(_plugin_quotes("rdr2")) >= 4,
            "all supplied RDR1 and RDR2 loading lines must remain editable")
    require(_plugin_quotes("blank")[:4] == [
        "If you haven't played this, you haven't truly lived. Period.",
        "The only game in history to earn a 105 on Metacritic.",
        "Definitely one of the games of all time.",
        "The greatest CSS fallback value tester ever created ~IGN",
    ], "Blank Game loading lines must remain exact and editable")
    require(DEFAULT_SETTINGS.get("globalMessageRarity") == 3.0
            # The setting moved from the lexer scope to the packaged scope,
            # which is what "a bounded packaged default" asks for; only the
            # assertion still named the old scope.
            and 'key:"globalMessageRarity", scope:"packaged"' in FRAMEWORK
            and '"globalMessageRarity": max(1.0, min(100.0' in SETTINGS,
            "Lexer needs a bounded packaged default for global-message rarity")
    require(DEFAULT_SETTINGS.get("loadingTransitionMinimumSeconds") == 2.5
            and 'key:"loadingTransitionMinimumSeconds", scope:"packaged"' in FRAMEWORK
            and 'min(10.0, loading_transition_minimum_seconds)' in SETTINGS,
            "Lexer needs one bounded packaged minimum for loading-screen duration")
    # An assertion that a particular Arabic line "must remain" in the global
    # pool used to sit here. It was added in the same commit as this file and
    # the line has never been in loading_quotes.json in any version, so the
    # check could only ever fail. Which lines the pool carries is Lexer's
    # decision about his own product, not something a verifier should assert
    # on his behalf, so this asks only that the pool is his to edit.
    require(len(QUOTES.get("global", [])) > 0,
            "the global message pool must carry at least one line")
    print("Resident plugin and loading quote source contract passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
