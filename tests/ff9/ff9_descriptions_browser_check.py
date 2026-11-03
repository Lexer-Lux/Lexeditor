"""FF9 descriptions edit in place and save to the project text overlay.

Synthetic Unity message archives plus synthetic Memoria CSVs only. An item
row shows its installed help text in an enabled box; typing, saving and
reloading round-trips through the FF9_Data overlay while vanilla stays the
restore value. Support abilities attach the same way.
"""
from __future__ import annotations

DEV_CACHE = __import__("pathlib").Path(__import__("tempfile").gettempdir()) / "lexeditor-dev"
import hashlib
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "ff9"))
from ff9_message_fixture import make_message_archives

from plugins.ff9 import memoria_baseline
from plugins.ff9.plugin import FF9Session

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else DEV_CACHE / "ff9-descriptions"
OUT.mkdir(parents=True, exist_ok=True)


def items_csv() -> bytes:
    rows = []
    for item_id in range(36):
        price = 250 + item_id
        rows.append(
            f"{item_id};{item_id};-1;-1;{price};{price//2};0;0;1;0;;"
            + ";".join("1" if flag == 0 else "0" for flag in range(8))
            + f";{item_id};" + ";".join("1" if char == 0 else "0" for char in range(12))
            + f";# Item {item_id:02d}\n"
        )
    return (
        "# Id;WeaponId;ArmorId;EffectId;Price;SellingPrice;GraphicsId;ColorId;Quality;BonusId;AbilityIds;"
        "Weapon;Armlet;Helmet;Armor;Accessory;Item;Gem;Usable;Order;Zidane;Vivi;Garnet;Steiner;Freya;Quina;Eiko;Amarant;Cinna;Marcus;Blank;Beatrix\n"
        "# Int32;Int32;Int32;Int32;UInt32;Int32;UInt8;UInt8;Single;Int32;Ability[];"
        "Bit;Bit;Bit;Bit;Bit;Bit;Bit;Bit;Single;Bit;Bit;Bit;Bit;Bit;Bit;Bit;Bit;Bit;Bit;Bit;Bit\n"
        + "".join(rows)
    ).encode()


def csv_for(relative: str) -> bytes:
    if relative == "Items/Items.csv":
        return items_csv()
    if relative == "Characters/Abilities/AbilityGems.csv":
        return b"# Id;Gems\n# Int32;Int32\n1;2;# Auto-Reflect\n"
    return b"# Id;Value\n# Int32;UInt8\n0;1;# Synthetic\n"


def wait_loaded(page):
    page.wait_for_function("!document.documentElement.classList.contains('lex-loading-live')")
    page.locator(".lex-plugin-loading-screen").wait_for(state="detached")


with tempfile.TemporaryDirectory(prefix="lexeditor-ff9-descriptions-") as name:
    temp = Path(name)
    game, project, data_root = temp / "game", temp / "project", temp / "data"
    for relative in ("FF9_Launcher.exe", "x64/FF9.exe", "x64/FF9_Data/Managed/Assembly-CSharp.dll"):
        target = game / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"synthetic")
    data_dir = game / "x64" / "FF9_Data"
    main, resources = make_message_archives({
        "items": [f"Item {index:02d} help text." for index in range(36)],
        "abilities": ["Support zero.", "Auto-Reflect help."],
    })
    (data_dir / "mainData").write_bytes(main)
    (data_dir / "resources.assets").write_bytes(resources)
    (project / "StreamingAssets/Data").mkdir(parents=True)

    hashes = {}
    for relative in memoria_baseline.FILES:
        payload = csv_for(relative)
        target = data_root / "StreamingAssets/Data" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        hashes[relative] = hashlib.sha256(payload).hexdigest()

    shim = temp / "shim"
    shim.mkdir()
    (shim / "sitecustomize.py").write_text(
        "from plugins.ff9 import memoria_baseline as b\n" + f"b.FILES={hashes!r}\nb._last=None\n",
        encoding="utf-8",
    )
    separator = ";" if sys.platform == "win32" else ":"
    env = {
        "LEXEDITOR_FF9_ROOT": str(game),
        "LEXEDITOR_FF9_DATA_ROOT": str(data_root),
        "LEXEDITOR_FF9_PROJECT": str(project),
        "LOCALAPPDATA": str(temp / "local"),
        "PYTHONPATH": str(shim) + separator + str(ROOT),
    }
    errors = []
    with FF9Session(env) as session, sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(session.url, wait_until="domcontentloaded")
            page.wait_for_function("typeof state==='object'&&state.dashboard&&typeof shell==='object'")
            page.wait_for_selector(".lex-paged-list-detail")
            wait_loaded(page)
            page.locator(".lex-column-list-row").first.click()
            page.wait_for_selector(".ff9-detail")
            area = page.locator(".ff9-detail textarea").first
            expect(area).to_have_value("Item 00 help text.")
            expect(area).to_be_enabled()
            save = page.locator("#global-save")

            area.fill("Item 00 edited help.")
            expect(save).to_be_enabled()
            save.click()
            page.wait_for_function("dirtyCount()===0")
            overlay = project / "FF9_Data" / "EmbeddedAsset" / "Text" / "US" / "item" / "itm_help.mes"
            assert overlay.is_file(), overlay
            assert b"Item 00 edited help." in overlay.read_bytes()
            page.reload(wait_until="domcontentloaded")
            page.wait_for_selector(".lex-paged-list-detail")
            wait_loaded(page)
            page.locator(".lex-column-list-row").first.click()
            page.wait_for_selector(".ff9-detail")
            area = page.locator(".ff9-detail textarea").first
            expect(area).to_have_value("Item 00 edited help.")
            page.screenshot(path=str(OUT / "ff9-description-saved.png"), full_page=True)

            page.evaluate("navigate('abilities')")
            page.wait_for_function("state.tab==='abilities'&&(state.datasets.abilities?.rows?.length>0)")
            page.locator(".lex-column-list-row").first.click()
            page.wait_for_selector(".ff9-detail")
            area = page.locator(".ff9-detail textarea").first
            expect(area).to_have_value("Auto-Reflect help.")
            expect(area).to_be_enabled()
            assert not errors, errors[:3]
            print("FF9 descriptions: edit, save and reload passed.")
        finally:
            browser.close()
