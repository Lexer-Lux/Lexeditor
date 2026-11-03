"""Native settings follow the shell's live process status without discarding edits."""
import json
from pathlib import Path

from test_shared_ui_feedback import framework, page

ROOT = Path(__file__).resolve().parents[2]


def test_native_settings_unlock_on_exit_and_preserve_dirty_edits(page, tmp_path):
    framework(page)
    settings = json.loads((ROOT / "ui/default_settings.json").read_text(encoding="utf-8"))
    settings.update(loadingTransitionMinimumSeconds=0, viewPreferences={})
    page.evaluate("""settings => {
      document.body.innerHTML='<div id="lexeditor-shell"></div><div id="toolbar"></div><main id="main"></main>';
      window.running=true; window.stateReads=0; window.diskValue=16;
      window.pywebview={api:new Proxy({
        lexeditor_settings:async()=>settings,
        game_process_status:async()=>({running:window.running,canLaunch:true}),
        onboarding_status:async()=>({show:false}),
        mod_projects:async()=>({canCreate:false,projects:[]}),
        project_info:async()=>({canCreate:false,projects:[]}),
        theme_sounds:async()=>({rows:[]}),
        window_state:async()=>({maximized:false})
      }, {get:(target,key)=>target[key]||(async()=>false)})};
      window.fetch=async path=>({ok:true,json:async()=>{
        if(path==='/api/plugin') return {pluginId:'fixture',name:'Native fixture',portName:'Fixture port'};
        if(path==='/api/datamap') return {rows:[]};
        if(path==='/api/state') {
          window.stateReads++;
          return {game:{supported:true,running:window.running},preferences:{fingerprint:'fixture',fields:[
            {key:'distance',label:'View distance',section:'World',kind:'number',min:0,max:30,step:1,value:window.diskValue}]}};
        }
        return {};
      }});
    }""", settings)
    page.add_script_tag(path=str(ROOT / "ui/native-port.js"))
    control = page.get_by_label("View distance", exact=True)
    control.wait_for()
    assert control.is_disabled()
    page.evaluate("window.running=false; window.diskValue=18")
    page.wait_for_function("!document.querySelector('input[aria-label=\"View distance\"]').disabled")
    page.wait_for_function("document.querySelector('input[aria-label=\"View distance\"]').value==='18'")
    reads = page.evaluate("window.stateReads")
    control.fill("24")
    control.dispatch_event("change")
    page.evaluate("window.running=true")
    page.wait_for_function("document.querySelector('input[aria-label=\"View distance\"]').disabled")
    page.evaluate("window.running=false; window.diskValue=20")
    page.wait_for_function("!document.querySelector('input[aria-label=\"View distance\"]').disabled")
    assert control.input_value() == "24"
    assert page.evaluate("window.stateReads") == reads
    page.screenshot(path=str(tmp_path / "native-settings-unlocked.png"))
