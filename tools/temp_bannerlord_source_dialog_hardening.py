from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# Raw-source saves must be compare-and-swap writes, not blind whole-file overwrites.
project_data = Path("games/bannerlord/project_data.py")
replace_once(
    project_data,
    '''def save_source(project: Path, requested: str, text: str) -> dict:\n    target = _safe_project_path(project, requested)\n    _old_text, encoding = _decode_source(target.read_bytes())\n    candidate = str(text)\n''',
    '''def save_source(\n    project: Path,\n    requested: str,\n    text: str,\n    original_text: str | None = None,\n) -> dict:\n    target = _safe_project_path(project, requested)\n    current_text, encoding = _decode_source(target.read_bytes())\n    if original_text is None:\n        raise ValueError("Source save requires the originally loaded text; reload before saving")\n    if current_text != str(original_text):\n        raise ValueError("Source file changed on disk; reload before saving")\n    candidate = str(text)\n''',
    "source compare-and-swap writer",
)

server = Path("games/bannerlord/server.py")
replace_once(
    server,
    '''                    save_source(\n                        PROJECT,\n                        str(payload.get("path") or ""),\n                        str(payload.get("text") or ""),\n                    )\n''',
    '''                    save_source(\n                        PROJECT,\n                        str(payload.get("path") or ""),\n                        str(payload.get("text") or ""),\n                        payload.get("originalText") if "originalText" in payload else None,\n                    )\n''',
    "source-save HTTP baseline",
)

core = Path("games/bannerlord/editor_core.js")
replace_once(
    core,
    '''  const {el,clone,showAlert}=LexeditorUI;\n''',
    '''  const {el,clone,showAlert,confirmAction}=LexeditorUI;\n''',
    "shared confirmation import",
)
replace_once(
    core,
    '''  const sourceDirty=()=>state.source&&state.savedSourceText!==null&&state.source.text!==state.savedSourceText;\n  function dirtyCount(){return Number(moduleDirty())+Number(projectDirty())+Number(skillsDirty())+Number(effectsDirty())+Number(perksDirty())+Number(xpSourcesDirty())+Number(sourceDirty())}\n''',
    '''  const sourceDirty=()=>state.source&&state.savedSourceText!==null&&state.source.text!==state.savedSourceText;\n  const normalizedFilePath=value=>String(value||"").replace(/\\\\/g,"/").replace(/\\/{2,}/g,"/").toLocaleLowerCase();\n  const sameFilePath=(left,right)=>{const a=normalizedFilePath(left),b=normalizedFilePath(right);return !!a&&!!b&&a===b};\n  function structuredSourceConflict(){\n    if(!sourceDirty())return "";\n    const sourcePath=state.source?.absolutePath||state.source?.path||"";\n    const candidates=[\n      ["SubModule.xml",moduleDirty(),state.module?.path],\n      ["project file",projectDirty(),state.project?.projectFile?.path],\n      ["custom skill definitions",skillsDirty(),state.skills?.path],\n      ["effect definitions",effectsDirty(),state.effects?.path],\n      ["perk definitions",perksDirty(),state.perks?.path],\n      ["XP source definitions",xpSourcesDirty(),state.xpSources?.path],\n      ["MCM defaults",mcmDirty(),state.mcmDefaults?.path],\n      ["Gauntlet prefab",gauntletDirty(),state.gauntlet?.path],\n      ["ModuleData XML",moduleDataDirty(),state.moduleData?.path],\n    ];\n    return candidates.find(([_label,dirty,path])=>dirty&&sameFilePath(sourcePath,path))?.[0]||"";\n  }\n  function dirtyCount(){return Number(moduleDirty())+Number(projectDirty())+Number(skillsDirty())+Number(effectsDirty())+Number(perksDirty())+Number(xpSourcesDirty())+Number(sourceDirty())}\n''',
    "structured/raw same-file conflict helper",
)

