"""A flag group's own pin stays out of its last box.

Lexer, FF8 Weapons > Renzokuken finishers: "mousing over this property
highlights the pin in the very last bool box for some reason, even when you're
not mousing over any specific bool box?"

Each flag box carries its own pin, and the field carries one for the whole
value. The field's pin was placed at the control's top-right corner, which in a
grid of boxes is inside the last box, and it lit up whenever any part of the
field was pointed at. The field's pin now sits by the label and stays hidden
while a single box is pointed at.
"""
from pathlib import Path

CSS = (Path(__file__).resolve().parents[2] / "ui" / "framework.css").read_text(encoding="utf-8")


def test_field_pin_leaves_the_last_box():
    assert ".lex-source-control:has(> .lex-detail-parts-switches) > .lex-column-pin { top:-6px; right:auto; left:-22px; }" in CSS


def test_field_pin_hides_while_a_box_is_pointed_at():
    assert (".lex-detail-field:has(.lex-detail-parts-switches .lex-toggle:hover) > .lex-detail-field-control"
            " > .lex-source-control > .lex-column-pin:not(.pinned) { opacity:0; }") in CSS
