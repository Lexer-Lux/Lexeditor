"""Hermetic RDR2 regressions: no game, mod install, or copyrighted fixtures needed."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from games.rdr2 import alcohol_strengths as alcohol
from games.rdr2 import server as s


def weapon_xml(effect="SHELL_ALPHA", weapon="WEAPON_ALPHA", flags="Alpha Beta"):
    return (f'<Root><!--preserve--><Item type="CWeaponInfo"><Name>{weapon}</Name>'
            f'<VfxWeaponShellInfoHashName>{effect}</VfxWeaponShellInfoHashName>'
            '<Damage value="37"/></Item><Item type="CAmmoProjectileInfo">'
            f'<Name>AMMO_ALPHA</Name><ProjectileFlags>{flags}</ProjectileFlags>'
            '</Item></Root>')


class ProjectFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.mine, self.vanilla = self.root/'mine', self.root/'vanilla'
        self.mine.mkdir(); self.vanilla.mkdir()
        self.patches = patch.multiple(s, DATASETS={
            'mine': {'dir': self.mine, 'readonly': False},
            'vanilla': {'dir': self.vanilla, 'readonly': True}},
            _files={}, _PROVENANCE_CACHE={})
        self.patches.start(); self.addCleanup(self.patches.stop)
        (self.mine/'install.xml').write_text('<LML><Resources><Resource/></Resources></LML>')

    def stack(self, mapped=False):
        self.files = []
        for i, (game_path, relative) in enumerate(s.WEAPON_STACK):
            target = ('nested/'+relative) if mapped else relative
            path = self.mine/target
            path.parent.mkdir(exist_ok=True)
            if relative.endswith('.ymt'):
                path.write_text(weapon_xml('', f'WEAPON_ALPHA_{i}'))
                (self.vanilla/relative).write_text(weapon_xml(f'SHELL_ALPHA_{i}', f'WEAPON_ALPHA_{i}'))
            else:
                path.write_text('<Root><Untouched value="19"/></Root>')
            self.files.append(path)
            if mapped:
                s.ensure_file_replacement(game_path, target)

    def snapshot(self):
        return {str(p.relative_to(self.mine)): p.read_bytes()
                for p in self.mine.rglob('*') if p.is_file() and not p.name.endswith('.bak')}


class ShellStackTests(ProjectFixture):
    def test_restore_and_reblank_every_layer_idempotently(self):
        self.stack()
        status = s.get_weapon_shell_vfx_status()
        self.assertTrue(status['available']); self.assertTrue(status['blanked'])
        self.assertEqual((status['blank'], status['total'], len(status['files'])), (7, 7, 7))
        components = {p: p.read_bytes() for p in self.files if p.suffix == '.meta'}
        self.assertEqual(s.apply_weapon_shell_vfx(False), 7)
        for i, (_, relative) in enumerate(s.WEAPON_STACK[:7]):
            root = s.load_file(relative)['root']
            self.assertEqual(s._weapon_shell_nodes(root)[f'WEAPON_ALPHA_{i}'].text, f'SHELL_ALPHA_{i}')
            self.assertEqual(root.find('./Item/Damage').get('value'), '37')
            self.assertIn('<!--preserve-->', (self.mine/relative).read_text())
            s._assert_weapon_projectile_flags(root, s.load_file(relative,'vanilla')['root'])
        self.assertEqual({p: p.read_bytes() for p in components}, components)
        self.assertEqual(len(s.install_replacements()), len(s.WEAPON_STACK))
        self.assertEqual(s.apply_weapon_shell_vfx(False), 0)
        self.assertEqual(s.get_weapon_shell_vfx_status()['blank'], 0)
        self.assertEqual(s.apply_weapon_shell_vfx(True), 7)
        self.assertTrue(s.get_weapon_shell_vfx_status()['blanked'])
        self.assertEqual(s.apply_weapon_shell_vfx(True), 0)

    def test_mapped_paths_are_restored_without_creating_root_copies(self):
        self.stack(mapped=True)
        self.assertEqual(s.apply_weapon_shell_vfx(False), 7)
        self.assertFalse((self.mine/'weapons.ymt').exists())
        self.assertTrue(all(value.startswith('nested/') for value in s.install_replacements().values()))
        self.assertEqual(s.get_weapon_shell_vfx_status()['blank'], 0)
        self.assertTrue(s.get_weapons()['available'])
        self.assertEqual(len(s.get_weapons()['weapons']), 7)

    def test_missing_patch_reference_refuses_every_write(self):
        self.stack()
        (self.vanilla/s.WEAPON_STACK[3][1]).unlink()
        before = self.snapshot()
        self.assertFalse(s.get_weapon_shell_vfx_status()['available'])
        with self.assertRaisesRegex(ValueError, 'references are unavailable'):
            s.apply_weapon_shell_vfx(False)
        self.assertEqual(self.snapshot(), before)

    def test_missing_component_refuses_every_write(self):
        self.stack(); self.files[-1].unlink(); before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'complete weapon stack'):
            s.apply_weapon_shell_vfx(False)
        self.assertEqual(self.snapshot(), before)

    def test_missing_weapon_record_is_not_a_complete_reference(self):
        self.stack(); self.files[3].write_text('<Root/>'); before = self.snapshot()
        status = s.get_weapon_shell_vfx_status()
        self.assertFalse(status['available']); self.assertTrue(status['missingRecords'])
        with self.assertRaises(ValueError): s.apply_weapon_shell_vfx(False)
        self.assertEqual(self.snapshot(), before)

    def test_patch_projectile_flags_checked_before_any_write(self):
        self.stack()
        self.files[4].write_text(weapon_xml('', 'WEAPON_ALPHA_4', 'Alpha'))
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'ProjectileFlags'):
            s.apply_weapon_shell_vfx(False)
        self.assertEqual(self.snapshot(), before)

    def test_late_write_failure_restores_disk_and_cached_trees(self):
        self.stack(); before = self.snapshot(); actual_save = s.save_file
        def fail_late(name, *args):
            actual_save(name, *args)
            if name == s.WEAPON_STACK[4][1]: raise OSError('simulated full disk')
        with patch.object(s, 'save_file', side_effect=fail_late):
            with self.assertRaisesRegex(OSError, 'simulated full disk'):
                s.apply_weapon_shell_vfx(False)
        self.assertEqual(self.snapshot(), before)
        self.assertTrue(s.get_weapon_shell_vfx_status()['blanked'])

    def test_install_failure_restores_all_layers_and_install_map(self):
        self.stack(); before = self.snapshot(); actual_ensure = s.ensure_file_replacement
        def fail_late(game_path, relative):
            actual_ensure(game_path, relative)
            if relative == s.WEAPON_STACK[3][1]: raise OSError('simulated install failure')
        with patch.object(s, 'ensure_file_replacement', side_effect=fail_late):
            with self.assertRaises(OSError): s.apply_weapon_shell_vfx(False)
        self.assertEqual(self.snapshot(), before)
        self.assertTrue(s.get_weapon_shell_vfx_status()['blanked'])

    def test_boolean_required(self):
        for value in ('false', 0, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                s.apply_weapon_shell_vfx(value)

    def test_mapped_path_escape_refused(self):
        self.stack()
        s.ensure_file_replacement(s.WEAPON_STACK[1][0], '../outside.ymt')
        with self.assertRaisesRegex(ValueError, 'escapes'):
            s.apply_weapon_shell_vfx(False)


class StartupCacheTests(ProjectFixture):
    def write_catalog(self, key='ITEM_ALPHA', target=None):
        path = target or self.mine/s.CATALOG_FILE
        path.parent.mkdir(exist_ok=True)
        path.write_text(f'<root><catalog><items><item key="{key}"><key>{key}</key></item></items></catalog></root>')
        return path

    def test_localization_and_crafting_use_one_catalog_parse(self):
        self.write_catalog()
        recipes = self.root/'recipes.tsv'; recipes.write_text('recipe_id\ttitle\tdescription\tcategory\tstation\tunlock\toutput_item\toutput_quantity\tingredients\n')
        with patch.multiple(s, CUSTOM_CRAFTING_FILE=recipes, VANILLA_CRAFTING_FILE=recipes), \
             patch.object(s.ET, 'fromstring', wraps=s.ET.fromstring) as parse:
            s._catalog_localization_aliases('mine', {})
            s.get_custom_crafting()
            s.load_file(s.CATALOG_FILE)
            self.assertEqual(parse.call_count, 1)

    def test_mapped_catalog_and_external_changes_invalidate_cache(self):
        self.write_catalog('ITEM_DECOY')
        active = self.write_catalog(target=self.mine/'nested'/'active.ymt')
        s.ensure_file_replacement(s.CATALOG_GAME_PATH, 'nested/active.ymt')
        first = s.load_file(s.CATALOG_FILE)['root']
        self.assertEqual(s._catalog_ids(), ['ITEM_ALPHA'])
        stamp=active.stat().st_mtime_ns
        self.write_catalog('ITEM_BETA', active)
        os.utime(active, ns=(stamp+1_000_000_000, stamp+1_000_000_000))
        s._catalog_localization_aliases('mine', {})
        self.assertIsNot(s.load_file(s.CATALOG_FILE)['root'], first)
        self.assertEqual(s._catalog_ids(), ['ITEM_BETA'])

    def test_reference_provenance_does_not_evict_editable_dataset(self):
        names=('build_challenge_reward_provenance', 'build_loot_chain_provenance',
               'build_fixed_placement_provenance', 'build_script_reference_provenance')
        from contextlib import ExitStack
        with ExitStack() as stack:
            mocks=[stack.enter_context(patch.object(s,name,return_value={})) for name in names]
            first=s.build_static_provenance('mine', [])
            s.build_static_provenance('vanilla', [])
            self.assertIs(s.build_static_provenance('mine', []), first)
            self.assertEqual([m.call_count for m in mocks], [2,2,2,1])

    def test_localization_changes_invalidate_provenance(self):
        before=s.provenance_cache_key('mine')
        (self.mine/s.LOCALIZATION_FILE).write_text('[LEXEDITOR OVERRIDES]\nNAME = Different')
        self.assertNotEqual(before, s.provenance_cache_key('mine'))


class AlcoholTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name); self.vanilla=root/'vanilla.csv'; self.override=root/'overrides.csv'
        # Synthetic per-drink fixtures, including an intentional full-strength override.
        self.vanilla.write_text('# key,drink,swig,swigs\nDRINK_ALPHA,0.1,0.025,4\nDRINK_BETA,0.3,0.3,1\nDRINK_GAMMA,0.17,0.17,1\n')
        self.override.write_text('DRINK_BETA,1,0.3,1\n')

    def read(self): return alcohol.get_alcohol_strengths(self.vanilla, self.override)
    def save(self, entries): return alcohol.save_alcohol_strengths(entries,self.vanilla,self.override)

    def test_distinct_values_and_deliberate_full_strength_preserved(self):
        self.assertEqual(self.read()['entries'], {'DRINK_ALPHA':0.1,'DRINK_BETA':1,'DRINK_GAMMA':0.17})
        self.save({'DRINK_ALPHA':0.2})
        self.assertEqual(self.read()['entries'], {'DRINK_ALPHA':0.2,'DRINK_BETA':1,'DRINK_GAMMA':0.17})
        self.assertIn('DRINK_ALPHA,0.2,0.1,4', self.override.read_text())

    def test_explicit_baseline_removes_only_its_override(self):
        self.save({'DRINK_ALPHA':0.2}); self.save({'DRINK_ALPHA':0.1})
        self.assertEqual(self.read()['overrides'], {'DRINK_BETA':1})

    def test_sparse_edit_preserves_newer_unrelated_value(self):
        stale=self.read()
        self.save({'DRINK_GAMMA':0.45})
        self.save({'DRINK_ALPHA':0.2})
        self.assertEqual(stale['entries']['DRINK_GAMMA'],0.17)
        self.assertEqual(self.read()['entries']['DRINK_GAMMA'],0.45)

    def test_invalid_values_never_mutate_saved_file(self):
        before=self.override.read_bytes()
        for value in (True, False, None, 'no', '', float('nan'), float('inf'), -0.1, 1.1, [], {}):
            with self.subTest(value=value), self.assertRaises(ValueError): self.save({'DRINK_ALPHA':value})
            self.assertEqual(self.override.read_bytes(),before)
        for entries in ([], None, {'UNKNOWN':0.1}):
            with self.subTest(entries=entries), self.assertRaises(ValueError): self.save(entries)
            self.assertEqual(self.override.read_bytes(),before)

    def test_unknown_existing_override_not_silently_discarded(self):
        self.override.write_text('UNKNOWN,0.2,0.1,1\n'); before=self.override.read_bytes()
        with self.assertRaisesRegex(ValueError,'no vanilla item'): self.save({'DRINK_ALPHA':0.2})
        self.assertEqual(self.override.read_bytes(),before)

    def test_missing_baseline_explicitly_unavailable_not_zero_or_one(self):
        self.vanilla.unlink(); result=self.read()
        self.assertFalse(result['available']); self.assertEqual(result['entries'],{})
        self.assertIn('unavailable',result['reason'])

    def test_round_trip_preserves_precision_including_values_below_blackout(self):
        for value in (0.12345678912345678, 0.99999999, 1e-10):
            self.save({'DRINK_ALPHA':value})
            self.assertEqual(self.read()['entries']['DRINK_ALPHA'], value)

    def test_duplicate_rows_rejected(self):
        self.vanilla.write_text('DRINK_ALPHA,0.1\nDRINK_ALPHA,0.5\n')
        with self.assertRaisesRegex(ValueError,'duplicate'): self.read()


if __name__ == '__main__':
    unittest.main(verbosity=2)
