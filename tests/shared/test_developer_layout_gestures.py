"""Developer Mode layout gestures: hiding a property, adding a section, and
the list of gestures behind a right-click on the shortcuts button.

Lexer: "in dev mode i should be able to hold right click on a property to hide
it for everyone who does not have 'show hidden properties' on", "right-click
hold a property header to create a new header to organize things by", and
"Right-clicking the hotkeys button ... should give me a list of all these
things I can do in dev mode".
"""
from test_shared_ui_feedback import framework, page
from test_vanilla_metadata_edit import mount_vanilla_shell

PANEL = """() => {
  const U = LexeditorUI;
  const field = (label, value) => U.detailField({label, property: label.toLowerCase(),
    control: U.el('input', {type: 'number', value})});
  document.querySelector('main').replaceChildren(U.detailPanel({title: 'Record', body: [
    U.detailSection({title: 'Combat', body: [field('Power', 7), field('Speed', 3)]}),
    U.detailSection({title: 'Drops', body: [field('Gold', 50)]})]}));
}"""


def hold_right(page, locator):
    box = locator.bounding_box()
    page.mouse.move(box["x"] + 12, box["y"] + box["height"] / 2)
    page.mouse.down(button="right")
    page.wait_for_timeout(850)
    page.mouse.up(button="right")
    page.wait_for_timeout(200)


def mount(page):
    framework(page)
    mount_vanilla_shell(page)
    page.evaluate(PANEL)
    page.wait_for_timeout(300)


def layout_saves(page):
    return [args[2] for args in page.evaluate("window.savedCalls")
            if any(".property-layout." in key for key in args[2])]


def test_holding_right_on_a_property_hides_it_and_shows_it_again(page):
    mount(page)
    speed = page.locator(".lex-detail-field", has_text="Speed")
    hold_right(page, speed)
    assert "lex-property-hidden" in speed.get_attribute("class")
    assert speed.is_hidden()
    assert page.get_by_role("button", name="Create a mod", exact=True).count() == 0
    assert layout_saves(page), "the hidden property is shared through the default view"
    # A reader who asked to see hidden properties still sees it, dimmed.
    page.evaluate("document.documentElement.dataset.lexShowHidden = 'true'")
    assert speed.is_visible()
    hold_right(page, speed)
    assert "lex-property-hidden" not in speed.get_attribute("class")


def test_holding_right_on_a_heading_adds_a_section_and_removes_an_empty_one(page):
    mount(page)
    hold_right(page, page.locator(".lex-detail-section-title", has_text="Combat"))
    added = page.locator("[data-lex-custom-section]")
    assert added.count() == 1
    assert added.locator(".lex-detail-section-title-text").text_content() == "New section"
    order = page.locator(".lex-detail-section-title-text").all_text_contents()
    assert order.index("New section") == order.index("Combat") + 1, order
    # Holding again on the empty added section takes it away.
    hold_right(page, added.locator(".lex-detail-section-title"))
    assert page.locator("[data-lex-custom-section]").count() == 0


def test_a_hidden_property_stays_hidden_when_the_page_gains_a_field(page):
    # Lexer: "I spent all this time hiding these properties and then they all
    # just unhid themselves." A layout was keyed by the page's exact field list.
    mount(page)
    hold_right(page, page.locator(".lex-detail-field", has_text="Speed"))
    page.evaluate("""() => {
      const U = LexeditorUI;
      const field = (label, value) => U.detailField({label, property: label.toLowerCase(),
        control: U.el('input', {type: 'number', value})});
      document.querySelector('main').replaceChildren(U.detailPanel({title: 'Record', body: [
        U.detailSection({title: 'Combat', body: [field('Power', 7), field('Speed', 3), field('Reach', 2)]}),
        U.detailSection({title: 'Drops', body: [field('Gold', 50)]})]}));
    }""")
    page.wait_for_timeout(300)
    assert "lex-property-hidden" in page.locator(".lex-detail-field", has_text="Speed").get_attribute("class")
    assert "lex-property-hidden" not in page.locator(".lex-detail-field", has_text="Reach").get_attribute("class")


def test_a_pages_own_section_is_removed_once_its_properties_are_moved_out(page):
    # Lexer: "I tried deleting a details panel header but couldn't." Holding on
    # a shipped heading only ever added another section.
    mount(page)
    drops = page.locator(".lex-detail-section", has=page.locator(".lex-detail-section-title", has_text="Drops"))
    # Move Gold into Combat, as dragging it would.
    page.evaluate("""() => {
      const gold = [...document.querySelectorAll('.lex-detail-field')].find(n => n.textContent.includes('Gold'));
      const combat = [...document.querySelectorAll('.lex-detail-section')].find(n => n.textContent.includes('Combat'));
      combat.querySelector('.lex-detail-section-content').append(gold);
    }""")
    hold_right(page, drops.locator(".lex-detail-section-title"))
    assert drops.is_hidden()
    assert page.locator("[data-lex-custom-section]").count() == 0, "removing must not add a section"
    assert any("removed" in __import__("json").loads(value) and __import__("json").loads(value)["removed"]
               for save in layout_saves(page) for value in save.values())
    # Undo brings it back.
    page.locator("body").click(position={"x": 2, "y": 2})
    page.keyboard.press("Control+z")
    page.wait_for_timeout(300)
    assert drops.is_visible()


def test_a_heading_drags_its_section_and_the_order_is_kept(page):
    # Lexer: "I can't move or rearrange [headers] like properties."
    mount(page)
    titles = lambda: page.locator(".lex-detail-section-title-text").all_text_contents()
    assert titles() == ["Combat", "Drops"]
    page.locator(".lex-detail-section-title", has_text="Drops").drag_to(
        page.locator(".lex-detail-section-title", has_text="Combat"), target_position={"x": 10, "y": 2})
    page.wait_for_timeout(200)
    assert titles() == ["Drops", "Combat"]
    page.evaluate(PANEL)
    page.wait_for_timeout(300)
    assert titles() == ["Drops", "Combat"], "the order belongs to the saved layout"
    page.locator("body").click(position={"x": 2, "y": 2})
    page.keyboard.press("Control+z")
    page.wait_for_timeout(300)
    assert titles() == ["Combat", "Drops"]


def test_holding_on_a_section_that_still_holds_properties_adds_one_instead(page):
    mount(page)
    hold_right(page, page.locator(".lex-detail-section-title", has_text="Drops"))
    assert page.locator(".lex-detail-section-title", has_text="Drops").is_visible()
    assert page.locator("[data-lex-custom-section]").count() == 1


def test_right_clicking_the_shortcuts_button_lists_the_developer_gestures(page):
    mount(page)
    page.locator("#lexeditor-shortcuts, [aria-label='Keyboard shortcuts'], button[title*='shortcuts' i]").first.click(button="right")
    panel = page.get_by_role("dialog", name="Developer Mode gestures")
    panel.wait_for()
    for gesture in ("Rename the property", "Edit the help bubble's text", "Move the property",
                    "Hide it for readers", "Add a new section below it"):
        assert panel.get_by_text(gesture).count() >= 1, gesture
