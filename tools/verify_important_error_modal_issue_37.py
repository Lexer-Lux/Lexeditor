"""Shared blocking save-error modal contract for Lexeditor issue 37."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRAMEWORK = (ROOT / "ui" / "framework.js").read_text(encoding="utf-8")
CSS = (ROOT / "ui" / "framework.css").read_text(encoding="utf-8")
FF8 = (ROOT / "games" / "ff8" / "editor.html").read_text(encoding="utf-8")
WARBAND = (ROOT / "games" / "warband" / "editor.html").read_text(encoding="utf-8")
RDR = (ROOT / "games" / "rdr" / "editor.html").read_text(encoding="utf-8")
RDR2 = (ROOT / "games" / "rdr2" / "editor.html").read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


require("const showAlert = options =>" in FRAMEWORK,
        "the shared important-message dialog is missing")
require("showAlert," in FRAMEWORK[FRAMEWORK.index("window.LexeditorUI ="):],
        "the shared important-message dialog is not exported")
alert_source = FRAMEWORK[FRAMEWORK.index("const showAlert = options =>"):
                         FRAMEWORK.index("const confirmUnsavedExit")]
require('role: "alertdialog"' in alert_source and '"aria-modal": "true"' in alert_source,
        "important messages must use an accessible blocking alert dialog")
require('class: "lex-important-list"' in alert_source and 'class: "lex-important-item-link"' in alert_source,
        "important messages need structured Item: issue rows with navigable items")
require('dialog.closest(".lex-dialog-backdrop")?.remove(); entry.activate()' in alert_source,
        "record links must close the modal before navigation")
require("event.target === backdrop" not in alert_source and 'event.key === "Escape"' not in alert_source,
        "backdrop click or Escape can still dismiss an important message")
require(".lex-important-dialog" in CSS and ".lex-important-message" in CSS,
        "the large untruncated important-message presentation is missing")
require("overflow-wrap: anywhere" in CSS,
        "long important messages can still be clipped horizontally")

require('items:[{item:row?.name||"Save",issue:message,activate:row?' in FF8 and 'closeLabel:"Confirm and Close"' in FF8,
        "FF8 save errors do not identify and link the selected record")
require('items:[{item:"Save",issue:error.message||String(error)}],closeLabel:"Confirm and Close"' in WARBAND,
        "Warband does not use the shared save-error dialog")
require('items:[{item:"Save",issue:error.message||String(error)}],closeLabel:"Confirm and Close"' in RDR,
        "RDR does not use the shared save-error dialog")
rdr_save = RDR[RDR.index("async function saveAll()"):
               RDR.index("const shell=LexeditorUI.mountShell")]
require("alert(state.status)" not in rdr_save,
        "RDR still uses a native browser alert for save failures")
require("function showSaveFailure(error)" in RDR2 and 'items:[{item:"Save",issue:message}],closeLabel:"Confirm and Close"' in RDR2,
        "RDR2 does not route save failures through the shared dialog")
require('toast("Save failed: "' not in RDR2 and 'toast("Save failed: "+' not in RDR2,
        "an RDR2 save path still exposes the full error only in a toast")
require("toast(`Cannot save:" not in RDR2,
        "an RDR2 validation failure still exposes the full error only in a toast")

print("PASS: save failures use a blocking structured modal with record navigation")
