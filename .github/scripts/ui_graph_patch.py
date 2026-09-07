from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
path = ROOT / "ui" / "framework.css"
text = path.read_text(encoding="utf-8")
marker = "LEXEDITOR_GRAPH_MARGIN_POSITIONING_20260906"
if marker not in text:
    text += r'''

/* LEXEDITOR_GRAPH_MARGIN_POSITIONING_20260906 */
/* Axis text belongs to the plot margin, not to normal document flow. An
   older shared selector reset .lex-curve-axis and .lex-curve-axis-name to
   position:relative after their original absolute rules, so right-axis
   values drifted into the graph. Reassert the graph contract last. */
.lex-curve-plot > :is(.lex-curve-axis,.lex-curve-axis-name) {
  position:absolute !important;
  z-index:2;
}
.lex-curve-axis-top,.lex-curve-axis-bottom {
  left:auto !important;
  right:7px !important;
  writing-mode:vertical-rl !important;
  text-orientation:mixed !important;
  transform:rotate(180deg) !important;
}
.lex-curve-axis-name-y {
  left:auto !important;
  right:22px !important;
  top:50% !important;
  bottom:auto !important;
  writing-mode:vertical-rl !important;
  text-orientation:mixed !important;
  transform:translateY(-50%) rotate(180deg) !important;
}
.lex-curve-axis-start,.lex-curve-axis-end,.lex-curve-axis-name-x {
  top:auto !important;
  bottom:4px !important;
}
'''
    path.write_text(text, encoding="utf-8", newline="\n")
