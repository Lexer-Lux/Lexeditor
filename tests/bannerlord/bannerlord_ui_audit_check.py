"""Rendered Bannerlord UI audit against synthetic multi-page fixtures.

This intentionally exercises the real Bannerlord HTML, shared framework, and editor
modules without requiring an installed game. It is visual/interaction evidence, not
in-game acceptance.
"""
from __future__ import annotations

# Dev caches and outputs live in the temp folder, never in the checkout.
DEV_CACHE = __import__("pathlib").Path(__import__("tempfile").gettempdir()) / "lexeditor-dev"
import json
import os
from pathlib import Path
import shutil
import sys

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bannerlord_browser_check import inline_editor  # noqa: E402

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else DEV_CACHE / "bannerlord-ui-audit"
OUT.mkdir(parents=True, exist_ok=True)
_SHARED_UI_ENV = os.environ.get("LEXEDITOR_SHARED_UI_ROOT", "").strip()
SHARED_UI_ROOT = Path(_SHARED_UI_ENV).resolve() if _SHARED_UI_ENV else ROOT
# The feature branch predates the shared Integration Data Map. Once the
# merged tree carries it, the strict current-guide assertions apply even
# when the shared UI root is the repo itself.
MERGE_TARGET_UI = SHARED_UI_ROOT != ROOT or 'Filter files by integration' in (ROOT / 'ui' / 'framework.js').read_text(encoding='utf-8')
SHARED_UI_SHA = os.environ.get("LEXEDITOR_SHARED_UI_SHA", "").strip()

