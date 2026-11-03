"""The shared sound preview: a player when playable, an honest note when not.

FF8's SFX layout is the standard: a playable sound renders an audio
element the detail panel adopts into its heading player with a scrubber,
and a sound with no playable file says so in its preview row.
"""
from test_shared_ui_feedback import framework, page  # noqa: F401


def test_a_playable_sound_renders_an_adoptable_player(page):
    framework(page)
    page.evaluate("""() => {
      document.querySelector('main').replaceChildren(
        LexeditorUI.soundPreview({src: '/sounds/hit.wav', label: 'Play Hit'}));
    }""")
    player = page.locator(".lex-detail-field audio")
    assert player.count() == 1
    assert player.get_attribute("src") == "/sounds/hit.wav"
    assert player.get_attribute("aria-label") == "Play Hit"
    assert player.evaluate("node => node.hasAttribute('controls')")


def test_a_detail_panel_adopts_the_player_into_its_heading(page):
    framework(page)
    page.evaluate("""() => {
      const U = LexeditorUI;
      document.querySelector('main').replaceChildren(U.detailPanel({title: 'Hit',
        body: [U.detailSection({title: 'PREVIEW',
          body: [U.soundPreview({src: '/sounds/hit.wav', label: 'Play Hit'})]})]}));
    }""")
    assert page.locator(".lex-audio-play").count() == 1
    assert page.locator(".lex-audio-scrub").count() == 1
    assert page.locator(".lex-detail-panel-body audio").count() == 0


def test_an_unplayable_sound_says_so_in_its_preview_row(page):
    framework(page)
    page.evaluate("""() => {
      const U = LexeditorUI;
      document.querySelector('main').replaceChildren(U.detailPanel({title: 'Bank',
        body: [U.detailSection({title: 'PREVIEW',
          body: [U.soundPreview({note: 'No preview',
            help: U.infoHelp('Sounds play in the game. They have no picture to show.')})]})]}));
    }""")
    assert page.locator(".lex-audio-play").count() == 0
    assert page.locator(".lex-detail-field input").input_value() == "No preview"
    assert page.locator(".lex-info-help").count() == 1
