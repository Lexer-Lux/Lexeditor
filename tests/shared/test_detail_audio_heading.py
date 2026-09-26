"""A sound's detail panel plays from its heading and scrubs along its edge.

Lexer: "in cases where a detail panel represents an audio file, like in
Warband's Sounds or FF8's SFX, the preview thumbnail bit of the header should
be a play/pause button and the borderline between the header and the rest of
the details panel should be a line showing the progress and length of the
playing through it that the user can also use to scrub through."
"""
from test_shared_ui_feedback import page, framework


def test_body_player_moves_into_the_heading(page):
    framework(page)
    page.evaluate('''() => {
      const U = LexeditorUI, rate = 8000, samples = rate;
      const bytes = new DataView(new ArrayBuffer(44 + samples * 2));
      const text = (at, value) => [...value].forEach((c, i) => bytes.setUint8(at + i, c.charCodeAt(0)));
      text(0, 'RIFF'); bytes.setUint32(4, 36 + samples * 2, true); text(8, 'WAVEfmt ');
      bytes.setUint32(16, 16, true); bytes.setUint16(20, 1, true); bytes.setUint16(22, 1, true);
      bytes.setUint32(24, rate, true); bytes.setUint32(28, rate * 2, true); bytes.setUint16(32, 2, true);
      bytes.setUint16(34, 16, true); text(36, 'data'); bytes.setUint32(40, samples * 2, true);
      const src = URL.createObjectURL(new Blob([bytes], {type: 'audio/wav'}));
      document.querySelector('main').append(U.detailPanel({title: 'Sound 1', body: [
        U.detailSection({title: 'PREVIEW', body: [U.detailField({label: '',
          control: U.el('audio', {src, controls: true, 'aria-label': 'Play Sound 1'})})]}),
        U.detailSection({title: 'SOUND', body: [U.detailField({label: 'LENGTH',
          control: U.readonlyField('1.0 s')})]})]}));
    }''')
    panel = page.locator('.lex-detail-panel')
    assert panel.locator('.lex-detail-panel-body audio').count() == 0
    assert panel.locator('.lex-detail-section-title', has_text='PREVIEW').count() == 0
    play = panel.locator('.lex-detail-panel-icon > .lex-audio-play')
    scrub = panel.locator('.lex-detail-panel-heading > .lex-audio-scrub')
    assert play.count() == 1 and scrub.count() == 1
    page.wait_for_function("Number(document.querySelector('.lex-audio-scrub').max) > .9")
    geometry = page.evaluate('''() => {
      const heading = document.querySelector('.lex-detail-panel-heading').getBoundingClientRect();
      const line = document.querySelector('.lex-audio-scrub').getBoundingClientRect();
      return {widthMatch: Math.abs(line.width - heading.width) < 2,
        onEdge: Math.abs((line.top + line.bottom) / 2 - heading.bottom) < 2};
    }''')
    assert geometry == {'widthMatch': True, 'onEdge': True}, geometry
    assert play.get_attribute('aria-label') == 'Play Sound 1'
    play.click()
    page.wait_for_function("document.querySelector('.lex-audio-play').getAttribute('aria-label') === 'Pause Sound 1'")
    play.click()
    page.wait_for_function("document.querySelector('.lex-audio-play').getAttribute('aria-label') === 'Play Sound 1'")
    scrub.evaluate("s => { s.value = '0.5'; s.dispatchEvent(new Event('input', {bubbles: true})); }")
    assert '0:00 of 0:01' == scrub.get_attribute('aria-valuetext')
    assert float(scrub.evaluate("s => s.style.getPropertyValue('--lex-audio-progress')").rstrip('%')) > 40