INJECT = r"""
(()=>{
  const attributes=Array.from({length:6},(_,i)=>({
    index:i,stringId:`Attribute${i}`,name:`Attribute ${i}`,abbreviation:`A${i}`,
    description:`Attribute ${i} groups related custom skills.`
  }));
  const skills=Array.from({length:48},(_,i)=>({
    index:i,stringId:`Skill${String(i).padStart(2,"0")}`,name:`Skill ${String(i).padStart(2,"0")}`,
    description:`Player-facing description for custom skill ${i}.`,
    howToLearn:`Perform supported gameplay action ${i} to earn XP.`,
    attributeId:attributes[i%attributes.length].stringId
  }));
  state.skills={available:true,path:"C:/fixture/src/CustomSkillDefinitions.cs",sourceHash:"skills-hash",attributes,skills};
  state.savedSkills=clone(state.skills);

  state.effects={available:true,path:"C:/fixture/src/CustomSkillEffectRanges.cs",sourceHash:"effects-hash",
    effects:Array.from({length:48},(_,i)=>({
      index:i,id:`Effect${String(i).padStart(2,"0")}`,label:`Effect ${String(i).padStart(2,"0")}`,
      skillId:skills[i%skills.length].stringId,defaultLow:i,defaultHigh:i+50,suffix:i%2?"%":""
    }))};
  state.savedEffects=clone(state.effects);

  state.perks={available:true,path:"C:/fixture/src/CustomSkillPerks.cs",sourceHash:"perks-hash",
    perks:Array.from({length:48},(_,i)=>({
      index:i,id:`Perk${String(i).padStart(2,"0")}`,name:`Perk ${String(i).padStart(2,"0")}`,
      skillId:skills[i%skills.length].stringId,level:(i*7)%101,implemented:i%4!==0,
      description:`Gameplay perk description ${i}.`
    }))};
  state.savedPerks=clone(state.perks);

  state.xpSources={available:true,path:"C:/fixture/src/CustomSkillXpSourcesConfig.cs",sourceHash:"xp-hash",
    sources:Array.from({length:48},(_,i)=>({
      index:i,id:`XpSource${String(i).padStart(2,"0")}`,label:`XP Source ${String(i).padStart(2,"0")}`,
      skillId:skills[i%skills.length].stringId,defaultAmount:i/4+0.5
    }))};
  state.savedXpSources=clone(state.xpSources);

  state.mcmDefaults={available:true,path:"C:/fixture/src/LexerSkillTweaksSettings.cs",sourceHash:"mcm-hash",
    settings:Array.from({length:48},(_,i)=>({
      property:`Setting${String(i).padStart(2,"0")}`,label:`Setting ${String(i).padStart(2,"0")}`,
      group:`Group ${String(Math.floor(i/4)).padStart(2,"0")}`,kind:i%3===0?"bool":i%3===1?"int":"float",
      default:i%3===0?i%2===0:i%3===1?i%11:i/10,min:i%3===0?undefined:0,max:i%3===0?undefined:100,
      hint:`Gameplay-facing help for setting ${i}.`,requireRestart:i%5===0,
      defaultExpression:String(i)
    }))};
  state.savedMcmDefaults=clone(state.mcmDefaults);

  state.runtimeOverrides={
    available:true,deployedRoot:"C:/game/Modules/FixtureMod",
    effectsHash:"runtime-effects",xpSourcesHash:"runtime-xp",
    effects:Array.from({length:48},(_,i)=>({
      id:`Effect${String(i).padStart(2,"0")}`,label:`Effect ${String(i).padStart(2,"0")}`,
      skillId:skills[i%skills.length].stringId,defaultLow:i,defaultHigh:i+50,low:i+1,high:i+51,
      overridden:i%3===0,suffix:i%2?"%":""
    })),
    xpSources:Array.from({length:48},(_,i)=>({
      id:`XpSource${String(i).padStart(2,"0")}`,label:`XP Source ${String(i).padStart(2,"0")}`,
      skillId:skills[i%skills.length].stringId,defaultAmount:i/4+0.5,amount:i/4+1,overridden:i%3===0
    }))
  };
  state.savedRuntimeOverrides=clone(state.runtimeOverrides);

  const dependencies=Array.from({length:42},(_,i)=>({
    index:i,id:`Dependency${String(i).padStart(2,"0")}`,dependentVersion:`v1.${i}.0`,
    optional:i%3===0,attributes:{}
  }));
  state.module={...state.module,dependencies,communityDependencies:[],legacyDependencies:[],
    modulesToLoadAfterThis:[],incompatibleModules:[],
    submodules:Array.from({length:36},(_,i)=>({
      index:i,name:`Submodule ${String(i).padStart(2,"0")}`,dllName:`Sub${i}.dll`,
      classType:`Fixture.Submodule${i}`,assemblies:[{index:0,value:`Extra${i}.dll`,attributes:{}}],
      tags:[{index:0,key:"DedicatedServerType",value:i%2?"none":"client",attributes:{}}]
    })),
    xmls:Array.from({length:36},(_,i)=>({
      index:i,id:`Xml${String(i).padStart(2,"0")}`,path:`ModuleData/xml_${i}`,
      includedGameTypes:[{index:0,value:i%2?"Campaign":"CustomGame",attributes:{}}]
    }))
  };
  state.savedModule=clone(state.module);

  state.gauntletFiles=Array.from({length:28},(_,i)=>`GUI/Prefabs/Fixture/Prefab_${String(i).padStart(2,"0")}.xml`);
  state.gauntlet={
    path:"C:/fixture/GUI/Prefabs/Fixture/Prefab_00.xml",relativePath:state.gauntletFiles[0],
    sourceHash:"gauntlet-hash",elementCount:48,
    elements:Array.from({length:48},(_,i)=>({
      index:i,path:`Prefab[0]/Widget[${i}]`,tag:"Widget",depth:1,line:i+2,hint:`@Binding${i}`,
      attributes:[
        {name:"IsEnabled",value:i%2?"true":"false",kind:"bool",choices:[]},
        {name:"SuggestedWidth",value:String(100+i),kind:"number",choices:[]},
        {name:"WidthSizePolicy",value:"StretchToParent",kind:"enum",choices:["Fixed","StretchToParent","CoverChildren"]}
      ]
    }))
  };
  state.savedGauntlet=clone(state.gauntlet);state.gauntletElementPath=state.gauntlet.elements[0].path;

  state.moduleDataFiles=Array.from({length:28},(_,i)=>`ModuleData/file_${String(i).padStart(2,"0")}.xml`);
  const records=Array.from({length:48},(_,i)=>({
    path:`Items[0]/Item[${i}]`,tag:"Item",line:i+2,id:`item_${String(i).padStart(2,"0")}`,
    name:`Fixture Item ${String(i).padStart(2,"0")}`,schemaIssueCount:i%11===0?1:0
  }));
  state.moduleData=prepareModuleData({
    path:"C:/fixture/ModuleData/file_00.xml",relativePath:state.moduleDataFiles[0],sourceHash:"moduledata-hash",
    rootTag:"Items",recordCount:records.length,records,
    elements:[
      {index:0,path:"Items[0]",tag:"Items",depth:0,line:1,hint:"",attributes:[],missingRequired:[],schemaIssues:[]},
      ...records.map((record,i)=>({
        index:i+1,path:record.path,tag:"Item",depth:1,line:record.line,hint:record.id,
        attributes:[
          {name:"enabled",value:i%2?"true":"false",kind:"bool",choices:[],schemaType:"boolean"},
          {name:"Type",value:i%2?"Weapon":"Armor",kind:"enum",choices:["Weapon","Armor"],schemaType:"string"},
          {name:"tier",value:String(i%7),kind:"number",choices:[],schemaType:"int",integer:true,min:0,max:6},
          {name:"id",value:record.id,kind:"text",choices:[],required:true,schemaType:"string"}
        ],
        missingRequired:[],schemaIssues:record.schemaIssueCount?["Fixture schema issue"]:[]
      }))
    ],
    schema:{id:"Items",path:"C:/game/XmlSchemas/Items.xsd",matchedByRegistration:true},
    schemaIssueCount:records.reduce((n,row)=>n+row.schemaIssueCount,0)
  });
  state.savedModuleData=clone(state.moduleData);applyModuleDataRecordSelection(records[0]);

  state.datamap={rows:Array.from({length:48},(_,i)=>({
    id:`map-${i}`,filename:`ModuleData/fixture_${String(i).padStart(2,"0")}.xml`,area:"Module data",
    controls:"Structured record editor",coverage:i%4===0?"view":"structured",status:"integrated",
    target:"moduledata",targets:["moduledata"],openable:true,sourceOpenable:true,sourceAvailable:true,
    editorPath:`ModuleData/fixture_${String(i).padStart(2,"0")}.xml`
  }))};
  state.deployment={...state.deployment,issues:[],inSync:true,descriptorInSync:true,
    runtimeOverrides:{
      "custom_skill_effects.json":{exists:true,valid:true,keys:48},
      "custom_skill_xp_sources.json":{exists:true,valid:true,keys:48}
    }
  };
  for(const key of Object.keys(state.uiTables||{}))delete state.uiTables[key];
  state.tweakPage=0;state.moduleView="metadata";state.skillView="definitions";
  state.gauntletView="files";state.moduleDataView="files";state.tab="module";
  render();refresh();
})()
"""