boot = Path("games/bannerlord/editor_boot.js")
replace_once(
    boot,
    '''"use strict";\n  async function save(){\n    try{\n      if(gauntletDirty()&&sourceDirty()&&state.source?.path===state.gauntlet?.relativePath){\n        throw new Error("The same Gauntlet prefab has unsaved structured and raw-source edits. Save or discard one editing surface before saving the other.");\n      }\n      if(moduleDataDirty()&&sourceDirty()&&state.source?.path===state.moduleData?.relativePath){\n        throw new Error("The same ModuleData XML has unsaved structured and raw-source edits. Save or discard one editing surface before saving the other.");\n      }\n''',
    '''"use strict";\n  async function reloadStructuredSource(absolutePath){\n    if(sameFilePath(absolutePath,state.module?.path)){\n      const value=await api("/api/module");state.module=value;state.savedModule=clone(value);return;\n    }\n    if(sameFilePath(absolutePath,state.project?.projectFile?.path)){\n      const selected=state.project?.projectFile?.name||"";\n      const value=await api(`/api/project${selected?`?project=${encodeURIComponent(selected)}`:""}`);\n      state.project=value;state.savedProject=clone(value);return;\n    }\n    if(sameFilePath(absolutePath,state.skills?.path)){const value=await api("/api/skills");state.skills=value;state.savedSkills=clone(value);return}\n    if(sameFilePath(absolutePath,state.effects?.path)){const value=await api("/api/effects");state.effects=value;state.savedEffects=clone(value);return}\n    if(sameFilePath(absolutePath,state.perks?.path)){const value=await api("/api/perks");state.perks=value;state.savedPerks=clone(value);return}\n    if(sameFilePath(absolutePath,state.xpSources?.path)){const value=await api("/api/xp-sources");state.xpSources=value;state.savedXpSources=clone(value);return}\n    if(sameFilePath(absolutePath,state.mcmDefaults?.path)){const value=await api("/api/settings-defaults");state.mcmDefaults=value;state.savedMcmDefaults=clone(value);return}\n    if(sameFilePath(absolutePath,state.gauntlet?.path)){\n      const value=await api(`/api/gauntlet?path=${encodeURIComponent(state.gauntlet.relativePath)}`);\n      state.gauntlet=value;state.savedGauntlet=clone(value);return;\n    }\n    if(sameFilePath(absolutePath,state.moduleData?.path)){\n      const value=prepareModuleData(await api(`/api/module-data?path=${encodeURIComponent(state.moduleData.relativePath)}`));\n      state.moduleData=value;state.savedModuleData=clone(value);return;\n    }\n  }\n\n  async function save(){\n    try{\n      const sourceConflict=structuredSourceConflict();\n      if(sourceConflict){\n        throw new Error(`The same ${sourceConflict} file has unsaved structured and raw-source edits. Save or discard one editing surface before saving the other.`);\n      }\n''',
    "generic source conflict preflight and reload",
)
replace_once(
    boot,
    '''      if(sourceDirty()){\n        const result=await post("/api/source/save",{path:state.source.path,text:state.source.text});\n        state.source=result;state.savedSourceText=result.text;\n        if(state.source.path.toLowerCase().endsWith(".csproj")){\n          state.project=await api("/api/project");state.savedProject=clone(state.project);\n        }\n      }\n''',
    '''      if(sourceDirty()){\n        const result=await post("/api/source/save",{\n          path:state.source.path,text:state.source.text,originalText:state.savedSourceText\n        });\n        state.source=result;state.savedSourceText=result.text;\n        await reloadStructuredSource(result.absolutePath||result.path);\n      }\n''',
    "raw source save baseline and structured reload",
)

