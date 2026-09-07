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
    first = "LEXEDITOR_UI_VISUAL_FIX_20260906"
    if first not in text:
        text += r'''

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
    second = "LEXEDITOR_FIELD_METADATA_GEOMETRY_20260906"
    if second not in text:
        text += r'''

/* LEXEDITOR_FIELD_METADATA_GEOMETRY_20260906 */
/* Property names own exactly ten percent of an ordinary Detail row.  The text
   sits against the value side of that lane; the shared type/help rail occupies
   the metadata space to its left and is positioned by framework.js from the
   actually rendered text width. */
.lex-detail-field:not(.lex-boolean-field) {
  grid-template-columns:10% minmax(0,1fr) !important;
}
.lex-detail-field:not(.lex-boolean-field) > .lex-detail-field-label {
  justify-content:flex-end;
  text-align:right;
}
.lex-field-type-rail { overflow:visible; }
'''
    third = "LEXEDITOR_BOOLEAN_REF_BOTTOM_MARGIN_20260906"
    if third not in text:
        text += r'''

/* LEXEDITOR_BOOLEAN_REF_BOTTOM_MARGIN_20260906 */
/* The ref rail is absolutely positioned so padding alone cannot keep the next
   property from touching it. Reserve actual inter-row space after any Boolean
   that is showing provenance. */
.lex-boolean-field:has(.lex-source-control > .lex-reference-values) {
  margin-bottom:8px;
}
'''
    fourth = "LEXEDITOR_MODEL_PREVIEW_OVERLAY_20260906"
    if fourth not in text:
        text += r'''

/* LEXEDITOR_MODEL_PREVIEW_OVERLAY_20260906 */
/* A preview is a drawer over the Detail body, not a third grid row.  Letting it
   auto-place as a third child changed the height of the 10% header row when it
   opened, so the icon itself moved before the X replaced it.  Absolute overlay
   keeps the heading geometrically invariant and makes the drawer actually slide
   out over the editing surface. */
