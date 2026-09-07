from pathlib import Path

p = Path("games/ff9/editor.html")
s = p.read_text(encoding="utf-8")
old = '''  async function loadDataset(key,force=false){if(!key)return null;if(!force&&state.datasets[key])return state.datasets[key];const meta=catalogRow(key);if(!meta?.available){state.datasets[key]={key,unavailable:true,error:`${meta?.relativePath||key} is not present in the project or a Memoria/Hades export.`};return state.datasets[key]}try{return installData(await api(`/api/dataset?key=${encodeURIComponent(key)}`))}catch(error){state.datasets[key]={key,unavailable:true,error:error.message};return state.datasets[key]}}\n'''
new = '''  async function loadDataset(key,force=false){if(!key)return null;if(!force&&state.datasets[key]&&!state.datasets[key].unavailable)return state.datasets[key];const meta=catalogRow(key);try{return installData(await api(`/api/dataset?key=${encodeURIComponent(key)}`))}catch(error){state.datasets[key]={key,unavailable:true,error:error.message,relativePath:meta?.relativePath};return state.datasets[key]}}\n'''
if old not in s:
    raise SystemExit("editor loadDataset anchor missing")
s = s.replace(old, new, 1)
old = '''  function unavailable(key){const meta=catalogRow(key);const data=state.datasets[key];return el("section",{class:"ff9-card"},el("h2",{},meta?.label||tabs.find(tab=>tab.id===state.tab)?.label||"FF9 data"),el("p",{},data?.error||"This format is not available."),el("p",{},"Lexeditor can safely edit this area after Hades Workshop or Memoria exports the matching CSV. The installed vanilla p0data containers are left untouched."),el("code",{class:"ff9-path"},meta?.projectPath||state.dashboard.project.root),el("span",{class:"ff9-warning"},"NO PROVED EDITABLE SOURCE"))}\n'''
new = '''  function unavailable(key){const meta=catalogRow(key);const data=state.datasets[key];return el("section",{class:"ff9-card"},el("h2",{},meta?.label||tabs.find(tab=>tab.id===state.tab)?.label||"FF9 data"),el("p",{},data?.error||"The verified source data could not be loaded right now."),el("p",{},"This editor format is integrated. Reopening it retries the verified Memoria baseline; saves still write only to the selected project overlay and never overwrite the installed-game baseline."),el("code",{class:"ff9-path"},meta?.projectPath||state.dashboard.project.root),el("span",{class:"ff9-warning"},"SOURCE CURRENTLY UNAVAILABLE"))}\n'''
if old not in s:
    raise SystemExit("editor unavailable anchor missing")
s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8")
