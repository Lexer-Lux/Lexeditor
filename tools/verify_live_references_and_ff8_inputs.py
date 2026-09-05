"""Shared live-reference and FF8 structured-input contracts."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    framework = (ROOT / "ui" / "framework.js").read_text(encoding="utf-8")
    ff8 = (ROOT / "games" / "ff8" / "editor.html").read_text(encoding="utf-8")

    # A shell refresh must update every mounted provenance control. Input and
    # change events must refresh synchronously; a tab rebuild is not allowed.
    assert "const refreshReferences =" in framework
    refresh_body = framework[framework.index("function refresh() {"):
                             framework.index("function refresh() {") + 900]
    assert refresh_body.index("refreshReferences();") < refresh_body.index("const dirty")
    assert 'addEventListener?.("input", refresh)' in framework
    assert 'addEventListener?.("change", refresh)' in framework
    assert "requestAnimationFrame(refresh)" not in framework

    # Hit rate is one stored byte with two synchronized player-facing inputs.
    assert "function ratio255Control" in ff8
    assert 'unitField(percent,"%")' in ff8
    assert 'unitField(exact,"/255")' in ff8
    assert 'if(field.field==="hit_rate")return ratio255Control' in ff8

    # Shop item choice uses the shared full-list searcher, not a select menu.
    shop = ff8[ff8.index("function shopDetail"):ff8.index("function displayFieldValue")]
    assert "itemSearchControl(" in shop
    assert "itemSelectControl(" not in shop

    print("Live references, dual hit rate, and FF8 Shop finder contracts passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
