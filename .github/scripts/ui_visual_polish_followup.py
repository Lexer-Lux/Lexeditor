from pathlib import Path


def read(path):
    return Path(path).read_text(encoding="utf-8")


def write(path, text):
    Path(path).write_text(text, encoding="utf-8", newline="\n")


def one(path, old, new, label):
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    write(path, text.replace(old, new, 1))


# The Detail-panel-local declaration was still overriding the intended global
# 10% label lane, which is why Blank continued to look like the old ~18% split.
one(
    "ui/framework.css",
    "  --lex-detail-label-width:clamp(125px, 18%, 230px);",
    "  --lex-detail-label-width:10%;",
    "detail label lane",
)

p = "ui/framework.css"
text = read(p)
marker = "/* LEXEDITOR_UI_VISUAL_POLISH_20260906 */"
if marker not in text:
    text += r'''

/* LEXEDITOR_UI_VISUAL_POLISH_20260906 */
/* Divider accessories intentionally protrude into the table pane. They must
   remain above the table cells or the visible +/- controls cannot be clicked. */
.lex-paged-list-detail > .lex-panel-layout-divider {
  z-index:40;
  overflow:visible;
}
.lex-paged-list-detail > .lex-barrelled-master {
  position:relative;
  z-index:1;
}
.lex-barrel-control { z-index:50; }

/* Ref tags are prefixes, not fixed-width columns. A 22px V lane left a huge
   visual hole before a boolean check/X. Keep every code compact, including LL. */
.lex-reference-values .lex-reference-tag {
  flex:0 0 auto;
  width:auto;
  min-width:0;
  max-width:none;
  margin-right:.22em;
}
.lex-source-control:has(input[type="checkbox"]) > .lex-reference-values {
  top:50%;
  bottom:auto;
  align-content:center;
  padding-block:2px;
  transform:translateY(-50%);
}
.lex-source-control:has(input[type="checkbox"]) .lex-reference-value,
.lex-source-control:has(input[type="checkbox"]) .lex-boolean-mark {
  align-items:center;
  line-height:1;
}
.lex-source-control:has(input[type="checkbox"]) .lex-boolean-mark {
  display:inline-grid;
  place-items:center;
}

/* The info bubble and its glyph each use the exact centre of the shared rail. */
.lex-field-type-rail > .lex-info-help {
  left:50% !important;
  top:50% !important;
  translate:none;
  transform:translate(-50%,-50%) !important;
}
.lex-info-help > span {
  display:grid;
  box-sizing:border-box;
  width:100%;
  height:100%;
  place-items:center;
  line-height:1;
  text-align:center;
}

/* Grouped boolean labels remain horizontal and must fit their existing box;
   content length never gets to grow the property row. */
.lex-toggle-name {
  min-width:0;
  max-width:100%;
  overflow:hidden;
  white-space:normal;
  overflow-wrap:anywhere;
  text-align:center;
}
'''
write(p, text)

# Resetting a numeric property must repaint both its explicit range control and
# the shared value-fill/slider. The value-fill listens to input, so emit the
# same event after the ref/Vanilla restore has completed.
p = "ui/framework.js"
text = read(p)
old = '''    requestAnimationFrame(() => requestAnimationFrame(() => {\n      syncRange(field);\n      const target = getComputedStyle(field).backgroundColor;\n'''
new = '''    requestAnimationFrame(() => requestAnimationFrame(() => {\n      syncRange(field);\n      const numeric = field.querySelector('input[type="number"]');\n      if (numeric) numeric.dispatchEvent(new Event('input', {bubbles: true}));\n      if (!field.isConnected) return;\n      const target = getComputedStyle(field).backgroundColor;\n'''
if text.count(old) != 1:
    raise SystemExit(f"reset slider sync: expected one match, found {text.count(old)}")
text = text.replace(old, new, 1)

# Fit both ordinary property labels and the actual shared toggle-name class.
old = '''  const fitAllLabels = root => root.querySelectorAll?.(\n    '.lex-detail-field-label,.lex-toggle-label,.lex-flag-label',\n  ).forEach(fitLabel);\n  const labelObserver = new MutationObserver(records => records.forEach(record => record.addedNodes.forEach(node => {\n    if (node instanceof Element) fitAllLabels(node);\n  })));\n  labelObserver.observe(document.documentElement, {childList: true, subtree: true});\n  window.addEventListener('resize', () => fitAllLabels(document));\n  requestAnimationFrame(() => fitAllLabels(document));\n'''
new = '''  const fittedLabelSelector = '.lex-detail-field-label,.lex-toggle-name,.lex-toggle-label,.lex-flag-label';\n  const labelResizeObserver = typeof ResizeObserver === 'function'\n    ? new ResizeObserver(entries => entries.forEach(entry => fitLabel(entry.target)))\n    : null;\n  const fitAllLabels = root => {\n    const labels = [\n      root instanceof Element && root.matches(fittedLabelSelector) ? root : null,\n      ...root.querySelectorAll?.(fittedLabelSelector) || [],\n    ].filter(Boolean);\n    labels.forEach(label => {\n      fitLabel(label);\n      labelResizeObserver?.observe(label);\n    });\n  };\n  const labelObserver = new MutationObserver(records => records.forEach(record => record.addedNodes.forEach(node => {\n    if (node instanceof Element) fitAllLabels(node);\n  })));\n  labelObserver.observe(document.documentElement, {childList: true, subtree: true});\n  window.addEventListener('resize', () => fitAllLabels(document));\n  document.fonts?.ready?.then(() => fitAllLabels(document));\n  requestAnimationFrame(() => fitAllLabels(document));\n'''
if text.count(old) != 1:
    raise SystemExit(f"label fitting: expected one match, found {text.count(old)}")
text = text.replace(old, new, 1)
write(p, text)
