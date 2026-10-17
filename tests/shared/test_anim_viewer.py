"""The shared animation viewer: transport, shortcuts and the shortcuts menu.

Every animations view mounts LexeditorUI.animationViewer: the scrub bar with
its event cues, one row of square transport buttons below it, and the
arrow/space bindings. The shortcuts panel lists those bindings only while a
viewer is mounted.
"""
from test_shared_ui_feedback import framework, page  # noqa: F401
from test_vanilla_metadata_edit import mount_vanilla_shell
from test_tab_rename import mount_shell

MOUNT = """() => {
  const U = LexeditorUI;
  const host = U.el("div", {id: "anim-host", style: "width:640px;height:360px;"});
  const timeline = U.el("div", {id: "anim-timeline"});
  const status = U.el("div", {id: "anim-status"});
  document.querySelector("main").replaceChildren(host, timeline, status);
  const canvas = U.el("canvas", {width: "320", height: "180"});
  host.append(canvas);
  const paint = canvas.getContext("2d");
  window.viewerErrors = [];
  window.viewer = U.animationViewer({host, timeline, status,
    statusText: "Sample: 48 frames.",
    frames: {count: 48, duration: 2, events: [{start: 0.5, label: "Cue one"}]},
    render: shown => {
      try {
        paint.fillStyle = "#111";
        paint.fillRect(0, 0, 320, 180);
        paint.fillStyle = "#fff";
        paint.fillRect((shown / 47) * 300, 80, 20, 20);
      } catch (error) { window.viewerErrors.push(String(error)); }
    }});
}"""

LABELS = ["Go to animation start", "Back one frame", "Play or pause",
          "Forward one frame", "Go to animation end"]


def mount(page):
    framework(page)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.evaluate(MOUNT)
    page.wait_for_selector("#anim-host[data-ready='true']")
    assert page.evaluate("window.viewerErrors") == []
    return errors


def transport(page):
    buttons = page.locator("[data-anim-transport] button")
    assert buttons.count() == 5
    return buttons


def readout(page):
    return page.locator("[data-anim-readout]").text_content()


def test_transport_row_sits_below_the_scrub_bar_with_five_square_buttons_in_order(page):
    mount(page)
    buttons = transport(page)
    assert [buttons.nth(index).get_attribute("aria-label") for index in range(5)] == LABELS
    for index in range(5):
        box = buttons.nth(index).bounding_box()
        assert abs(box["width"] - box["height"]) < 1, (index, box)
    scrub = page.locator(".lex-anim-scrub").bounding_box()
    bar = page.locator("[data-anim-transport]").bounding_box()
    assert bar["y"] >= scrub["y"] + scrub["height"] - 1, (scrub, bar)
    assert bar["y"] - (scrub["y"] + scrub["height"]) < 20, (scrub, bar)


def test_transport_buttons_drive_playback(page):
    errors = mount(page)
    buttons = transport(page)
    by_label = {label: buttons.nth(index) for index, label in enumerate(LABELS)}
    by_label["Play or pause"].click()
    assert page.evaluate("window.viewer.playing") is False
    by_label["Go to animation end"].click()
    assert readout(page).startswith("47.0"), readout(page)
    by_label["Go to animation start"].click()
    assert readout(page).startswith("0.0"), readout(page)
    by_label["Forward one frame"].click()
    assert readout(page).startswith("1.0"), readout(page)
    by_label["Back one frame"].click()
    assert readout(page).startswith("0.0"), readout(page)
    assert page.evaluate("window.viewer.playing") is False
    by_label["Play or pause"].click()
    assert page.evaluate("window.viewer.playing") is True
    assert page.evaluate("window.viewerErrors") == []
    assert errors == []


def test_markers_jump_to_their_event_time(page):
    mount(page)
    page.locator("[data-anim-transport] button[aria-label='Play or pause']").click()
    marker = page.locator(".lex-anim-marker")
    assert marker.count() == 1
    assert marker.get_attribute("aria-label") == "Cue one (0.50s)"
    marker.click()
    page.wait_for_timeout(200)
    assert readout(page).endswith("0.50s"), readout(page)


