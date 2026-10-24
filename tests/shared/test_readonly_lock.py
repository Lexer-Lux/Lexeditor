"""Read-only locks sit inside the value box: inputs, textareas, selects,
checkboxes and keyed faces (which carry no input to sniff).
"""
from test_shared_ui_feedback import page, framework  # noqa: F401


MOUNT = """() => {
  const U = LexeditorUI;
  const host = U.el("div", {id: "lock-host", style: "width:520px;"});
  document.querySelector("main").replaceChildren(host);
  const face = U.el("span", {class: "face-box", "data-field-key": "face"});
  face.textContent = "Linked record";
  face.style.cssText = "display:block;border:1px solid #888;border-radius:3px;padding:2px 6px;";
  const section = U.detailSection({title: "Locks", body: [
    U.detailField({label: "Text", property: "text",
      control: U.el("input", {type: "text", value: "locked", disabled: true})}),
    U.detailField({label: "Area", property: "area",
      control: U.el("textarea", {disabled: true}, "locked lines")}),
    U.detailField({label: "Pick", property: "pick",
      control: (() => { const s = U.el("select", {disabled: true});
        s.append(U.el("option", {value: "a"}, "A")); return s; })()}),
    U.detailField({label: "Face", property: "face", control: face, readOnly: true}),
  ]});
  host.append(section);
  return host.querySelectorAll(".lex-detail-field").length;
}"""

GEOMETRY = """() => [...document.querySelectorAll(".lex-detail-field")].map(field => {
  const lock = field.querySelector(".lex-field-readonly-lock");
  if (!lock) return "NOLOCK";
  const box = lock.getBoundingClientRect();
  const host = lock.parentElement;
  const hbox = host.getBoundingClientRect();
  const inside = box.left >= hbox.left - 1 && box.right <= hbox.right + 1 &&
    box.top >= hbox.top - 1 && box.bottom <= hbox.bottom + 1;
  return `${Math.round(box.width)}x${Math.round(box.height)}@${host.className.split(" ")[0]}:${inside ? "in" : "OUT"}`;
})"""


def test_readonly_locks_sit_inside_their_boxes(page):
    framework(page)
    assert page.evaluate(MOUNT) == 4
    assert page.evaluate(GEOMETRY) == [
        "11x11@lex-detail-field-control:in",
        "11x11@lex-detail-field-control:in",
        "11x11@lex-detail-field-control:in",
        "11x11@face-box:in",
    ]
