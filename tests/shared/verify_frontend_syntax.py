"""Check shipped JavaScript, including inline plugin scripts, without game files."""
from html.parser import HTMLParser
from pathlib import Path
import re
import shutil
import tempfile
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


class Scripts(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.active = False
        self.blocks = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script":
            self.active = "src" not in attrs and attrs.get("type", "").lower() in (
                "", "text/javascript", "application/javascript", "module")
            if self.active:
                self.blocks.append((self.getpos()[0], attrs.get("type") == "module", ""))

    def handle_data(self, data):
        if self.active:
            line, module, text = self.blocks[-1]
            self.blocks[-1] = (line, module, text + data)

    def handle_endtag(self, tag):
        if tag == "script":
            self.active = False


def main():
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node.js is required for JavaScript syntax checks.")
    files = sorted((ROOT / "ui").glob("*.js")) + sorted((ROOT / "plugins").glob("*/*.js"))
    html = sorted((ROOT / "ui").glob("*.html")) + sorted((ROOT / "plugins").glob("*/editor.html"))
    blocks = []
    for path in html:
        parser = Scripts()
        parser.feed(path.read_text(encoding="utf-8-sig"))
        blocks.extend((f"{path.relative_to(ROOT)}:{line}", module, text)
                      for line, module, text in parser.blocks)
    failures = []
    # node --check by path silently passes broken ES modules, and stdin
    # as commonjs rejects even valid ones, so files with static
    # import/export go through a .mjs copy where node parses them as
    # modules for real. Everything else is checked by path as classic.
    module_like = re.compile(r"^\s*(import[\s({]|export[\s{*])", re.M)
    with tempfile.TemporaryDirectory(prefix="lexeditor-syntax") as tmp:
        for path in files:
            label = str(path.relative_to(ROOT))
            text = path.read_text(encoding="utf-8-sig")
            check, shown = str(path), label
            if module_like.search(text):
                probe = Path(tmp) / (path.stem + ".mjs")
                probe.write_bytes(path.read_bytes())
                check = str(probe)
            result = subprocess.run([node, "--check", check], capture_output=True, timeout=30)
            if result.returncode:
                failures.append(label)
                print(f"FAIL {shown}\n{result.stderr.decode('utf-8', 'replace')}")
    for label, module, text in blocks:
        result = subprocess.run([node, "--check", "--input-type=" + ("module" if module else "commonjs")],
                                input=text, text=True, encoding="utf-8", capture_output=True, timeout=30)
        if result.returncode:
            failures.append(label)
            print(f"FAIL {label}\n{result.stderr}")
    total = len(files) + len(blocks)
    print(f"JavaScript syntax: {total-len(failures)}/{total} scripts passed")
    return bool(failures)


if __name__ == "__main__":
    sys.exit(main())
