// The FF7 text meter counts encoded bytes, never plain characters.
const assert = require('node:assert/strict');
const {test} = require('node:test');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');
const vm = require('node:vm');
const source = readFileSync(join(__dirname, '../../plugins/ff7/controls.js'), 'utf8');

function controls() {
  const node = (tag, attrs = {}, ...children) => {
    const classes = new Set(String(attrs.class || '').split(/\s+/).filter(Boolean));
    return {tag, attrs, children, value: attrs.value ?? '', textContent: '', style: {},
      classList: {
        toggle: (name, force) => {
          if (force === undefined) {
            if (classes.has(name)) classes.delete(name); else classes.add(name);
          } else if (force) classes.add(name); else classes.delete(name);
        },
        contains: name => classes.has(name),
      },
      append(...values) { this.children.push(...values); }};
  };
  const captured = [];
  const context = vm.createContext({
    el: node,
    state: {tab: 'enemies', invalid: {}, data: {vanilla: {}}, records: {}},
    readonly: () => false,
    rowById: () => ({values: {name: 'Vanilla'}}),
    provenanceControl: options => { captured.push(options); return node('provenance', {}, options.control); },
    shellRefresh: () => {},
  });
  vm.runInContext(source, context);
  const find = (root, match) => {
    if (!root || typeof root !== 'object') return null;
    if (match(root)) return root;
    for (const child of root.children || []) {
      const hit = find(child, match);
      if (hit) return hit;
    }
    return null;
  };
  return {
    count: text => vm.runInContext(`ff7EncodedByteCount(${JSON.stringify(text)})`, context),
    render: (row, field) => {
      context.__row = row;
      context.__field = field;
      const root = vm.runInContext('textControl(__row, __field)', context);
      const input = find(root, node => node.tag === 'textarea');
      const meter = find(root, node => node.tag === 'small');
      return {root, input, meter, provenance: captured[captured.length - 1],
        type: value => { input.value = value; input.attrs.oninput({target: input}); }};
    },
  };
}

test('byte counting treats escapes as one byte and rejects malformed ones', () => {
  const ui = controls();
  assert.equal(ui.count('ABC'), 3);
  assert.equal(ui.count(''), 0);
  assert.equal(ui.count('A\\x41B'), 3);
  assert.equal(ui.count('\\\\'), 1);
  assert.equal(ui.count('\\x41\\x42'), 2);
  assert.equal(ui.count('A\\'), -1);
  assert.equal(ui.count('\\x4'), -1);
  assert.equal(ui.count('\\xZZ'), -1);
  assert.equal(ui.count('\\q'), -1);
});

test('metered text shows a live encoded-byte count', () => {
  const ui = controls();
  const row = {id: 0, name: 'Enemy', values: {name: 'Imp'}};
  const field = {key: 'name', label: 'Enemy name', dataType: 'text', byteCapacity: 31};
  const view = ui.render(row, field);
  assert.ok(view.meter, 'expected a byte-count meter');
  assert.equal(view.meter.textContent, '3 of 31 encoded bytes.');
  assert.equal(view.meter.classList.contains('lex-ff7-byte-meter-over'), false);
  view.type('Imp\\xF8\\x00');
  assert.equal(row.values.name, 'Imp\\xF8\\x00');
  assert.equal(view.meter.textContent, '5 of 31 encoded bytes.');
});

test('over-capacity and malformed text warn instead of clipping', () => {
  const ui = controls();
  const view = ui.render({id: 0, name: 'Enemy', values: {name: ''}},
    {key: 'name', label: 'Enemy name', dataType: 'text', byteCapacity: 11});
  view.type('A'.repeat(12));
  assert.match(view.meter.textContent, /12 of 11 encoded bytes\. Too long to save\./);
  assert.equal(view.meter.classList.contains('lex-ff7-byte-meter-over'), true);
  assert.equal(view.meter.style.color, '#ff8080');
  view.type('AB\\');
  assert.match(view.meter.textContent, /Check the byte escapes/);
  assert.equal(view.meter.classList.contains('lex-ff7-byte-meter-over'), true);
  view.type('AB');
  assert.equal(view.meter.textContent, '2 of 11 encoded bytes.');
  assert.equal(view.meter.style.color, '');
});

test('row-level capacity serves per-record limits and restores refresh the meter', () => {
  const ui = controls();
  const view = ui.render({id: 0, name: 'Menu text', byteCapacity: 29, values: {text: ''}},
    {key: 'text', label: 'Text', dataType: 'text'});
  assert.ok(view.meter, 'expected a meter from the row capacity');
  assert.equal(view.meter.textContent, '0 of 29 encoded bytes.');
  view.provenance.apply('B'.repeat(30));
  assert.match(view.meter.textContent, /Too long to save\./);
  view.provenance.apply('OK');
  assert.equal(view.meter.textContent, '2 of 29 encoded bytes.');
});

test('text without a served capacity renders no meter', () => {
  const ui = controls();
  const view = ui.render({id: 0, name: 'AI', values: {script0: 'END'}},
    {key: 'script0', label: 'Script', dataType: 'text', language: 'ff7-asm'});
  assert.equal(view.meter, null);
  assert.equal(view.root.children[0].tag, 'textarea');
  view.type('NOP');
  assert.equal(view.root.children.length, 1);
});
