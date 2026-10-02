"""Optional CI evidence remains generated and scoped to an explicit plugin."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools import check_plugin


def test_targeted_workflow_keeps_evidence_opt_in(monkeypatch):
    monkeypatch.setattr(check_plugin, "PLUGINS", ["ds1", "other"])
    monkeypatch.setattr(check_plugin, "CONFIG", {"capture_evidence": ["ds1"]})
    captured = check_plugin.workflow_files("ds1")
    assert set(captured) == {"ds1-checks.yml"}
    text = captured["ds1-checks.yml"]
    assert "LEXEDITOR_CHECK_ARTIFACTS:" in text
    assert "actions/upload-artifact@v4" in text
    assert "retention-days: 7" in text
    assert "if: always()" in text
    plain = check_plugin.workflow_files("other")["other-checks.yml"]
    assert "upload-artifact" not in plain
    assert "LEXEDITOR_CHECK_ARTIFACTS" not in plain
