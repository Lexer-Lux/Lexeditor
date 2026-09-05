"""Shared Searcher source, settings, and first FF8 adoption contract."""

from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from settings_manager import SettingsStore  # noqa: E402


FRAMEWORK = (ROOT / "ui" / "framework.js").read_text(encoding="utf-8")
CSS = (ROOT / "ui" / "framework.css").read_text(encoding="utf-8")
FF8 = (ROOT / "games" / "ff8" / "editor.html").read_text(encoding="utf-8")


def main() -> int:
    assert "const beginSearcher = options =>" in FRAMEWORK
    assert "const decorateSearchCandidate = (node, options) =>" in FRAMEWORK
    assert "--lex-search-hold" in FRAMEWORK and ".lex-search-candidate.selecting::before" in CSS
    assert ".lex-search-candidate > *" in CSS and "z-index:2" in CSS
    assert "lex-searcher-active" in CSS and "lex-searcher-cancel" in CSS
    assert 'type:"items",prompt,target:()=>navigate("items")' in FF8
    assert "decorateSearchCandidate(node,{type:view,value:row.id,label:row.name})" in FF8
    with tempfile.TemporaryDirectory(prefix="lexeditor-searcher-settings-", ignore_cleanup_errors=True) as name:
        path = Path(name) / "settings.json"
        store = SettingsStore(path)
        assert store.snapshot()["selectionHoldMs"] == 500
        store.save("weekly", selection_hold_ms=900)
        assert SettingsStore(path).snapshot()["selectionHoldMs"] == 900
        store.save("weekly", selection_hold_ms=9000)
        assert SettingsStore(path).snapshot()["selectionHoldMs"] == 2000
    print("Shared Searcher framework, hold setting, and FF8 Weapons adoption passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