PAGES = [
    ("module-metadata", 'state.moduleView="metadata";navigate("module")'),
    ("module-dependencies", 'state.moduleView="dependencies";navigate("module")'),
    ("module-submodules", 'state.moduleView="submodules";navigate("module")'),
    ("module-xml", 'state.moduleView="xmls";navigate("module")'),
    ("skills-definitions", 'state.skillView="definitions";navigate("skills")'),
    ("skills-effects", 'state.skillView="effects";navigate("skills")'),
    ("skills-perks", 'state.skillView="perks";navigate("skills")'),
    ("skills-xp", 'state.skillView="xp";navigate("skills")'),
    ("tweaks", 'navigate("tweaks")'),
    ("runtime-effects", 'state.runtimeKind="effects";navigate("runtime")'),
    ("runtime-xp", 'state.runtimeKind="xp";navigate("runtime")'),
    ("gauntlet-files", 'state.gauntletView="files";navigate("gauntlet")'),
    ("gauntlet-widgets", 'state.gauntletView="widgets";navigate("gauntlet")'),
    ("moduledata-files", 'state.moduleDataView="files";navigate("moduledata")'),
    ("moduledata-records", 'state.moduleDataView="records";navigate("moduledata")'),
    ("build", 'navigate("build")'),
    ("info", 'navigate("info")'),
    ("datamap", 'navigate("datamap")'),
    ("source", 'state.source={path:"src/Test.cs",absolutePath:"C:/fixture/src/Test.cs",encoding:"utf-8",size:10,text:"class X{}"};state.savedSourceText="class X{}";navigate("source")'),
]


