from pathlib import Path

p = Path('games/rdr/server.py')
s = p.read_text(encoding='utf-8')
s = s.replace('from . import mission_rewards, paths\n', 'from . import camera_features, mission_rewards, paths\n', 1)
s = s.replace('''GRINGO_OVERRIDE_ROOT = MOD_ROOT / "gringores"\nARCHIVE_SPECS = (\n''', '''GRINGO_OVERRIDE_ROOT = MOD_ROOT / "gringores"\nCAMERA_GENERATED_ROOT = PROJECT / ".lexeditor-generated" / "camera"\nARCHIVE_SPECS = (\n''', 1)
s = s.replace('''    ArchiveSpec("gringores", Path("game") / "gringores.rpf", GRINGO_OVERRIDE_ROOT),\n)\n''', '''    ArchiveSpec("gringores", Path("game") / "gringores.rpf", GRINGO_OVERRIDE_ROOT),\n    ArchiveSpec("camera", camera_features.CAMERA_ARCHIVE_RELATIVE, CAMERA_GENERATED_ROOT),\n)\n''', 1)
marker = '\ndef dashboard_payload() -> dict:\n'
assert marker in s
insert = r'''
def _prepare_cover_shoulder_override() -> str:
    """Materialize the proven CoverCamera side-switch override when a real install is present."""
    camera_archive = GAME_ROOT / camera_features.CAMERA_ARCHIVE_RELATIVE
    if not camera_archive.is_file():
        return (f"RDR camera archive is missing: {camera_archive}"
                if (GAME_ROOT / "RDR.exe").is_file() else "")
    try:
        camera_features.ensure_cover_shoulder_override(
            GAME_ROOT, paths.RPF6_TOOL, CAMERA_GENERATED_ROOT)
        return ""
    except Exception as error:
        return f"Cover shoulder-swap override is not ready: {error}"


def _deployment_payload() -> dict:
    problem = _prepare_cover_shoulder_override()
    payload = deployment_status(GAME_ROOT, ARCHIVE_SPECS)
    generated = CAMERA_GENERATED_ROOT / camera_features.CAMERA_ENTRY_RELATIVE
    payload["coverShoulder"] = {
        "prepared": generated.is_file(),
        "path": str(generated),
        "problem": problem,
        "changedLine": camera_features.COVER_ASSIGNMENT_LINE,
    }
    if problem:
        payload["problem"] = problem
    return payload
'''
s = s.replace(marker, insert + marker, 1)
s = s.replace('''            "Shop overrides": str(GRINGO_OVERRIDE_ROOT),\n            "Mission ASI override": str(mission_rewards.OVERRIDE_FILE),\n''', '''            "Shop overrides": str(GRINGO_OVERRIDE_ROOT),\n            "Generated camera fixes": str(CAMERA_GENERATED_ROOT),\n            "Mission ASI override": str(mission_rewards.OVERRIDE_FILE),\n''', 1)
s = s.replace('''        "deployment": deployment_status(GAME_ROOT, ARCHIVE_SPECS),\n''', '''        "deployment": _deployment_payload(),\n''', 1)
s = s.replace('''            elif path == "/api/deployment":\n                self.json_response(deployment_status(GAME_ROOT, ARCHIVE_SPECS))\n''', '''            elif path == "/api/deployment":\n                self.json_response(_deployment_payload())\n''', 1)
s = s.replace('''            elif path == "/api/deployment/deploy":\n                self.json_response(deploy_archives(\n                    GAME_ROOT, paths.RPF6_TOOL, ARCHIVE_SPECS))\n''', '''            elif path == "/api/deployment/deploy":\n                cover_problem = _prepare_cover_shoulder_override()\n                if cover_problem:\n                    raise RuntimeError(cover_problem)\n                self.json_response(deploy_archives(\n                    GAME_ROOT, paths.RPF6_TOOL, ARCHIVE_SPECS))\n''', 1)
p.write_text(s, encoding='utf-8')
