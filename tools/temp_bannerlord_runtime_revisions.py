from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


revision = Path("games/bannerlord/source_revision.py")
text = revision.read_text(encoding="utf-8")
addition = '''\n\nMISSING_SOURCE_REVISION = "missing"\n\ndef optional_source_revision(path: Path) -> str:\n    path = Path(path)\n    return source_revision(path) if path.is_file() else MISSING_SOURCE_REVISION\n\n\ndef require_optional_source_revision(path: Path, expected) -> None:\n    token = str(expected or "").strip()\n    if not token:\n        raise ValueError("Runtime save requires the loaded source revision; reload before saving")\n    if optional_source_revision(path) != token:\n        raise ValueError("Runtime source changed on disk; reload before saving")\n'''
if "MISSING_SOURCE_REVISION" in text:
    raise SystemExit("optional source revision helpers already exist")
revision.write_text(text.rstrip() + addition + "\n", encoding="utf-8")

runtime = Path("games/bannerlord/runtime_overrides.py")
replace_once(
    runtime,
    '''from .skill_data import read_effect_definitions\n''',
    '''from .skill_data import read_effect_definitions\nfrom .source_revision import optional_source_revision, require_optional_source_revision\n''',
    "runtime revision imports",
)
replace_once(
    runtime,
    '''        "effectsPath": str(effects_path),\n        "xpSourcesPath": str(xp_path),\n        "effects": effects,\n''',
    '''        "effectsPath": str(effects_path),\n        "xpSourcesPath": str(xp_path),\n        "effectsHash": optional_source_revision(effects_path),\n        "xpSourcesHash": optional_source_revision(xp_path),\n        "effects": effects,\n''',
    "runtime read revisions",
)
replace_once(
    runtime,
    '''    current = read_runtime_overrides(project, game_root)\n    known_effects = {row["id"]: row for row in current["effects"]}\n    known_xp = {row["id"]: row for row in current["xpSources"]}\n    effect_values = _load_object(effects_path)\n    xp_values = _load_object(xp_path)\n    changed_effects = 0\n    changed_xp = 0\n\n    for edit in list(payload.get("effects") or []):\n''',
    '''    effect_edits = list(payload.get("effects") or [])\n    xp_edits = list(payload.get("xpSources") or [])\n    if effect_edits:\n        require_optional_source_revision(effects_path, payload.get("effectsHash"))\n    if xp_edits:\n        require_optional_source_revision(xp_path, payload.get("xpSourcesHash"))\n    current = read_runtime_overrides(project, game_root)\n    known_effects = {row["id"]: row for row in current["effects"]}\n    known_xp = {row["id"]: row for row in current["xpSources"]}\n    effect_values = _load_object(effects_path)\n    xp_values = _load_object(xp_path)\n    changed_effects = 0\n    changed_xp = 0\n\n    for edit in effect_edits:\n''',
    "runtime revision preflight",
)
replace_once(runtime, '''    for edit in list(payload.get("xpSources") or []):\n''', '''    for edit in xp_edits:\n''', "runtime XP edit list")

boot = Path("games/bannerlord/editor_boot.js")
replace_once(
    boot,
    '''        const result=await post("/api/runtime-overrides/save",{effects:effectEdits,xpSources:xpEdits});\n''',
    '''        const result=await post("/api/runtime-overrides/save",{\n          effects:effectEdits,xpSources:xpEdits,\n          effectsHash:state.savedRuntimeOverrides.effectsHash||"",\n          xpSourcesHash:state.savedRuntimeOverrides.xpSourcesHash||""\n        });\n''',
    "runtime UI revisions",
)

test = Path("tests/test_bannerlord_runtime_overrides.py")
text = test.read_text(encoding="utf-8")
insert = '''\n\ndef with_runtime_revisions(project: Path, game: Path, payload: dict) -> dict:\n    current = read_runtime_overrides(project, game)\n    return {\n        **payload,\n        "effectsHash": current["effectsHash"],\n        "xpSourcesHash": current["xpSourcesHash"],\n    }\n'''
needle = '''def write_module(root: Path, module_id: str) -> Path:\n'''
if text.count(needle) != 1:
    raise SystemExit("runtime test helper insertion point changed")