def outer_metrics(page):
    return page.evaluate("""()=>({
      bodyWidth:document.body.scrollWidth, viewportWidth:innerWidth,
      bodyHeight:document.body.scrollHeight, viewportHeight:innerHeight,
      main:(()=>{const z=Number.parseFloat(getComputedStyle(document.body).zoom)||1;const r=document.querySelector("#main").getBoundingClientRect();return {left:r.left/z,right:r.right/z,top:r.top/z,bottom:r.bottom/z,width:r.width/z,height:r.height/z}})()
    })""")


def assert_outer_fit(page, label):
    metrics = outer_metrics(page)
    assert metrics["bodyWidth"] <= metrics["viewportWidth"] + 3, (label, "horizontal overflow", metrics)
    assert metrics["bodyHeight"] <= metrics["viewportHeight"] + 3, (label, "outer vertical overflow", metrics)
    assert metrics["main"]["right"] <= metrics["viewportWidth"] + 2, (label, "main right clipped", metrics)
    assert metrics["main"]["bottom"] <= metrics["viewportHeight"] + 2, (label, "main bottom clipped", metrics)


def assert_pager_fit(page, label):
    pager = page.locator(".lex-pager").first
    if not pager.count():
        return
    metrics = pager.evaluate("""node=>{
      const box=node.getBoundingClientRect();
      const visible=[...node.children].filter(child=>getComputedStyle(child).display!=="none" && !child.hidden);
      const right=visible.length?Math.max(...visible.map(child=>child.getBoundingClientRect().right)):box.right;
      return {left:box.left,right:box.right,width:box.width,scrollWidth:node.scrollWidth,clientWidth:node.clientWidth,contentRight:right};
    }""")
    assert metrics["scrollWidth"] <= metrics["clientWidth"] + 2, (label, "pager horizontal overflow", metrics)
    assert metrics["contentRight"] <= metrics["right"] + 1, (label, "pager controls clipped", metrics)


def settle_screen(page, label):
    if label == "datamap":
        page.locator(".lex-data-map-table").wait_for()
    elif label == "source":
        page.locator("#main .lex-text-editor textarea").wait_for()
    elif label == "info":
        page.locator(".lex-information-panel").wait_for()
        page.locator(".lex-plugin-mod-loading").wait_for()
        page.locator(".lex-plugin-credits").wait_for()
        page.get_by_text("Lexer / Lexers Mod for Bannerlord", exact=True).wait_for()
        assert page.locator('.lex-information-panel [role="alert"]').count() == 0, "Bannerlord Info contains shared metadata error"
    else:
        page.wait_for_timeout(100)


def exercise_resizer(page, label):
    divider = page.locator(".lex-panel-layout-divider").first
    if not divider.count():
        raise AssertionError((label, "expected shared resizable panel divider"))
    before = divider.get_attribute("aria-valuenow")
    divider.focus()
    divider.press("ArrowRight")
    page.wait_for_function(
        """before=>{const d=document.querySelector('.lex-panel-layout-divider');
          return !!d && d.getAttribute('aria-valuenow')!==before}""",
        arg=before,
    )
    moved = page.locator(".lex-panel-layout-divider").first.get_attribute("aria-valuenow")
    assert moved != before, (label, "keyboard resize did not move divider")
    page.locator(".lex-panel-layout-divider").first.click(button="right")
    page.wait_for_function(
        """before=>{const d=document.querySelector('.lex-panel-layout-divider');
          return !!d && d.getAttribute('aria-valuenow')===before}""",
        arg=before,
    )


