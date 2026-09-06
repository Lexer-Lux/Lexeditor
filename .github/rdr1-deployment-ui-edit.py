from pathlib import Path

server = Path('games/rdr/server.py')
s = server.read_text(encoding='utf-8')
old = 'from . import mission_rewards, paths\n'
new = ('from . import mission_rewards, paths\n'
       'from .archive_deployment import (\n'
       '    ArchiveSpec, deploy_archives, deployment_status, revert_archives,\n'
       ')\n')
assert s.count(old) == 1
s = s.replace(old, new, 1)
old = '''GRINGO_OVERRIDE_ROOT = MOD_ROOT / "gringores"\nSETTINGS_FILE = paths.SETTINGS_FILE\n'''
new = '''GRINGO_OVERRIDE_ROOT = MOD_ROOT / "gringores"\nARCHIVE_SPECS = (\n    ArchiveSpec("tuning", Path("game") / "tune_d11generic.rpf", OVERRIDE_ROOT),\n    ArchiveSpec("content", Path("game") / "content.rpf", CONTENT_OVERRIDE_ROOT),\n    ArchiveSpec("gringores", Path("game") / "gringores.rpf", GRINGO_OVERRIDE_ROOT),\n)\nSETTINGS_FILE = paths.SETTINGS_FILE\n'''
assert s.count(old) == 1
s = s.replace(old, new, 1)
old = '''        "manifest": manifest,\n        "redHook": redhook_payload(),\n        "problems": paths.check()\n'''
new = '''        "manifest": manifest,\n        "redHook": redhook_payload(),\n        "deployment": deployment_status(GAME_ROOT, ARCHIVE_SPECS),\n        "problems": paths.check()\n'''
assert s.count(old) == 1
s = s.replace(old, new, 1)
old = '''                        "data-map", "redhook-prerequisite", "github-workspace",\n                    ],\n'''
new = '''                        "data-map", "redhook-prerequisite", "github-workspace",\n                        "archive-copy-deployment",\n                    ],\n'''
assert s.count(old) == 1
s = s.replace(old, new, 1)
old = '''            elif path == "/api/dashboard":\n                self.json_response(dashboard_payload())\n            elif path == "/api/files":\n'''
new = '''            elif path == "/api/dashboard":\n                self.json_response(dashboard_payload())\n            elif path == "/api/deployment":\n                self.json_response(deployment_status(GAME_ROOT, ARCHIVE_SPECS))\n            elif path == "/api/files":\n'''
assert s.count(old) == 1
s = s.replace(old, new, 1)
old = '''            elif path == "/api/redhook/configure":\n                self.json_response(configure_redhook())\n            else:\n'''
new = '''            elif path == "/api/redhook/configure":\n                self.json_response(configure_redhook())\n            elif path == "/api/deployment/deploy":\n                self.json_response(deploy_archives(\n                    GAME_ROOT, paths.RPF6_TOOL, ARCHIVE_SPECS))\n            elif path == "/api/deployment/revert":\n                self.json_response(revert_archives(GAME_ROOT, ARCHIVE_SPECS))\n            else:\n'''
assert s.count(old) == 1
s = s.replace(old, new, 1)
server.write_text(s, encoding='utf-8')

