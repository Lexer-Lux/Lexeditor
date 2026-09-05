"""Source and persistence contract for the shared N-barrelled table preset."""

from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from settings_manager import SettingsStore  # noqa: E402
FRAMEWORK = (ROOT / "ui" / "framework.js").read_text(encoding="utf-8")
CSS = (ROOT / "ui" / "framework.css").read_text(encoding="utf-8")
SETTINGS = (ROOT / "settings_manager.py").read_text(encoding="utf-8")
DESKTOP = (ROOT / "desktop_host.py").read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    require('"viewPreferences"' in SETTINGS and "def save_view_preference" in SETTINGS,
            "local settings must persist per-view UI preferences")
    require("def save_lexeditor_view_preference" in DESKTOP,
            "the native host must expose local preference persistence")
    require("const barrelPreferenceKey =" in FRAMEWORK,
            "the shared preset must derive one game/view barrel key")
    require("const readBarrelCount =" in FRAMEWORK and "const saveBarrelCount =" in FRAMEWORK,
            "barrel counts need shared local read and save paths")
    require("const barrelSize = pageSize * barrels" in FRAMEWORK,
            "one group must contain one old page per barrel")
    require("records.slice(groupStart + index * pageSize" in FRAMEWORK,
            "barrels must show consecutive old page slices")
    require('class: "lex-barrelled-master"' in FRAMEWORK,
            "the shared master must own the side-by-side barrel grid")
    require('`lex-barrel-control${openBarrelControlKey' in FRAMEWORK
            and ".lex-barrel-control.open" in CSS,
            "the shared Table panel needs one compact control that stays open for repeated changes")
    require("dividerAccessories: [barrelControl]" in FRAMEWORK
            and "options.dividerAccessories" in FRAMEWORK,
            "the barrel control must belong to the shared divider rail")
    require('"aria-label": "Decrease table barrels"' in FRAMEWORK
            and '"aria-label": "Increase table barrels"' in FRAMEWORK,
            "minus and plus controls need explicit accessible actions")
    require("masterNodes = barrelRows.map" in FRAMEWORK and "masterNodes[0]" in FRAMEWORK,
            "selection and fitted row measurement must use the shared barrel masters")
    require("if (pages > 1 || hasBottomTools) {" in FRAMEWORK and "const pagerNode = pager(" in FRAMEWORK,
            "the bottom bar must remain when it owns search or filters, even when one barrel group fits")
    require('available: root' in FRAMEWORK
            and 'visibleRows: () => searchActive ? pageSize : Math.max(1' in FRAMEWORK
            and 'masterNode.style.height = `${height}px`' in FRAMEWORK
            and 'fixedRows: searchActive ? pageSize : (pages === 1 ? Math.max(1' in FRAMEWORK,
            "barrel tables must measure the stable composed view, then fit only the visible master rows")
    require("const hasTableRowsOverride" in FRAMEWORK and "const clearTableRows" in FRAMEWORK
            and "def clear_view_preference" in SETTINGS
            and "def clear_lexeditor_view_preference" in DESKTOP,
            "per-page row overrides must show inheritance and support a persistent clear operation")
    # This slice ended at "const pagerNode =", 382 lines further on, so the
    # "no onchange" rule was policing the whole pager region rather than the
    # Rows override it is about - and it tripped on an unrelated "Hide empty
    # slots" checkbox that legitimately uses onchange. Ends at the row after
    # the control instead, so the contract still covers exactly what it names.
    _rows_start = FRAMEWORK.index("const commitRows =")
    row_control = FRAMEWORK[_rows_start:FRAMEWORK.index(
        'const right = element("div", {class: "lex-pager-right"}', _rows_start)]
    require('onblur: event => commitRows(event.target)' in row_control
            and 'event.key === "Enter"' in row_control
            and "onchange:" not in row_control
            and '" inherited"' in row_control,
            "the Rows override must keep keyboard focus until commit and show inherited state")
    require('class: "lex-column-heading"' in FRAMEWORK and "column.help ? infoHelp" in FRAMEWORK,
            "table columns must support an independent standard help control")
    require(".lex-barrelled-master" in CSS and ".lex-barrel-control" in CSS,
            "the shared barrel grid and control need shared layout rules")
    require("rotate(-90deg)" in CSS
            and ".lex-panel-layout-divider:hover > .lex-barrel-control" in CSS,
            "the divider rail must reveal the rotated barrel control")
    require('divider.addEventListener("contextmenu"' in FRAMEWORK
            and 'divider.addEventListener("dblclick"' not in FRAMEWORK,
            "right-click, not double-click, must reset a panel split")
    require("const barrelPanelMinimum =" in FRAMEWORK
            and "minLeft: barrelPanelMinimum" in FRAMEWORK,
            "the table-panel pixel minimum must grow with the barrel count")
    require("minimumSplit: Math.min(78, 22 * barrels)" in FRAMEWORK
            and "minimumFractions" in FRAMEWORK,
            "the shared panel composer must consume the barrel-aware split minimum")
    require("fitBarrelTableColumns" in FRAMEWORK,
            "barrel table tracks must fit inside their assigned panel without clipping an edge")
    require("splitKey:`ff8-${view}`" in (ROOT / "games" / "ff8" / "editor.html").read_text(encoding="utf-8"),
            "FF8 must keep a game-and-view-specific preference key")

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "settings.json"
        store = SettingsStore(path)
        store.save("daily")
        store.save_view_preference("barrels:ff8-magic", 3)
        store.save_view_preference("barrels:rdr2-items", 2)
        store.save_view_preference("rows:ff8-weapons", 33)
        store.save("weekly", True, table_rows_per_page=19)
        reread = SettingsStore(path).snapshot()
        require(reread["viewPreferences"] == {
            "barrels:ff8-magic": 3,
            "barrels:rdr2-items": 2,
            "rows:ff8-weapons": 33,
        }, "barrel and per-page row preferences must survive reload and remain independent")
        require(reread["updateCheckFrequency"] == "weekly" and reread["developerMode"] is True,
                "saving barrel counts must preserve other Lexeditor settings")
        require(reread["tableRowsPerPage"] == 19,
                "the global table-row target must survive barrel preference saves")
        store.clear_view_preference("rows:ff8-weapons")
        require("rows:ff8-weapons" not in store.snapshot()["viewPreferences"],
                "clearing a row override must restore global inheritance")
        for invalid in (0, 7):
            try:
                store.save_view_preference("barrels:ff8-magic", invalid)
            except ValueError:
                continue
            raise AssertionError("barrel counts outside 1 through 6 must be rejected")
        for invalid in (4, 81):
            try:
                store.save_view_preference("rows:ff8-weapons", invalid)
            except ValueError:
                continue
            raise AssertionError("per-page row counts outside 5 through 80 must be rejected")
    print("Shared N-barrelled table source contract passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
