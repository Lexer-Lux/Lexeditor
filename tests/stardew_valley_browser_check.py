"""Scoped real-rendered acceptance for the Stardew Valley plugin UI.

Runs the real loopback service against synthetic Stardew/Content Patcher fixtures.
No installed game or user project is touched.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "out" / "stardew-valley-browser"
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT))

from games.stardew_valley.content_pack import ContentPackStore, initialize_project  # noqa: E402
from games.stardew_valley.plugin import StardewValleySession  # noqa: E402
from games.stardew_valley.source_data import objects_source_path  # noqa: E402


def make_fixture(root: Path) -> tuple[Path, Path]:
    game = root / "game"
    project = root / "project"
    (game / "Content" / "Data").mkdir(parents=True)
    (game / "Content" / "Data" / "Objects.xnb").write_bytes(b"synthetic objects xnb")
    (game / "Stardew Valley.exe").write_bytes(b"fixture")
    (game / "StarewModdingAPI.exe").write_bytes(b"fixture")
    cp = game / "Mods" / "Content Patcher"
    cp.mkdir(parents=True)
    (cp / "manifest.json").write_text(json.dumps({
        "Name": "Content Patcher", "UniqueID": "Pathoschild.ContentPatcher",
        "Version": "2.9.1", "MinimumApiVersion": "4.4.0",
    }) + "\n", encoding="utf-8")

    records: dict[str, dict] = {}
    for index in range(1, 96):
        object_id = str(1000 + index)
        records[object_id] = {
            "Name": f"FixtureObject{index:03}",
            "DisplayName": f"Fixture Object {index:03}",
            "Description": f"Synthetic object {index:03} used only for browser acceptance.",
            "Price": index * 3,
            "Edibility": -300 if index % 5 == 0 else index,
            "IsDrink": index % 7 == 0,
        }
    records["390"] = {
        "Name": "Stone", "DisplayName": "Stone", "Description": "A useful material.",
        "Price": 2, "Edibility": -300, "IsDrink": False,
    }
    source = objects_source_path(game)
    source.parent.mkdir(parents=True)
    source.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")

    shutil.copytree(ROOT / "games" / "stardew_valley" / "project_template", project)
    initialize_project(project)
    return game, project


def visible_table_values(page, key: str) -> list[str]:
    return page.locator(f'.lex-column-list-row [data-column-key="{key}"] .lex-column-cell-content').all_inner_texts()


def assert_geometry(page, label: str) -> dict:
    metrics = page.evaluate("""()=>{
      const main=document.querySelector('#main');
      const root=main?.firstElementChild;
      const detail=document.querySelector('.sv-detail,.lex-data-map-detail');
      const pager=document.querySelector('.lex-pager');
      return {
        viewport:[innerWidth,innerHeight],
        bodyWidth:document.body.scrollWidth,bodyHeight:document.body.scrollHeight,
        mainWidth:main?.clientWidth||0,mainScrollWidth:main?.scrollWidth||0,
        mainHeight:main?.clientHeight||0,mainScrollHeight:main?.scrollHeight||0,
        rootBottom:root?.getBoundingClientRect().bottom||0,
        pagerBottom:pager?.getBoundingClientRect().bottom||0,
        detailScroll:detail?.scrollHeight||0,detailHeight:detail?.clientHeight||0,
      };
    }""")
    assert metrics["bodyWidth"] <= metrics["viewport"][0] + 2, (label, metrics)
    assert metrics["bodyHeight"] <= metrics["viewport"][1] + 2, (label, metrics)
    assert metrics["mainScrollWidth"] <= metrics["mainWidth"] + 2, (label, metrics)
    assert metrics["rootBottom"] <= metrics["viewport"][1] + 2, (label, metrics)
    if metrics["pagerBottom"]:
        assert metrics["pagerBottom"] <= metrics["viewport"][1] + 2, (label, metrics)
    return metrics


def screenshot(page, name: str) -> None:
    page.screenshot(path=str(OUT / name), full_page=True)


def run_viewport(browser, url: str, project: Path, width: int, height: int, *, zoom: float = 1.0) -> dict:
    page = browser.new_page(viewport={"width": width, "height": height})
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    delayed = {"done": False}
    def delay_dashboard(route):
        if not delayed["done"]:
            delayed["done"] = True
            time.sleep(.35)
        route.continue_()
    page.route("**/api/dashboard", de[^WЩ\Ъ›Ш\™
B€YЩK™ЫЭК\›ШZ]Э[ќ[H™ЫXЫЫќ[ќШYYЉB€YЩK™Щ]ШћWЬ›ЫJњЭ]\ИЉK™љ[\Љ\ЧЭ^H“ШY[™ИЭ\™]И[^H›Ъ™XЭЉKќШZ]Щ›ЬЉ
B€YЩKќШZ]Щ›Ь—ЬЩ[XЭЬЉ	Л›^\YЩY[\ЭY]Z[›^XЫЫ[[‹[\Э\›ЭЙЛ[Y[Э]LЊ
B€Y€›ЫЫHOHN‚€YЩK™][X]Jќ[YOOћЩШЭ[Y[ќ›ЩKњЭ[Kћ›ЫЫOTЭљ[™К[YJ_H‹›ЫЫJB€YЩKќШZ]Щ›Ь—Э[Y[Э]
НL
B‚€X™[H€ћЭЪY^ЪZYЪK^ћЮ›ЫЫ_H‚€\ЬЩ\ќYЩK›ШШ]ЬЉ	ИЬYЪ[‹Y]K[X\	КKЫЭ[ќ

HOHB€\ЬЩ\ќYЩK›ШШ]ЬЉ	ИЬYЪ[‹Z[™›ЙКKЫЭ[ќ

HOHB€\ЬЩ\ќYЩK›ШШ]ЬЉ	Ы[љЦЪ™YЏH™Y]Ь‹ЬЬИ—IКKЫЭ[ќ

HOHB€\ЬЩ\ќYЩK›ШШ]ЬЉ	ЬШЬљ\ЬЬПH™Y]Ь‹љњИ—IКKЫЭ[ќ

HOHB€\ЬЩ\ќYЩK›ШШ]ЬЉ	Л›^XЫЫ[[‹[\Э\›ЭЙКKЫЭ[ќ

HЏH‚€\ЬЩ\ќYЩK›ШШ]ЬЉ	Л›^\YЩ\‰КKЫЭ[ќ

HOHB€\ЬЩ\ќЩЩ[ЫY]ћJYЩKX™[
И‹[Шљ™XЭИЉB€ШЬ™Y[њЪЭ
YЩK€›Шљ™XЭЛ^ЫX™[Kњ™ИЉB‚€И[\HЩX\Ъ™\Э[И]™HH™X[[\HЭ]H[њЭXYЩ€HZЩH›Ь\ќK‚€ЩX\ЪHYЩK›ШШ]ЬЉ	Л›^\YЩ\‹\ЩX\Ъ[њ]	КK™љ\њЭ€ЩX\Ъ™љ[
““ЧФХPТФХT‘]ЧУР’‘PХЉB€YЩKќШZ]Щ›Ь—Э[Y[Э]
N
B€\ЬЩ\ќ“›И]KУШљ™XЭИ™XЫЬ™ИX]Ъ€[€YЩK›ШШ]ЬЉ	ЛњЭ‹Y]Z[	КKљ[›™\—Э^

B€ЩX\Ъ™љ[
€ЉB€YЩKќШZ]Щ›Ь—Э[Y[Э]
N
B‚€И][K\YЩH]љYШ][Ы€]\ЭY[ЩH[™™[XZ[€ЭX›K‚€љ\њЭШ™Y›Ь™HHYЩK›ШШ]ЬЉ	Л›^XЫЫ[[‹[\Э\›ЭЙКK™љ\њЭљ[›™\—Э^

B€™^Шќ]Ы€HYЩK™Щ]ШћWЬ›ЫJќ]Ы€‹[YOH“™^YЩH‹^XЭUќYJB€\ЬЩ\ќ™^Шќ]Ы‹љ\ЧЩ[X›Y

KX™[€™^Шќ]Ы‹ЫXЪК
B€YЩKќШZ]Щ›Ь—Э[Y[Э]
ЌL
B€љ\њЭШYќ\€HYЩK›ШШ]ЬЉ	Л›^XЫЫ[[‹[\Э\›ЭЙКK™љ\њЭљ[›™\—Э^

B€\ЬЩ\ќљ\њЭШYќ\€OHљ\њЭШ™Y›Ь™K
X™[њYЩ\€Y›ЭY[ЩHЉB€YЩKќШZ]Щ›Ь—Э[Y[Э]
ЌL
B€\ЬЩ\ќYЩK›ШШ]ЬЉ	Л›^XЫЫ[[‹[\Э\›ЭЙКK™љ\њЭљ[›™\—Э^

HOHљ\њЭШYќ\‚€YЩK™Щ]ШћWЬ›ЫJќ]Ы€‹[YOH”™]љ[Э\ИYЩH‹^XЭUќYJKЫXЪК
B‚€ИЫЬќ[™И\ИHXY\€XЭ[Ы‹[™Щ[XЭ[Ы€Ь[њИHЫЬњ™\ЬЫ™[™И]Z[‚€YЩK™Щ]ШћWЬ›ЫJќ]Ы€‹[YOH”ЫЬќћHЩ[љXЩH‹^XЭUќYJKЫXЪК
B€YЩKќШZ]Щ›Ь—Э[Y[Э]
ЌL
B€љXЩ\ИHЪ[ќ
[YKњ™\XЩJ‹‹€ЉJH›Ь€[YH[€љ\ЪX›WЭX›WЭ[Y\КYЩK”љXЩHЉHY€[YKњЭљ\
ё %ЉWB€\ЬЩ\ќљXЩ\ИOHЫЬќY
љXЩ\КK
X™[љXЩ\ЦОЊLJB‚€ЩX\ЪHYЩK›ШШ]ЬЉ	Л›^\YЩ\‹\ЩX\Ъ[њ]	КK™љ\њЭ€ЩX\Ъ™љ[
”ЭЫ™HЉB€YЩKќШZ]Щ›Ь—Э[Y[Э]
ЌL
B€ЭЫ™HHYЩK›ШШ]ЬЉ	Л›^XЫЫ[[‹[\Э\›ЭЙКK™љ[\Љ\ЧЭ^H”ЭЫ™HЉK™љ\њЭ€\ЬЩ\ќЭЫ™KЫЭ[ќ

HOHB€ЭЫ™KЫXЪК
B€YЩKќШZ]Щ›Ь—Э[Y[Э]
ML
B€\ЬЩ\ќ”ЭЫ™H€[€YЩK›ШШ]ЬЉ	Л›^Y]Z[\[™[ZXY[™ЙКKљ[›™\—Э^

B‚€ИЩ[X[ќXИ[]\Э™HЩ^X›Ш\™™XXЪX›H[™Э]HXЭX[Ш[Y\^HY™™XЭЛ‚€[ЫX\љЩ\€HYЩK›ШШ]ЬЉ	ЦЩ]K[^\›Ь\ќOH‘YXљ[]H—H›^Z[™›ЛZ[	КK™љ\њЭ€[ЫX\љЩ\‹™›ШЭ\К
B€ЫЫ\HYЩK™Щ]ШћWЬ›ЫJќЫЫ\ЉB€ЫЫ\ќШZ]Щ›ЬЉ
B€[Э^HЫЫ\љ[›™\—Э^

B€\ЬЩ\ќ™[™\™ЮH€[€[Э^›ЭЩ\Љ
H[™љX[€[€[Э^›ЭЩ\Љ
H[™Њ‹ЌH€[€[Э^€[ЫX\љЩ\‹њ™\ЬКђ\њ›ЭСЭЫ€ЉB€\ЬЩ\ќЫЫ\™][X]J››ЩOO™ШЭ[Y[ќXЭ]™Q[[Y[ќOO[›ЩHЉB€ЫЫ\њ™\ЬК‘\ШШ\HЉB‚€ИX›HЩ[Y][™ИЬ™X]\ИHЭ\ЬќYЭ™\њљYH[™љ]™\ИHЪ\™Y\ќKЬШ]™HЭ]K‚€љXЩWШЩ[HЭЫ™K›ШШ]ЬЉ	ЦЩ]KXЫЫ[[‹ZЩ^OH”љXЩH—IКK™љ\њЭ€љXЩWШЩ[™›ЫXЪК
B€Y]Ь€HљXЩWШЩ[›ШШ]ЬЉ	Ъ[њ]Э\OH›ќ[X™\€—IКB€Y]Ь‹™љ[
ЋЉB€Y]Ь‹њ™\ЬК‘[ќ\€ЉB€YЩKќШZ]Щ›Ь—Э[Y[Э]
ML
B€Ш]™HHYЩK›ШШ]ЬЉ	ИЩЫШ[\Ш]™IКB€\ЬЩ\ќШ]™Kљ\ЧЩ[X›Y

B€\ЬЩ\ќYЩK™][X]J™\ќPЫЭ[ќ

HЉHOHB€\ЬЩ\ќYЩK›ШШ]ЬЉ	ЦЩ]K[^\›Ь\ќOH”љXЩH—H[њ]Э\OH›ќ[X™\€—IКKљ[њ]Э[YJ
HOHЋ‚€Ш]™KЫXЪК
B€YЩKќШZ]Щ›Ь—Щќ[Э[ЫЉЉ
OO™ШЭ[Y[ќњ]Y\ћTЩ[XЭЬЉ	ИЩЫШ[\Ш]™IКOЛ™\ШX›YOO]ќYHЉB€ЫЫќ[ќHњЫЫ‹›ШYК
›Ъ™XЭИЫЫќ[ќљњЫЫ€ЉKњ™XYЭ^
[ЫЩ[™ПHќ]‹NЉJB€]ЪH™^
Ъ[™ЩH›Ь€Ъ[™ЩH[€ЫЫќ[ќИђЪ[™Щ\И—HY€Ъ[™ЩK™Щ]
“ЩУ[YHЉHOH“^Y]Ь€]KУШљ™XЭИљY[Э™\њљY\ИЉB€\ЬЩ\ќ]ЪИ‘љY[И—VИЊОL—VИ”љXЩH—HOH‚€И™[Ь[€њ›ЫH\ЪЛXZЩH[›Э\€Ъ[™ЩK[™\ШШ\™›ЭYЪHЪ\™YШ]™HЫЫќ›Ы	ЬИЫЫќ^XЭ[Ы‹‚€YЩKњ™[ШY
ШZ]Э[ќ[H™ЫXЫЫќ[ќШYYЉB€YЩKќШZ]Щ›Ь—ЬЩ[XЭЬЉ	Л›^\YЩY[\ЭY]Z[›^XЫЫ[[‹[\Э\›ЭЙКB€YЩK›ШШ]ЬЉ	Л›^\YЩ\‹\ЩX\Ъ[њ]	КK™љ\њЭ™љ[
”ЭЫ™HЉB€YЩKќШZ]Щ›Ь—Э[Y[Э]
Њ
B€ЭЫ™HHYЩK›ШШ]ЬЉ	Л›^XЫЫ[[‹[\Э\›ЭЙКK™љ[\Љ\ЧЭ^H”ЭЫ™HЉK™љ\њЭ€\ЬЩ\ќЋ€[€ЭЫ™K›ШШ]ЬЉ	ЦЩ]KXЫЫ[[‹ZЩ^OH”љXЩH—IКKљ[›™\—Э^

B€Щ[HЭЫ™K›ШШ]ЬЉ	ЦЩ]KXЫЫ[[‹ZЩ^OH”љXЩH—IКK™љ\њЭ€Щ[™›ЫXЪК
NИЩ[›ШШ]ЬЉ	Ъ[њ]	КK™љ[
ЋNHЉNИЩ[›ШШ]ЬЉ	Ъ[њ]	КKњ™\ЬК‘[ќ\€ЉB€YЩKќШZ]Щ›Ь—Э[Y[Э]
L
B€\ЬЩ\ќYЩK›ШШ]ЬЉ	ИЩЫШ[\Ш]™IКKљ\ЧЩ[X›Y

B€YЩK›ШШ]ЬЉ	ИЩЫШ[\Ш]™IКKЫXЪКќ]ЫЏHњљYЪЉB€YЩK™Щ]ШћWЬ›ЫJќ]Ы€‹[YOH‘\ШШ\™Ъ[™Щ\И‹^XЭUќYJKЫXЪК
B€YЩKќШZ]Щ›Ь—Щќ[Э[ЫЉЉ
OO™ШЭ[Y[ќњ]Y\ћTЩ[XЭЬЉ	ИЩЫШ[\Ш]™IКOЛ™\ШX›YOO]ќYHЉB€YЩKќШZ]Щ›Ь—Э[Y[Э]
ML
B€YЩK›ШШ]ЬЉ	Л›^\YЩ\‹\ЩX\Ъ[њ]	КK™љ\њЭ™љ[
”ЭЫ™HЉB€YЩKќШZ]Щ›Ь—Э[Y[Э]
ML
B€\ЬЩ\ќЋ€[€YЩK›ШШ]ЬЉ	Л›^XЫЫ[[‹[\Э\›ЭЙКK™љ[\Љ\ЧЭ^H”ЭЫ™HЉK™љ\њЭ›ШШ]ЬЉ	ЦЩ]KXЫЫ[[‹ZЩ^OH”љXЩH—IКKљ[›™\—Э^

B‚€ИHЭ[HЬљ]H]\ЭЭ\™XЩH[€\њ›Ь€Э]H[™ЩY\HY]\ќH[ќ[\ШШ\™Y‚€]ИHњЫЫ‹›ШYК
›Ъ™XЭИЫЫќ[ќљњЫЫ€ЉKњ™XYЭ^
[ЫЩ[™ПHќ]‹NЉJB€]ЦИ‘^\›[љ^\™PЪ[™ЩH—HHќYB€
›Ъ™XЭИЫЫќ[ќљњЫЫ€ЉKќЬљ]WЭ^
њЫЫ‹™[\К]Л[™[ќLЉH
И—€‹[ЫЩ[™ПHќ]‹NЉB€ЭЫ™HHYЩK›ШШ]ЬЉ	Л›^XЫЫ[[‹[\Э\›ЭЙКK™љ[\Љ\ЧЭ^H”ЭЫ™HЉK™љ\њЭ€Щ[HЭЫ™K›ШШ]ЬЉ	ЦЩ]KXЫЫ[[‹ZЩ^OH”љXЩH—IКK™љ\њЭ€Щ[™›ЫXЪК
NИЩ[›ШШ]ЬЉ	Ъ[њ]	КK™љ[
ЋLHЉNИЩ[›ШШ]ЬЉ	Ъ[њ]	КKњ™\ЬК‘[ќ\€ЉB€YЩK›ШШ]ЬЉ	ИЩЫШ[\Ш]™IКKЫXЪК
B€\њ›Ь—ЩX[ЩИHYЩK™Щ]ШћWЬ›ЫJ[\ќX[ЩИЉB€\њ›Ь—ЩX[ЩЛќШZ]Щ›ЬЉ
B€\ЬЩ\ќЪ[™ЩY€[€\њ›Ь—ЩX[ЩЛљ[›™\—Э^

K›ЭЩ\Љ
B€\ЬЩ\ќYЩK™][X]J™\ќPЫЭ[ќ

HЉHOHB€\њ›Ь—ЩX[ЩЛ™Щ]ШћWЬ›ЫJќ]Ы€‹[YOHђЫЬЩH‹^XЭUќYJKЫXЪК
B€YЩK›ШШ]ЬЉ	ИЩЫШ[\Ш]™IКKЫXЪКќ]ЫЏHњљYЪЉB€YЩK™Щ]ШћWЬ›ЫJќ]Ы€‹[YOH‘\ШШ\™Ъ[™Щ\И‹^XЭUќYJKЫXЪК
B€YЩKќШZ]Щ›Ь—Щќ[Э[ЫЉЉ
OO™ШЭ[Y[ќњ]Y\ћTЩ[XЭЬЉ	ИЩЫШ[\Ш]™IКOЛ™\ШX›YOO]ќYHЉB‚€ИЩ^X›Ш\™\™\Ъ^™HHЪ\™Y]љY\€[™›Э™H^[Э]Э^\И›Э[™Y‚€]љY\€HYЩK›ШШ]ЬЉ	Л›^\[™[[^[Э]Y]љY\‰КK™љ\њЭ€™Y›Ь™HH[ќ
]љY\‹™Щ]Ш]љXќ]J	Ш\љXK][Y[›ЭЙКJB€]љY\‹™›ШЭ\К
NИ]љY\‹њ™\ЬК”ЪYќ
Р\њ›ЭФљYЪЉB€YЩKќШZ]Щ›Ь—Э[Y[Э]
ML
B€Yќ\€H[ќ
]љY\‹™Щ]Ш]љXќ]J	Ш\љXK][Y[›ЭЙКJB€\ЬЩ\ќYќ\€OH™Y›Ь™K
X™[™Y›Ь™KYќ\ЉB€\ЬЩ\ќЩЩ[ЫY]ћJYЩKX™[
И‹\™\Ъ^™YЉB‚€И]HX\\Щ\ИЪ\™YЫЭ™\YЩKЪ[ќYЬ][Ы€XЫЫ›ЩЬ\H[™Ш[€›Э]HXЪИИШљ™XЭЛ‚€YЩK›ШШ]ЬЉ	ИЬYЪ[‹Y]K[X\	КKЫXЪК
B€YЩKќШZ]Щ›Ь—ЬЩ[XЭЬЉ	Л›^Y]K[X\]X›H›^XЫЫ[[‹[\Э\›ЭЙКB€\ЬЩ\ќYЩK›ШШ]ЬЉ	Л›^Z[ќYЬ][Ы‹\Э]\Л›^XЫЭ™\YЩKZXЫЫ‰КKЫЭ[ќ

H€€\ЬЩ\ќЩЩ[ЫY]ћJYЩKX™[
И‹Y][X\ЉB€ШЬ™Y[њЪЭ
YЩK€™][X\^ЫX™[Kњ™ИЉB€Ь[—ЫШљ™XЭИHYЩK™Щ]ШћWЬ›ЫJќ]Ы€‹[YOH“Ь[€Шљ™XЭИ‹^XЭUќYJB€Y€Ь[—ЫШљ™XЭЛЫЭ[ќ

N‚€Ь[—ЫШљ™XЭЛЫXЪК
NИYЩKќШZ]Щ›Ь—ЬЩ[XЭЬЉ	ЛњЭ‹]X›IКB‚€И[™›Ь›X][Ы€]\ЭШЬ›ЫИ]Иљ[[XШЩ\[ЩHЫЫќ›ЫИ]ЫX[Ы\™ЩHШШ[K‚€YЩK›ШШ]ЬЉ	ИЬYЪ[‹Z[™›ЙКKЫXЪК
B€YЩKќШZ]Щ›Ь—ЬЩ[XЭЬЉ	Л›^Z[™›Ь›X][Ы‹\[™[	КB€[™›ЧШ›ЩHHYЩK›ШШ]ЬЉ	Л›^Z[™›Ь›X][Ы‹\[™[›^Y]Z[\[™[X›ЩIКB€[™›ЧШ›ЩK™][X]J››ЩOO››ЩKњШЬ›ЫЬ[›ЩKњШЬ›ЫZYЪЉB€\ЭШXЭ[Ы€HYЩK™Щ]ШћWЬ›ЫJќ]Ы€‹[YOH•™\љYћHXШЩ\[ЩH]љY[ЩH‹^XЭUќYJB€\ЭШXЭ[Ы‹њШЬ›ЫЪ[ќЧЭљY]ЧЪY—Ы™YYY

B€›ЮH\ЭШXЭ[Ы‹›Э[™[™ЧШ›Ю

B€\ЬЩ\ќ›Ю[™›ЮИћH—HZYЪ[™›ЮИћH—H
И›ЮИљZYЪ—H€
X™[›Ю
B€\ЬЩ\ќЩЩ[ЫY]ћJYЩKX™[
И‹Z[™›ИЉB€ШЬ™Y[њЪЭ
YЩK€љ[™›Л^ЫX™[Kњ™ИЉB‚€\ЬЩ\ќ›Э\њ›ЬњЛ
X™[\њ›ЬњКB€™\Э[HИ›X™[Ћ€X™[њ\ЬЩYЋ€ќYKњ›ЭЬИЋ€YЩK›ШШ]ЬЉ	Л›^XЫЫ[[‹[\Э\›ЭЙКKЫЭ[ќ

_B€YЩKЫЬЩJ
B€™]\›€™\Э[‚‚™Y€XZ[Љ
HO€[ќ‚€Ъ][\љ[K•[\Ь\ћQ\™XЭЬћJ™Yљ^H›^Y]Ь‹\Э\™]ЛXњ›ЭЬЩ\‹HЉH\И[YN‚€›ЫЭH]
[YJB€Ш[YK›Ъ™XЭHXZЩWЩљ^\™J›ЫЭ
B€Ъ]Э\™]Х[^TЩ\ЬЪ[ЫЉВ€“VQUФ—ФХT‘UЧФ“УХЋ€ЭЉШ[YJK€“VQUФ—ФХT‘UЧФ“Т‘PХЋ€ЭЉ›Ъ™XЭ
K€JH\ИЩ\ЬЪ[Ы‹Ю[ЧЬ^]ЬљYЪ

H\И^N‚€њ›ЭЬЩ\€H^KЪ›ЫZ][K›][Ъ
^XЭ]X›WЬ]\Ъ][ќЪXЪ
Ъ›ЫZ][HЉHЬ€›Ы™KXY\ЬПUќYK\™ЬПVИ‹K[›Л\Ш[™›Ю—JB€ћN‚€™\Э[ИHВ€ќ[—ЭљY]ЬЬќ
њ›ЭЬЩ\‹Щ\ЬЪ[Ы‹ќ\››Ъ™XЭML
K€ќ[—ЭљY]ЬЬќ
њ›ЭЬЩ\‹Щ\ЬЪ[Ы‹ќ\››Ъ™XЭLЊЊ
K€ќ[—ЭљY]ЬЬќ
њ›ЭЬЩ\‹Щ\ЬЪ[Ы‹ќ\››Ъ™XЭLLНЊ›ЫЫOLKЊНJK€B€љ[[N‚€њ›ЭЬЩ\‹ЫЬЩJ
B€ИHњ›ЭЬЩ\€Ш]™H\И[ќ[ќ[Ы[љ^\™HЭ]]И›И[њЭ[YШ[YHљ[HX^HЪ[™ЩK‚€\ЬЩ\ќ
Ш[YHИђЫЫќ[ќ€И‘]H€И“Шљ™XЭЛћ€ЉKњ™XYШћ]\К
HOH€њЮ[ќ]XИШљ™XЭИ€‚€
ХUИњ™\Э[ЛљњЫЫ€ЉKќЬљ]WЭ^
њЫЫ‹™[\К™\Э[Л[™[ќLЉH
И—€‹[ЫЩ[™ПHќ]‹NЉB€љ[ќ
њЫЫ‹™[\К™\Э[Л[™[ќLЉJB€™]\›€‚‚љY€ЧЫ[YWЧИOH—ЧЫXZ[—ЧИЋ‚€Z\ЩHЮ\Э[Q^]
XZ[Љ
JB