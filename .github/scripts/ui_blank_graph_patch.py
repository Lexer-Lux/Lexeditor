from pathlib import Path

path = Path(__file__).resolve().parents[2] / "games" / "blank" / "editor.html"
text = path.read_text(encoding="utf-8")
old = '.blank-graphs{display:grid;grid-template-columns:repeat(auto-fit,minmax(400px,1fr));align-content:start;gap:16px;height:100%;overflow:auto}'
new = '.blank-graphs{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,600px),1fr));align-content:start;gap:16px;height:100%;overflow:auto}'
if old in text:
    text = text.replace(old, new, 1)
elif new not in text:
    raise SystemExit('Blank graph-grid rule not found')
path.write_text(text, encoding="utf-8", newline="\n")
