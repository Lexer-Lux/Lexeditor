from pathlib import Path

path = Path(__file__).resolve().parents[2] / "ui" / "framework.css"
text = path.read_text(encoding="utf-8")
marker = "LEXEDITOR_FIXED_PROPERTY_LABEL_TRACK_20260906"
if marker not in text:
    text += r'''

/* LEXEDITOR_FIXED_PROPERTY_LABEL_TRACK_20260906 */
/* A long property NAME is allowed to wrap/shrink inside its allocated lane,
   but its intrinsic text height must never make the property row taller.
   Size containment removes the label's intrinsic block-size contribution;
   the row is then sized by the actual control, and fitLabel() scales/wraps the
   label into that fixed space. */
.lex-detail-field > .lex-detail-field-label {
  contain:size;
  min-block-size:0;
  overflow:hidden;
}
'''
    path.write_text(text, encoding="utf-8", newline="\n")
