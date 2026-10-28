"""Recovery when preparing a game launch (core/mod_builds.py).

An identified mod failure disables that mod and its dependents, then the
remaining set installs fresh: no stale payload from the faulty mod is used.
Unattributed failures still stop deployment without disabling anything.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.mod_builds import ModBuildError, activate_for_launch


def write_mod(parent: Path, folder: str, name: str | None = None, **extra) -> Path:
    mod = parent / folder
    mod.mkdir(parents=True, exist_ok=True)
    data = {"name": name or folder, "enabled": True}
    data.update(extra)
    (mod / "mod.json").write_text(json.dumps(data), encoding="utf-8")
    return mod


def write_schema_requires(mod: Path, requires: list[str]) -> None:
    (mod / "settings.schema.json").write_text(
        json.dumps({"fields": [], "requires": list(requires)}), encoding="utf-8")


def enabled_of(mod: Path) -> bool:
    return json.loads((mod / "mod.json").read_text(encoding="utf-8"))["enabled"]


class ScriptedAdapter:
    """A synthetic adapter.activate fixture that records every attempt."""

    def __init__(self, behavior):
        self._behavior = behavior
        self.calls: list[list[Path]] = []

    def activate(self, active, game_root):
        self.calls.append([Path(folder) for folder in active])
        return self._behavior(list(active), game_root)


def deploy_from_active(active, game_root):
    """A successful build deploys exactly the mods it was given, nothing else."""
    del game_root
    return {"deployed": sorted(Path(folder).name for folder in active)}


class ActivateForLaunchTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="mod-build-recovery-")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.game_root = self.root / "game"
        self.game_root.mkdir()

    def test_identified_failure_disables_mod_and_retries_without_it(self):
        good = write_mod(self.root, "good", "Good Mod")
        bad = write_mod(self.root, "bad", "Bad Mod")

        def behavior(active, game_root):
            if bad.resolve() in [Path(folder).resolve() for folder in active]:
                raise ModBuildError([bad], "Bad Mod broke the build")
            return deploy_from_active(active, game_root)

        adapter = ScriptedAdapter(behavior)
        result = activate_for_launch(adapter, [good, bad], self.game_root)

        self.assertFalse(enabled_of(bad))
        self.assertTrue(enabled_of(good))
        self.assertEqual(len(adapter.calls), 2)
        self.assertEqual([folder.name for folder in adapter.calls[1]], ["good"])
        self.assertEqual(result["deployed"], ["good"])
        self.assertEqual(result["disabledMods"],
                         [{"folder": "bad", "name": "Bad Mod",
                           "error": "Bad Mod broke the build"}])

    def test_actual_script_failure_is_attributed_and_good_mod_is_rebuilt(self):
        from core import script_mods
        good = write_mod(self.root, 'good', script={'version': 1})
        bad = write_mod(self.root, 'bad', script={'version': 1})
        for mod in (good, bad):
            (mod/'script').mkdir()
            (mod/'script/__init__.py').write_text('')
            (mod/'settings.schema.json').write_text('{"fields": []}')
        (good/'script/tweak.py').write_text(
            'def build(settings, context):\n    return {"native/good.json": "fresh"}\n')
        (bad/'script/tweak.py').write_text(
            'def build(settings, context):\n    raise ValueError("broken source")\n')
        def behavior(active, game_root):
            rows = [script_mods.catalog_row(folder) for folder in active]
            script_mods.build_batch(rows, SimpleNamespace(current=''), allowed_roots=('native',))
            return {'payload': [(folder/'native/good.json').read_text() for folder in active]}
        adapter = ScriptedAdapter(behavior)
        result = activate_for_launch(adapter, [good, bad], self.game_root)
        self.assertEqual(result['payload'], ['fresh'])
        self.assertFalse(enabled_of(bad))
        self.assertIn('broken source', result['disabledMods'][0]['error'])

    def test_actual_launch_path_starts_game_after_disabling_bad_mod_and_reports_it(self):
        from core.desktop_host import HostApi
        library = self.root/'library/ds1'
        good = write_mod(library, 'good', 'Good Mod')
        bad = write_mod(library, 'bad', 'Bad Mod')
        def behavior(active, game_root):
            if bad.resolve() in active:
                raise ModBuildError([bad], 'broken layout')
            return deploy_from_active(active, game_root)
        adapter = ScriptedAdapter(behavior)
        adapter.deploys_on_launch = True
        adapter.active_mod_ids = lambda game: ['good', 'bad']
        host = SimpleNamespace(
            _plugins={'ds1': SimpleNamespace(can_launch=False, name='Dark Souls', mod_adapter=adapter)},
            _steam_app_id=lambda plugin: '570940',
            _mod_adapter=lambda plugin: adapter,
            _installations=SimpleNamespace(snapshot=lambda plugin: {'root': str(self.game_root)}),
            game_process_status=lambda plugin: {'running': False},
            mod_library_status=lambda plugin: {'root': str(library.parent)},
            _mod_library_lock=threading.RLock(),
            _launch_notice=lambda plugin: 'Offline mode')
        host._deploy_before_launch = lambda plugin: HostApi._deploy_before_launch(host, plugin)
        with patch('core.desktop_host.os.startfile') as start:
            result = HostApi.launch_game(host, 'ds1')
        start.assert_called_once_with('steam://rungameid/570940')
        self.assertEqual(adapter.calls[-1], [good.resolve()])
        self.assertIn('Bad Mod was disabled: broken layout', result['notice'])
        self.assertIn('Offline mode', result['notice'])

    def test_failed_generated_file_rollback_does_not_disable_mods_or_retry(self):
        from core import script_mods
        good = write_mod(self.root, 'good', script={'version': 1})
        bad = write_mod(self.root, 'bad', script={'version': 1})
        for mod in (good, bad):
            (mod/'settings.schema.json').write_text('{"fields": []}')
            (mod/'script').mkdir()
            (mod/'script/__init__.py').write_text('')
            (mod/'script/tweak.py').write_text('def build(settings, context):\n    return {}\n')
        def behavior(active, game_root):
            rows = [script_mods.catalog_row(folder) for folder in active]
            script_mods.build_batch(rows, SimpleNamespace(current=''), allowed_roots=('native',))
            self.fail('A failed rollback must not reach deployment')
        adapter = ScriptedAdapter(behavior)
        with patch.object(script_mods, 'build', side_effect=[{'files': []}, ValueError('broken')]), \
                patch.object(script_mods, 'restore_generated', side_effect=OSError('cannot restore')):
            with self.assertRaisesRegex(ModBuildError, 'rollback failed'):
                activate_for_launch(adapter, [good, bad], self.game_root)
        self.assertEqual(len(adapter.calls), 1)
        self.assertTrue(enabled_of(good))
        self.assertTrue(enabled_of(bad))

    def test_transitive_manifest_requires_disabled_with_failure(self):
        base = write_mod(self.root, "base", "Base Mod", id="base-id")
        mid = write_mod(self.root, "mid", "Mid Mod", requires=["base-id"])
        top = write_mod(self.root, "top", "Top Mod", requires=["mid"])
        solo = write_mod(self.root, "solo", "Solo Mod")

        def behavior(active, game_root):
            if base.resolve() in [Path(folder).resolve() for folder in active]:
                raise ModBuildError([base], "Base Mod broke the build")
            return deploy_from_active(active, game_root)

        adapter = ScriptedAdapter(behavior)
        result = activate_for_launch(adapter, [base, mid, top, solo], self.game_root)

        self.assertFalse(enabled_of(base))
        self.assertFalse(enabled_of(mid))
        self.assertFalse(enabled_of(top))
        self.assertTrue(enabled_of(solo))
        self.assertEqual([folder.name for folder in adapter.calls[-1]], ["solo"])
        self.assertEqual(result["deployed"], ["solo"])
        by_folder = {entry["folder"]: entry for entry in result["disabledMods"]}
        self.assertEqual(set(by_folder), {"base", "mid", "top"})
        self.assertEqual(by_folder["base"]["error"], "Base Mod broke the build")
        self.assertEqual(by_folder["mid"]["error"], "A required mod could not be built.")
        self.assertEqual(by_folder["top"]["error"], "A required mod could not be built.")

    def test_transitive_tweak_schema_requires_disabled_with_failure(self):
        base = write_mod(self.root, "base", "Base Mod", id="base-id")
        tweak = write_mod(self.root, "tweak", "Tweak Mod")
        write_schema_requires(tweak, ["base-id"])
        solo = write_mod(self.root, "solo", "Solo Mod")

        def behavior(active, game_root):
            if base.resolve() in [Path(folder).resolve() for folder in active]:
                raise ModBuildError([base], "Base Mod broke the build")
            return deploy_from_active(active, game_root)

        adapter = ScriptedAdapter(behavior)
        result = activate_for_launch(adapter, [base, tweak, solo], self.game_root)

        self.assertFalse(enabled_of(base))
        self.assertFalse(enabled_of(tweak))
        self.assertTrue(enabled_of(solo))
        self.assertEqual(result["deployed"], ["solo"])
        by_folder = {entry["folder"]: entry for entry in result["disabledMods"]}
        self.assertEqual(by_folder["tweak"]["name"], "Tweak Mod")
        self.assertEqual(by_folder["tweak"]["error"], "A required mod could not be built.")

    def test_sequential_independent_failures_each_removed_with_finite_retries(self):
        bad1 = write_mod(self.root, "bad1", "Bad One")
        bad2 = write_mod(self.root, "bad2", "Bad Two")
        good = write_mod(self.root, "good", "Good Mod")

        def behavior(active, game_root):
            resolved = [Path(folder).resolve() for folder in active]
            if bad1.resolve() in resolved:
                raise ModBuildError([bad1], "first failure")
            if bad2.resolve() in resolved:
                raise ModBuildError([bad2], "second failure")
            return deploy_from_active(active, game_root)

        adapter = ScriptedAdapter(behavior)
        result = activate_for_launch(adapter, [bad1, bad2, good], self.game_root)

        self.assertFalse(enabled_of(bad1))
        self.assertFalse(enabled_of(bad2))
        self.assertTrue(enabled_of(good))
        self.assertEqual(result["deployed"], ["good"])
        self.assertLessEqual(len(adapter.calls), 4)
        by_folder = {entry["folder"]: entry["error"] for entry in result["disabledMods"]}
        self.assertEqual(by_folder, {"bad1": "first failure", "bad2": "second failure"})

    def test_unexpected_error_propagates_without_disabling(self):
        first = write_mod(self.root, "first", "First Mod")
        second = write_mod(self.root, "second", "Second Mod")

        def behavior(active, game_root):
            del active, game_root
            raise RuntimeError("disk exploded")

        adapter = ScriptedAdapter(behavior)
        with self.assertRaises(RuntimeError):
            activate_for_launch(adapter, [first, second], self.game_root)

        self.assertTrue(enabled_of(first))
        self.assertTrue(enabled_of(second))
        self.assertEqual(len(adapter.calls), 1)

    def test_failure_outside_active_set_propagates_without_disabling(self):
        first = write_mod(self.root, "first", "First Mod")
        second = write_mod(self.root, "second", "Second Mod")
        outsider = write_mod(self.root, "outsider", "Outsider Mod")

        for failed in ([outsider], [first, outsider]):
            with self.subTest(failed=[folder.name for folder in failed]):
                def behavior(active, game_root, failed=failed):
                    del active, game_root
                    raise ModBuildError(failed, "unattributed")

                adapter = ScriptedAdapter(behavior)
                with self.assertRaises(ModBuildError):
                    activate_for_launch(adapter, [first, second], self.game_root)

                self.assertTrue(enabled_of(first))
                self.assertTrue(enabled_of(second))
                self.assertTrue(enabled_of(outsider))

    def test_empty_failure_set_propagates_without_disabling(self):
        first = write_mod(self.root, "first", "First Mod")

        def behavior(active, game_root):
            del active, game_root
            raise ModBuildError([], "unknown failure")

        adapter = ScriptedAdapter(behavior)
        with self.assertRaises(ModBuildError):
            activate_for_launch(adapter, [first], self.game_root)

        self.assertTrue(enabled_of(first))

if __name__ == "__main__":
    unittest.main()