.lex-detail-panel:has(> .lex-model-preview-drawer) { position:relative; }
.lex-model-preview-drawer {
  position:absolute;
  z-index:3;
  left:0;
  right:0;
  top:10%;
  bottom:0;
  min-height:0;
  background:var(--lex-panel);
}
'''
    return text


def fix_framework_js(text: str) -> str:
    # Migrate older preview-slot positioning implementations first.
    slot_v0 = '''    const syncCloseSlot = () => {\n      close.style.left = `${icon.offsetLeft}px`;\n      close.style.top = `${icon.offsetTop}px`;\n      close.style.width = `${icon.offsetWidth}px`;\n      close.style.height = `${icon.offsetHeight}px`;\n    };'''
    slot_v1 = '''    const syncCloseSlot = () => {\n      // offsetLeft/offsetWidth round fractional grid geometry, which moved the\n      // X by a couple of pixels at narrower window sizes. Measure both boxes\n      // in the same coordinate system so the close button literally overlays\n      // the header icon at any scale.\n      const headingBox = heading.getBoundingClientRect();\n      const iconBox = icon.getBoundingClientRect();\n      const originX = headingBox.left + heading.clientLeft;\n      const originY = headingBox.top + heading.clientTop;\n      close.style.left = `${iconBox.left - originX}px`;\n      close.style.top = `${iconBox.top - originY}px`;\n      close.style.width = `${iconBox.width}px`;\n      close.style.height = `${iconBox.height}px`;\n    };'''
    if slot_v0 in text:
        text = text.replace(slot_v0, slot_v1, 1)

    slot_v2 = '''    const syncCloseSlot = () => {\n      const iconBox = icon.getBoundingClientRect();\n      close.style.transform = 'none';\n      close.style.left = `${icon.offsetLeft}px`;\n      close.style.top = `${icon.offsetTop}px`;\n      close.style.width = `${iconBox.width}px`;\n      close.style.height = `${iconBox.height}px`;\n      const closeBox = close.getBoundingClientRect();\n      if (closeBox.width && closeBox.height) {\n        close.style.transform = `translate(${iconBox.left - closeBox.left}px, ${iconBox.top - closeBox.top}px)`;\n      }\n    };'''
    if slot_v1 in text:
        text = text.replace(slot_v1, slot_v2, 1)

    # The drawer may still cause plugin content to settle asynchronously. Keep
    # the replacement locked to the rendered icon box across two paint frames.
    slot_v3 = slot_v2 + '''\n    const settleCloseSlot = () => {\n      syncCloseSlot();\n      requestAnimationFrame(() => {\n        syncCloseSlot();\n        requestAnimationFrame(syncCloseSlot);\n      });\n    };'''
    if slot_v2 in text and 'const settleCloseSlot = () =>' not in text:
        text = text.replace(slot_v2, slot_v3, 1)

    open_v0 = '''    const open = async () => {\n      syncCloseSlot();\n      if (!drawer.childNodes.length) {\n        const content = await getContent?.();\n        if (content instanceof Node) drawer.append(content);\n      }\n      drawer.hidden = false;\n      panel.classList.add('lex-model-preview-open');\n      icon.setAttribute('aria-expanded', 'true');'''
    open_v1 = '''    const open = async () => {\n      if (!drawer.childNodes.length) {\n        const content = await getContent?.();\n        if (content instanceof Node) drawer.append(content);\n      }\n      drawer.hidden = false;\n      panel.classList.add('lex-model-preview-open');\n      syncCloseSlot();\n      icon.setAttribute('aria-expanded', 'true');'''
    if open_v0 in text:
        text = text.replace(open_v0, open_v1, 1)
    if open_v1 in text and 'settleCloseSlot();' not in text:
        text = text.replace(
            "      panel.classList.add('lex-model-preview-open');\n      syncCloseSlot();\n      icon.setAttribute('aria-expanded', 'true');",
            "      panel.classList.add('lex-model-preview-open');\n      settleCloseSlot();\n      icon.setAttribute('aria-expanded', 'true');",
            1,
        )

    marker = "LEXEDITOR_FIELD_METADATA_GEOMETRY_20260906"
    if marker in text:
        return text
    return text + r'''

/* LEXEDITOR_FIELD_METADATA_GEOMETRY_20260906 */
(() => {
  const alignFieldMetadata = root => {
    const fields = root?.matches?.('.lex-detail-field')
      ? [root] : [...(root?.querySelectorAll?.('.lex-detail-field') || [])];
    for (const field of fields) {
      if (field.classList.contains('lex-boolean-field')) continue;
      const rail = field.querySelector(':scope > .lex-field-type-rail');
      const help = rail?.querySelector('.lex-info-help');
      const label = field.querySelector(':scope > .lex-detail-field-label');
      if (!rail || !help || !label) continue;
      const text = [...label.childNodes].find(node =>
        node.nodeType === Node.TEXT_NODE && node.textContent.trim());
      if (!text) continue;
      const range = document.createRange();
      range.selectNodeContents(text);
      const fieldBox = field.getBoundingClientRect();
      const textBox = range.getBoundingClientRect();
      const railBox = rail.getBoundingClientRect();
      if (!fieldBox.width || !textBox.width || !railBox.width) continue;
      // User-facing contract: the info bubble/type rail is centred between the
      // panel-side edge of the property row and the RIGHT edge of its label.
      const centre = (fieldBox.left + textBox.right) / 2;
      rail.style.left = `${Math.max(0, centre - fieldBox.left - railBox.width / 2)}px`;
    }
  };
  const schedule = root => requestAnimationFrame(() => alignFieldMetadata(root || document));
  new MutationObserver(records => records.forEach(record => record.addedNodes.forEach(node => {
    if (node instanceof Element) schedule(node);
  }))).observe(document.documentElement, {childList:true, subtree:true});
  window.addEventListener('resize', () => schedule(document));
  schedule(document);
})();
'''


def fix_blank(text: str) -> str:
    text = text.replace('    .blank-editable-table :is(input,select){width:100%;text-align:center}\n', '')
    text = re.sub(
        r'\n  function editableTablePanel\(\)\{.*?\n  function tweaksPanel\(\)',
        '\n  function tweaksPanel()', text, flags=re.S,
    )
    return text


def fix_visual_acceptance(text: str) -> str:
    old = '''            results[prefix] = {\n                "errors": errors,\n'''
    new = '''            # set_content() runs the fixture at about:blank with a fake <base>.\n            # The app's final history.replaceState therefore raises one expected\n            # null-origin security error that cannot occur in the real HTTP/WebView\n            # host. Keep every other page error fatal.\n            real_errors = [error for error in errors if not (\n                "Failed to execute 'replaceState' on 'History'" in error and\n                "origin 'null'" in error\n            )]\n            results[prefix] = {\n                "errors": real_errors,\n'''
    if old in text:
        text = text.replace(old, new, 1)
    text = text.replace('            assert not errors, (width, errors)\n',
                        '            assert not real_errors, (width, real_errors)\n', 1)
    return text


edit("ui/framework.css", fix_framework_css)
edit("ui/framework.js", fix_framework_js)
edit("games/blank/editor.html", fix_blank)
edit(".github/scripts/ui_visual_acceptance.py", fix_visual_acceptance)
