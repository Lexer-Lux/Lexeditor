"""Native category boundaries and rendered ability identity across views."""
from pathlib import Path
import sys
import tempfile
import json

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, r"C:\RDR2Mod\tools\reverse-engineering")
from games.ff8 import formats, game_icons
from games.ff8.plugin import FF8Session
from render_crime_editors_55_62 import wait_eval
from tools.verify_panel_layout_visual_46 import browser_session, close_browser, screenshot


def main():
    previous = 0
    for category, limit in enumerate(game_icons.ABILITY_LIMITS):
        for value in (previous, limit - 1):
            assert game_icons.ability_identity(value)["iconId"] == 216 + category
        previous = limit
    for value in (-1, 116, 255):
        assert game_icons.ability_identity(value)["iconId"] is None
    game_icons.ensure_icons()
    for section in formats.ABILITY_SECTIONS:
        for row in formats.kernel_rows(section)["rows"]:
            assert game_icons.icon_path(row["iconId"]).is_file()
    profile = browser = cdp = None
    try:
        profile, browser, cdp = browser_session()
        with tempfile.TemporaryDirectory(prefix="ff8-ability-icons-") as project:
            with FF8Session({"LEXEDITOR_FF8_PROJECT": project}) as session:
                cdp.call("Page.navigate", {"url": session.url})
                wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 90)
                results = []
                for view, icon in zip(("abilityJunction", "abilityCommand", "abilityStat", "abilityCharacter", "abilityParty", "abilityGf", "abilityMenu"), range(216, 223)):
                    cdp.eval(f"state.abilityTab={json.dumps(view)};navigate('abilities')")
                    wait_eval(cdp, "[...document.querySelectorAll('.ff8-ability-icon img')].length>1&&[...document.querySelectorAll('.ff8-ability-icon img')].every(i=>i.complete&&i.naturalWidth>0)", 15)
                    rows = cdp.eval("[...document.querySelectorAll('.ff8-ability-icon img')].map(i=>({src:i.getAttribute('src'),width:i.getBoundingClientRect().width}))")
                    assert all(r["src"] == f"/assets/icons/{icon}.png" and r["width"] > 0 for r in rows), rows
                    results.append({"view": view, "icons": len(rows)})
                screenshot(cdp, "github-95-abilities.png")
                cdp.eval("navigate('gfs')")
                wait_eval(cdp, "document.querySelectorAll('.ff8-ability-select').length>0", 20)
                wait_eval(cdp, "[...document.querySelectorAll('.ff8-ability-select img')].every(i=>i.complete&&i.naturalWidth>0)", 15)
                assert cdp.eval("document.querySelectorAll('.ff8-ability-select img').length") > 0
                screenshot(cdp, "github-95-gf-selectors.png")
                print(json.dumps(results))
    finally:
        close_browser(profile, browser, cdp)


if __name__ == "__main__":
    main()
