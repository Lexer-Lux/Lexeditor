from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
EDITOR = ROOT / "games" / "rdr2" / "editor.html"

html = EDITOR.read_text(encoding="utf-8")

# One component owns membership/value comparison, per-entry reference stacks,
# and the reference-only ghost segment for all three requested fields.
assert "function multiValueReferences({" in html
assert "function multiValueReferenceStack(" in html
assert 'class:"multi-ref-ghosts"' in html
assert 'class:"multi-ref-entry multi-ref-ghost"' in html
assert '"data-multi-ref-kind":kind' in html
assert 'kind:"item-effects"' in html
assert 'kind:"item-tags"' in html
assert 'kind:"challenge-rewards"' in html
assert ':is(.ref,.multi-ref-stack) .vtag' in html
assert '.ref .vtag {' not in html
stack_style = re.search(r':is\(\.ref\.refstack,\.multi-ref-stack\)\s*\{([^}]+)\}', html)
assert stack_style
assert 'font-family:var(--rdr-font-body)' in stack_style.group(1)
font_size = re.search(r'font-size:([\d.]+)px', stack_style.group(1))
assert font_size and float(font_size.group(1)) >= 10
assert 'font:8.5px/1.3 Consolas,monospace' not in html

# The old field-level and index-based comparisons can report a green check for
# the wrong set. They must not return.
assert "tagsEqual(src.tags,current)" not in html
assert "vrank?.rewards?.[index]" not in html
assert 'class:"restore-ref"' not in html

# The established full selectors remain the only add paths. The shared New
# button derives its accessible name from this required title.
assert 'newButton({title:"Add effect"' in html
assert 'newButton({title:"Add catalog tag"' in html
assert "pickIdentifier(\"Add effect\"" in html
assert "pickCatalogTag(it" in html
assert "dl-effects" not in html
assert "dl-tags" not in html

print("PASS: Lexeditor #5 shared multi-value references and picker contracts")
