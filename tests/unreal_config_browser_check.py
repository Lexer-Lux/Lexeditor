"""Rendered Engine Config acceptance for both Unreal games (issue 478).

Uses the real loopback services with synthetic projects and Engine.ini
fixtures. No installed game is required. Proves the one shared panel renders,
saves through both Tweaks pages, and stays readable at a small window size and
a large UI scale.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from ff7r2_fixture import (  # noqa: E402
    battle_item_possession_fixture,
    battle_player_parameter_fixture,
    fixture,
)
from plugins.ff7r.plugin import FF7RSession  # noqa: E402
from plugins.ff7r2.plugin import Ff7r2Session  # noqa: E402

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "out" / "unreal-config-browser"
OUT.mkdir(parents=True, exist_ok=True)

PLAYER = Path("End/Content/DataObject/Resident/PlayerParameter.uasset")
BATTLE_PLAYER = Path("End/Content/DataObject/Resident/BattlePlayerParameter.uasset")
BATTLE_ITEM = Path("End/Content/DataObject/Resident/BattleItemPossession.uasset")


def launch(playwright):
    return playwright.chromium.launch(
        executable_path=shutil.which("chromium") or None,
        headless=True,
        args=["--no-sandbox"],
    )


def overflow_x(page) -> dict:
    return page.evaluate("""()=>({
      scroll: document.scrollingElement.scrollWidth,
      inner: window.innerWidth,
    })""")


def reveal(page, locator, *, pages: int = 12) -> None:
    """Turn tweaks-pager pages until the target is on screen, like a reader."""
    pager = page.locator(".lex-tweaks-pages")
    for _ in range(pages):
        if locator.first.is_visible():
            return
        nxt = pager.get_by_role("button", name="Next page")
        if nxt.count() and nxt.first.is_enabled():
            nxt.first.click()
        else:
            first = pager.get_by_role("button", name="First page")
            if first.count() == 0 or not first.first.is_enabled():
                break
            first.first.click()
        page.wait_for_timeout(150)
    expect(locator.first).to_be_visible()


def check_engine_panel(page, ini: Path, *, name: str) -> None:
    """The shared panel renders, saves, and fits small and scaled windows."""
    reveal(page, page.get_by_text("ENGINE CONFIG", exact=True))
    motion = page.locator('input[aria-label="Motion blur"]')
    reveal(page, motion)
    save = page.get_by_role("button", name="Save settings")
    reveal(page, save)
    expect(save).to_be_disabled()
    reveal(page, motion)
    motion.fill("2")
    # Tab cycles subtabs Lexeditor-wide, so committing means leaving the
    # field the way a mouse user does: blur it.
    motion.evaluate("(el) => el.blur()")
    # Editing re-renders the page back to page one; the draft survives, so
    # page over to Save settings like a reader would.
    reveal(page, save)
    expect(save).to_be_enabled()
    save.click()
    # Saving re-renders back to page one, so the file reaching disk — not the
    # button state on a later page — proves the round trip.
    deadline = time.monotonic() + 30
    while "r.MotionBlurQuality=2" not in ini.read_text(encoding="utf-8"):
        assert time.monotonic() < deadline, \
            "Engine Config save did not reach Engine.ini"
        page.wait_for_timeout(200)
    reveal(page, save)
    expect(save).to_be_disabled()
    page.screenshot(path=str(OUT / f"{name}-engine.png"), full_page=True)

    page.set_viewport_size({"width": 800, "height": 600})
    page.wait_for_timeout(300)
    small = overflow_x(page)
    assert small["scroll"] <= small["inner"] + 2, small
    reveal(page, page.get_by_text("ENGINE CONFIG", exact=True))
    reveal(page, page.locator('input[aria-label="Motion blur"]'))
    page.screenshot(path=str(OUT / f"{name}-engine-small.png"), full_page=True)

    page.set_viewport_size({"width": 1440, "height": 900})
    page.evaluate('document.documentElement.style.zoom="150%"')
    page.wait_for_timeout(300)
    reveal(page, page.get_by_text("ENGINE CONFIG", exact=True))
    reveal(page, page.locator('input[aria-label="Motion blur"]'))
    # CSS zoom approximates desktop-host UI scale. A full-page capture
    # multiplies Chromium's document height and adds an artificial blank tail
    # that is not visible in the host.
    page.screenshot(path=str(OUT / f"{name}-engine-150-percent.png"), full_page=False)
    page.evaluate('document.documentElement.style.zoom="100%"')


def check_rebirth() -> None:
    with tempfile.TemporaryDirectory(prefix="lexeditor-unreal-browser-") as temp_name:
        temp = Path(temp_name)
        project = temp / "RebirthBrowser"
        project.mkdir()
        (project / "lexeditor-project.json").write_text(
            '{"format":1,"game":"ff7r2"}\n', encoding="utf-8")
        source = project / "source" / PLAYER
        source.parent.mkdir(parents=True)
        source.write_bytes(fixture())
        battle_player_source = project / "source" / BATTLE_PLAYER
        battle_player_source.parent.mkdir(parents=True, exist_ok=True)
        battle_player_source.write_bytes(battle_player_parameter_fixture())
        battle_source = project / "source" / BATTLE_ITEM
        battle_source.parent.mkdir(parents=True, exist_ok=True)
        battle_source.write_bytes(battle_item_possession_fixture())
        ini = temp / "Engine.ini"
        ini.write_text("[SystemSettings]\nr.BloomQuality=5\n", encoding="utf-8")
        environment = {
            "LEXEDITOR_FF7R2_PROJECT": str(project),
            "LEXEDITOR_FF7R2_ENGINE_INI": str(ini),
        }
        errors = []
        with Ff7r2Session(environment) as session:
            with sync_playwright() as playwright:
                browser = launch(playwright)
                try:
                    page = browser.new_page(viewport={"width": 1440, "height": 900})
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto(session.url, wait_until="domcontentloaded")
                    page.wait_for_selector(".lex-paged-list-detail")
                    page.locator(".lex-plugin-loading-screen").wait_for(
                        state="detached", timeout=10000)
                    page.evaluate('navigate("tweaks")')
                    page.get_by_role("tab", name="Engine Config").click()
                    check_engine_panel(page, ini, name="rebirth")
                    page.close()
                finally:
                    browser.close()
        assert "r.MotionBlurQuality=2" in ini.read_text(encoding="utf-8")
        assert "r.BloomQuality=5" in ini.read_text(encoding="utf-8")
        assert not errors, errors


def check_remake() -> None:
    with tempfile.TemporaryDirectory(prefix="lexeditor-unreal-browser-") as temp_name:
        temp = Path(temp_name)
        game = temp / "game"
        (game / "End" / "Content" / "Paks").mkdir(parents=True)
        fixture_root = temp / "fixture" / "End" / "Content" / "GameContents" / "DataObject"
        fixture_root.mkdir(parents=True)
        (fixture_root / "Equipment.uasset").write_bytes(b"fixture")
        (fixture_root / "Equipment.uexp").write_bytes(b"fixture")
        ini = temp / "Engine.ini"
        ini.write_text("[SystemSettings]\nr.BloomQuality=5\n", encoding="utf-8")
        environment = {
            "LEXEDITOR_FF7R_ROOT": str(game),
            "LEXEDITOR_FF7R_DATA_ROOT": str(temp / "data"),
            "LEXEDITOR_FF7R_PROJECT": str(temp / "project"),
            "LEXEDITOR_FF7R_ENGINE_INI": str(ini),
            "LEXEDITOR_FF7R_TEST_DATAOBJECTS": str(temp / "fixture"),
        }
        errors = []
        with FF7RSession(environment) as session:
            with sync_playwright() as playwright:
                browser = launch(playwright)
                try:
                    page = browser.new_page(viewport={"width": 1440, "height": 900})
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto(session.url, wait_until="domcontentloaded")
                    page.locator(".lex-plugin-loading-screen").wait_for(
                        state="detached", timeout=30000)
                    page.evaluate('navigate("tweaks")')
                    page.wait_for_function(
                        "()=>document.body.textContent.includes('ENGINE CONFIG')",
                        timeout=60000)
                    page.wait_for_function(
                        "()=>typeof state==='undefined'||!state.tweaksPending",
                        timeout=120000)
                    reveal(page, page.get_by_text("INI UNLOCKER", exact=True))
                    check_engine_panel(page, ini, name="remake")
                    page.close()
                finally:
                    browser.close()
        assert "r.MotionBlurQuality=2" in ini.read_text(encoding="utf-8")
        assert "r.BloomQuality=5" in ini.read_text(encoding="utf-8")
        assert not errors, errors


check_rebirth()
check_remake()
print("Unreal Engine Config rendered browser acceptance passed")