def exercise_table(page, label):
    table = page.locator(".lex-column-list").first
    if not table.count():
        return
    rows = table.locator(".lex-column-list-row")
    assert rows.count() > 0, label
    pager = page.locator(".lex-pager").first
    assert pager.count() == 1, (label, "record list missing shared pager")
    next_button = pager.get_by_role("button", name="Next page", exact=True)
    if next_button.count() and next_button.is_enabled():
        first = rows.first.inner_text()
        next_button.click()
        page.wait_for_timeout(120)
        second = page.locator(".lex-column-list").first.locator(".lex-column-list-row").first.inner_text()
        assert first != second, (label, "next page did not advance")
        pager = page.locator(".lex-pager").first
        pager.get_by_role("button", name="Previous page", exact=True).click()
        page.wait_for_timeout(100)

    search = pager.locator('input[type="search"]').first
    if search.count():
        needle = "__no_such_bannerlord_record__"
        search.fill(needle)
        page.wait_for_function(
            """()=>{const table=document.querySelector('.lex-column-list');
              return !!table && !table.querySelector('.lex-column-list-row:not(.lex-filler-row)')}"""
        )
        table = page.locator(".lex-column-list").first
        real_rows = table.locator(".lex-column-list-row:not(.lex-filler-row)")
        assert real_rows.count() == 0, (label, "search did not filter real records")
        assert "No " in page.locator(".lex-detail-panel").last.inner_text(), (label, "filtered table did not show shared empty detail")
        search = page.locator(".lex-pager").first.locator('input[type="search"]').first
        # Clear with real keystrokes. The pager search re-renders on every
        # applied input, and a programmatic fill("") can straddle that node
        # replacement without delivering an input event, leaving the stale
        # filter applied. Select-all plus Backspace reaches the same handler
        # a player uses when clearing the box.
        search.click()
        page.keyboard.press("ControlOrMeta+a")
        page.keyboard.press("Backspace")
        page.wait_for_function(
            """()=>{const table=document.querySelector('.lex-column-list');
              return !!table && !!table.querySelector('.lex-column-list-row:not(.lex-filler-row)')}"""
        )
        assert page.locator(".lex-column-list").first.locator(".lex-column-list-row:not(.lex-filler-row)").count() > 0, (label, "clearing search did not restore records")

    sort_button = page.locator(".lex-column-list-header .lex-column-sort").first
    if sort_button.count():
        sort_button.click()
        sorted_header = page.locator('.lex-column-list-head-cell[aria-sort="ascending"], .lex-column-list-head-cell[aria-sort="descending"]').first
        sorted_header.wait_for()
        first_direction = sorted_header.get_attribute("aria-sort")
        assert first_direction in {"ascending", "descending"}, (label, "sort state not exposed")
        page.locator(".lex-column-list-header .lex-column-sort").first.click()
        page.wait_for_function(
            """direction=>[...document.querySelectorAll('.lex-column-list-head-cell')].some(
                node=>['ascending','descending'].includes(node.getAttribute('aria-sort')) && node.getAttribute('aria-sort')!==direction)""",
            arg=first_direction,
        )

    rows = page.locator(".lex-column-list").first.locator(".lex-column-list-row")
    if rows.count() > 1:
        rows.nth(1).click()
        page.wait_for_timeout(50)
        assert rows.nth(1).get_attribute("aria-selected") == "true", (label, "selection did not move")
        rows.nth(1).press("ArrowUp")
        page.wait_for_timeout(50)


def screenshot(page, name, suffix):
    page.screenshot(path=str(OUT / f"{name}-{suffix}.png"), full_page=True)


