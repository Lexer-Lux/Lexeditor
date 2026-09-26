"""Rendered FF9 acceptance using the real loopback service and synthetic fixtures only."""
from __future__ import annotations

# Dev caches and outputs live in the temp folder, never in the checkout.
DEV_CACHE = __import__("pathlib").Path(__import__("tempfile").gettempdir()) / "lexeditor-dev"
import hashlib
import json
from pathlib import Path
import runpy
import shutil
import sys
import tempfile

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from plugins.ff9 import memoria_baseline
from plugins.ff9.plugin import FF9Session

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else DEV_CACHE / "ff9-browser"
OUT.mkdir(parents=True, exist_ok=True)
archive = runpy.run_path(str(ROOT / "tests" / "ff9" / "test_ff9_battle_scene.py"))["archive"]
walkmesh_archive = runpy.run_path(str(ROOT / "tests" / "ff9" / "test_ff9_field_walkmesh.py"))["archive"]


def csv_bytes(relative: str) -> bytes:
    if relative == "Items/Items.csv":
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
    if relative == "Battle/Actions.csv":
        return (
            "# Comment;id;menuWindow;targets;defaultAlly;forDead;defaultOnDead;defaultCamera;animationId1;animationId2;scriptId;power;elements;rate;category;statusIndex;mp;type;commandTitle\n"
            "# ;Int32;UInt8;UInt8;Boolean;Boolean;Boolean;Boolean;Int16;UInt16;Int32;Int32;UInt8;Int32;UInt8;Int32;Int32;UInt8;UInt8\n"
            "Fire;1;Hp(1);SingleEnemy(2);0;0;0;0;1;2;3;16;1;100;0;0;6;1;255;# Fire\n"
            "Cure;2;Hp(1);ManyAny(3);1;1;0;0;9;8;10;16;0;0;71;0;10;1;255;# Cure\n"
        ).encode()
    if relative == "Battle/StatusData.csv":
        return (
            "# Comment;Id;Priority(unused);OprCount(tick);ContiCount(duration);ClearOnApply;ImmunityProvided;SPSEffect;SPSAttach;SPSExtraPos;SHPEffect;SHPAttach;SHPExtraPos;ColorKind;ColorPriority;ColorBase\n"
            "# ;Int32;UInt8;UInt8;UInt16;Status[];Status[];Int32;Int32;Vector3;Int32;Int32;Vector3;Int32;Int32;Int32[3]\n"
            "Petrify;0;2;0;0;;;-1;0;1, 2, 3;-1;0;4, 5, 6;-1;0;-48, -72, -88;# Petrify\n"
        ).encode()
    if relative == "Characters/Leveling.csv":
        return b"# Experience;BonusHP;BonusMP\n# UInt32;UInt16;UInt16\n0;250;200;# Level 1\n16;314;206;# Level 2\n"
    if relative == "World/TransportControls.csv":
        return b"# type;flg_gake;speed_move;flg_fly;encount;radius\n# Byte;Byte;Int16;Boolean;Boolean;Int16\n0;0;112;0;1;0;# Walking\n"
    if relative == "World/WeatherColors.csv":
        return b"# light0.vx;light0.vy;light0.vz;fogAMP;offsetX;scaleY\n# Int16;Int16;Int16;UInt16;Single;Single\n100;100;100;4096;0;0;# Daylight 0\n"
    if relative == "Items/ShopItems.csv":
        return (b"# Comment;Id;Items\n# ;Int32;Int32[]\n"
                b"Shop 0000;0;1, 2, 35;# Shop 0000 Test Shop\n"
                b"Shop 0023;23;;# Shop 0023 Closed Shop\n")
    if relative == "TetraMaster/TripleTriad.csv":
        return (
            "# Comment;Id;ATK(UP);MDEF(RIGHT);MATK(DOWN);PDEF(LEFT);Icon\n"
            "# ;Int32;UInt8;UInt8;UInt8;UInt8;String\n"
            "Goblin;0;2;5;1;3;MONSTER\n"
            "Fang;1;6;1;1;2;SUMMON\n"
            "Skeleton;2;1;2;4;5;CASTLE\n"
        ).encode()
    if relative == "Characters/Abilities/Beatrix1.csv":
        return b"# Id;AP\n# Ability;Int32\nAA:1;0;# Fire\nAA:2;0;# Cure\n0;0;# Void\n0;0;# Void\n"
    return b"# Id;Value\n# Int32;UInt8\n0;1;# Synthetic\n"


