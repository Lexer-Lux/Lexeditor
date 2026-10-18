"""Mod warning flags reach every row that needs attention, on or off.

Alerts (a mod changed since the last build) mark switched-off rows too:
the Mods tab and the mod selector show them so the reader knows a mod
needs Save before it can apply cleanly. Conflicts stay on switched-on
rows only: two mods clash only in combination.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core.desktop_host import HostApi


class StubAdapter:
    def __init__(self, reports):
        self._reports = reports

    def conflicts(self, mods, game_root):
        return self._for("conflicts", mods)

    def alerts(self, mods, game_root):
        return self._for("alerts", mods)

    def _for(self, method, mods):
        wanted = {Path(each).resolve() for each in mods}
        return {str(path): list(lines) for path, lines in self._reports[method].items()
                if Path(path).resolve() in wanted}


def test_alerts_mark_switched_off_rows(tmp_path):
    on, off = tmp_path / "on", tmp_path / "off"
    on.mkdir()
    off.mkdir()
    result = {"rows": [{"path": str(on), "enabled": True},
                       {"path": str(off), "enabled": False}]}
    adapter = StubAdapter({"alerts": {on: ["changed"], off: ["changed"]}, "conflicts": {}})
    HostApi._attach_report(result, adapter, [on, off], str(tmp_path), "alerts", "alertsError", False)
    assert result["rows"][0]["alerts"] == ["changed"]
    assert result["rows"][1]["alerts"] == ["changed"]
    assert "alertsError" not in result


def test_conflicts_stay_on_switched_on_rows(tmp_path):
    on, off = tmp_path / "on", tmp_path / "off"
    on.mkdir()
    off.mkdir()
    result = {"rows": [{"path": str(on), "enabled": True},
                       {"path": str(off), "enabled": False}]}
    adapter = StubAdapter({"alerts": {}, "conflicts": {on: ["clash"], off: ["clash"]}})
    HostApi._attach_report(result, adapter, [on], str(tmp_path), "conflicts", "conflictError", True)
    assert result["rows"][0]["conflicts"] == ["clash"]
    assert "conflicts" not in result["rows"][1]
