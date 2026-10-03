"""Shared live-reference and FF8 structured-input contracts."""

from pathlib import Path
from plugin_ui import plugin_ui


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    framework = (ROOT / "ui" / "framework.js").read_text(encoding="utf-8")
    ff8 = plugin_ui('ff8')

    # A shell refresh must update every mounted provenance control. Input and
    # change events must refresh synchronously; a tab rebuild is not allowed.
    assert "const refreshReferences =" in framework
    refresh_body = framework[framework.index("function refresh() {"):
                             framework.index("function refresh() {") + 900]
    assert refresh_body.index("refreshReferences();") < refresh_body.index("const dirty")
    provenance = framework[framework.index('const provenanceControl ='):
                           framework.index('const integrationStatus =')]
    assert 'addEventListener?.("input", refresh)' in provenance
    assert 'addEventListener?.("change", refresh)' in provenance
    # A panel-layout refresh also uses this local name, but its animation
    # frame does not defer reference updates after an input event.
    assert "requestAnimationFrame(refresh)" not in provenance
    assert "requestAnimationFrame(refresh)" not in refresh_body

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
