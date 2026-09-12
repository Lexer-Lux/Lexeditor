from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch

TEXT = r'''using System;
public sealed class Settings {
    private bool _show = true;
    private bool _native;
    private float _interval = 3f;
    private float _ratio = 5f / 7f;
    private int _columns = 5;

    [SettingPropertyBool("Show XP Notifications", Order = 2, RequireRestart = false, HintText = "Shows XP.")]
    [SettingPropertyGroup("XP", GroupOrder = 1)]
    public bool Show { get { return _show; } set { _show = value; } }

    [SettingPropertyBool("Native strip", Order = 3, RequireRestart = true)]
    [SettingPropertyGroup("XP")]
    public bool Native { get { return _native; } set { _native = value; } }

    [SettingPropertyFloatingInteger("Interval", 0.25f, 30f, "#0.00", Order = 4, RequireRestart = false)]
    [SettingPropertyGroup("XP")]
    public float Interval { get { return _interval; } set { _interval = value; } }

    [SettingPropertyFloatingInteger("Ratio", 0.45f, 1.25f, "#0.00", Order = 0, RequireRestart = true)]
    [SettingPropertyGroup("Party", GroupOrder = 4)]
    public float Ratio { get { return _ratio; } set { _ratio = value; } }

    [SettingPropertyInteger("Columns", 5, 20, Order = 1, RequireRestart = true)]
    [SettingPropertyGroup("Party")]
    public int Columns { get { return _columns; } set { _columns = value; } }
}
'''

class SettingsTests(unittest.TestCase):
    def test_reads_bounds_groups_and_defaults_and_saves_field_only(self):
        from games.bannerlord.settings_data import read_mcm_defaults, save_mcm_defaults
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);(root/'src').mkdir();path=root/'src/LexerSkillTweaksSettings.cs';path.write_text(TEXT,encoding='utf-8')
            model=read_mcm_defaults(root);rows={r['property']:r for r in model['settings']}
            self.assertTrue(rows['Show']['default']);self.assertFalse(rows['Native']['default'])
            self.assertEqual(rows['Interval']['min'],0.25);self.assertEqual(rows['Interval']['max'],30.0)
            self.assertAlmostEqual(rows['Ratio']['default'],5/7);self.assertEqual(rows['Columns']['kind'],'int')
            self.assertTrue(rows['Native']['requireRestart']);self.assertEqual(rows['Ratio']['groupOrder'],4)
            result=save_mcm_defaults(root,[{'property':'Native','value':True},{'property':'Interval','value':4.5},{'property':'Columns','value':10}])
            self.assertEqual(result['saved'],3);self.assertTrue(Path(result['backup']).is_file())
            rewritten=path.read_text();self.assertIn('private bool _native = true;',rewritten);self.assertIn('private float _interval = 4.5f;',rewritten);self.assertIn('private int _columns = 10;',rewritten)
            self.assertIn('[SettingPropertyFloatingInteger("Interval", 0.25f, 30f',rewritten)
            with self.assertRaises(ValueError):save_mcm_defaults(root,[{'property':'Columns','value':21}])
            with self.assertRaises(ValueError):save_mcm_defaults(root,[{'property':'Native','value':1}])

    def test_settings_writer_preserves_bom_and_crlf(self):
        from games.bannerlord.settings_data import save_mcm_defaults
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);(root/"src").mkdir();path=root/"src/LexerSkillTweaksSettings.cs"
            path.write_bytes(b"\xef\xbb\xbf"+TEXT.replace("\n","\r\n").encode())
            save_mcm_defaults(root,[{"property":"Native","value":True}])
            raw=path.read_bytes();self.assertTrue(raw.startswith(b"\xef\xbb\xbf"));self.assertNotIn(b"\n",raw[3:].replace(b"\r\n",b""));self.assertIn(b"private bool _native = true;",raw)

    def test_settings_write_helpers_do_not_follow_existing_hardlinks(self):
        from games.bannerlord.settings_data import save_mcm_defaults
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root/'src').mkdir()
            path = root/'src/LexerSkillTweaksSettings.cs'
            path.write_text(TEXT, encoding='utf-8')
            backup = path.with_name(path.name + '.lexeditor.bak')
            temporary_path = path.with_name(path.name + '.lexeditor.tmp')
            outside_backup = root/'outside-backup.txt'
            outside_temporary = root/'outside-temporary.txt'
            outside_backup.write_text('backup sentinel', encoding='utf-8')
            outside_temporary.write_text('temporary sentinel', encoding='utf-8')
            os.link(outside_backup, backup)
            os.link(outside_temporary, temporary_path)

            result = save_mcm_defaults(root, [{'property':'Native','value':True}])

            self.assertEqual(result['saved'], 1)
            self.assertEqual(outside_backup.read_text(encoding='utf-8'), 'backup sentinel')
            self.assertEqual(outside_temporary.read_text(encoding='utf-8'), 'temporary sentinel')
            self.assertEqual(backup.read_text(encoding='utf-8'), TEXT)
            self.assertIn('private bool _native = true;', path.read_text(encoding='utf-8'))

    def test_settings_source_redirection_outside_project_is_rejected(self):
        from games.bannerlord.settings_data import save_mcm_defaults
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / 'src').mkdir()
            source = root / 'src/LexerSkillTweaksSettings.cs'
            source.write_text(TEXT, encoding='utf-8')
            outside = root.parent / (root.name + '-outside-settings.cs')
            outside.write_text(TEXT, encoding='utf-8')
            root_resolved = root.resolve()
            source_path = root_resolved / 'src' / 'LexerSkillTweaksSettings.cs'
            outside_resolved = outside.resolve()
            real_resolve = Path.resolve

            def fake_resolve(path, *args, **kwargs):
                if path == source_path:
                    return outside_resolved
                return real_resolve(path, *args, **kwargs)

            try:
                with patch.object(Path, 'resolve', new=fake_resolve):
                    with self.assertRaisesRegex(ValueError, 'project path escaped'):
                        save_mcm_defaults(root, [{'property':'Native','value':True}])
                self.assertEqual(outside.read_text(encoding='utf-8'), TEXT)
            finally:
                outside.unlink(missing_ok=True)

if __name__=='__main__':unittest.main()
