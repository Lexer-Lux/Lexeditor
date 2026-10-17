"""Universal model viewer modes: Regular, Fullbright, Wireframe.

Every modelStage mounts the corner buttons; modelViewModes puts the same
buttons on any other 3D host. Clicking retints the bound scene - Fullbright
glows each material in its own colors, Wireframe shows edges only - and
Regular restores exactly what was there before.
"""
from test_shared_ui_feedback import page, framework  # noqa: F401


LABELS = ["Regular", "Fullbright", "Wireframe"]


def mount(page, options=""):
    framework(page)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.evaluate(f"""() => {{
      const stage = LexeditorUI.modelStage({{message: "Model fixture", {options}}});
      stage.id = "stage";
      document.querySelector("main").replaceChildren(stage);
    }}""")
    page.wait_for_selector("#stage")
    return errors


def fake_scene(page):
    page.evaluate("""() => {
      const color = hex => ({hex,
        getHex() { return this.hex; }, setHex(value) { this.hex = value; }});
      window.fakeMats = [0, 1].map(index => ({wireframe: false,
        emissive: color(0x111111 * (index + 1)), emissiveMap: null,
        emissiveIntensity: 1, map: null, color: color(0x9aa3ad),
        needsUpdate: false}));
      // One textured face: Fullbright must light it through its own map.
      window.fakeMats[1].map = {isTexture: true};
      const scene = {traverse(fn) {
        window.fakeMats.forEach(mat => fn({material: mat})); }};
      document.querySelector("#stage").lexBindScene(scene);
    }""")
    return page.evaluate("""() => window.fakeMats.map(mat => ({
      wireframe: mat.wireframe, emissive: mat.emissive.getHex(),
      emissiveMap: mat.emissiveMap === mat.map ? "map"
        : mat.emissiveMap === null ? null : "other",
      emissiveIntensity: mat.emissiveIntensity}))""")


def test_stage_mounts_three_corner_buttons_with_regular_pressed(page):
    errors = mount(page)
    bar = page.locator("#stage .lex-model-view-modes")
    assert bar.count() == 1
    buttons = bar.locator("button")
    assert buttons.count() == 3
    assert [buttons.nth(index).get_attribute("aria-label") for index in range(3)] == LABELS
    for index in range(3):
        assert buttons.nth(index).locator("svg").count() == 1, LABELS[index]
    assert buttons.nth(0).get_attribute("aria-pressed") == "true"
    assert buttons.nth(0).evaluate("node => node.classList.contains('active')")
    stage, first = (page.locator("#stage").bounding_box(),
                    buttons.nth(0).bounding_box())
    assert first["x"] - stage["x"] < 16, (stage, first)
    assert stage["y"] + stage["height"] - (first["y"] + first["height"]) < 16, (stage, first)
    assert page.evaluate("document.querySelector('#stage').lexViewModes.mode()") == "regular"
    assert errors == []


def test_clicks_move_pressed_state_without_a_scene(page):
    mount(page)
    buttons = page.locator("#stage .lex-model-view-modes button")
    buttons.nth(1).click()
    assert page.evaluate("document.querySelector('#stage').lexViewModes.mode()") == "fullbright"
    assert buttons.nth(1).evaluate("node => node.classList.contains('active')")
    assert buttons.nth(1).get_attribute("aria-pressed") == "true"
    assert buttons.nth(0).get_attribute("aria-pressed") == "false"
    buttons.nth(2).click()
    assert page.evaluate("document.querySelector('#stage').lexViewModes.mode()") == "wireframe"


def test_modes_retint_a_bound_scene_and_regular_restores(page):
    mount(page)
    before = fake_scene(page)
    assert [mat["emissive"] for mat in before] == [0x111111, 0x222222]
    page.locator("#stage .lex-model-view-modes button").nth(1).click()
    lit = page.evaluate("""() => window.fakeMats.map(mat => ({
      emissive: mat.emissive.getHex(),
      emissiveMap: mat.emissiveMap === null ? null
        : mat.emissiveMap === mat.map ? "map" : "other"}))""")
    assert lit[0] == {"emissive": 0x9AA3AD, "emissiveMap": None}, lit
    assert lit[1] == {"emissive": 0xFFFFFF, "emissiveMap": "map"}, lit
    page.locator("#stage .lex-model-view-modes button").nth(2).click()
    wired = page.evaluate("""() => window.fakeMats.map(mat => ({
      wireframe: mat.wireframe, emissive: mat.emissive.getHex(),
      emissiveMap: mat.emissiveMap}))""")
    assert [mat["wireframe"] for mat in wired] == [True, True], wired
    assert [mat["emissive"] for mat in wired] == [0x111111, 0x222222], wired
    page.locator("#stage .lex-model-view-modes button").nth(0).click()
    after = page.evaluate("""() => window.fakeMats.map(mat => ({
      wireframe: mat.wireframe, emissive: mat.emissive.getHex(),
      emissiveMap: mat.emissiveMap, emissiveIntensity: mat.emissiveIntensity}))""")
    assert [mat["wireframe"] for mat in after] == [False, False], after
    assert [mat["emissive"] for mat in after] == [0x111111, 0x222222], after
    assert [mat["emissiveMap"] for mat in after] == [None, None], after
    assert [mat["emissiveIntensity"] for mat in after] == [1, 1], after


def test_attach_to_a_plain_host_is_idempotent(page):
    framework(page)
    page.evaluate("""() => {
      const host = LexeditorUI.el("div",
        {id: "plain", style: "position:relative;min-height:120px;"});
      document.querySelector("main").replaceChildren(host);
      LexeditorUI.modelViewModes(host);
      LexeditorUI.modelViewModes(host);
    }""")
    assert page.locator("#plain .lex-model-view-modes").count() == 1
    assert page.locator("#plain .lex-model-view-modes button").count() == 3


def test_modes_false_leaves_the_stage_bare_and_unknown_modes_rest(page):
    errors = mount(page, "modes: false")
    assert page.locator("#stage .lex-model-view-modes").count() == 0
    page.evaluate("""() => {
      const stage = LexeditorUI.modelStage({message: "Second"});
      stage.id = "second";
      document.querySelector("main").append(stage);
    }""")
    assert page.evaluate("""() => {
      const stage = document.querySelector("#second");
      stage.lexSetViewMode("nope");
      return stage.lexViewModes.mode();
    }""") == "regular"
    assert errors == []
