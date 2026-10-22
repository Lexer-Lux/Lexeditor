"""Field labels in one pane share one size and refit when renamed.

DS1 Items -> Ammo -> Standard Arrow -> Defense showed "Strike", "Slash" and
"Thrust" tiny after being renamed from long shipped names, while neighbours
stayed full size: each label was shrunk alone, and nothing re-measured it
when its text changed. Labels are now fitted per pane - one size for all,
only as small as the longest needs, wrapping to two lines at full size
before shrinking - and any text change refits the pane.
"""
from test_shared_ui_feedback import framework, page
from test_tab_rename import mount_shell

NAMES = {
    "Requirements": ["Horizontal Guard Angle", "Guard Stability",
                     "Guard Animation Set", "Parry Defense",
                     "Base Repel: Defense", "Guard Absorption Invalidation",
                     "Guard Damage Level", "Enables Guard"],
    "Defenses": ["Physical Guard Cut Rate", "Strike Guard Cut Rate",
                 "Slash Guard Cut Rate", "Thrust Guard Cut Rate",
                 "Magic Guard Cut Rate", "Fire Guard Cut Rate",
                 "Lightning Guard Cut Rate"],
    "Resistances": ["Poison guard", "Toxic guard", "Bleed guard", "Curse guard"],
}

SIZES = """() => [...document.querySelectorAll('.lex-detail-field-label')].map(label => ({
  name: label.querySelector(':scope > .lex-detail-field-label-text').textContent,
  size: getComputedStyle(label).fontSize,
  inline: label.style.fontSize || null,
}))"""

LINES = """() => [...document.querySelectorAll('.lex-detail-field-label-text')].map(text => {
  const range = document.createRange();
  range.selectNodeContents(text);
  return {name: text.textContent,
    lines: [...range.getClientRects()].filter(box => box.width && box.height).length};
})"""


def test_renamed_labels_keep_their_panes_size(page, tmp_path):
    framework(page)
    mount_shell(page)
    page.evaluate("""(names) => {
      const U = LexeditorUI, main = document.querySelector('main');
      main.style.width = '1200px';
      const field = label => U.detailField({label, help: U.infoHelp('Help for ' + label),
        control: U.el('input', {type: 'number', value: 0, min: 0, max: 100})});
      main.append(U.detailPanel({title: 'Standard Arrow', body: Object.entries(names).map(
        ([title, labels]) => U.detailSection({title, body: labels.map(field)}))}));
    }""", NAMES)
    page.wait_for_timeout(800)
    before = page.evaluate(SIZES)
    assert len({row["size"] for row in before}) == 1, before
    page.screenshot(path=str(tmp_path / "labels-before-rename.png"))

    for long, short in [("Strike Guard Cut Rate", "Strike"),
                        ("Slash Guard Cut Rate", "Slash"),
                        ("Thrust Guard Cut Rate", "Thrust")]:
        page.locator(".lex-detail-field-label-text", has_text=long).first.dblclick()
        editor = page.locator(".lex-detail-field-label .lex-label-rename").first
        editor.wait_for(timeout=3000)
        editor.fill(short)
        editor.press("Enter")
        page.wait_for_timeout(400)

    after = page.evaluate(SIZES)
    by_name = {row["name"]: row for row in after}
    neighbours = {by_name[name]["size"] for name in
                  ("Physical Guard Cut Rate", "Magic Guard Cut Rate",
                   "Fire Guard Cut Rate", "Lightning Guard Cut Rate")}
    for short in ("Strike", "Slash", "Thrust"):
        assert by_name[short]["size"] in neighbours, after
        assert by_name[short]["inline"] is None, by_name[short]
    assert len({row["size"] for row in after}) == 1, after
    assert len(neighbours) == 1, after
    lines = {row["name"]: row["lines"] for row in page.evaluate(LINES)}
    assert max(lines.values()) <= 2, lines
    page.screenshot(path=str(tmp_path / "labels-after-rename.png"))
