"""Discover nested read-only tab views without game-specific navigation."""
import json


GROUPS = r"""(()=>{
  const shown=n=>{const r=n.getBoundingClientRect(),s=getComputedStyle(n);
    return r.width>0&&r.height>0&&s.visibility==='visible'&&s.display!=='none';};
  return JSON.stringify([...document.querySelectorAll('main [role=tablist],#main [role=tablist],.lex-shell-main [role=tablist]')]
    .filter(shown).map(bar=>({label:bar.getAttribute('aria-label')||'',
      tabs:[...bar.querySelectorAll(':scope > [role=tab]')].filter(shown).map(b=>({
        id:b.dataset.subtab||b.id||b.querySelector('.lex-tab-label-text')?.textContent||b.textContent.trim(),
        selected:b.getAttribute('aria-selected')==='true'||b.classList.contains('active'),
        disabled:b.disabled||b.getAttribute('aria-disabled')==='true'
      }))})).filter(g=>g.tabs.length));
})()"""


def sweep_nested_tabs(evaluate, settle, measure, limit=80):
    """Measure each reachable visible tab state, restoring parent selections.

    Only tab controls are activated. Inputs, record creation and save controls
    are never selected. A bound is an explicit coverage failure, not success.
    """
    visited = set()

    def groups():
        return json.loads(evaluate(GROUPS))

    def identity(group):
        return (group['label'], tuple(t['id'] for t in group['tabs']))

    def choose(group, occurrence, tab):
        script = """(()=>{
          const description=%s, occurrence=%s, id=%s;
          const shown=n=>{const r=n.getBoundingClientRect(),s=getComputedStyle(n);
            return r.width>0&&r.height>0&&s.visibility==='visible'&&s.display!=='none';};
          const bars=[...document.querySelectorAll('main [role=tablist],#main [role=tablist],.lex-shell-main [role=tablist]')]
            .filter(shown).filter(bar=>{
              const buttons=[...bar.querySelectorAll(':scope > [role=tab]')].filter(shown);
              const ids=buttons.map(b=>b.dataset.subtab||b.id||b.querySelector('.lex-tab-label-text')?.textContent||b.textContent.trim());
              return (bar.getAttribute('aria-label')||'')===description[0]&&JSON.stringify(ids)===JSON.stringify(description[1]);
            });
          const button=[...bars[occurrence]?.querySelectorAll(':scope > [role=tab]')||[]]
            .find(b=>(b.dataset.subtab||b.id||b.querySelector('.lex-tab-label-text')?.textContent||b.textContent.trim())===id);
          if(!button||button.disabled||button.getAttribute('aria-disabled')==='true')return false;
          button.click();return true;
        })()""" % (json.dumps(identity(group)), occurrence, json.dumps(tab))
        if not evaluate(script):
            raise AssertionError(f'Tab navigation disappeared: {group["label"]} / {tab}')
        settle()

    def visit(path):
        current = groups()
        signature = json.dumps(current, sort_keys=True)
        if signature in visited:
            return
        if len(visited) >= limit:
            raise AssertionError(f'Nested tab audit exceeded {limit} states; coverage is incomplete')
        visited.add(signature)
        measure(path)
        occurrences = {}
        for group in current:
            key = identity(group)
            occurrence = occurrences.get(key, 0)
            occurrences[key] = occurrence + 1
            selected = next((tab['id'] for tab in group['tabs'] if tab['selected']), None)
            if selected is None:
                raise AssertionError(f'Tab group has no selected tab: {key}')
            for tab in group['tabs']:
                if tab['selected'] or tab['disabled']:
                    continue
                choose(group, occurrence, tab['id'])
                try:
                    visit(path + [tab['id']])
                finally:
                    choose(group, occurrence, selected)

    visit([])
    return len(visited)
