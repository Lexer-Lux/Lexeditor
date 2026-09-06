from pathlib import Path

root = Path.cwd()

script = root / 'games/rdr/script_features.py'
text = script.read_text(encoding='utf-8')
old = '    if code_length <= COACH_FUNCTION_OFFSET or code_length > len(raw):\n        raise ValueError(f"Unexpected WSC code length: {code_length}")\n'
new = '    if code_length <= 0 or code_length > len(raw):\n        raise ValueError(f"Unexpected WSC code length: {code_length}")\n'
if text.count(old) != 1:
    raise SystemExit('script_features: expected one carriage-specific CodeLength guard')
text = text.replace(old, new)
old = '    start = COACH_FUNCTION_OFFSET\n    if code[start] != 45:\n'
new = ('    start = COACH_FUNCTION_OFFSET\n'
       '    if start >= len(code):\n'
       '        raise ValueError(f"Passenger coach WSC is shorter than audited Function_41 offset 0x{start:X}")\n'
       '    if code[start] != 45:\n')
if text.count(old) != 1:
    raise SystemExit('script_features: expected one Function_41 entry guard')
script.write_text(text.replace(old, new), encoding='utf-8')

server = root / 'games/rdr/server.py'
text = server.read_text(encoding='utf-8')
old = 'from . import camera_features, mission_rewards, paths, script_features\n'
new = 'from . import camera_features, input_remaps, mission_rewards, paths, script_features\n'
if text.count(old) != 1:
    raise SystemExit('server: expected one RDR feature import')
text = text.replace(old, new)
old = '''                script_features.prepare_auto_carriage_rest(
                    GAME_ROOT, paths.RPF6_TOOL, CONTENT_OVERRIDE_ROOT,
                    PROJECT / ".lexeditor-generated" / "rdr-script-features.json")
                cover_problem = _prepare_cover_shoulder_override()
'''
new = '''                feature_state = PROJECT / ".lexeditor-generated" / "rdr-script-features.json"
                script_features.prepare_auto_carriage_rest(
                    GAME_ROOT, paths.RPF6_TOOL, CONTENT_OVERRIDE_ROOT, feature_state)
                input_remaps.prepare_input_remaps(
                    GAME_ROOT, paths.RPF6_TOOL, CONTENT_OVERRIDE_ROOT, feature_state)
                cover_problem = _prepare_cover_shoulder_override()
'''
if text.count(old) != 1:
    raise SystemExit('server: expected one deployment generation block')
server.write_text(text.replace(old, new), encoding='utf-8')