def field(page, label: str):
    row = page.locator(".lex-detail-field").filter(has=page.get_by_text(label, exact=True)).first
    expect(row).to_be_visible()
    return row


def numeric_field(page, label: str):
    # Shared Detail converts wide-range numbers to grouped text inputs so they
    # can display thousands separators while unfocused. Small ranges stay
    # type=number. Both are the same semantic numeric control.
    control = field(page, label).locator('input[type="number"], input[inputmode="decimal"]').first
    expect(control).to_be_visible()
    return control


def wait_loaded(page):
    page.wait_for_function("!document.documentElement.classList.contains('lex-loading-live')")
    page.locator(".lex-plugin-loading-screen").wait_for(state="detached")


def assert_table_headers_fit(page):
    overflow = page.evaluate("""()=>[...document.querySelectorAll('.lex-column-list-head-cell')]
      .filter(cell=>cell.offsetParent!==null && cell.scrollWidth>cell.clientWidth+1)
      .map(cell=>({text:cell.innerText.trim(),client:cell.clientWidth,scroll:cell.scrollWidth}))""")
    assert not overflow, overflow


def assert_table_rows_do_not_overlap(page, selector=".lex-column-list"):
    # Rows are positioned inside their own table, so each table is measured on
    # its own: two tables in different panels are not a row order.
    overlaps = page.evaluate("""(selector)=> {
      const bad=[];
      for(const root of document.querySelectorAll(selector)){
        if(root.offsetParent===null)continue;
        const rows=[...root.querySelectorAll('.lex-column-list-row')]
          .filter(row=>row.offsetParent!==null && !row.classList.contains('lex-filler-row'));
        for(let i=0;i<rows.length;i++){
          const box=rows[i].getBoundingClientRect();
          const content=[...rows[i].querySelectorAll('.lex-column-cell-content')]
            .map(node=>node.getBoundingClientRect())
            .filter(rect=>rect.width>0&&rect.height>0);
          if(content.some(rect=>rect.top < box.top-1 || rect.bottom > box.bottom+1))
            bad.push({table:root.className,index:i,row:{top:box.top,bottom:box.bottom},content:content.map(rect=>({top:rect.top,bottom:rect.bottom}))});
          if(i+1<rows.length){
            const next=rows[i+1].getBoundingClientRect();
            if(box.bottom > next.top+1) bad.push({table:root.className,index:i,overlapsNext:true,bottom:box.bottom,nextTop:next.top});
          }
        }
      }
      return bad;
    }""", selector)
    assert not overlaps, overlaps