editor = Path('games/rdr/editor.html')
e = editor.read_text(encoding='utf-8')
old = '''    const deliveryCard=el("section",{class:"card"},el("h2",{},"Saved files and game delivery"),\n      el("p",{},"Save updates the workspace only. It does not install XML/WGD overrides or prove that LexerRDR.asi loaded a changed INI/JSON file."),\n      el("p",{},"Game deployment is not verified. Do not overwrite installed archives. The native runtime and its loader must be checked before an in-game test."),\n      ...Object.entries(state.dashboard.paths).filter(([name])=>["Editable overrides","Inventory overrides","Shop overrides","Settings","Loot ASI override","Mission ASI override"].includes(name)).map(([name,path])=>el("div",{class:"path-row"},el("b",{},name),el("code",{title:path},path))));\n'''
new = '''    const deployment=state.dashboard.deployment||{rows:[],pending:false,active:false};\n    const deploymentRows=(deployment.rows||[]).filter(row=>row.overrideCount||row.targetExists).map(row=>\n      el("div",{class:"path-row"},el("b",{},`${row.name}: ${row.overrideCount} override${row.overrideCount===1?"":"s"}`),\n        el("code",{title:row.target},row.changedSinceDeploy?"changed outside Lexeditor — deployment locked":row.deployed?"deployed and current":row.overrideCount?"saved; deployment needed":"not deployed")));\n    const deliveryCard=el("section",{class:"card"},el("h2",{},"Saved files and game delivery"),\n      el("p",{},"Save writes the project workspace. Deploy Project rebuilds verified copies of only the affected RPF archives and installs those copies under the loader's update\\game folder. The original game\\*.rpf archives are never overwritten."),\n      el("p",{},"LexerRDR.ini, loot JSON and mission JSON are consumed by the native runtime from this workspace; archive-backed XML/WGD edits use the update-folder copies below."),\n      el("div",{class:deployment.pending?"error":deployment.active?"ok":"source-note"},deployment.pending?"Saved archive edits are newer than the current deployment.":deployment.active?"Archive deployment matches the saved project.":"No Lexeditor archive-copy deployment is active."),\n      el("div",{class:"redhook-actions"},\n        el("button",{type:"button",onclick:()=>deployProject(),disabled:!deployment.pending},deployment.active?"Redeploy Project":"Deploy Project"),\n        el("button",{type:"button",class:"secondary",onclick:()=>revertProject(),disabled:!deployment.active},"Revert Deployment")),\n      el("div",{class:"path-row"},el("b",{},"Update-folder target"),el("code",{title:deployment.updateRoot||""},deployment.updateRoot||"Unavailable")),\n      ...deploymentRows,\n      ...Object.entries(state.dashboard.paths).filter(([name])=>["Editable overrides","Inventory overrides","Shop overrides","Settings","Loot ASI override","Mission ASI override"].includes(name)).map(([name,path])=>el("div",{class:"path-row"},el("b",{},name),el("code",{title:path},path))));\n'''
assert e.count(old) == 1
e = e.replace(old, new, 1)
old = '''  async function configureRedHook(){await api("/api/redhook/configure",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});state.dashboard=await api("/api/dashboard");}\n'''
new = '''  async function configureRedHook(){await api("/api/redhook/configure",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});state.dashboard=await api("/api/dashboard");}\n  async function deployProject(){\n    try{setStatus("Building verified RPF copies…");const result=await api("/api/deployment/deploy",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});state.dashboard=await api("/api/dashboard");setStatus(result.message||"Project archive copies deployed");renderProject();}\n    catch(error){setStatus("Deployment failed");showAlert({title:"Deployment failed",items:[{item:"Archive copies",issue:error.message||String(error)}],closeLabel:"Confirm and Close"});}\n  }\n  async function revertProject(){\n    try{setStatus("Reverting Lexeditor archive copies…");const result=await api("/api/deployment/revert",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});state.dashboard=await api("/api/dashboard");setStatus(result.message||"Archive deployment reverted");renderProject();}\n    catch(error){setStatus("Revert failed");showAlert({title:"Revert failed",items:[{item:"Archive copies",issue:error.message||String(error)}],closeLabel:"Confirm and Close"});}\n  }\n'''
assert e.count(old) == 1
e = e.replace(old, new, 1)
old = '''      [state.files,state.items,state.shops,state.missions,state.settings,state.loot]=await Promise.all([api("/api/files"),api("/api/items"),api("/api/shops"),api("/api/missions"),optionalRuntime("/api/settings"),optionalRuntime("/api/loot")]);\n      state.itemEdits={};state.shopEdits={};state.missionEdits={};state.settingEdits={};state.lootDocument=clone(state.loot.document);state.lootDirty=false;shell.history.clear();setStatus(`Saved to workspace: ${saved.join(", ")}. In-game deployment is not verified.`);render();\n'''
new = '''      [state.files,state.items,state.shops,state.missions,state.settings,state.loot,state.dashboard]=await Promise.all([api("/api/files"),api("/api/items"),api("/api/shops"),api("/api/missions"),optionalRuntime("/api/settings"),optionalRuntime("/api/loot"),api("/api/dashboard")]);\n      state.itemEdits={};state.shopEdits={};state.missionEdits={};state.settingEdits={};state.lootDocument=clone(state.loot.document);state.lootDirty=false;shell.history.clear();setStatus(`Saved to workspace: ${saved.join(", ")}. ${state.dashboard.deployment?.pending?"Deploy Project to rebuild the archive copies.":"Runtime-backed files are ready from the workspace."}`);render();\n'''
assert e.count(old) == 1
e = e.replace(old, new, 1)
editor.write_text(e, encoding='utf-8')

browser = Path('tools/verify_rdr_editing_browser.py')
b = browser.read_text(encoding='utf-8')
old = '''                    assert page.get_by_text('Saved files and game delivery', exact=True).count()\n'''
new = '''                    assert page.get_by_text('Saved files and game delivery', exact=True).count()\n                    assert page.get_by_role('button', name='Deploy Project').count()\n                    assert page.get_by_role('button', name='Revert Deployment').count()\n                    assert page.get_by_text('original game\\\\*.rpf archives are never overwritten', exact=False).count()\n'''
assert b.count(old) == 1
b = b.replace(old, new, 1)
browser.write_text(b, encoding='utf-8')
