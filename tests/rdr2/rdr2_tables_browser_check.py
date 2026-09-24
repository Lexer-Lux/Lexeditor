"""Every RDR2 tab that used to hand-build a table still draws its rows.

The tables on this page are the shared column list now. This check feeds each
tab a small synthetic payload of the shape its renderer reads, opens the tab and
asserts that rows were drawn and that nothing threw. No game data, no host.
"""
from pathlib import Path
import argparse
import json
import sys

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import rdr2_browser_check as base

CRIME_FIELDS = {"CrimeValue": "500", "PunishingCrimeValue": "250", "ImmediateDetectionRange": "30",
                "Timeout": "10", "MinTimeBeforeNotifyLawEnforcement": "4", "MinWantedLevelSP": "1",
                "ForcedWantedLevelIncreaseSP": "0", "NumWitnesses": "2", "ConfrontChance": "0.2",
                "Disabled": "false"}


def payloads():
    crimes = {"crimes": [dict(key=f"CRIME_{name}", severity="Low", **CRIME_FIELDS)
                         for name in ("THEFT", "ASSAULT")]}
    dispatch = {"rows": [{"group": "LAW_RESPONSE", "field": "WantedLevel1", "value": "3"},
                         {"group": "LAW_RESPONSE", "field": "WantedLevel2", "value": "5"}]}
    bounty = {"available": True, "scopeNote": "Synthetic",
              "settings": [{"id": "RandomWeight", "value": "1", "vanilla": "1"}],
              "cooldowns": [{"eventLabel": "Bounty acquired", "level": "Clean", "help": "", "levelHelp": "",
                             "min": "1", "max": "4", "ids": {"min": "cd_min", "max": "cd_max"}, "vanilla": {}}],
              "phases": [{"label": "Phase 1", "multiplier": "1.0", "multiplierId": "p1", "multiplierHelp": "",
                          "multiplierVanilla": "1.0",
                          "groups": [{"bucket": "fixed", "presetLabel": "Hunter", "min": "1", "max": "2",
                                      "chance": "0.5", "weight": "1",
                                      "ids": {"min": "g_min", "max": "g_max", "chance": "g_chance", "weight": "g_weight"}}]}],
              "presets": [{"preset": "PRESET_HUNTER", "label": "Hunter", "combatInfo": "COMBAT_A",
                           "chaseProfile": "CHASE_A", "loadouts": [{"name": "Rifle", "weight": 2}]}]}
    honor = {"available": True,
             "events": [{"id": "honor_event_1", "label": "Helped a stranger", "enabled": True}],
             "tiers": [{"id": "honor_tier_1", "vanilla": "40", "amount": 40, "enabled": True}]}
    mobs = {"combat": {"available": True, "source": "synthetic combatbehaviour.meta", "file": "combat",
                       "records": [{"name": "GANG_ODRISCOLLS", "group": "humans", "section": "CombatConfig",
                                    "fields": [{"field": "WeaponAccuracy", "value": "0.6",
                                                "path": ["WeaponAccuracy"], "kind": "float"}]}]},
            "health": {"available": True, "source": "synthetic pedhealth.meta", "file": "health",
                       "records": [{"name": "ENEMY_EASIEST", "group": "humans", "section": "HealthConfig",
                                    "fields": [{"field": "DefaultEnergy", "value": "100",
                                                "path": ["DefaultEnergy"], "kind": "float"}]}]}}
    mobModels = {"available": True, "rows": [{"model": "A_C_Bear_01", "observedHealth": 500,
                                              "probeStatus": "", "candidates": ["BEAR"]}]}
    ai = {"available": True, "fields": [{"context": "COMBAT", "field": "Accuracy", "value": "0.5",
                                         "path": ["COMBAT", "Accuracy"], "kind": "float"}]}
    aiFile = "ai/combatbehaviour.meta"
    shops = {"shops": [{"type": "ST_GENERAL", "items": [{"item": "CONSUMABLE_RUM", "requirements": [],
                                                         "requirementGroups": [], "cataloguePages": []}]}]}
    buyers = {"shops": ["ST_GENERAL"], "buyers": {"ST_GENERAL": ["CONSUMABLE_RUM"]}, "overrides": {}}
    return {"/api/crime": crimes, "/api/dispatch": dispatch, "/api/bounty-hunters": bounty,
            "/api/honor-actions": honor, "/api/mobs": mobs, "/api/mob-models": mobModels,
            "/api/ai/" + aiFile: ai, "/api/ai-reference/" + aiFile: {"fields": []},
            "/api/datamap": {"sections": [{"lines": []}]},
            "/api/shops": shops, "/api/shop-buyers": buyers,
            "/api/shops/acceptance": {"available": True, "shops": ["ST_GENERAL"], "rows": [],
                                      "summary": {"ST_GENERAL": {"listed": 1}},
                                      "unresolvedListed": {}}}


def document():
    # The base fixture defines window.__responses; ours has to land after it and
    # before the editor boots, so it goes right where that fixture script ends.
    html = base.document().replace("<head>", '<head><base href="https://lexeditor.test/">', 1)
    anchor = "window.__requests=[];"
    start = html.index(anchor)
    end = html.index("</script>", start)
    injection = ("\nObject.assign(window.__responses," + json.dumps(payloads()) + ");\n"
                 "const datasets=window.__responses['/api/config'].datasets;"
                 "datasets.crimeTweaks={label:'crimeTweaks',dir:'synthetic/crimeTweaks',"
                 "readonly:true,catalog:false,lootFiles:[]};"
                 "for(const key of Object.keys(datasets))"
                 "Object.assign(datasets[key],{crime:true,dispatch:true});\n")
    return html[:end] + injection + html[end:]


TABS = [("weapons", None), ("ai", ".ai-field-table"),
        ("mobs", ".mob-table, .mob-model-table"), ("crime", ".crime-table")]
SHOP_MODES = [("report", ".shop-acceptance-table")]
CRIME_SECTIONS = [("crimes", ".crime-table"), ("dispatch", ".dispatch-table"),
                  ("bounty", ".cooldown-table"), ("honor", ".honor-table")]


def run(executable):
    html = document()
    failures = []
    with sync_playwright() as playwright:
        options = {"headless": True}
        if executable:
            options["executable_path"] = executable
        browser = playwright.chromium.launch(**options)
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.route("**/*", lambda route: route.abort())
        page.set_content(html, wait_until="domcontentloaded")
        page.wait_for_timeout(400)
        for tab, selector in TABS:
            page.evaluate("t=>{state.tab=t;render();}", tab)
            page.wait_for_timeout(500)
            if selector and not page.locator(selector).count():
                failures.append(f"{tab}: no rows drawn ({selector})")
        for mode, selector in SHOP_MODES:
            page.evaluate("s=>{state.tab='shops';state.filters.shopMode=s;render();}", mode)
            page.wait_for_timeout(600)
            if not page.locator(selector).count():
                failures.append(f"shops/{mode}: no rows drawn ({selector})")
        for section, selector in CRIME_SECTIONS:
            page.evaluate("s=>{state.tab='crime';state.filters.crimeSection=s;render();}", section)
            page.wait_for_timeout(500)
            if not page.locator(selector).count():
                failures.append(f"crime/{section}: no rows drawn ({selector})")
        if errors:
            failures.append("page errors: " + "; ".join(errors[:4]))
        browser.close()
    if failures:
        print("FAIL:", *failures, sep="\n  ")
        return 1
    print("PASS: every converted RDR2 table draws its rows")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--chromium")
    sys.exit(run(parser.parse_args().chromium))
