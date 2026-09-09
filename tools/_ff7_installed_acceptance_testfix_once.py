"""One-shot compatibility update for the hardened installed-check report."""
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "tools/verify_ff7_completion.py"
text = path.read_text(encoding="utf-8")
old = "            self.assertIn('scene',report['errors']);self.assertFalse(report['passed'])\n"
new = "            self.assertIn('source:scene',report['errors']);self.assertFalse(report['passed'])\n"
if text.count(old) != 1:
    raise SystemExit("expected one installed-diagnostic scene assertion")
path.write_text(text.replace(old, new), encoding="utf-8")
