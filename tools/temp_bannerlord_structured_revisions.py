from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


Path("games/bannerlord/source_revision.py").write_text('''"""Whole-file optimistic-concurrency tokens for structured Bannerlord editors."""\n\nfrom __future__ import annotations\n\nfrom hashlib import sha256\nfrom pathlib import Path\n\n\ndef source_revision(path: Path) -> str:\n    path = Path(path)\n    if not path.is_file():\n        return ""\n    return sha256(path.read_bytes()).hexdigest()\n\n\ndef attach_source_revision(payload: dict, path: Path | None = None) -> dict:\n    result = dict(payload)\n    source = Path(path) if path is not None else Path(str(result.get("path") or ""))\n    result["sourceHash"] = source_revision(source)\n    return result\n\n\ndef require_source_revision(path: Path, expected) -> None:\n    path = Path(path)\n    token = str(expected or "").strip()\n    if not token:\n        raise ValueError("Structured save requires the loaded source revision; reload before saving")\n    if not path.is_file():\n        raise FileNotFoundError(path)\n    if source_revision(path) != token:\n        raise ValueError("Structured source changed on disk; reload before saving")\n''', encoding="utf-8")

server = Path("games/bannerlord/server.py")
replace_once(
    server,
    '''from .settings_data import read_mcm_defaults, save_mcm_defaults\nfrom .project_data import (\n''',
    '''from .settings_data import read_mcm_defaults, save_mcm_defaults\nfrom .source_revision import attach_source_revision, require_source_revision\nfrom .project_data import (\n''',
    "server revision import",
)
replace_once(
    server,
    '''    return {\n        "root": str(PROJECT),\n        "projectFiles": [path.name for path in files],\n        "projectFile": read_project_file(selected) if selected else None,\n        "projectError": project_error,\n    }\n''',
    '''    return {\n        "root": str(PROJECT),\n        "projectFiles": [path.name for path in files],\n        "projectFile": attach_source_revision(read_project_file(selected), selected) if selected else None,\n        "projectError": project_error,\n    }\n''',
    "project GET revision",
)
replace_once(server, '''                self.send_json(read_submodule(source))\n''', '''                self.send_json(attach_source_revision(read_submodule(source), source))\n''', "module GET revision")
for endpoint, reader, label in [
    ("skills", "read_skill_definitions", "skills"),
    ("effects", "read_effect_definitions", "effects"),
    ("perks", "read_perk_definitions", "perks"),
    ("xp-sources", "read_xp_source_definitions", "XP sources"),
    ("settings-defaults", "read_mcm_defaults", "MCM defaults"),
]:
    replace_once(
        server,
        f'''        if path == "/api/{endpoint}":\n            try:\n                self.send_json({reader}(PROJECT))\n''',
        f'''        if path == "/api/{endpoint}":\n            try:\n                self.send_json(attach_source_revision({reader}(PROJECT)))\n''',
        f"{label} GET revision",
    )

replace_once(
    server,
    '''                self.send_json(save_module(source, self.read_json()))\n''',
    '''                payload = self.read_json()\n                require_source_revision(source, payload.pop("sourceHash", None))\n                result = save_module(source, payload)\n                result["module"] = attach_source_revision(result["module"], source)\n                self.send_json(result)\n''',
    "module POST revision",
)
replace_once(
    server,
    '''        if path == "/api/skills/save":\n            try:\n                self.send_json(save_skill_definitions(PROJECT, self.read_json()))\n''',
    '''        if path == "/api/skills/save":\n            try:\n                payload = self.read_json()\n                snapshot = read_skill_definitions(PROJECT)\n                source = Path(str(snapshot.get("path") or ""))\n                require_source_revision(source, payload.pop("sourceHash", None))\n                self.send_json(attach_source_revision(save_skill_definitions(PROJECT, payload)))\n''',
    "skills POST revision",
)
for endpoint, reader, saver, label in [
    ("effects", "read_effect_definitions", "save_effect_definitions", "effects"),
    ("perks", "read_perk_definitions", "save_perk_definitions", "perks"),
    ("xp-sources", "read_xp_source_definitions", "save_xp_source_definitions", "XP sources"),
    ("settings-defaults", "read_mcm_defaults", "save_mcm_defaults", "MCM defaults"),
]:
    old = f'''        if path == "/api/{endpoint}/save":\n            try:\n                payload = self.read_json()\n                self.send_json({saver}(PROJECT, list(payload.get("edits") or [])))\n'''
    new = f'''        if path == "/api/{endpoint}/save":\n            try:\n                payload = self.read_json()\n                snapshot = {reader}(PROJECT)\n                source = Path(str(snapshot.get("path") or ""))\n                require_source_revision(source, payload.pop("sourceHash", None))\n                self.send_json(attach_source_revision({saver}(PROJECT, list(payload.get("edits") or []))))\n'''
    replace_once(server, old, new, f"{label} POST revision")