# Native browser dialogs in split Bannerlord JS must use the shared themed confirmation UI.
gauntlet = Path("games/bannerlord/editor_gauntlet.js")
replace_once(
    gauntlet,
    '''  if(ask&&gauntletDirty()&&!window.confirm("Discard unsaved Gauntlet prefab changes?"))return;\n''',
    '''  if(ask&&gauntletDirty()){\n    const confirmed=await confirmAction({\n      title:"Discard unsaved Gauntlet changes?",\n      message:"Discard unsaved Gauntlet prefab changes?",confirmLabel:"Discard"\n    });\n    if(!confirmed)return;\n  }\n''',
    "Gauntlet discard confirmation",
)

moduledata = Path("games/bannerlord/editor_moduledata.js")
replace_once(
    moduledata,
    '''  if(ask&&moduleDataDirty()&&!window.confirm("Discard unsaved ModuleData changes?"))return;\n''',
    '''  if(ask&&moduleDataDirty()){\n    const confirmed=await confirmAction({\n      title:"Discard unsaved ModuleData changes?",\n      message:"Discard unsaved ModuleData changes?",confirmLabel:"Discard"\n    });\n    if(!confirmed)return;\n  }\n''',
    "ModuleData discard confirmation",
)
replace_once(
    moduledata,
    '''  if(action==="delete"&&!window.confirm(`Delete ${moduleDataRecordLabel(record)} from ${state.moduleData.relativePath}? A .lexeditor.bak backup will be created.`))return;\n''',
    '''  if(action==="delete"){\n    const confirmed=await confirmAction({\n      title:"Delete ModuleData record?",\n      message:`Delete ${moduleDataRecordLabel(record)} from ${state.moduleData.relativePath}? A .lexeditor.bak backup will be created.`,\n      confirmLabel:"Delete"\n    });\n    if(!confirmed)return;\n  }\n''',
    "ModuleData delete confirmation",
)

# Make the global contract cover split editor JS, not only editor.html shells.
contract = Path("tools/verify_shared_ui_contract.py")
replace_once(
    contract,
    '''for source_path in [ROOT / "ui" / "framework.js", ROOT / "ui" / "chooser.html"] + [\n        plugin / "editor.html" for plugin in sorted((ROOT / "games").iterdir())\n        if (plugin / "editor.html").is_file()]:\n    text = source_path.read_text(encoding="utf-8")\n''',
    '''dialog_sources = [ROOT / "ui" / "framework.js", ROOT / "ui" / "chooser.html"]\nfor plugin in sorted((ROOT / "games").iterdir()):\n    editor = plugin / "editor.html"\n    if not editor.is_file():\n        continue\n    dialog_sources.append(editor)\n    dialog_sources.extend(sorted(plugin.glob("editor*.js")))\nfor source_path in dialog_sources:\n    text = source_path.read_text(encoding="utf-8")\n''',
    "shared dialog contract split-JS coverage",
)

# Backend stale-write regressions.
test_source = Path("tests/test_bannerlord_source_safety.py")
test_source.write_text('''from pathlib import Path\nimport tempfile\nimport unittest\n\nfrom games.bannerlord.project_data import read_source, save_source\n\n\nclass BannerlordSourceSafetyTests(unittest.TestCase):\n    def test_source_save_requires_loaded_baseline(self):\n        with tempfile.TemporaryDirectory() as name:\n            project=Path(name); source=project/"notes.cs"; source.write_text("before\\n",encoding="utf-8")\n            before=source.read_bytes()\n            with self.assertRaisesRegex(ValueError,"originally loaded text"):\n                save_source(project,"notes.cs","after\\n")\n            self.assertEqual(source.read_bytes(),before)\n            self.assertFalse(source.with_name(source.name+".lexeditor.bak").exists())\n            self.assertFalse(source.with_name(source.name+".lexeditor.tmp").exists())\n\n    def test_external_source_change_is_rejected_before_backup_or_write(self):\n        with tempfile.TemporaryDirectory() as name:\n            project=Path(name); source=project/"notes.cs"; source.write_text("loaded\\n",encoding="utf-8")\n            baseline=read_source(project,"notes.cs")["text"]\n            source.write_text("external\\n",encoding="utf-8")\n            before=source.read_bytes()\n            with self.assertRaisesRegex(ValueError,"changed on disk"):\n                save_source(project,"notes.cs","my edit\\n",baseline)\n            self.assertEqual(source.read_bytes(),before)\n            self.assertFalse(source.with_name(source.name+".lexeditor.bak").exists())\n            self.assertFalse(source.with_name(source.name+".lexeditor.tmp").exists())\n\n    def test_matching_source_baseline_writes_and_backs_up(self):\n        with tempfile.TemporaryDirectory() as name:\n            project=Path(name); source=project/"notes.cs"; source.write_text("loaded\\n",encoding="utf-8")\n            baseline=read_source(project,"notes.cs")["text"]\n            result=save_source(project,"notes.cs","edited\\n",baseline)\n            self.assertEqual(source.read_text(encoding="utf-8"),"edited\\n")\n            self.assertEqual(Path(result["backup"]).read_text(encoding="utf-8"),"loaded\\n")\n            self.assertEqual(result["text"],"edited\\n")\n\n\nif __name__ == "__main__":\n    unittest.main()\n''', encoding="utf-8")

