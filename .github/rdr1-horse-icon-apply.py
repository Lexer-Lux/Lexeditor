from pathlib import Path

root = Path.cwd()
server = root / 'games/rdr/server.py'
text = server.read_text(encoding='utf-8')
old = 'from . import camera_features, input_remaps, mission_rewards, paths, script_features\n'
new = 'from . import camera_features, input_remaps, map_icon_features, mission_rewards, paths, script_features\n'
if text.count(old) != 1:
    raise SystemExit('server: expected one feature import line')
text = text.replace(old, new)
old = 'CAMERA_GENERATED_ROOT = PROJECT / ".lexeditor-generated" / "camera"\n'
new = (old + 'MAP_ICON_GENERATED_ROOT = PROJECT / ".lexeditor-generated" / "map-icons"\n')
if text.count(old) != 1:
    raise SystemExit('server: expected camera generated root')
text = text.replace(old, new)
old = '    ArchiveSpec("camera", camera_features.CAMERA_ARCHIVE_RELATIVE, CAMERA_GENERATED_ROOT),\n'
new = (old + '    ArchiveSpec("mapres", map_icon_features.MAPRES_ARCHIVE_RELATIVE, MAP_ICON_GENERATED_ROOT),\n')
if text.count(old) != 1:
    raise SystemExit('server: expected camera archive spec')
text = text.replace(old, new)
old = '''                input_remaps.prepare_input_remaps(
                    GAME_ROOT, paths.RPF6_TOOL, CONTENT_OVERRIDE_ROOT, feature_state)
                cover_problem = _prepare_cover_shoulder_override()
'''
new = '''                input_remaps.prepare_input_remaps(
                    GAME_ROOT, paths.RPF6_TOOL, CONTENT_OVERRIDE_ROOT, feature_state)
                map_icon_features.ensure_owned_horse_icon_override(
                    GAME_ROOT, paths.RPF6_TOOL, MAP_ICON_GENERATED_ROOT)
                cover_problem = _prepare_cover_shoulder_override()
'''
if text.count(old) != 1:
    raise SystemExit('server: expected deployment generation block')
server.write_text(text.replace(old, new), encoding='utf-8')

plugin = root / 'games/rdr/plugin.py'
text = plugin.read_text(encoding='utf-8')
old = '        required_paths=("RDR.exe", "game/tune_d11generic.rpf", "game/content.rpf"),\n'
new = '        required_paths=("RDR.exe", "game/tune_d11generic.rpf", "game/content.rpf", "game/mapres.rpf"),\n'
if text.count(old) != 1:
    raise SystemExit('plugin: expected installation required_paths')
plugin.write_text(text.replace(old, new), encoding='utf-8')