with tempfile.TemporaryDirectory(prefix="lexeditor-ff9-browser-") as name:
    temp = Path(name)
    game, project, data_root = temp / "game", temp / "project", temp / "data"
    for relative in ("FF9_Launcher.exe", "x64/FF9.exe", "x64/FF9_Data/Managed/Assembly-CSharp.dll"):
        target = game / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"synthetic")
    target = game / "StreamingAssets/p0data2.bin"
    target.parent.mkdir(parents=True)
    target.write_bytes(archive())
    (game / "StreamingAssets/p0data11.bin").write_bytes(walkmesh_archive())
    (game / "StreamingAssets/p0data12.bin").write_bytes(walkmesh_archive("FBG_N21_TEST_MAP001_TEST_1"))
    (project / "StreamingAssets/Data").mkdir(parents=True)

    hashes = {}
    for relative in memoria_baseline.FILES:
        payload = csv_bytes(relative)
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
            assert page.locator(".lex-column-list-row").count() >= 10
            assert_table_headers_fit(page)

            # The tab strip shares its width between the fifteen tabs, so the
            # bar reaches the right edge of the window instead of stopping
            # short of it, and no label is clipped or scrolled to get there.
            strip = page.evaluate("""()=>{
              const nav=document.querySelector('.lex-shell-header nav');
              const box=nav.getBoundingClientRect();
              const tabs=[...nav.querySelectorAll('button[data-tab]')]
                .filter(tab=>tab.offsetParent!==null);
              const labels=tabs.map(tab=>tab.querySelector('.lex-tab-label-text')).filter(Boolean);
              return {right:box.right,lastRight:tabs[tabs.length-1].getBoundingClientRect().right,
                      scroll:nav.scrollWidth,client:nav.clientWidth,
                      clipped:labels.filter(label=>label.scrollWidth>label.clientWidth+1)
                        .map(label=>label.textContent.trim())};
            }""")
            assert abs(strip["right"] - strip["lastRight"]) <= 2, strip
            assert strip["scroll"] <= strip["client"] + 1, strip
            assert not strip["clipped"], strip
            # The Items tab names the records it shows itself, so the panel
            # carries no file-name subtitle under the record's own name.
            expect(page.locator(".ff9-detail .lex-detail-panel-meta")).to_have_count(0)

            price = numeric_field(page, "BUY PRICE")
            expect(price).to_have_value("250")
            page.screenshot(path=str(OUT / "ff9-items-wide.png"), full_page=True)
            save = page.locator("#global-save")
            # Right-clicking a property puts back the value its record shipped
            # with. The shared Detail owns the reset and the reference entry;
            # the plugin supplies the vanilla value and the way to write one.
            price.fill("333")
            expect(save).to_be_enabled()
            expect(page.locator(".lex-source-control.lex-value-modified")).to_have_count(1)
            page.screenshot(path=str(OUT / "ff9-items-modified.png"), full_page=True)
            price.click(button="right")
            expect(price).to_have_value("250")
            expect(save).to_be_disabled()
            expect(page.locator(".lex-source-control.lex-value-modified")).to_have_count(0)
            page.screenshot(path=str(OUT / "ff9-items-restored.png"), full_page=True)

            price.fill("333")
            expect(save).to_be_enabled()
            save.click(button="right")
            page.get_by_role("button", name="Discard Changes", exact=True).click()
            expect(price).to_have_value("250")
            expect(save).to_be_disabled()

            price.fill("333")
            save.click()
            page.wait_for_function("dirtyCount()===0")
            overlay = project / "StreamingAssets/Data/Items/Items.csv"
            assert overlay.is_file() and b"0;0;-1;-1;333;" in overlay.read_bytes()
            page.reload(wait_until="domcontentloaded")
            page.wait_for_selector(".lex-paged-list-detail")
            wait_loaded(page)
            expect(numeric_field(page, "BUY PRICE")).to_have_value("333")

            page.evaluate("navigate('enemies')")
            page.wait_for_function("state.datasets.enemies?.rows?.length===1")
            enemy_hp = numeric_field(page, "MAX HP")
            # Shared numeric controls keep digit grouping while unfocused and
            # while focused; input handlers receive plain digits and grouping
            # returns after dispatch.
            expect(enemy_hp).to_have_value("1,234")
            enemy_hp.focus()
            expect(enemy_hp).to_have_value("1,234")
            enemy_hp.fill("2345")
            expect(save).to_be_enabled()
            save.click()
            page.wait_for_function("dirtyCount()===0")
            raw16_overlay = (
                project / "StreamingAssets/Assets/Resources/BattleMap/BattleScene"
                / "EVT_BATTLE_B3_001/dbfile0000.raw16.bytes"
            )
            assert raw16_overlay.is_file(), raw16_overlay
            page.reload(wait_until="domcontentloaded")
            page.wait_for_selector(".lex-paged-list-detail")
            wait_loaded(page)
            page.evaluate("navigate('enemies')")
            page.wait_for_function("state.datasets.enemies?.rows?.length===1")
            expect(numeric_field(page, "MAX HP")).to_have_value("2,345")
            expect(page.get_by_text("Enemies · project BattleScene raw16", exact=True)).to_be_visible()
            page.screenshot(path=str(OUT / "ff9-enemy-save-reopen.png"), full_page=True)

            page.evaluate("navigate('info')")
            expect(page.get_by_text("EXTERNAL MOD COMPATIBILITY", exact=True)).to_be_visible()
            expect(page.get_by_label("ENABLED", exact=True)).to_have_value("None detected")
            expect(page.get_by_label("RUNTIME ORDER", exact=True)).to_have_value("No active mod folders")
            expect(page.get_by_label("METADATA WARNINGS", exact=True)).to_have_value("None detected")
            expect(page.get_by_label("UNSUPPORTED RUNTIME", exact=True)).to_have_value("None detected")
            expect(page.get_by_label("RUNTIME UNKNOWN", exact=True)).to_have_value("None detected")
            expect(page.get_by_label("DECLARED CONFLICTS", exact=True)).to_have_value("None declared")
            expect(page.get_by_label("EXACT PATH OVERLAPS", exact=True)).to_have_value("None detected")
            page.get_by_text("EXTERNAL MOD COMPATIBILITY", exact=True).scroll_into_view_if_needed()
            page.screenshot(path=str(OUT / "ff9-info-mod-compat.png"), full_page=True)

            page.evaluate("navigate('magic')")
            page.wait_for_function("state.datasets.actions?.rows?.length===2")
            targets = field(page, "TARGETS").locator("select")
            expect(targets).to_have_value("SingleEnemy(2)")
            assert set(targets.locator("option").all_text_contents()) == {"SingleEnemy(2)", "ManyAny(3)"}
            page.screenshot(path=str(OUT / "ff9-magic-actions.png"), full_page=True)
            page.evaluate("state.datasetChoice.magic='status-data';render()")
            page.wait_for_function("state.datasets['status-data']?.rows?.length===1")
            expect(field(page, "SPS EXTRA POSITION").locator('input[type="number"], input[inputmode="decimal"]')).to_have_count(3)
            expect(field(page, "GLOW BASE COLOR").locator('input[type="number"], input[inputmode="decimal"]')).to_have_count(3)
            assert_table_headers_fit(page)
            page.screenshot(path=str(OUT / "ff9-status-vectors.png"), full_page=True)

            page.evaluate("navigate('world')")
            page.wait_for_function("state.datasets['world-transport']?.rows?.length===1")
            assert "ID" not in page.locator(".lex-column-list-header").inner_text().split()
            assert page.locator(".lex-detail-panel-heading .lex-record-id").count() == 0

            page.evaluate("state.datasetChoice.world='field-walkmesh';loadDataset('field-walkmesh').then(render)")
            page.wait_for_function("state.datasets['field-walkmesh']?.rows?.length===4")
            # One checkbox in one property is a boolean: the shared field lays
            # it out as a checkbox with its leader arrow. Passed the CSV's own
            # word for the storage type, it fell through to the ordinary row
            # rules and stretched the checkbox across the whole line.
            walkmesh_active = field(page, "FLOOR ACTIVE")
            assert walkmesh_active.get_attribute("data-lex-type") == "BOOL"
            boolean_box = walkmesh_active.locator('input[type="checkbox"]')
            # The panel is rebuilt as the dataset settles, so wait for the box
            # itself before measuring it; a detached node measures as nothing.
            expect(boolean_box).to_be_visible()
            expect(walkmesh_active.locator(".lex-field-boolean-arrow")).to_be_visible()
            box_size = boolean_box.bounding_box()
            assert box_size and 12 <= box_size["width"] <= 32 and 12 <= box_size["height"] <= 32, box_size
            page.screenshot(path=str(OUT / "ff9-boolean.png"), full_page=True)
            active = field(page, "FLOOR ACTIVE").locator('input[type="checkbox"]')
            expect(active).to_be_checked()
            expect(field(page, "OTHER FLAG BITS").locator("input")).to_have_value("64")
            active.uncheck()
            expect(page.locator("#global-save")).to_be_enabled()
            page.locator("#global-save").click()
            page.wait_for_function("state.datasets['field-walkmesh']?.rows?.[0]?.source==='project'")
            expect(field(page, "FLOOR ACTIVE").locator('input[type="checkbox"]')).not_to_be_checked()
            expect(page.get_by_text("Field walkmesh floors · project BGI", exact=True)).to_be_visible()
            page.evaluate("loadDataset('field-walkmesh',true).then(render)")
            page.wait_for_function("state.datasets['field-walkmesh']?.rows?.[0]?.source==='project'")
            expect(field(page, "FLOOR ACTIVE").locator('input[type="checkbox"]')).not_to_be_checked()
            page.screenshot(path=str(OUT / "ff9-walkmesh-save-reopen.png"), full_page=True)

            page.evaluate("state.datasetChoice.world='field-walkmesh-triangles';loadDataset('field-walkmesh-triangles').then(render)")
            page.wait_for_function("state.datasets['field-walkmesh-triangles']?.rows?.length===2")
            chooser = page.get_by_label("Field walkmesh", exact=True)
            expect(chooser.locator("option")).to_have_count(2)
            tri_active = field(page, "TRIANGLE ACTIVE").locator('input[type="checkbox"]')
            expect(tri_active).to_be_checked()
            expect(field(page, "ALTERNATE FOOTSTEP").locator('input[type="checkbox"]')).to_be_checked()
            expect(field(page, "PREVENT NPC PATHING").locator('input[type="checkbox"]')).to_be_checked()
            expect(field(page, "PREVENT PC PATHING").locator('input[type="checkbox"]')).to_be_checked()
            expect(field(page, "OTHER FLAG BITS").locator("input")).to_have_value("32")
            tri_active.uncheck()
            expect(chooser).to_be_disabled()
            page.locator("#global-save").click()
            page.wait_for_function("state.datasets['field-walkmesh-triangles']?.rows?.[0]?.source==='project'")
            expect(field(page, "TRIANGLE ACTIVE").locator('input[type="checkbox"]')).not_to_be_checked()
            expect(field(page, "ALTERNATE FOOTSTEP").locator('input[type="checkbox"]')).to_be_checked()
            expect(field(page, "PREVENT NPC PATHING").locator('input[type="checkbox"]')).to_be_checked()
            expect(field(page, "PREVENT PC PATHING").locator('input[type="checkbox"]')).to_be_checked()
            expect(page.get_by_text("Field walkmesh triangles · project BGI", exact=True)).to_be_visible()
            expect(chooser).to_be_enabled()
            first_scene = page.evaluate("state.datasets['field-walkmesh-triangles'].activeScene")
            second_scene = page.evaluate("state.datasets['field-walkmesh-triangles'].scenes.find(row=>row.value!==state.datasets['field-walkmesh-triangles'].activeScene).value")
            chooser.select_option(second_scene)
            page.wait_for_function("scene=>state.datasets['field-walkmesh-triangles']?.activeScene===scene", arg=second_scene)
            chooser = page.get_by_label("Field walkmesh", exact=True)
            chooser.select_option(first_scene)
            page.wait_for_function("scene=>state.datasets['field-walkmesh-triangles']?.activeScene===scene", arg=first_scene)
            expect(field(page, "TRIANGLE ACTIVE").locator('input[type="checkbox"]')).not_to_be_checked()
            page.screenshot(path=str(OUT / "ff9-walkmesh-triangle-save-reopen.png"), full_page=True)

            page.evaluate("navigate('encounters')")
            page.wait_for_function("state.datasets.encounters?.rows?.length===1")
            expect(numeric_field(page, "MONSTER COUNT")).to_have_attribute("max", "4")
            expect(numeric_field(page, "ENEMY 1 TYPE")).to_have_attribute("max", "0")
            page.screenshot(path=str(OUT / "ff9-encounters.png"), full_page=True)

            # A shop's CSV cell is a list of item ids. The list must say how
            # many items the shop holds, and the panel must name them.
            page.evaluate("navigate('shops')")
            page.wait_for_function("state.datasets.shops?.rows?.length===2")
            shop_rows = page.locator(".ff9-table .lex-column-list-row")
            expect(shop_rows).to_have_count(2)
            expect(shop_rows.filter(has_text="Test Shop")).to_contain_text("3 items")
            expect(shop_rows.filter(has_text="Closed Shop")).to_contain_text("Nothing")
            shop_rows.filter(has_text="Test Shop").click()
            stock = page.locator(".ff9-shop-table .lex-column-list-row")
            expect(stock).to_have_count(3)
            expect(stock.first).to_contain_text("Item 01")
            expect(stock.first).to_contain_text("251 gil")
            expect(stock.last).to_contain_text("Item 35")
            stock_header = page.locator(".ff9-shop-table .lex-column-list-header").inner_text()
            assert "Buy price" in stock_header and "Sell price" in stock_header, stock_header
            assert_table_headers_fit(page)
            assert_table_rows_do_not_overlap(page)
            page.screenshot(path=str(OUT / "ff9-shops.png"), full_page=True)

            # A Tetra Master card is read the way the game draws it: the four
            # values in card order (attack up, defence left, defence right,
            # attack down) on the shared card, with the card's own icon, and
            # that same card is the control for changing a value.
            page.evaluate("navigate('tetra-master')")
            page.wait_for_function("state.datasets['tetra-cards']?.rows?.length===3")
            card = page.locator(".ff9-card-detail .lex-stat-card")
            expect(card).to_be_visible()
            ranks = page.locator(".ff9-card-detail .lex-stat-card-ranks > button")
            expect(ranks).to_have_count(4)
            selected_card = page.evaluate("""()=>{const data=state.datasets['tetra-cards'];
              return data.rows.find(row=>row.line===state.selected['tetra-cards']).values}""")
            card_sides = ["ATK(UP)", "PDEF(LEFT)", "MDEF(RIGHT)", "MATK(DOWN)"]
            shown = lambda key: "A" if selected_card[key] == 10 else str(selected_card[key])
            expect(ranks).to_have_text([shown(key) for key in card_sides])
            expect(card.locator(".lex-stat-card-corner")).to_contain_text(selected_card["Icon"])
            # The four values are bounded to what QuadMist can draw, and the
            # icon is a choice rather than a free text box.
            expect(field(page, "ATK (UP)").locator(
                "input[type='number'], input[inputmode='decimal']")).to_have_attribute("max", "10")
            expect(field(page, "ICON").locator("select")).to_have_count(1)
            page.screenshot(path=str(OUT / "ff9-tetra-master.png"), full_page=True)
            raised = "A" if selected_card["ATK(UP)"] % 10 + 1 == 10 else str(selected_card["ATK(UP)"] % 10 + 1)
            ranks.first.click()
            expect(ranks.first).to_have_text(raised)
            ranks.first.click(button="right")
            expect(ranks.first).to_have_text(shown("ATK(UP)"))

            # An ability slot carries no cost of its own: the cost belongs to
            # the battle action the slot names, and the file pads the list with
            # void rows that have to be told apart.
            page.evaluate("state.datasetChoice.abilities='ability-beatrix-1'")
            page.evaluate("navigate('abilities')")
            page.wait_for_function("state.datasets['ability-beatrix-1']?.rows?.length===4")
            ability_rows = page.locator(".ff9-table .lex-column-list-row")
            expect(ability_rows).to_have_count(4)
            expect(ability_rows.filter(has_text="Empty slot 1")).to_have_count(1)
            expect(ability_rows.filter(has_text="Empty slot 2")).to_have_count(1)
            assert "MP cost" in page.locator(".ff9-table .lex-column-list-header").inner_text()
            page.locator(".ff9-table .lex-column-list-row").filter(has_text="Fire").first.click()
            expect(page.locator(".lex-detail-panel-heading")).to_contain_text("Fire")
            expect(page.locator(".lex-detail")).to_contain_text("BATTLE ACTION")
            expect(field(page, "MP COST")).to_contain_text("6")
            expect(field(page, "AP")).to_be_visible()
            assert_table_headers_fit(page)
            page.screenshot(path=str(OUT / "ff9-abilities.png"), full_page=True)

            page.locator("#plugin-data-map").click()
            page.wait_for_selector(".lex-data-map-view")
            map_search = page.get_by_role("searchbox", name="Search the data map")
            map_search.fill("BattleScene")
            page.wait_for_function("state.mapQuery==='BattleScene'")
            assert "BattleScene" in page.locator(".lex-data-map-view").inner_text()
            map_search.fill("p0data1")
            page.wait_for_function("state.mapQuery==='p0data1'")
            partial_row = page.locator(".lex-column-list-row").filter(has_text="BGI_FLOOR_ACTIVE").first
            expect(partial_row).to_be_visible()
            expect(partial_row.locator('.lex-integration-status[aria-label="Partial"]')).to_be_visible()
            triangle_row = page.locator(".lex-column-list-row").filter(has_text="BGI_TRI_ACTIVE").first
            expect(triangle_row).to_be_visible()
            expect(triangle_row.locator('.lex-integration-status[aria-label="Partial"]')).to_be_visible()
            map_search.fill("p0data4.bin")
            page.wait_for_function("state.mapQuery==='p0data4.bin'")
            map_text = page.locator(".lex-data-map-view").inner_text()
            assert "p0data4.bin" in map_text and "Field and character 3D models" in map_text
            gap_row = page.locator(".lex-column-list-row").filter(has_text="p0data4.bin").first
            expect(gap_row).to_be_visible()
            gap_row.click()
            expect(page.locator(".lex-data-map-detail")).to_contain_text("mesh/rig")
            page.screenshot(path=str(OUT / "ff9-datamap.png"), full_page=True)
            map_search.fill("")

            page.set_viewport_size({"width": 900, "height": 620})
            page.evaluate("navigate('items')")
            page.wait_for_selector(".lex-paged-list-detail")
            metrics = page.evaluate("()=>({body:document.body.scrollWidth,viewport:innerWidth,main:document.querySelector('main').scrollWidth,width:document.querySelector('main').clientWidth})")
            assert metrics["body"] <= metrics["viewport"] + 2 and metrics["main"] <= metrics["width"] + 2, metrics
            # Responsive paging can rerender once after the viewport change.
            # Wait for that fit pass, then resolve fresh locators against the settled DOM.
            page.wait_for_timeout(150)
            field(page, "EQUIPPABLE BY").scroll_into_view_if_needed()
            expect(field(page, "EQUIPPABLE BY")).to_be_visible()
            field(page, "WEAPON ID").scroll_into_view_if_needed()
            page.screenshot(path=str(OUT / "ff9-900x620.png"))

            # Desktop UI scale is WebView page zoom, not CSS `zoom`. At 150% a
            # 1000x700 physical client has about a 667x467 CSS-pixel layout viewport.
            # Use that responsive viewport plus DPR 1.5 so the artifact is rendered
            # at the same effective scale without bypassing responsive layout.
            scale_context = browser.new_context(
                viewport={"width": 667, "height": 467}, device_scale_factor=1.5)
            try:
                scale_page = scale_context.new_page()
                scale_page.on("pageerror", lambda error: errors.append(str(error)))
                scale_page.goto(session.url, wait_until="domcontentloaded")
                scale_page.wait_for_function("typeof state==='object'&&state.dashboard&&typeof shell==='object'")
                scale_page.wait_for_selector(".lex-paged-list-detail")
                wait_loaded(scale_page)
                expect(scale_page.locator("#global-save")).to_be_visible()
                assert_table_rows_do_not_overlap(scale_page)
                metrics = scale_page.evaluate("()=>({body:document.body.scrollWidth,viewport:innerWidth,main:document.querySelector('main').scrollWidth,width:document.querySelector('main').clientWidth,dpr:devicePixelRatio})")
                assert metrics["body"] <= metrics["viewport"] + 2 and metrics["main"] <= metrics["width"] + 2, metrics
                assert metrics["dpr"] == 1.5, metrics
                scale_page.screenshot(path=str(OUT / "ff9-scale-150.png"), scale="device")
            finally:
                scale_context.close()

            page.evaluate("document.querySelector('#main').replaceChildren(statusPanel('Actions','Verified source','Loading records…'))")
            expect(page.get_by_text("Loading records…", exact=True)).to_be_visible()
            page.evaluate("state.datasets.actions={key:'actions',unavailable:true,error:'Synthetic source failure'};renderDataset(state.datasets.actions,'actions')")
            expect(page.get_by_text("Synthetic source failure", exact=True)).to_be_visible()
            expect(page.get_by_text("Source currently unavailable", exact=True)).to_be_visible()
            page.screenshot(path=str(OUT / "ff9-error.png"), full_page=True)
        finally:
            browser.close()
    assert session.wait_closed(), "FF9 browser child service did not close"

    # A game nobody has modded opens on its own data, read-only, under Vanilla.
    # FF9's default project folder used to fall back to the plugin's shipped
    # project_template, so this state did not exist: the header named the
    # starter as the current, editable mod. The snapshot below comes from the
    # real project store driven by the plugin's own declaration, so the menu
    # cannot drift from what the app would show; only the mod menu's transport
    # is stubbed, the way the shared shell receives it from the host.
    from dataclasses import replace as replace_field

    from core.project_manager import ProjectManager
    from plugins.ff9.plugin import PLUGIN

    no_project = temp / "no-project-folder"
    no_mod_plugin = replace_field(PLUGIN, projects=replace_field(
        PLUGIN.projects, default_root=no_project))
    snapshot = ProjectManager({PLUGIN.plugin_id: no_mod_plugin},
                              temp / "no-mod-projects.json").snapshot(PLUGIN.plugin_id)
    current_row = next(row for row in snapshot["projects"] if row["current"])
    assert current_row["noMod"] and not current_row["valid"], current_row
    assert current_row["path"] == str(no_project.resolve()), current_row
    assert current_row["name"] != "project_template", current_row

    no_mod_env = {
        **env,
        "LEXEDITOR_FF9_PROJECT": str(no_project),
        # What the host sets when it opens a game with no mod.
        "LEXEDITOR_MOD_READ_ONLY": "1",
        "LEXEDITOR_NO_MOD": "1",
    }
    with FF9Session(no_mod_env) as session, sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.add_init_script(
                "window.pywebview={api:{"
                f"mod_projects:async()=>({json.dumps(snapshot)}),"
                "mod_library_status:async()=>({canManage:false,"
                "message:'Mod management is not supported for this game yet.'}),"
                "}};")
            page.goto(session.url + "?lexNoMod=1", wait_until="domcontentloaded")
            page.wait_for_selector(".lex-paged-list-detail")
            wait_loaded(page)
            state = page.evaluate("""()=>{
              const save=document.querySelector('#global-save');
              return {
                readonly:document.documentElement.getAttribute('data-lex-project-readonly'),
                badge:document.querySelector('.lex-shell-header .lex-badge')?.textContent||null,
                saveDisabled:save?save.disabled:null,
                trigger:document.querySelector('.lex-project-control')?.innerText.trim()||'',
              };
            }""")
            assert state["readonly"] == "true", state
            assert state["badge"] == "NO MOD", state
            assert state["saveDisabled"] is True, state
            # The control names the source that is shown. It used to read the
            # folder a mod would use, which for FF9 was the shipped starter.
            assert "Vanilla" in state["trigger"], state
            assert "project_template" not in state["trigger"], state
            # The game's own data is still on the page, not an empty table.
            price = numeric_field(page, "BUY PRICE")
            expect(price).to_have_value("250")
            expect(page.locator(".lex-column-list-row")).not_to_have_count(0)
            page.screenshot(path=str(OUT / "ff9-no-mod.png"), full_page=True)
            # An edit attempt is refused and offers the one action that ends
            # the read-only state, instead of leaving a dead control.
            price.click()
            dialog = page.locator(".lex-dialog")
            dialog.wait_for(state="visible", timeout=5000)
            assert "Create a mod" in dialog.inner_text(), dialog.inner_text()
            page.keyboard.type("333")
            expect(price).to_have_value("250")
            dialog.get_by_role("button", name="Cancel", exact=False).first.click()
            page.wait_for_timeout(200)
            expect(price).to_have_value("250")
        finally:
            browser.close()
    assert session.wait_closed(), "FF9 no-mod browser child service did not close"
    assert not errors, errors

print("FF9 rendered browser acceptance passed")
