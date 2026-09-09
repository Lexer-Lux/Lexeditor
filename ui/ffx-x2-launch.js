"use strict";

(() => {
  const rail = document.querySelector('.ffxx2-rail');
  if (!rail || document.getElementById('ffxx2-play-controls')) return;

  const panel = document.createElement('section');
  panel.id = 'ffxx2-play-controls';
  panel.style.cssText = 'padding:10px;border-top:1px solid #7770a455;background:#0d0f1fd9';
  panel.innerHTML = `
    <div style="display:grid;gap:7px">
      <div><strong style="display:block;font-size:12px">Play through Fahrenheit</strong><span id="ffxx2-play-status" class="ffxx2-summary" style="display:block;margin:2px 0 0">Checking Stage 0…</span></div>
      <div class="ffxx2-toolbar" style="margin:0;align-items:stretch">
        <button id="ffxx2-play-x" class="ffxx2-button primary" type="button" disabled>Play FFX</button>
        <button id="ffxx2-play-x2" class="ffxx2-button primary" type="button" disabled>Play FFX-2</button>
      </div>
    </div>`;
  rail.appendChild(panel);

  const labels = {x: 'FFX', x2: 'FFX-2'};
  let launchState = null;

  function render(state) {
    launchState = state;
    const x = state?.games?.x || {};
    const x2 = state?.games?.x2 || {};
    $('ffxx2-play-x').disabled = !x.launchReady;
    $('ffxx2-play-x2').disabled = !x2.launchReady;
    $('ffxx2-play-x').title = x.reason || '';
    $('ffxx2-play-x2').title = x2.reason || '';

    let text;
    if (!state?.platformSupported) text = 'Windows host required for Stage 0 launch.';
    else if (!state?.stage0Ready) text = 'fhstage0.exe is missing.';
    else if (!state?.stage1Ready) text = 'fhstage1.dll is missing.';
    else if (!x.ready && !x2.ready) text = 'FFX.exe and FFX-2.exe are missing.';
    else if (!x.ready) text = 'FFX-2 ready · FFX.exe missing.';
    else if (!x2.ready) text = 'FFX ready · FFX-2.exe missing.';
    else text = 'FFX and FFX-2 ready · fixed Stage 0 targets.';
    $('ffxx2-play-status').textContent = text;
  }

  async function refresh() {
    render(await api('/api/launch'));
  }

  async function play(game) {
    showError();
    const state = launchState?.games?.[game];
    if (!state?.launchReady) return;
    const button = $(`ffxx2-play-${game}`);
    button.disabled = true;
    try {
      await api('/api/play', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({game}),
      });
      playUiSfx();
      $('ffxx2-play-status').textContent = `${labels[game]} launched through Fahrenheit Stage 0.`;
    } finally {
      button.disabled = !launchState?.games?.[game]?.launchReady;
    }
  }

  $('ffxx2-play-x').addEventListener('click', () => play('x').catch(showError));
  $('ffxx2-play-x2').addEventListener('click', () => play('x2').catch(showError));
  refresh().catch(showError);
})();
