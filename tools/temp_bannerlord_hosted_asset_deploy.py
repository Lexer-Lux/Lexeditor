from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


project_data = Path("games/bannerlord/project_data.py")
replace_once(
    project_data,
    '''        "ModuleDir": str(module_dir),\n        "OutputPath": str(output_path) + os.sep,\n''',
    '''        "ModuleDir": str(module_dir),\n        "OutputPath": str(output_path) + os.sep,\n        "LexeditorSkipAssetDeploy": "true",\n''',
    "hosted build override",
)

template = Path("games/bannerlord/template/BannerlordModule.csproj")
replace_once(
    template,
    '<Target Name="CopyModuleFiles" AfterTargets="Build">',
    '<Target Name="CopyModuleFiles" AfterTargets="Build" Condition="\'$(LexeditorSkipAssetDeploy)\' != \'true\'">',
    "template CopyModuleFiles condition",
)

test = Path("tests/test_bannerlord_build_install.py")
replace_once(
    test,
    '''                "OutputPath": str((selected / "Modules" / "SafeModule" / "bin" / "Win64_Shipping_Client").resolve()) + os.sep,\n            }\n''',
    '''                "OutputPath": str((selected / "Modules" / "SafeModule" / "bin" / "Win64_Shipping_Client").resolve()) + os.sep,\n                "LexeditorSkipAssetDeploy": "true",\n            }\n''',
    "build-install expected overrides",
)
replace_once(
    test,
    '''            self.assertIn(f"-p:ModuleDir={(selected / 'Modules' / 'SafeModule').resolve()}", command)\n            self.assertEqual(result["gameRootOverride"], str(selected))\n''',
    '''            self.assertIn(f"-p:ModuleDir={(selected / 'Modules' / 'SafeModule').resolve()}", command)\n            self.assertIn("-p:LexeditorSkipAssetDeploy=true", command)\n            self.assertEqual(result["gameRootOverride"], str(selected))\n''',
    "environment-root hosted skip assertion",
)
