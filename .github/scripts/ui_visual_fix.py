from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]

framework = ROOT / "ui" / "framework.js"
text = framework.read_text(encoding="utf-8")

replacement = r'''  const attachModelPreview = (panel, spec) => {
    if (!(panel instanceof Element) || !spec) return panel;
    const heading = panel.querySelector(':scope > .lex-detail-panel-heading');
    const icon = heading?.querySelector('.lex-detail-panel-icon');
    if (!heading || !icon) return panel;
    const getContent = typeof spec === 'function' ? spec : () => spec.content;
    const onOpen = typeof spec === 'object' ? spec.onOpen : null;
    const onClose = typeof spec === 'object' ? spec.onClose : null;
    const openLabel = typeof spec === 'object' && spec.openLabel ? spec.openLabel : 'Open model preview';
    const closeLabel = typeof spec === 'object' && spec.closeLabel ? spec.closeLabel : 'Close model preview';

    // Keep the SAME header icon element as the control in both states. This
    // makes the X occupy the exact same rendered box by construction instead
    // of trying to chase the icon with a separately positioned button.
    const iconContent = document.createElement('span');
    iconContent.className = 'lex-model-preview-icon-content';
    while (icon.firstChild) iconContent.append(icon.firstChild);
    const closeMark = document.createElement('span');
    closeMark.className = 'lex-model-preview-close';
    closeMark.setAttribute('aria-hidden', 'true');
    closeMark.textContent = '×';
    icon.append(iconContent, closeMark);

    const drawer = document.createElement('section');
    drawer.className = 'lex-model-preview-drawer';
    drawer.hidden = true;
    drawer.setAttribute('aria-label', typeof spec === 'object' && spec.label ? spec.label : 'Model preview');
    heading.after(drawer);

    let busy = false;
    const open = async () => {
      if (busy || panel.classList.contains('lex-model-preview-open')) return;
      busy = true;
      try {
        if (!drawer.childNodes.length) {
          const content = await getContent?.();
          if (content instanceof Node) drawer.append(content);
        }
        drawer.hidden = false;
        panel.classList.add('lex-model-preview-open');
        icon.setAttribute('aria-expanded', 'true');
        icon.setAttribute('aria-label', closeLabel);
        icon.title = closeLabel;
        await onOpen?.(drawer);
      } finally { busy = false; }
    };
    const shut = async () => {
      if (busy || !panel.classList.contains('lex-model-preview-open')) return;
      busy = true;
      try {
        await onClose?.(drawer);
        panel.classList.remove('lex-model-preview-open');
        drawer.hidden = true;
        icon.setAttribute('aria-expanded', 'false');
        icon.setAttribute('aria-label', openLabel);
        icon.title = openLabel;
      } finally { busy = false; }
    };
    const toggle = () => panel.classList.contains('lex-model-preview-open') ? shut() : open();

    icon.classList.add('lex-model-preview-trigger');
    icon.tabIndex = 0;
    icon.setAttribute('role', 'button');
    icon.setAttribute('aria-label', openLabel);
    icon.setAttribute('aria-expanded', 'false');
    icon.title = openLabel;
    icon.addEventListener('click', event => {
      event.preventDefault();
      event.stopPropagation();
      toggle();
    });
    icon.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        toggle();
      }
    });
    panel.lexModelPreview = {open, close: shut, drawer};
    return panel;
  };
  ui.attachModelPreview = attachModelPreview;'''

pattern = re.compile(
    r"  const attachModelPreview = \(panel, spec\) => \{.*?\n  ui\.attachModelPreview = attachModelPreview;",
    re.S,
)
text, count = pattern.subn(replacement, text, count=1)
if count != 1:
    raise SystemExit(f"attachModelPreview block replacement count={count}")
framework.write_text(text, encoding="utf-8", newline="\n")

css_path = ROOT / "ui" / "framework.css"
css = css_path.read_text(encoding="utf-8")
marker = "LEXEDITOR_MODEL_PREVIEW_SAME_SLOT_20260906"
if marker not in css:
    css += r'''

/* LEXEDITOR_MODEL_PREVIEW_SAME_SLOT_20260906 */
/* The preview X is not a second control positioned near the icon. It is a
   state of the standard Detail header icon itself, so both states have the
   exact same box at every size/theme/scale. */
.lex-model-preview-trigger { position:relative; }
.lex-model-preview-trigger > .lex-model-preview-icon-content,
.lex-model-preview-trigger > .lex-model-preview-close {
  position:absolute !important;
  inset:0 !important;
  width:100% !important;
  height:100% !important;
  margin:0 !important;
  transform:none !important;
  place-items:center;
}
.lex-model-preview-trigger > .lex-model-preview-icon-content { display:grid; }
.lex-model-preview-trigger > .lex-model-preview-close {
  display:none;
  box-sizing:border-box;
  padding:0;
  color:inherit;
  background:transparent;
  font:700 1.6em/1 var(--lex-symbol-font);
  pointer-events:none;
}
.lex-model-preview-open > .lex-detail-panel-heading .lex-detail-panel-icon {
  visibility:visible !important;
  pointer-events:auto !important;
}
.lex-model-preview-open > .lex-detail-panel-heading .lex-model-preview-icon-content { display:none; }
.lex-model-preview-open > .lex-detail-panel-heading .lex-model-preview-close { display:grid; }
'''
css_path.write_text(css, encoding="utf-8", newline="\n")
