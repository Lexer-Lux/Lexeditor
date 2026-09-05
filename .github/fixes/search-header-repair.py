"""One-time repair, removed by the validation job after successful tests.

Both inputs and outputs are pinned so this cannot alter a concurrent revision.
Only the two named UTF-8 editor files are written; no game or binary is touched.
"""
from hashlib import sha256
from pathlib import Path

SEARCH = '''  const bottomSearchChangeTimers = new Map();
  const bottomSearch = options => {
    const key = String(options.key || options.label || "records");
    let composing = false;
    const control = element("input", {
      type: "search", value: options.value || "", placeholder: "",
      "aria-label": options.label || options.placeholder || "Search records",
      "data-lex-bottom-search": key,
    });
    const change = event => {
      clearTimeout(bottomSearchChangeTimers.get(key));
      bottomSearchChangeTimers.delete(key);
      // Replacing an input in the middle of an IME composition discards text.
      if (composing || event?.isComposing) return;
      const apply = () => {
        bottomSearchChangeTimers.delete(key);
        // A delayed filter must not render an old page after navigation.
        if (composing || !control.isConnected) return;
        const focused = document.activeElement === control;
        const start = control.selectionStart;
        const end = control.selectionEnd;
        const direction = control.selectionDirection;
        options.change?.(control.value);
        // Most list views rebuild their pager when filtering. Restore focus
        // before this input event returns, not two animation frames later:
        // keystrokes arriving between frames would otherwise go to <body>.
        if (!focused || control.isConnected) return;
        const active = document.activeElement;
        if (active && active !== document.body && active !== document.documentElement) return;
        const next = [...document.querySelectorAll("[data-lex-bottom-search]")]
          .find(node => node.dataset.lexBottomSearch === key);
        if (!next) return;
        next.focus({preventScroll: true});
        if (Number.isInteger(start)) next.setSelectionRange(
          start, Number.isInteger(end) ? end : start, direction || "none");
      };
      const delay = Math.max(0, Number(options.delay) || 0);
      if (delay) bottomSearchChangeTimers.set(key, setTimeout(apply, delay));
      else apply();
    };
    control.addEventListener("input", change);
    control.addEventListener("compositionstart", () => {
      composing = true;
      clearTimeout(bottomSearchChangeTimers.get(key));
      bottomSearchChangeTimers.delete(key);
    });
    control.addEventListener("compositionend", () => { composing = false; change(); });
    return element("label", {class: "lex-pager-search"}, searchIcon(), control);
  };
'''

INPUTS = {
    'ui/framework.js': '6193624c8361881fc65e41995873a0cd1264864067b4649db6d2184c6ca1fe17',
    'games/ff8/editor.html': 'e9ccadd3781a0551805cbf93fa0e153662e8ff41cd9c5ba29b2a44a4ccd036dc',
}
OUTPUTS = {
    'ui/framework.js': '1c255894932c0bb6323e05f650f334fbc2fb681db8e85ee7a974f4208193b4a9',
    'games/ff8/editor.html': 'e08bd147f1b3c2f72dde6053020c5d366aa7f855b2b9e420eeee25193f94d4bc',
}

def replace_once(text, old, new):
    if text.count(old) != 1:
        raise RuntimeError('Expected exactly one source anchor: ' + old)
    return text.replace(old, new, 1)

sources = {}
for name, expected in INPUTS.items():
    data = Path(name).read_bytes()
    if sha256(data).hexdigest() != expected:
        raise RuntimeError('Source changed; refusing to overwrite ' + name)
    sources[name] = data.decode('utf-8')

framework = sources['ui/framework.js']
start = framework.index('  let pendingBottomSearchFocus = null;')
end = framework.index('\n  const pager = options =>', start)
framework = framework[:start] + SEARCH + framework[end:]
framework = replace_once(framework,
    '      element("header", {class: "lex-platform-config-head"},',
    '      options.showHeader === false ? null : element("header", {class: "lex-platform-config-head"},')
sources['ui/framework.js'] = framework
sources['games/ff8/editor.html'] = replace_once(sources['games/ff8/editor.html'],
    'platformConfigView({config:state.platformConfig,query:',
    'platformConfigView({config:state.platformConfig,showHeader:false,query:')

planned = {name: text.encode('utf-8') for name, text in sources.items()}
for name, data in planned.items():
    if sha256(data).hexdigest() != OUTPUTS[name]:
        raise RuntimeError('Repair differs from tested output: ' + name)
for name, data in planned.items():
    Path(name).write_bytes(data)
    print('Applied verified repair:', name, sha256(data).hexdigest())
