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

    let frozenSlot = null;
    let slotLockGeneration = 0;
    const releaseIconSlot = () => {
      icon.style.left = '';
      icon.style.top = '';
    };
    const lockIconSlot = target => {
      if (!target || !panel.classList.contains('lex-model-preview-open')) return;
      releaseIconSlot();
      const current = icon.getBoundingClientRect();
      // Relative offsets affect only paint position, not the heading's grid
      // geometry, so the control cannot feed its correction back into layout.
      icon.style.left = `${target.left - current.left}px`;
      icon.style.top = `${target.top - current.top}px`;
    };
    const holdIconSlot = target => {
      const generation = ++slotLockGeneration;
      const started = performance.now();
      const tick = now => {
        if (generation !== slotLockGeneration || !panel.classList.contains('lex-model-preview-open')) return;
        lockIconSlot(target);
        if (now - started < 360) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    };

    let busy = false;
    const open = async () => {
      if (busy || panel.classList.contains('lex-model-preview-open')) return;
      busy = true;
      try {
        const box = icon.getBoundingClientRect();
        frozenSlot = {left:box.left, top:box.top, width:box.width, height:box.height};
        if (!drawer.childNodes.length) {
          const content = await getContent?.();
          if (content instanceof Node) drawer.append(content);
        }
        drawer.hidden = false;
        panel.classList.add('lex-model-preview-open');
        lockIconSlot(frozenSlot);
        holdIconSlot(frozenSlot);
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
        ++slotLockGeneration;
        await onClose?.(drawer);
        panel.classList.remove('lex-model-preview-open');
        drawer.hidden = true;
        releaseIconSlot();
        frozenSlot = null;
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
    window.addEventListener('resize', () => {
      if (!frozenSlot || !panel.classList.contains('lex-model-preview-open')) return;
      releaseIconSlot();
      const box = icon.getBoundingClientRect();
      frozenSlot = {left:box.left, top:box.top, width:box.width, height:box.height};
      lockIconSlot(frozenSlot);
      holdIconSlot(frozenSlot);
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

acceptance_path = ROOT / ".github" / "scripts" / "ui_visual_acceptance.py"
acceptance = acceptance_path.read_text(encoding="utf-8")
old = '''            icon_box = icon.bounding_box()\n            icon.click(); page.wait_for_timeout(100)\n            drawer = page.locator('.lex-model-preview-drawer').first\n            close = page.locator('.lex-model-preview-close').first\n            assert drawer.is_visible(), (width, 'shared model preview did not open')\n            close_box = close.bounding_box()\n            assert max(abs(icon_box[k] - close_box[k]) for k in ('x','y','width','height')) <= 1.5, (width, 'model preview X is not in the header-icon slot', icon_box, close_box)\n            close.click(); page.wait_for_timeout(80)\n            assert not drawer.is_visible(), (width, 'shared model preview did not close')\n'''
new = '''            icon_box = icon.bounding_box()\n            icon.click(); page.wait_for_timeout(100)\n            drawer = page.locator('.lex-model-preview-drawer').first\n            close = page.locator('.lex-model-preview-close').first\n            assert drawer.is_visible(), (width, 'shared model preview did not open')\n            assert close.is_visible(), (width, 'model preview X is not visible')\n            open_icon_box = icon.bounding_box()\n            assert max(abs(icon_box[k] - open_icon_box[k]) for k in ('x','y','width','height')) <= 0.5, (width, 'model preview changed the header-icon control slot', icon_box, open_icon_box)\n            assert icon.get_attribute('aria-label') == 'Close model preview', (width, 'header icon did not become the close control')\n            icon.click(); page.wait_for_timeout(80)\n            assert not drawer.is_visible(), (width, 'shared model preview did not close')\n'''
if old in acceptance:
    acceptance = acceptance.replace(old, new, 1)
elif new not in acceptance:
    raise SystemExit("model preview acceptance block not found")
acceptance_path.write_text(acceptance, encoding="utf-8", newline="\n")
