from pathlib import Path

path = Path(__file__).resolve().parents[2] / "ui" / "framework.js"
text = path.read_text(encoding="utf-8")
old = "while (size > 8 && (label.scrollHeight > label.clientHeight + 1 || label.scrollWidth > label.clientWidth + 1)) {"
new = "while (size > 6 && (label.scrollHeight > label.clientHeight + 1 || label.scrollWidth > label.clientWidth + 1)) {"
if old in text:
    text = text.replace(old, new, 1)
elif new not in text:
    raise SystemExit("fitLabel minimum-font loop not found")
path.write_text(text, encoding="utf-8", newline="\n")