text = text.replace(needle, insert + "\n" + needle, 1)
text = text.replace('''            saved = save_runtime_overrides(project, {\n                "effects": [{"id": effect["id"], "overridden": True, "low": 125, "high": 75}],\n                "xpSources": [{"id": xp["id"], "overridden": True, "amount": 22.5}],\n            }, game)\n''', '''            saved = save_runtime_overrides(project, with_runtime_revisions(project, game, {\n                "effects": [{"id": effect["id"], "overridden": True, "low": 125, "high": 75}],\n                "xpSources": [{"id": xp["id"], "overridden": True, "amount": 22.5}],\n            }), game)\n''', 1)
text = text.replace('''            reverted = save_runtime_overrides(project, {\n                "effects": [{"id": effect["id"], "overridden": False}],\n                "xpSources": [{"id": xp["id"], "overridden": False}],\n            }, game)\n''', '''            reverted = save_runtime_overrides(project, with_runtime_revisions(project, game, {\n                "effects": [{"id": effect["id"], "overridden": False}],\n                "xpSources": [{"id": xp["id"], "overridden": False}],\n            }), game)\n''', 1)
text = text.replace('''            saved = save_runtime_overrides(project, {\n                "effects": [{"id": effect["id"], "overridden": True, "low": 125, "high": 75}],\n            }, game)\n''', '''            saved = save_runtime_overrides(project, with_runtime_revisions(project, game, {\n                "effects": [{"id": effect["id"], "overridden": True, "low": 125, "high": 75}],\n            }), game)\n''', 1)
text = text.replace('''                save_runtime_overrides(project, {\n                    "effects": [{"id": "Nope", "overridden": True, "low": 1, "high": 2}]\n                }, game)\n''', '''                save_runtime_overrides(project, with_runtime_revisions(project, game, {\n                    "effects": [{"id": "Nope", "overridden": True, "low": 1, "high": 2}]\n                }), game)\n''', 1)
text = text.replace('''                save_runtime_overrides(project, {\n                    "xpSources": [{"id": source["id"], "overridden": True, "amount": -1}]\n                }, game)\n''', '''                save_runtime_overrides(project, with_runtime_revisions(project, game, {\n                    "xpSources": [{"id": source["id"], "overridden": True, "amount": -1}]\n                }), game)\n''', 1)
marker = '''    def test_runtime_overrides_require_an_existing_deployed_module(self):\n'''
addition = '''    def test_external_runtime_file_creation_invalidates_missing_revision(self):\n        temporary, project, game, deployed = self.fixture()\n        try:\n            current = read_runtime_overrides(project, game)\n            effect = current["effects"][0]\n            module_data = deployed / "ModuleData"\n            module_data.mkdir()\n            effects_path = module_data / "custom_skill_effects.json"\n            effects_path.write_text("{}\\n", encoding="utf-8")\n            before = effects_path.read_bytes()\n            with self.assertRaisesRegex(ValueError, "changed on disk"):\n                save_runtime_overrides(project, {\n                    "effects": [{"id": effect["id"], "overridden": True, "low": 1, "high": 2}],\n                    "effectsHash": current["effectsHash"],\n                    "xpSourcesHash": current["xpSourcesHash"],\n                }, game)\n            self.assertEqual(effects_path.read_bytes(), before)\n            self.assertFalse(effects_path.with_name(effects_path.name + ".lexeditor.bak").exists())\n        finally:\n            temporary.cleanup()\n\n    def test_external_runtime_value_change_is_rejected(self):\n        temporary, project, game, deployed = self.fixture()\n        try:\n            module_data = deployed / "ModuleData"\n            module_data.mkdir()\n            effects_path = module_data / "custom_skill_effects.json"\n            effects_path.write_text("{}\\n", encoding="utf-8")\n            current = read_runtime_overrides(project, game)\n            effect = current["effects"][0]\n            effects_path.write_text('{"external": 1}\\n', encoding="utf-8")\n            before = effects_path.read_bytes()\n            with self.assertRaisesRegex(ValueError, "changed on disk"):\n                save_runtime_overrides(project, {\n                    "effects": [{"id": effect["id"], "overridden": True, "low": 1, "high": 2}],\n                    "effectsHash": current["effectsHash"],\n                    "xpSourcesHash": current["xpSourcesHash"],\n                }, game)\n            self.assertEqual(effects_path.read_bytes(), before)\n        finally:\n            temporary.cleanup()\n\n    def test_runtime_editor_sends_loaded_revisions(self):\n        boot = Path(__file__).resolve().parents[1] / "games" / "bannerlord" / "editor_boot.js"\n        text = boot.read_text(encoding="utf-8")\n        self.assertIn('effectsHash:state.savedRuntimeOverrides.effectsHash||""', text)\n        self.assertIn('xpSourcesHash:state.savedRuntimeOverrides.xpSourcesHash||""', text)\n\n'''
if text.count(marker) != 1:
    raise SystemExit("runtime stale test insertion point changed")
text = text.replace(marker, addition + marker, 1)
test.write_text(text, encoding="utf-8")
