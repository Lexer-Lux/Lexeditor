from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
path = ROOT / "ui" / "framework.js"
text = path.read_text(encoding="utf-8")

old_slot = '''    const syncCloseSlot = () => {
      const iconBox = icon.getBoundingClientRect();
      close.style.transform = 'none';
      close.style.left = `${icon.offsetLeft}px`;
      close.style.top = `${icon.offsetTop}px`;
      close.style.width = `${iconBox.width}px`;
      close.style.height = `${iconBox.height}px`;
      const closeBox = close.getBoundingClientRect();
      if (closeBox.width && closeBox.height) {
        close.style.transform = `translate(${iconBox.left - closeBox.left}px, ${iconBox.top - closeBox.top}px)`;
      }
    };
    const settleCloseSlot = () => {
      syncCloseSlot();
      requestAnimationFrame(() => {
        syncCloseSlot();
        requestAnimationFrame(syncCloseSlot);
      });
    };'''
new_slot = '''    const syncCloseSlot = targetBox => {
      const iconBox = targetBox || icon.getBoundingClientRect();
      close.style.transform = 'none';
      close.style.left = `${icon.offsetLeft}px`;
      close.style.top = `${icon.offsetTop}px`;
      close.style.width = `${iconBox.width}px`;
      close.style.height = `${iconBox.height}px`;
      const closeBox = close.getBoundingClientRect();
      if (closeBox.width && closeBox.height) {
        close.style.transform = `translate(${iconBox.left - closeBox.left}px, ${iconBox.top - closeBox.top}px)`;
      }
    };
    const settleCloseSlot = targetBox => {
      syncCloseSlot(targetBox);
      requestAnimationFrame(() => {
        syncCloseSlot(targetBox);
        requestAnimationFrame(() => syncCloseSlot(targetBox));
      });
    };'''
if old_slot in text:
    text = text.replace(old_slot, new_slot, 1)

old_open = '''    const open = async () => {
      if (!drawer.childNodes.length) {
        const content = await getContent?.();
        if (content instanceof Node) drawer.append(content);
      }
      drawer.hidden = false;
      panel.classList.add('lex-model-preview-open');
      settleCloseSlot();
      icon.setAttribute('aria-expanded', 'true');'''
new_open = '''    const open = async () => {
      // Capture the slot while the ordinary header icon is still visible. The
      // close control replaces THAT exact box even if opening the drawer causes
      // a plugin theme to restyle or realign the hidden icon afterward.
      const closedIconBox = icon.getBoundingClientRect();
      if (!drawer.childNodes.length) {
        const content = await getContent?.();
        if (content instanceof Node) drawer.append(content);
      }
      drawer.hidden = false;
      panel.classList.add('lex-model-preview-open');
      settleCloseSlot(closedIconBox);
      icon.setAttribute('aria-expanded', 'true');'''
if old_open in text:
    text = text.replace(old_open, new_open, 1)

if old_slot not in text and new_slot not in text:
    raise SystemExit("preview slot block not found")
if old_open not in text and new_open not in text:
    raise SystemExit("preview open block not found")
path.write_text(text, encoding="utf-8", newline="\n")
