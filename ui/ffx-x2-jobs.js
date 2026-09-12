"use strict";

(() => {
  const nav = document.querySelector('.ffxx2-nav');
  const workspace = document.querySelector('.ffxx2-workspace');
  const archivesPanel = document.querySelector('[data-panel="archives"]');
  if (!nav || !workspace || !archivesPanel || document.querySelector('[data-panel="ffx2-jobs"]')) return;

  const navButton = document.createElement('button');
  navButton.type = 'button';
  navButton.dataset.view = 'ffx2-jobs';
  navButton.textContent = 'X-2 Dresspheres';
  const accessoryButton = nav.querySelector('[data-view="ffx2-accessories"]');
  const archiveButton = nav.querySelector('[data-view="archives"]');
  nav.insertBefore(navButton, accessoryButton || archiveButton || null);

  const panel = document.createElement('main');
  panel.className = 'ffxx2-panel';
  panel.dataset.panel = 'ffx2-jobs';
  panel.hidden = true;
  panel.innerHTML = `
    <div class="ffxx2-panel-head">
      <div class="ffxx2-panel-title">
        <h2>FFX-2 Dressphere Ability Trees</h2>
        <p><span class="ffxx2-path">new_uspc/battle/kernel/job.bin</span> · 16 required-ability / learned-ability pairs only; growth, weapon, creature, flag, and string data stay opaque.</p>
      </div>
      <button id="x2-job-save" class="ffxx2-button save" type="button" disabled>Save edits</button>
    </div>
    <div class="ffxx2-panel-body">
      <div class="ffxx2-toolbar">
        <label>Dressphere<select id="x2-job-select"></select></label>
        <button id="x2-job-refresh" class="ffxx2-button" type="button">Refresh source</button>
      </div>
      <p id="x2-job-summary" class="ffxx2-summary"></p>
      <div id="x2-job-fields" class="ffxx2-slot-grid"></div>
    </div>`;
  const accessoryPanel = workspace.querySelector('[data-panel="ffx2-accessories"]');
  workspace.insertBefore(panel, accessoryPanel || archivesPanel);

  const x2Card = document.querySelector('[data-panel="dashboard"] .ffxx2-dashboard-card:nth-child(2)');
  if (x2Card) {
    const detail = x2Card.querySelector('p');
    const count = x2Card.querySelector('.big');
    if (detail) detail.textContent = 'Command animation IDs, accessory base abilities/prices, and dressphere ability trees are structured; unproved fields remain read-only.';
    if (count) count.textContent = '3 editors';
  }

  let state = null;
  const dirty = new Map();

  function selected() {
    if (!state) return null;
    const id = Number($('x2-job-select').value);
    return state.rows.find(row => row.id === id) || state.rows[0] || null;
  }

  function dirtySlots(id) {
    if (!dirty.has(id)) dirty.set(id, new Set());
    return dirty.get(id);
  }

  function dirtyCount() {
    let count = 0;
    for (const slots of dirty.values()) count += slots.size;
    return count;
  }

  function renderSelector(preferred) {
    if (!state) return;
    $('x2-job-select').innerHTML = state.rows.map(row =>
      `<option value="${row.id}">${row.id} · ${hex(row.id)} · icon ${row.icon}</option>`
    ).join('');
    if (preferred != null && state.rows.some(row => row.id === preferred)) {
      $('x2-job-select').value = String(preferred);
    }
  }

  function renderSummary(row) {
    const count = dirtyCount();
    $('x2-job-save').disabled = count === 0;
    $('x2-job-summary').textContent =
      `Dressphere ${row.id} (${hex(row.id)}) · icon ${row.icon} · default Berserk action ${hex(row.berserkAction)} · ` +
      `name ref ${hex(row.nameOffset)}/${hex(row.nameKey)} · help ref ${hex(row.helpOffset)}/${hex(row.helpKey)} · ` +
      `${state.source === 'project' ? 'staged X-2 project override' : 'installed FFX-2 VBF'}${count ? ` · ${count} unsaved ability slot(s)` : ''}`;
  }

  function render() {
    const row = selected();
    if (!row) {
      $('x2-job-fields').innerHTML = '<div class="ffxx2-empty">No dressphere records.</div>';
      $('x2-job-save').disabled = true;
      return;
    }
    const changed = dirty.get(row.id) || new Set();
    $('x2-job-fields').innerHTML = row.abilities.map((ability, slot) => `
      <div class="ffxx2-slot ${changed.has(slot) ? 'ffxx2-dirty' : ''}" data-x2-job-slot="${slot}">
        <span>Ability ${slot + 1}</span><span class="ffxx2-hex">+${hex(state.abilityOffset + slot * 4)}</span>
        <label>Required ability
          <input aria-label="Dressphere ${row.id} ability ${slot + 1} requirement" data-x2-job-field="requirementId" type="number" min="0" max="65535" value="${ability.requirementId}">
        </label>
        <label>Ability
          <input aria-label="Dressphere ${row.id} ability ${slot + 1}" data-x2-job-field="abilityId" type="number" min="0" max="65535" value="${ability.abilityId}">
        </label>
      </div>`).join('');
    renderSummary(row);
  }

  async function refresh() {
    showError();
    const previous = selected()?.id;
    state = await api('/api/ffx2-jobs');
    dirty.clear();
    renderSelector(previous);
    render();
  }

  function inputChanged(target) {
    const slotCard = target.closest('[data-x2-job-slot]');
    const row = selected();
    if (!slotCard || !row) return;
    const slot = Number(slotCard.dataset.x2JobSlot);
    const field = target.dataset.x2JobField;
    if (!['requirementId', 'abilityId'].includes(field)) return;
    row.abilities[slot][field] = Number(target.value);
    dirtySlots(row.id).add(slot);
    slotCard.classList.add('ffxx2-dirty');
    renderSummary(row);
  }

  async function save() {
    showError();
    if (!state || !dirtyCount()) return;
    const edits = [...dirty.entries()].sort((a, b) => a[0] - b[0]).map(([id, slots]) => {
      const row = state.rows.find(item => item.id === id);
      return {
        id,
        abilities: [...slots].sort((a, b) => a - b).map(slot => ({
          slot,
          requirementId: row.abilities[slot].requirementId,
          abilityId: row.abilities[slot].abilityId,
        })),
      };
    });
    const previous = selected()?.id;
    state = await api('/api/ffx2-jobs/save', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({headerMd5: state.headerMd5, baselineSha256: state.baselineSha256, edits}),
    });
    dirty.clear();
    renderSelector(previous);
    render();
    await Promise.all([refreshOverview(), refreshMap(), searchArchive()]);
  }

  $('x2-job-select').addEventListener('change', render);
  $('x2-job-refresh').addEventListener('click', () => refresh().catch(showError));
  $('x2-job-save').addEventListener('click', () => save().catch(showError));
  $('x2-job-fields').addEventListener('input', event => inputChanged(event.target));

  const originalExtractIndex = extractIndex;
  extractIndex = async function patchedExtractIndex(index) {
    const entry = catalog?.entries?.[index];
    await originalExtractIndex(index);
    if (entry?.eflPath === state?.archivePath) await refresh();
  };

  refresh().catch(showError);
})();