# Browser coverage: originalText transport and same-file structured/raw preflight.
browser = Path("tests/bannerlord_browser_check.py")
replace_once(
    browser,
    '''    if(path==="/api/module-data/save")return new Response(JSON.stringify(__moduleDataFixed),{{status:200}});\n''',
    '''    if(path==="/api/source/save"){{\n      return new Response(JSON.stringify({{\n        path:body.path,absolutePath:`C:/fixture/${{body.path}}`,encoding:"utf-8",text:body.text,size:body.text.length,saved:1,backup:`C:/fixture/${{body.path}}.lexeditor.bak`\n      }}),{{status:200}});\n    }}\n    if(path==="/api/module-data/save")return new Response(JSON.stringify(__moduleDataFixed),{{status:200}});\n''',
    "browser source-save fixture",
)
replace_once(
    browser,
    '''            assert page.evaluate("state.savedModule.legacyDependencies[0].id") == "LegacyBrowserRenamed"\n\n            page.evaluate('navigate("deployment")')\n''',
    '''            assert page.evaluate("state.savedModule.legacyDependencies[0].id") == "LegacyBrowserRenamed"\n\n            page.evaluate('''\n                window.__bannerlordRequests=[];\n                state.source={path:"src/Notes.cs",absolutePath:"C:/fixture/src/Notes.cs",encoding:"utf-8",text:"after"};\n                state.savedSourceText="before";\n            ''')\n            page.evaluate("save()")\n            page.wait_for_function("!sourceDirty()")\n            source_request = page.evaluate("window.__bannerlordRequests.find(row=>row.path==='/api/source/save')")\n            assert source_request["body"]["text"] == "after"\n            assert source_request["body"]["originalText"] == "before"\n\n            page.evaluate('navigate("deployment")')\n''',
    "browser source baseline transport",
)
replace_once(
    browser,
    '''            page.screenshot(path=str(ARTIFACTS / "bannerlord-editor.png"), full_page=True)\n            results.append({"viewport": [1280, 820], "status": "passed"})\n''',
    '''            page.screenshot(path=str(ARTIFACTS / "bannerlord-editor.png"), full_page=True)\n\n            page.evaluate('''\n                window.__bannerlordRequests=[];\n                state.source={path:"SubModule.xml",absolutePath:"C:/fixture/SubModule.xml",encoding:"utf-8",text:"raw changed"};\n                state.savedSourceText="raw before";\n                state.module.name="Structured changed";\n            ''')\n            page.evaluate("save()")\n            page.wait_for_timeout(100)\n            conflicting_requests = page.evaluate("window.__bannerlordRequests.filter(row=>row.path==='/api/module/save'||row.path==='/api/source/save')")\n            assert conflicting_requests == [], conflicting_requests\n\n            results.append({"viewport": [1280, 820], "status": "passed"})\n''',
    "browser structured/raw conflict preflight",
)
