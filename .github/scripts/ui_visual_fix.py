from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]


def edit(path: str, transform):
    target = ROOT / path
    original = target.read_text(encoding="utf-8")
    updated = transform(original)
    if updated != original:
        target.write_text(updated, encoding="utf-8", newline="\n")


def fix_framework_css(text: str) -> str:
    marker = "LEXEDITOR_UI_VISUAL_FIX_20260906"
    if marker in text:
        return text
    return text + r'''

/* LEXEDITOR_UI_VISUAL_FIX_20260906 */
/* Barrel controls sit on the divider but extend over the table pane.  The
   divider's old z-index left the visible +/- buttons underneath table-cell
   content, so a real pointer click hit the table instead. */
.lex-panel-layout-divider { z-index:20; }
.lex-panel-layout-divider > .lex-barrel-control { z-index:30; }
.lex-barrel-control button { pointer-events:auto; }

/* Boolean references deliberately sit below their checkbox.  Keep that small
   second line inside the row's visual rhythm and do not give a one-character
   source tag the full generic 22px reference-label column. */
.lex-boolean-field:has(.lex-source-control > .lex-reference-values) {
  padding-bottom:8px;
}
.lex-boolean-field .lex-source-control > .lex-reference-values {
  width:max-content;
  min-width:0;
  transform:translateX(-50%);
  justify-items:center;
}
.lex-boolean-field .lex-reference-values .lex-reference-value {
  align-items:center;
  justify-content:center;
  padding-block:0;
}
.lex-boolean-field .lex-reference-values .lex-reference-tag {
  flex:0 0 auto;
  width:auto;
  min-width:0;
  max-width:none;
  margin-right:4px;
}
.lex-boolean-field .lex-reference-values .lex-boolean-mark {
  align-self:center;
  line-height:1;
}
'''


def fix_blank(text: str) -> str:
    text = text.replace('    .blank-editable-table :is(input,select){width:100%;text-align:center}\n', '')
    text = re.sub(
        r'\n  function editableTablePanel\(\)\{.*?\n  function tweaksPanel\(\)',
        '\n  function tweaksPanel()', text, flags=re.S,
    )
    return text


edit("ui/framework.css", fix_framework_css)
edit("games/blank/editor.html", fix_blank)