def main() -> None:
    errors = []
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=shutil.which("chromium") or None,
                                    headless=True, args=["--no-sandbox"])
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.set_content(inline_editor(SHARED_UI_ROOT), wait_until="domcontentloaded")
            page.wait_for_function("state.module && state.project && state.datamap", timeout=8000)
            page.evaluate(INJECT)
            page.wait_for_timeout(200)

            # Shared shell icon routes: these must not exist as ordinary tabs.
            assert page.locator('nav button[data-tab="datamap"]').count() == 0
            assert page.locator('nav button[data-tab="info"]').count() == 0
            assert page.locator('nav button[data-tab="deployment"]').count() == 0
            page.locator("#plugin-data-map").click()
            page.wait_for_function('state.tab==="datamap"')
            page.locator(".lex-data-map-table").wait_for()
            if MERGE_TARGET_UI:
                assert page.locator(".lex-integration-status.integrated").count() > 0
                assert page.locator(".lex-integration-status.integrated .lex-status-mark").count() > 0
                # The status column shows an icon, so its meaning rides on the header title.
                assert page.locator('.lex-column-list-header .lex-column-list-head-cell[data-lex-title="Integration"]').count() == 1
            else:
                # The feature branch predates master's shared Integration Data Map.
                # Keep this native-candidate pass for layout sanity; the strict
                # current-guide assertion is made in the merge-target pass above.
                assert page.locator(".lex-coverage-cell").count() > 0
            page.locator("#plugin-info").click()
            page.wait_for_function('state.tab==="info"')

            # Navigation exposes a loading state before the next animation frame.
            loading = page.evaluate("""()=>{navigate("skills");return document.querySelector("#main").innerText}""")
            assert "Loading" in loading, loading
            page.wait_for_timeout(80)

            for name, command in PAGES:
                page.evaluate(command)
                settle_screen(page, name)
                assert "Bannerlord UI error" not in page.locator("#main").inner_text(), name
                assert_outer_fit(page, name)
                exercise_table(page, name)
                screenshot(page, name, "desktop")
                results.append({"screen": name, "mode": "desktop", "status": "passed"})

            # Resizing belongs to the shared layout and must remain keyboard-accessible.
            page.evaluate('state.moduleView="dependencies";navigate("module")')
            settle_screen(page, "module-dependencies")
            exercise_resizer(page, "module-dependencies")
            page.evaluate('navigate("build")')
            settle_screen(page, "build")
            exercise_resizer(page, "build")

            # Direct cell editor on a real editable shared table cell.
            page.evaluate('state.skillView="effects";navigate("skills")')
            page.wait_for_timeout(100)
            editable = page.locator(".lex-column-list-cell.lex-cell-editable").first
            assert editable.count() == 1
            before = page.evaluate("state.effects.effects[0].defaultLow")
            editable.dblclick()
            number = editable.locator('input[type="number"]')
            assert number.count() == 1
            number.fill(str(float(before) + 7))
            number.press("Enter")
            page.wait_for_timeout(80)
            assert page.evaluate("effectsDirty()") is True
            page.evaluate("state.effects=clone(state.savedEffects);render();refresh()")

            # Empty and error states use shared panels rather than blank/custom pages.
            page.evaluate('state.effects.available=false;state.skillView="effects";navigate("skills")')
            # Navigation flashes a loading panel first; wait for the settled empty state.
            page.wait_for_function("()=>[...document.querySelectorAll('#main input')].some(i=>i.value.includes('does not contain'))")
            empty_state = page.locator(".lex-detail-field").filter(has_text="State").locator("input.lex-readonly-field").first
            empty_state.wait_for()
            assert "does not contain" in empty_state.input_value()
            assert page.locator(".lex-detail-panel").count() >= 1
            page.evaluate('state.effects.available=true;state.effects=clone(state.savedEffects);render()')
            page.evaluate('window.__savedRenderBuild=renderBuild;renderBuild=()=>{throw new Error("fixture render failure")};navigate("build")')
            error_state = page.locator(".lex-detail-field").filter(has_text="What happened").locator("input.lex-readonly-field").first
            error_state.wait_for()
            assert error_state.input_value() == "fixture render failure"
            assert page.locator(".lex-detail-panel").count() >= 1
            page.evaluate('renderBuild=window.__savedRenderBuild;delete window.__savedRenderBuild;navigate("build")')

            # Small viewport: every screen remains within the outer window.
            page.set_viewport_size({"width": 900, "height": 620})
            page.evaluate('document.body.style.zoom=""')
            for name, command in PAGES:
                page.evaluate(command);settle_screen(page, name)
                assert_outer_fit(page, f"{name}-small")
                if name == "datamap":
                    assert_pager_fit(page, f"{name}-small")
                screenshot(page, name, "small")
                results.append({"screen": name, "mode": "small", "status": "passed"})

            # Large UI scale proxy: Chromium CSS zoom exercises the same CSS boxes
            # under enlarged controls/text while the host's actual scale is native WebView zoom.
            page.set_viewport_size({"width": 1200, "height": 800})
            page.evaluate('document.body.style.zoom="1.5"')
            for name, command in PAGES:
                page.evaluate(command);settle_screen(page, name)
                assert_outer_fit(page, f"{name}-150pct")
                screenshot(page, name, "150pct")
                results.append({"screen": name, "mode": "150pct", "status": "passed"})

            # Tweaks must expose later groups through the shared pager and the last
            # control must be reachable at enlarged scale.
            page.evaluate('state.tweakPage=0;navigate("tweaks")');page.wait_for_timeout(100)
            assert "Group 11" not in page.locator("#main").inner_text()
            tweaks_pager = page.locator(".lex-tweaks-pages .lex-pager")
            assert tweaks_pager.count() == 1
            # Page size follows the measured fit, so walk forward until the last group appears.
            for _ in range(6):
                if "Group 11" in page.locator("#main").inner_text():
                    break
                tweaks_pager.get_by_role("button", name="Next page", exact=True).click()
                page.wait_for_timeout(100)
            assert "Group 11" in page.locator("#main").inner_text()
            last = page.locator(".lex-detail-field").filter(has_text="Setting 47").last
            assert last.count() == 1
            last.scroll_into_view_if_needed()
            box = last.bounding_box()
            assert box and box["y"] < 800 and box["y"] + box["height"] > 0, box
            screenshot(page, "tweaks-last-controls", "150pct")

            # The bottom of the unified Info panel, including shared Credits, must also be reachable.
            page.evaluate('document.body.style.zoom="1.5";navigate("info")')
            settle_screen(page, "info")
            info_last = page.locator(".lex-plugin-credits").last
            info_last.scroll_into_view_if_needed()
            info_box = info_last.bounding_box()
            assert info_box and info_box["y"] < 800 and info_box["y"] + info_box["height"] > 0, info_box
            screenshot(page, "info-last-controls", "150pct")

            # Raw source remains reachable and editable as a specialized source surface.
            page.evaluate('document.body.style.zoom="";state.source={path:"src/Test.cs",absolutePath:"C:/fixture/src/Test.cs",encoding:"utf-8",size:10,text:"class X{}"};state.savedSourceText="class X{}";navigate("source")')
            settle_screen(page, "source")
            source_box = page.locator("#main .lex-text-editor textarea")
            assert source_box.count() == 1
            source_box.fill("class Y{}")
            assert page.evaluate("sourceDirty()") is True
            page.evaluate('state.source.text=state.savedSourceText;render();refresh()')
            assert page.evaluate("sourceDirty()") is False
            assert_outer_fit(page, "source")

            # Keyboard help uses the shared focus/ArrowDown/Escape contract.
            page.evaluate('state.moduleView="metadata";navigate("module")')
            page.wait_for_timeout(80)
            help_marker = page.locator(".lex-info-help").first
            assert help_marker.count() == 1
            help_marker.focus()
            page.wait_for_timeout(40)
            popover = page.locator(".lex-help-popover")
            assert popover.count() == 1
            help_marker.press("ArrowDown")
            assert page.evaluate("document.activeElement?.classList.contains('lex-help-popover')") is True
            page.keyboard.press("Escape")
            page.wait_for_timeout(40)
            assert page.locator(".lex-help-popover").count() == 0

            page.locator("#lexeditor-shortcuts").click()
            page.wait_for_timeout(50)
            assert page.locator(".lex-shortcut-panel, .lex-dialog").count() >= 1
            page.keyboard.press("Escape")

            page.close()
        finally:
            browser.close()

    report={"fixtureOnly":True,"sharedUi":"current-master" if MERGE_TARGET_UI else "branch-native","sharedUiSha":SHARED_UI_SHA,"results":results,"errors":errors}
    (OUT / "results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    assert not errors, errors
    print(json.dumps({"checks":len(results),"errors":errors}, indent=2))


if __name__ == "__main__":
    main()
