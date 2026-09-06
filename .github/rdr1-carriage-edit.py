from pathlib import Path

root = Path.cwd()

# Enable the already-supported MagicRDR AES path for type-2 WSC repacks.
p = root / 'tools/magic-rdr/cli/Rpf6ReadCli.cs'
s = p.read_text(encoding='utf-8')
old = '''        int resourceType = BitConverter.ToInt32(packed, 4);\n        if (resourceType == 2)\n            throw new InvalidDataException("Encrypted RSC85 resources are not supported by this command.");\n        byte[] original = ResourceUtils.ResourceInfo.GetDataFromResourceBytes(packed);\n'''
new = '''        int resourceType = BitConverter.ToInt32(packed, 4);\n        byte[] original = ResourceUtils.ResourceInfo.GetDataFromResourceBytes(packed);\n'''
assert old in s
s = s.replace(old, new, 1)
old = '''        byte[] compressed = DataUtils.CompressZStandard(unpacked);\n        byte[] result = new byte[16 + compressed.Length];\n'''
new = '''        byte[] compressed = DataUtils.CompressZStandard(unpacked);\n        if (resourceType == 2)\n            compressed = DataUtils.Encrypt(compressed, AppGlobals.EncryptionKey);\n        byte[] result = new byte[16 + compressed.Length];\n'''
assert old in s
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')

# Prepare the derived passenger-coach script before building the safe content.rpf copy.
p = root / 'games/rdr/server.py'
s = p.read_text(encoding='utf-8')
old = 'from . import camera_features, mission_rewards, paths\n'
new = 'from . import camera_features, mission_rewards, paths, script_features\n'
assert old in s
s = s.replace(old, new, 1)
old = '''            elif path == "/api/deployment/deploy":\n                cover_problem = _prepare_cover_shoulder_override()\n'''
new = '''            elif path == "/api/deployment/deploy":\n                script_features.prepare_auto_carriage_rest(\n                    GAME_ROOT, paths.RPF6_TOOL, CONTENT_OVERRIDE_ROOT,\n                    PROJECT / ".lexeditor-generated" / "rdr-script-features.json")\n                cover_problem = _prepare_cover_shoulder_override()\n'''
assert old in s
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')
