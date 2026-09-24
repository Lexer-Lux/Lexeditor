from pathlib import Path


import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from plugin_ui import plugin_ui


def test_project_deployment_ui_exposes_guarded_remove_action():
    source = plugin_ui("ff7r")
    assert '"/api/deploy/remove"' in source
    assert '"Remove deployed PAK"' in source
    assert "info.projectDeployment?.managed" in source
    assert "unmanaged or externally changed files are preserved" in source
