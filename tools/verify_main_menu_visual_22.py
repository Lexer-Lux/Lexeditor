"""Hidden rendered check for the square box-art chooser (GitHub #22)."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(r"C:\RDR2Mod\tools\reverse-engineering")))

from render_crime_editors_55_62 import Cdp, free_port, wait_eval, wait_json  # noqa: E402


def main() -> int:
    edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    covers = Path(os.environ["LOCALAPPDATA"]) / "Lexeditor" / "cover-art"
    rows = [
        ("blank", "Blank Game", "added", "", str(ROOT / "ui" / "assets" / "blank-game-cover.png")),
        ("ff8", "Final Fantasy VIII", "added", "", "ff8-39150.jpg"),
        ("warband", "Mount & Blade: Warband", "warning", "The game executable is missing.", "warband-48700.jpg"),
        ("rdr", "Red Dead Redemption", "not-added", "The game is not installed.", "rdr-2668510.jpg"),
        ("rdr2", "Red Dead Redemption 2", "added", "", "rdr2-1174180.jpg"),
    ]
    payload = []
    for plugin_id, name, status, problem, filename in rows:
        cover = Path(filename) if Path(filename).is_absolute() else covers / filename
        if not cover.is_file():
            raise FileNotFoundError(cover)
        font_items = ([{"name": "Redemption", "installed": True}, {"name": "RDR Lino", "installed": True}]
                      if plugin_id in {"rdr", "rdr2"} else [])
        payload.append({
            "id": plugin_id, "name": name, "status": status,
            "canOpen": status == "added", "scanInProgress": False,
            "root": f"C:\\Games\\{name}", "problems": [problem] if problem else [],
            "gameVersion": "1.2.3.4",
            "statusText": problem or "Ready", "resident": plugin_id == "ff8",
            "dirtyCount": 3 if plugin_id == "ff8" else 0,
            "coverArt": {"state": "ready", "uri": cover.as_uri()},
            "fonts": {"total": len(font_items), "installed": len(font_items), "items": font_items},
        })

    output = ROOT / "worklog" / "issues" / "rendered" / "github-22-main-menu-box-art-current.png"
    settings_output = ROOT / "worklog" / "issues" / "rendered" / "github-23-settings-current.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    profile = tempfile.TemporaryDirectory(prefix="lexeditor-menu-edge-", ignore_cleanup_errors=True)
    browser = None
    cdp = None
    port = free_port()
    hidden = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        browser = subprocess.Popen([
            str(edge), "--headless=new", "--no-first-run", "--no-default-browser-check",
            "--remote-allow-origins=*", "--use-angle=swiftshader",
            f"--remote-debugging-port={port}", f"--user-data-dir={profile.name}", "about:blank",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=hidden)
        page = next(row for row in wait_json(f"http://127.0.0.1:{port}/json/list") if row.get("type") == "page")
        cdp = Cdp(page["webSocketDebuggerUrl"])
        cdp.call("Page.enable")
        cdp.call("Runtime.enable")
        cdp.call("Emulation.setDeviceMetricsOverride", {
            "width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False,
        })
        cdp.call("Page.navigate", {"url": (ROOT / "ui" / "chooser.html").as_uri()})
        wait_eval(cdp, "!!window.__lexChooser", 20)
        source = """
          window.__testSettings={developerMode:false,lexerMode:true,lexerAuthorized:true,lexerLogin:'Lexer-Lux',hoverableAltClick:false,selectionHoldMs:650,tableRowsPerPage:15,panelGapPercent:1,residentHandleWidthPercent:5,mainMenuHeightPercent:9,soundEnabled:true,soundVolumePercent:50,absentGameDesaturationPercent:75,globalMessageRarity:3,loadingTransitionMinimumSeconds:1.5,viewPreferences:{},updateCheckFrequency:'daily',updateCheckChoices:[{value:'daily',label:'Daily'},{value:'weekly',label:'Weekly'}],defaultValues:{developerMode:false,hoverableAltClick:false,selectionHoldMs:650,tableRowsPerPage:15,panelGapPercent:1,residentHandleWidthPercent:5,mainMenuHeightPercent:9,soundEnabled:true,soundVolumePercent:50,absentGameDesaturationPercent:75,globalMessageRarity:3,loadingTransitionMinimumSeconds:1.5,updateCheckFrequency:'daily'},helpers:[]};
          window.__savedSettingsCalls=0;
          window.__savedDefaults=[];
          window.__restartCalls=0;
          window.__homeLinks=[];
          window.pywebview={api:{
            plugins:async()=>PAYLOAD,
            window_state:async()=>({maximized:false}),
            lexeditor_settings:async()=>structuredClone(window.__testSettings),
            save_lexeditor_settings:async values=>{window.__savedSettingsCalls++;Object.assign(window.__testSettings,values);return structuredClone(window.__testSettings)},
            save_lexer_setting_defaults:async defaults=>{const unsupported=Object.keys(defaults).filter(key=>!Object.prototype.hasOwnProperty.call(window.__testSettings.defaultValues,key));if(unsupported.length)throw new Error(`Setting cannot be a packaged default: ${unsupported[0]}`);window.__savedDefaults.push(structuredClone(defaults));window.__testSettings.defaultValues={...window.__testSettings.defaultValues,...defaults};return structuredClone(window.__testSettings)},
            open_home_link:async target=>{window.__homeLinks.push(target);return{opened:true,target}},
            restart_lexeditor:async()=>{window.__restartCalls++;return{restarting:true}},
            cover_art_data_uri:async id=>({uri:`data:image/jpeg;base64,${btoa(id)}`})
          }};
          window.dispatchEvent(new Event('pywebviewready'));
        """.replace("PAYLOAD", json.dumps(payload))
        cdp.eval(source)
        wait_eval(cdp, "document.querySelectorAll('.game-cover').length===5", 20)
        title_before = cdp.eval("getComputedStyle(document.querySelector('[data-plugin=\"warband\"] .game-name')).opacity")
        cdp.eval("document.querySelector('[data-plugin=\"warband\"]').focus()")
        wait_eval(cdp, "getComputedStyle(document.querySelector('[data-plugin=\"warband\"] .game-hover')).opacity==='1'", 10)
        result = cdp.eval("""(()=>{const cards=[...document.querySelectorAll('.game')],broken=document.querySelector('[data-plugin="warband"]'),hoveredTitle=broken.querySelector('.game-name').getBoundingClientRect(),hoveredCard=broken.getBoundingClientRect(),folderBox=broken.querySelector('.game-folder-button').getBoundingClientRect(),versionBox=broken.querySelector('.game-version').getBoundingClientRect(),resident=document.querySelector('#resident-handle'),header=document.querySelector('#chooser-window-header'),save=resident.querySelector('.resident-save').getBoundingClientRect(),name=resident.querySelector('.resident-game-name').getBoundingClientRect(),arrow=resident.querySelector('.resident-arrow').getBoundingClientRect(),headerBox=header.getBoundingClientRect(),residentBox=resident.getBoundingClientRect(),windowActions=document.querySelector('.chooser-window-controls>.lex-window-actions'),windowButton=windowActions.querySelector('.lex-window-button'),windowButtonStyle=getComputedStyle(windowButton),windowBox=windowActions.getBoundingClientRect(),twitter=document.querySelector('#home-twitter');return{
          cards:cards.length,names:cards.map(card=>card.querySelector('.game-name')?.textContent),
          hoveredNameOpacity:getComputedStyle(broken.querySelector('.game-name')).opacity,
          hoveredNameAbove:Math.abs(hoveredTitle.bottom-hoveredCard.top)<=1,
          hoveredNameHeight:hoveredTitle.height,
          hoveredNameBackground:getComputedStyle(broken.querySelector('.game-name')).backgroundColor,
          instructions:document.body.innerText.toLowerCase().includes('click to open'),
          shades:document.querySelectorAll('.game-shade').length,
          radii:cards.map(card=>getComputedStyle(card).borderRadius),
          borders:cards.map(card=>getComputedStyle(card).outlineStyle),
          states:cards.map(card=>card.querySelector('.state-label').textContent),
          brokenReason:broken.querySelector('.hover-detail').textContent,
          actionSize:broken.querySelector('.game-action-icon').getBoundingClientRect().width,
          actionIcons:cards.map(card=>card.querySelector('.game-action-icon').textContent.trim()),
          coverFilters:cards.map(card=>getComputedStyle(card.querySelector('.game-cover')).filter),
          absentSymbol:(()=>{const node=document.querySelector('[data-plugin="rdr"] .state-symbol'),box=node.getBoundingClientRect();return{text:node.textContent,width:box.width,fontSize:getComputedStyle(node).fontSize}})(),
          folderVisible:getComputedStyle(broken.querySelector('.game-folder-button')).visibility,
          folderTop:folderBox.top-hoveredCard.top,
          versionTop:versionBox.top-hoveredCard.top,
          version:broken.querySelector('.game-version').textContent,
          overlay:getComputedStyle(broken.querySelector('.game-hover')).backgroundColor,
          borderWidth:getComputedStyle(broken).borderTopWidth,
          stateOrder:(()=>{const label=broken.querySelector('.state-label').getBoundingClientRect(),symbol=broken.querySelector('.state-symbol').getBoundingClientRect();return label.right<=symbol.left})(),
          background:getComputedStyle(document.body).backgroundColor,
          resident:!document.querySelector('#resident-handle').hidden,
          residentHeight:document.querySelector('#resident-handle').getBoundingClientRect().height,
          residentTop:residentBox.top,
          menuHeight:headerBox.height,
          menuBottom:headerBox.bottom,
          headerRight:headerBox.right,
          windowActions:{left:windowBox.left,right:windowBox.right,top:windowBox.top,bottom:windowBox.bottom,opacity:getComputedStyle(windowActions).opacity,borderRadius:windowButtonStyle.borderRadius,borderStyle:windowButtonStyle.borderStyle,background:windowButtonStyle.backgroundColor},
          residentName:resident.querySelector('.resident-game-name').textContent,
          residentCount:resident.querySelector('.lex-save-count').textContent,
          residentCountHidden:resident.querySelector('.lex-save-count').hidden,
          residentOrder:save.bottom<name.top,
          residentSafeTop:save.top-residentBox.top,
          residentSafeBottom:residentBox.bottom-name.bottom,
          residentSafeExpected:residentBox.height*.15,
          residentNameAxis:Math.abs((name.left+name.right)/2-(residentBox.left+residentBox.right)/2),
          residentArrowNameGap:name.top-arrow.bottom,
          residentSaveSize:save.width,
          residentWidth:resident.getBoundingClientRect().width,
          residentArrowStroke:getComputedStyle(resident.querySelector('.resident-arrow svg')).strokeWidth,
          social:[...document.querySelectorAll('.home-social-button')].map(button=>button.getAttribute('aria-label')),
          twitterBefore:{bird:getComputedStyle(twitter.querySelector('.twitter-bird')).display,x:getComputedStyle(twitter.querySelector('.twitter-x')).display},
          viewportHeight:innerHeight
        }})()""")
        assert result["cards"] == 5 and result["names"] == [row[1] for row in rows], result
        assert title_before == "0" and result["hoveredNameOpacity"] == "1" and result["hoveredNameAbove"], result
        assert abs(result["hoveredNameHeight"] - 52) <= 1, result
        assert result["hoveredNameBackground"] == "rgba(0, 0, 0, 0)", result
        assert not result["instructions"], result
        assert result["shades"] == 0 and set(result["radii"]) == {"0px"}, result
        assert set(result["borders"]) == {"none"} and result["states"] == ["Ready", "Ready", "Broken", "Absent", "Ready"], result
        assert result["brokenReason"] == "The game executable is missing." and result["actionSize"] >= 55, result
        assert result["actionIcons"] == ["✍️", "✍️", "🛠️", "🔍", "✍️"] and result["folderVisible"] == "visible", result
        assert 14 <= result["folderTop"] <= 16 and 14 <= result["versionTop"] <= 16, result
        assert result["coverFilters"] == ["none", "none", "none", "grayscale(0.75)", "none"], result
        assert result["absentSymbol"] == {"text": "✕", "width": 18, "fontSize": "21px"}, result
        assert result["version"] == "v1.2.3.4" and result["borderWidth"] == "3px", result
        assert result["overlay"] == "rgba(0, 0, 0, 0.47)" and result["stateOrder"], result
        assert result["resident"] and result["residentHeight"] == result["viewportHeight"] and result["residentTop"] == 0, result
        assert result["menuHeight"] == 81, result
        assert result["windowActions"]["right"] <= result["headerRight"], result
        assert result["windowActions"]["top"] >= 0, result
        assert result["windowActions"]["right"] <= result["headerRight"], result
        assert float(result["windowActions"]["opacity"]) >= .5, result
        assert float(result["windowActions"]["borderRadius"].rstrip("px")) > 0, result
        assert result["windowActions"]["borderStyle"] == "solid", result
        assert result["windowActions"]["background"] not in {"rgba(0, 0, 0, 0)", "transparent"}, result
        assert result["residentName"] == "Final Fantasy VIII" and result["residentCount"] == "3", result
        assert not result["residentCountHidden"] and result["residentOrder"], result
        assert result["residentSafeTop"] >= result["residentSafeExpected"] - .5, result
        assert result["residentSafeBottom"] >= result["residentSafeExpected"] - .5, result
        assert result["residentSaveSize"] > 30, result
        assert abs(result["residentWidth"] - 72) < 1, result
        assert result["residentNameAxis"] <= 1, result
        assert result["residentArrowNameGap"] >= 8, result
        assert 3.5 <= float(result["residentArrowStroke"].rstrip("px")) <= 5, result
        resident_scale = cdp.eval("""(()=>{const root=document.documentElement,handle=document.querySelector('#resident-handle'),icon=handle.querySelector('.resident-save');root.style.setProperty('--lex-resident-handle-width','2.5vw');sizeResidentHandle();const narrow={handle:handle.getBoundingClientRect().width,icon:icon.getBoundingClientRect().width};root.style.setProperty('--lex-resident-handle-width','12vw');sizeResidentHandle();const wide={handle:handle.getBoundingClientRect().width,icon:icon.getBoundingClientRect().width};root.style.setProperty('--lex-resident-handle-width','5vw');sizeResidentHandle();return{narrow,wide}})()""")
        assert resident_scale["wide"]["handle"] > resident_scale["narrow"]["handle"], resident_scale
        assert resident_scale["wide"]["icon"] > resident_scale["narrow"]["icon"], resident_scale
        assert result["social"] == ["Open Lexeditor on GitHub", "Open @LexerLux on Twitter"], result
        assert result["twitterBefore"] == {"bird": "block", "x": "none"}, result
        twitter_box = cdp.eval("""(()=>{const box=document.querySelector('#home-twitter').getBoundingClientRect();return{x:box.left+box.width/2,y:box.top+box.height/2}})()""")
        cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": twitter_box["x"], "y": twitter_box["y"]})
        wait_eval(cdp, "getComputedStyle(document.querySelector('#home-twitter .twitter-x')).display==='block'", 5)
        twitter_hover = cdp.eval("""(()=>{const node=document.querySelector('#home-twitter');return{bird:getComputedStyle(node.querySelector('.twitter-bird')).display,x:getComputedStyle(node.querySelector('.twitter-x')).display}})()""")
        assert twitter_hover == {"bird": "none", "x": "block"}, twitter_hover
        cdp.eval("document.querySelector('#home-github').click();document.querySelector('#home-twitter').click()")
        wait_eval(cdp, "window.__homeLinks.length===2", 5)
        assert cdp.eval("window.__homeLinks") == ["github", "twitter"]
        cdp.eval("window.__testSettings.developerMode=true;applySharedSettings(window.__testSettings);chooser.plugins=PAYLOAD.map(row=>({...row,resident:false}));render(chooser.plugins)".replace("PAYLOAD", json.dumps(payload)))
        assert not cdp.eval("document.querySelector('#chooser-restart').hidden")
        cdp.eval("document.querySelector('#chooser-restart').click()")
        wait_eval(cdp, "window.__restartCalls===1", 5)
        home_shot = cdp.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False, "fromSurface": True})
        output.write_bytes(base64.b64decode(home_shot["data"]))
        cdp.eval("""transitionSnapshot().then(html=>window.__transitionProof={embedded:html.split('data:image/jpeg;base64,').length-1,localImage:html.includes('src=\"file:///'),resident:html.includes('id=\"resident-handle\"')})""")
        wait_eval(cdp, "!!window.__transitionProof", 20)
        transition = cdp.eval("window.__transitionProof")
        assert transition["embedded"] == 5 and not transition["localImage"] and transition["resident"], transition
        cdp.eval("LexeditorUI.openSettings()")
        wait_eval(cdp, "document.querySelectorAll('.lex-settings-lane').length===3", 10)
        settings_layout = cdp.eval("""(()=>{const lanes=[...document.querySelectorAll('.lex-settings-lane')],positions=lanes.map(node=>node.getBoundingClientRect().left),defaults=[...document.querySelectorAll('.lex-setting-default-control:not([hidden])')],user=document.querySelector('.lex-settings-lane-user'),lexer=document.querySelector('.lex-settings-lane-lexer');const current=document.querySelector('#lex-updateCheckFrequency'),target=document.querySelector('#lex-default-updateCheckFrequency');current.value='weekly';current.closest('.lex-global-setting').querySelector('.lex-setting-copy').dispatchEvent(new MouseEvent('dblclick',{bubbles:true,cancelable:true}));const sample=defaults[0],sampleStyle=getComputedStyle(sample),label=sample.querySelector(':scope>span'),checkbox=document.querySelector('.lex-setting-default-control input[type=checkbox]'),number=document.querySelector('.lex-setting-default-control input[type=number]');return{headings:lanes.map(node=>node.querySelector('h3').textContent),positions,defaults:defaults.length,copied:target.value,rarity:document.querySelector('#lex-default-globalMessageRarity')?.value,transitionMinimum:document.querySelector('#lex-default-loadingTransitionMinimumSeconds')?.value,authorized:!document.querySelector('#lex-lexer-mode').disabled,userBg:getComputedStyle(user).backgroundColor,lexerBg:getComputedStyle(lexer).backgroundColor,paired:defaults.every(node=>node.closest('.lex-global-setting')),defaultLabel:label?.textContent,defaultLabelColor:getComputedStyle(label).color,defaultBorder:sampleStyle.borderTopWidth,defaultBackground:sampleStyle.backgroundColor,checkboxAccent:getComputedStyle(checkbox).accentColor,numberBorder:getComputedStyle(number).borderTopColor}})()""")
        assert settings_layout["headings"] == ["GLOBAL SETTINGS", "LEXEDITOR EDITOR SETTINGS", "LEXER"], settings_layout
        assert settings_layout["positions"] == sorted(settings_layout["positions"]), settings_layout
        assert settings_layout["defaults"] == 8 and settings_layout["copied"] == "weekly" and settings_layout["paired"], settings_layout
        assert settings_layout["rarity"] == "3", settings_layout
        assert settings_layout["transitionMinimum"] == "1.5", settings_layout
        assert cdp.eval("document.querySelector('#lex-absentGameDesaturationPercent')===null&&document.querySelector('#lex-default-absentGameDesaturationPercent').value==='75'"), settings_layout
        assert settings_layout["authorized"] and settings_layout["userBg"] != settings_layout["lexerBg"], settings_layout
        assert settings_layout["defaultLabel"] == "DEFAULT" and settings_layout["defaultBorder"] == "0px", settings_layout
        assert settings_layout["defaultBackground"] == "rgba(0, 0, 0, 0)", settings_layout
        assert settings_layout["checkboxAccent"] == "rgb(157, 93, 204)" and settings_layout["numberBorder"] == "rgb(157, 93, 204)", settings_layout
        setting_geometry = cdp.eval("""(()=>{const rows=[...document.querySelectorAll('.lex-setting-control-pair')].map(pair=>{const controls=[...pair.querySelectorAll('input[type="number"],select')].filter(node=>!node.disabled),boxes=controls.map(node=>{const r=node.getBoundingClientRect(),owner=node.closest('.lex-setting-default-control,.lex-unit-field')||node,or=owner.getBoundingClientRect();return{id:node.id,left:r.left,right:r.right,width:r.width,ownerLeft:or.left,ownerRight:or.right,clientWidth:node.clientWidth,scrollWidth:node.scrollWidth}});return{boxes,overlap:boxes.length>1&&boxes[0].right>boxes[1].left+.5,contained:boxes.every(box=>box.left>=box.ownerLeft-.5&&box.right<=box.ownerRight+.5),readable:boxes.every(box=>box.width>=80&&box.scrollWidth<=box.clientWidth+1)}});return{rows,overflow:document.querySelector('.lex-global-settings').scrollWidth-document.querySelector('.lex-global-settings').clientWidth}})()""")
        assert all(not row["overlap"] and row["contained"] and row["readable"] for row in setting_geometry["rows"]), setting_geometry
        assert setting_geometry["overflow"] <= 1, setting_geometry
        pre_selection_dirty = int(cdp.eval("document.querySelector('.lex-global-settings .lex-save-count').textContent||'0'"))
        cdp.eval("""(()=>{const input=document.querySelector('#lex-selectionHoldMs');input.value='700';input.dispatchEvent(new Event('input',{bubbles:true}))})()""")
        wait_eval(cdp, "!document.querySelector('.lex-global-settings .lex-settings-save-control').disabled", 5)
        dirty = cdp.eval("""(()=>{const save=document.querySelector('.lex-global-settings .lex-settings-save-control'),badge=save.querySelector('.lex-save-count');return{disabled:save.disabled,count:badge.textContent,countHidden:badge.hidden}})()""")
        assert not dirty["disabled"] and not dirty["countHidden"] and int(dirty["count"]) >= pre_selection_dirty + 1, dirty
        cdp.eval("document.querySelector('.lex-global-settings .lex-settings-save-control').dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true}))")
        wait_eval(cdp, "!!document.querySelector('.lex-discard-dialog')", 5)
        cdp.eval("[...document.querySelectorAll('.lex-discard-dialog button')].find(button=>button.textContent==='Discard Changes').click()")
        wait_eval(cdp, "!document.querySelector('.lex-discard-dialog')", 5)
        discarded = cdp.eval("""(()=>{const input=document.querySelector('#lex-selectionHoldMs'),save=document.querySelector('.lex-global-settings .lex-settings-save-control'),badge=save.querySelector('.lex-save-count');return{value:input.value,disabled:save.disabled,countHidden:badge.hidden}})()""")
        assert discarded == {"value": "650", "disabled": True, "countHidden": True}, discarded
        cdp.eval("""(()=>{const input=document.querySelector('#lex-selectionHoldMs');input.value='700';input.dispatchEvent(new Event('input',{bubbles:true}))})()""")
        wait_eval(cdp, "!document.querySelector('.lex-global-settings .lex-settings-save-control').disabled", 5)
        cdp.eval("document.querySelector('.lex-global-settings .lex-settings-save-control').click()")
        wait_eval(cdp, "window.__savedSettingsCalls===1&&!document.querySelector('.lex-global-settings')", 5)
        saved = cdp.eval("(()=>({value:window.__testSettings.selectionHoldMs,calls:window.__savedSettingsCalls,closed:!document.querySelector('.lex-global-settings')}))()")
        assert saved == {"value": 700, "calls": 1, "closed": True}, saved
        cdp.eval("LexeditorUI.openSettings()")
        wait_eval(cdp, "!!document.querySelector('.lex-global-settings')", 5)
        cdp.eval("""(()=>{const current=document.querySelector('#lex-mainMenuHeightPercent'),fallback=document.querySelector('#lex-default-mainMenuHeightPercent');current.value='10';fallback.value='12';current.dispatchEvent(new Event('input',{bubbles:true}));fallback.dispatchEvent(new Event('input',{bubbles:true}))})()""")
        wait_eval(cdp, "!document.querySelector('.lex-global-settings .lex-settings-save-control').disabled", 5)
        cdp.eval("document.querySelector('.lex-global-settings .lex-settings-save-control').click()")
        wait_eval(cdp, "window.__savedSettingsCalls===2&&!document.querySelector('.lex-global-settings')", 5)
        paired_default = cdp.eval("""(()=>({current:window.__testSettings.mainMenuHeightPercent,fallback:window.__testSettings.defaultValues.mainMenuHeightPercent,menuHeight:document.querySelector('#chooser-window-header').getBoundingClientRect().height}))()""")
        assert paired_default == {"current": 10, "fallback": 12, "menuHeight": 90}, paired_default
        cdp.eval("LexeditorUI.openSettings()")
        wait_eval(cdp, "!!document.querySelector('.lex-global-settings')", 5)
        fit = cdp.eval("""(()=>{const dialog=document.querySelector('.lex-global-settings');return{scrolling:dialog.classList.contains('lex-settings-must-scroll'),scrollHeight:dialog.scrollHeight,viewport:innerHeight}})()""")
        assert not fit["scrolling"] and fit["scrollHeight"] <= fit["viewport"] - 24, fit
        cdp.call("Emulation.setDeviceMetricsOverride", {
            "width": 1440, "height": 600, "deviceScaleFactor": 1, "mobile": False,
        })
        wait_eval(cdp, "document.querySelector('.lex-global-settings').classList.contains('lex-settings-must-scroll')", 5)
        small_fit = cdp.eval("""(()=>{const dialog=document.querySelector('.lex-global-settings');return{scrolling:dialog.classList.contains('lex-settings-must-scroll'),clientHeight:dialog.clientHeight,scrollHeight:dialog.scrollHeight,viewport:innerHeight}})()""")
        assert (small_fit["scrolling"] and small_fit["scrollHeight"] > small_fit["clientHeight"]
                and small_fit["clientHeight"] <= small_fit["viewport"] - 24), small_fit
        cdp.call("Emulation.setDeviceMetricsOverride", {
            "width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False,
        })
        wait_eval(cdp, "!document.querySelector('.lex-global-settings').classList.contains('lex-settings-must-scroll')", 5)
        cdp.eval("""(()=>{const input=document.querySelector('#lex-selectionHoldMs');input.value='725';input.dispatchEvent(new Event('input',{bubbles:true}));const backdrop=document.querySelector('.lex-global-settings-backdrop'),box=backdrop.getBoundingClientRect();backdrop.dispatchEvent(new MouseEvent('click',{bubbles:true,clientX:box.left+2,clientY:box.top+2}))})()""")
        assert cdp.eval("!!document.querySelector('.lex-global-settings')&&document.querySelector('#lex-selectionHoldMs').value==='725'"), "Backdrop click closed or discarded dirty settings"
        cdp.eval("document.querySelector('.lex-global-settings .lex-close-button').click()")
        wait_eval(cdp, "!!document.querySelector('.lex-discard-dialog')", 5)
        cdp.eval("[...document.querySelectorAll('.lex-discard-dialog button')].find(button=>button.textContent==='Cancel').click()")
        assert cdp.eval("!!document.querySelector('.lex-global-settings')&&document.querySelector('#lex-selectionHoldMs').value==='725'"), "Cancel did not preserve the settings draft"
        cdp.eval("document.querySelector('.lex-global-settings .lex-close-button').click()")
        wait_eval(cdp, "!!document.querySelector('.lex-discard-dialog')", 5)
        cdp.eval("[...document.querySelectorAll('.lex-discard-dialog button')].find(button=>button.textContent==='Discard Changes').click()")
        wait_eval(cdp, "!document.querySelector('.lex-global-settings')", 5)
        cdp.eval("delete window.__testSettings.defaultValues.loadingTransitionMinimumSeconds;LexeditorUI.openSettings()")
        wait_eval(cdp, "!!document.querySelector('.lex-global-settings')", 5)
        stale_host = cdp.eval("""(()=>{const transition=document.querySelector('#lex-default-loadingTransitionMinimumSeconds'),description=transition.closest('.lex-global-setting').textContent;const input=document.querySelector('#lex-selectionHoldMs');input.value='710';input.dispatchEvent(new Event('input',{bubbles:true}));return{transitionDisabled:transition.disabled,description}})()""")
        wait_eval(cdp, "!document.querySelector('.lex-global-settings .lex-settings-save-control').disabled", 5)
        cdp.eval("document.querySelector('.lex-global-settings .lex-settings-save-control').click()")
        wait_eval(cdp, "window.__savedSettingsCalls===3&&!document.querySelector('.lex-global-settings')", 5)
        stale_host.update(cdp.eval("""(()=>({sentUnsupported:Object.prototype.hasOwnProperty.call(window.__savedDefaults.at(-1),'loadingTransitionMinimumSeconds'),saved:window.__testSettings.selectionHoldMs,closed:!document.querySelector('.lex-global-settings')}))()"""))
        assert stale_host["transitionDisabled"] and "Restart LEXEDITOR" in stale_host["description"], stale_host
        assert not stale_host["sentUnsupported"] and stale_host["saved"] == 710 and stale_host["closed"], stale_host
        cdp.eval("LexeditorUI.openSettings()")
        wait_eval(cdp, "!!document.querySelector('.lex-global-settings')", 5)
        document = cdp.eval("document.querySelector('.lex-global-settings').outerHTML.length")
        assert document > 1000, document
        result["settings"] = settings_layout
        result["settingsSave"] = {"dirty": dirty, "discarded": discarded, "saved": saved, "fit": fit, "smallFit": small_fit, "geometry": setting_geometry}
        result["twitterHover"] = twitter_hover
        result["pairedUserDefault"] = paired_default
        result["staleHostSettings"] = stale_host
        clean_resident = cdp.eval("""(()=>{const rows=window.__lexChooser?PAYLOAD:null;rows.find(row=>row.id==='ff8').dirtyCount=0;window.__lexChooser.render(rows);const save=document.querySelector('#resident-handle .resident-save'),count=save.querySelector('.lex-save-count');return{disabled:save.classList.contains('disabled'),countHidden:count.hidden}})()""".replace("PAYLOAD", json.dumps(payload)))
        assert clean_resident == {"disabled": True, "countHidden": True}, clean_resident
        result["transition"] = transition
        result["cleanResident"] = clean_resident
        shot = cdp.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False, "fromSurface": True})
        settings_output.write_bytes(base64.b64decode(shot["data"]))
        print(json.dumps({**result, "screenshot": str(output), "settingsScreenshot": str(settings_output)}, ensure_ascii=True))
        return 0
    finally:
        if cdp:
            cdp.close()
        if browser:
            browser.terminate()
            browser.wait(timeout=10)
        profile.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