replace_once(
    server,
    '''                project_file = resolve_project_file(PROJECT, payload.get("project"))\n                self.send_json(\n                    save_project_properties(project_file, dict(payload.get("edits") or {}))\n                )\n''',
    '''                project_file = resolve_project_file(PROJECT, payload.get("project"))\n                require_source_revision(project_file, payload.pop("sourceHash", None))\n                result = save_project_properties(project_file, dict(payload.get("edits") or {}))\n                result["project"] = attach_source_revision(result["project"], project_file)\n                self.send_json(result)\n''',
    "project POST revision",
)

core = Path("games/bannerlord/editor_core.js")
replace_once(
    core,
    '''  const moduleSavePayload=(m,baseline)=>({...moduleEditable(m),legacyDependenciesBaseline:clone(baseline?.legacyDependencies||[])});\n''',
    '''  const moduleSavePayload=(m,baseline)=>({...moduleEditable(m),legacyDependenciesBaseline:clone(baseline?.legacyDependencies||[]),sourceHash:baseline?.sourceHash||""});\n''',
    "module UI revision",
)

boot = Path("games/bannerlord/editor_boot.js")
replace_once(
    boot,
    '''          const result=await post("/api/project/save",{project:state.project.projectFile?.name||null,edits});\n''',
    '''          const result=await post("/api/project/save",{project:state.project.projectFile?.name||null,edits,sourceHash:state.savedProject.projectFile?.sourceHash||""});\n''',
    "project UI revision",
)
replace_once(
    boot,
    '''          attributes:makeEdits(state.skills.attributes,state.savedSkills.attributes,attributeFields),\n          skills:makeEdits(state.skills.skills,state.savedSkills.skills,skillFields)\n''',
    '''          attributes:makeEdits(state.skills.attributes,state.savedSkills.attributes,attributeFields),\n          skills:makeEdits(state.skills.skills,state.savedSkills.skills,skillFields),\n          sourceHash:state.savedSkills.sourceHash||""\n''',
    "skills UI revision",
)
replace_once(boot, '''        const result=await post("/api/effects/save",{edits});\n''', '''        const result=await post("/api/effects/save",{edits,sourceHash:state.savedEffects.sourceHash||""});\n''', "effects UI revision")
replace_once(boot, '''        const result=await post("/api/perks/save",{edits});\n''', '''        const result=await post("/api/perks/save",{edits,sourceHash:state.savedPerks.sourceHash||""});\n''', "perks UI revision")
replace_once(boot, '''        const result=await post("/api/xp-sources/save",{edits});\n''', '''        const result=await post("/api/xp-sources/save",{edits,sourceHash:state.savedXpSources.sourceHash||""});\n''', "XP UI revision")
replace_once(boot, '''        const result=await post("/api/settings-defaults/save",{edits});\n''', '''        const result=await post("/api/settings-defaults/save",{edits,sourceHash:state.savedMcmDefaults.sourceHash||""});\n''', "MCM UI revision")

plugin = Path("games/bannerlord/plugin.py")
replace_once(
    plugin,
    '''            saved = request_json(session.url + "api/module/save", {\n                "metadata": {"name": "Smoke Module Edited"}\n            })\n''',
    '''            saved = request_json(session.url + "api/module/save", {\n                "metadata": {"name": "Smoke Module Edited"},\n                "sourceHash": module.get("sourceHash", ""),\n            })\n''',
    "service smoke revision",
)

