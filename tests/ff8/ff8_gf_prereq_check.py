"""A GF ability's prerequisite selector is wide enough for its own text.

Lexer: "gfs -> right panel -> abilities -> prereq: doesn't follow the rule of
cell contents taking up all available space ... the dropdown on the right has
its text cut off."

The prerequisite cell holds two controls: the kind selector, which only ever
says "Level" or "Ability", and the ability-slot selector, whose options are
names as long as "#02 GFHP+20%". Both used to take half the cell, so the slot
selector was narrower than its own longest option and the browser cut the text
off. This builds that cell with the plugin's own column template and its own
stylesheet, and measures the selector against the text it must show.
"""
from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
SHOTS = Path(tempfile.gettempdir()) / "lexeditor-dev"
SLOTS = ["#01 GFHP+10%", "#02 GFHP+20%", "#03 GFHP+30%", "#08 MedData",
         "#10 Spr+20%", "#11 Spr+40%", "#04 SumMag+10%", "#05 SumMag+20%"]


def column_template() -> str:
    source = (ROOT / "plugins" / "ff8" / "party.js").read_text(encoding="utf-8")
    start = source.find("function gfAbilities(")
    assert start >= 0, "the GF ability table was not found in party.js"
    end = source.find('table.dataset.gfAbilities="true"', start)
    assert end > start, "the GF ability table builder was not found"
    template = re.search(r'template:"([^"]+)"', source[start:end])
    assert template, "the GF ability column template was not found"
    return template.group(1)


def main():
    template = column_template()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        page.route("http://fixture/", lambda route: route.fulfill(
            content_type="text/html",
            body='<body data-lex-plugin="ff8"><main></main></body>'))
        page.goto("http://fixture/")
        page.add_style_tag(content=(ROOT / "ui" / "framework.css").read_text(encoding="utf-8"))
        page.add_style_tag(content=(ROOT / "plugins" / "ff8" / "editor.css").read_text(encoding="utf-8"))
        page.add_script_tag(content=(ROOT / "ui" / "framework.js").read_text(encoding="utf-8"))
        page.evaluate("""([template, slots]) => {
          const U = LexeditorUI;
          const rows = [0, 1, 2].map(index => ({key: "ability" + index, slot: index}));
          const cell = () => {
            const kind = U.el("select", {class: "gf-prereq-kind", "aria-label": "Prerequisite kind"},
              U.el("option", {value: "level"}, "Level"), U.el("option", {value: "slot"}, "Ability"));
            kind.value = "slot";
            const slot = U.el("select", {class: "gf-prereq-slot", "aria-label": "Required ability"},
              ...slots.map(name => U.el("option", {}, name)));
            return U.controlGroup([kind, slot], {className: "gf-prereq-cell"});
          };
          const table = U.columnList({
            rows, key: row => row.key, fill: true, template,
            columns: [
              {key: "slot", label: "Slot", render: row => row.slot},
              {key: "ability", label: "Ability", render: () => U.readonlyField("GFHP+10%")},
              {key: "level", label: "Prereq", render: cell},
              {key: "alternate", label: "Alt. Prereq", render: () => U.readonlyField(255)},
            ]});
          const main = document.querySelector("main");
          main.style.width = "650px";
          main.style.height = "500px";
          main.append(table);
        }""", [template, SLOTS])
        page.wait_for_timeout(300)
        result = page.evaluate("""slots => {
          const selects = [...document.querySelectorAll(".gf-prereq-slot")];
          const measure = document.createElement("canvas").getContext("2d");
          const rows = selects.map(select => {
            const style = getComputedStyle(select);
            measure.font = `${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
            const needed = Math.max(...slots.map(text => measure.measureText(text).width));
            const cell = select.closest(".lex-column-list-cell");
            const group = select.parentElement;
            return {
              client: select.clientWidth,
              needed: Math.round(needed * 10) / 10,
              cell: Math.round(cell.getBoundingClientRect().width),
              content: Math.round(group.parentElement.getBoundingClientRect().width),
              group: Math.round(group.getBoundingClientRect().width),
              columns: getComputedStyle(group).gridTemplateColumns,
            };
          });
          return rows;
        }""", SLOTS)
        assert len(result) == 3, result
        for row in result:
            # One pixel of slack for the select's own arrow and padding.
            assert row["client"] >= row["needed"] - 1, (row, template)
            # The two controls fill the room the cell gives its contents.
            assert abs(row["group"] - row["content"]) <= 3, (row, template)
            assert row["columns"].split()[0] != "0px", (row, template)
        shot = SHOTS / "ff8-gf-prereq.png"
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(shot))
        browser.close()
    print(f"GF prerequisite selector: the slot selector is {result[0]['client']}px wide for "
          f"{result[0]['needed']}px of text in a {result[0]['cell']}px cell, three rows measured. "
          f"Screenshot {shot}.")


if __name__ == "__main__":
    sys.exit(main())