def test_arrow_space_and_shift_shortcuts_drive_the_viewer(page):
    framework(page)
    mount_vanilla_shell(page)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.evaluate(MOUNT)
    page.wait_for_selector("#anim-host[data-ready='true']")
    page.evaluate("document.activeElement?.blur()")
    page.keyboard.press("Space")
    assert page.evaluate("window.viewer.playing") is False
    before = page.evaluate("window.viewer.frame")
    page.keyboard.press("ArrowRight")
    assert page.evaluate("window.viewer.frame") == before + 1
    page.keyboard.press("ArrowLeft")
    assert page.evaluate("window.viewer.frame") == before
    page.keyboard.press("Shift+ArrowRight")
    assert page.evaluate("window.viewer.frame") == 47
    assert readout(page).startswith("47.0"), readout(page)
    page.keyboard.press("Shift+ArrowLeft")
    assert page.evaluate("window.viewer.frame") == 0
    page.keyboard.press("Space")
    assert page.evaluate("window.viewer.playing") is True
    # On the scrub slider itself the arrows still step whole frames.
    page.keyboard.press("Space")
    page.keyboard.press("Shift+ArrowLeft")
    page.locator("#anim-timeline input[type='range']").focus()
    page.keyboard.press("ArrowRight")
    assert page.evaluate("window.viewer.frame") == 1
    assert errors == []


def test_shortcuts_menu_lists_animation_keys_only_while_mounted(page):
    framework(page)
    mount_vanilla_shell(page)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    opener = page.locator("#lexeditor-shortcuts")
    opener.click()
    assert page.locator('[data-lex-shortcut="save"]').count() == 1
    assert page.locator('[data-lex-shortcut^="anim-"]').count() == 0
    page.keyboard.press("Escape")
    page.evaluate(MOUNT)
    page.wait_for_selector("#anim-host[data-ready='true']")
    page.evaluate("document.activeElement?.blur()")
    page.keyboard.press("Space")
    assert page.evaluate("window.viewer.playing") is False
    opener.click()
    found = page.locator("[data-lex-shortcut^='anim-']").evaluate_all(
        "rows => rows.map(row => row.dataset.lexShortcut)")
    assert found == ["anim-start", "anim-prev", "anim-play", "anim-next", "anim-end"], found
    # With the panel open the keys are a legend, not live controls.
    frame = page.evaluate("window.viewer.frame")
    page.keyboard.press("ArrowRight")
    page.wait_for_timeout(200)
    assert page.evaluate("window.viewer.frame") == frame
    assert page.locator(".lex-shortcut-panel").count() == 1
    page.keyboard.press("Escape")
    page.evaluate("window.viewer.stop()")
    opener.click()
    assert page.locator('[data-lex-shortcut^="anim-"]').count() == 0
    assert page.locator('[data-lex-shortcut="save"]').count() == 1
    assert errors == []


def test_animation_keys_rest_while_typing_and_outside_a_view(page):
    framework(page)
    mount_shell(page)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.evaluate(MOUNT)
    page.wait_for_selector("#anim-host[data-ready='true']")
    page.evaluate("document.activeElement?.blur()")
    page.keyboard.press("Space")
    frame = page.evaluate("window.viewer.frame")
    page.evaluate("""() => {
      const field = LexeditorUI.el("input", {type: "text", id: "typing", value: "ab"});
      document.querySelector("main").append(field);
      field.focus();
      field.setSelectionRange(1, 1);
    }""")
    for key in ["ArrowLeft", "ArrowRight", "Space", "Shift+ArrowRight"]:
        page.keyboard.press(key)
    assert page.evaluate("window.viewer.frame") == frame
    assert page.evaluate("window.viewer.playing") is False
    assert page.evaluate("document.querySelector('#typing').value") == "a b"
    page.evaluate("window.viewer.stop()")
    for key in ["ArrowLeft", "ArrowRight", "Space"]:
        page.keyboard.press(key)
    page.wait_for_timeout(200)
    assert errors == []