browser = Path("tests/bannerlord_browser_check.py")
replace_once(
    browser,
    '''    "version": "v1.0.0", "defaultModule": False, "singleplayer": True, "multiplayer": False,\n''',
    '''    "version": "v1.0.0", "defaultModule": False, "singleplayer": True, "multiplayer": False,\n    "sourceHash": "module-hash",\n''',
    "browser module revision fixture",
)
replace_once(
    browser,
    '''      const module={{...current,...metadata,\n        dependencies:body.dependencies??current.dependencies,\n''',
    '''      const module={{...current,...metadata,sourceHash:"module-hash-after",\n        dependencies:body.dependencies??current.dependencies,\n''',
    "browser module save revision response",
)
replace_once(
    browser,
    '''            assert request["body"]["legacyDependenciesBaseline"][0]["attributes"]["Future"] == "keep-browser"\n            assert page.evaluate("state.savedModule.legacyDependencies[0].id") == "LegacyBrowserRenamed"\n''',
    '''            assert request["body"]["legacyDependenciesBaseline"][0]["attributes"]["Future"] == "keep-browser"\n            assert request["body"]["sourceHash"] == "module-hash"\n            assert page.evaluate("state.savedModule.legacyDependencies[0].id") == "LegacyBrowserRenamed"\n            assert page.evaluate("state.savedModule.sourceHash") == "module-hash-after"\n''',
    "browser module revision transport",
)

Path("tests/test_bannerlord_source_revision.py").write_text('''from pathlib import Path\nimport tempfile\nimport unittest\n\nfrom games.bannerlord.source_revision import attach_source_revision, require_source_revision, source_revision\n\n\nclass BannerlordSourceRevisionTests(unittest.TestCase):\n    def test_revision_is_exact_file_bytes_and_rejects_stale_save(self):\n        with tempfile.TemporaryDirectory() as name:\n            source=Path(name)/"source.cs"\n            source.write_bytes(b"before\\r\\n")\n            token=source_revision(source)\n            self.assertEqual(len(token),64)\n            require_source_revision(source,token)\n            source.write_bytes(b"after\\n")\n            with self.assertRaisesRegex(ValueError,"changed on disk"):\n                require_source_revision(source,token)\n\n    def test_missing_revision_is_rejected(self):\n        with tempfile.TemporaryDirectory() as name:\n            source=Path(name)/"source.cs";source.write_text("x",encoding="utf-8")\n            with self.assertRaisesRegex(ValueError,"loaded source revision"):\n                require_source_revision(source,"")\n\n    def test_attach_revision_uses_payload_path(self):\n        with tempfile.TemporaryDirectory() as name:\n            source=Path(name)/"source.cs";source.write_text("x",encoding="utf-8")\n            payload=attach_source_revision({"path":str(source),"available":True})\n            self.assertEqual(payload["sourceHash"],source_revision(source))\n\n    def test_frontend_sends_saved_revision_for_every_structured_source(self):\n        root=Path(__file__).resolve().parents[1]/"games"/"bannerlord"\n        core=(root/"editor_core.js").read_text(encoding="utf-8")\n        boot=(root/"editor_boot.js").read_text(encoding="utf-8")\n        self.assertIn('sourceHash:baseline?.sourceHash||""',core)\n        for token in (\n            'sourceHash:state.savedProject.projectFile?.sourceHash||""',\n            'sourceHash:state.savedSkills.sourceHash||""',\n            'sourceHash:state.savedEffects.sourceHash||""',\n            'sourceHash:state.savedPerks.sourceHash||""',\n            'sourceHash:state.savedXpSources.sourceHash||""',\n            'sourceHash:state.savedMcmDefaults.sourceHash||""',\n        ):\n            self.assertIn(token,boot)\n\n\nif __name__ == "__main__":\n    unittest.main()\n''', encoding="utf-8")
