/* Ordered GF pages are mod data; native stock is never edited here. */
window.FF8SpellbooksUI = (() => {
  const selectedPages = new Map();
  const {el, detailSection, infoHelp} = LexeditorUI;
  const render = options => {
    const {row, payload, settings, readonly, magics, abilities, references,
      change, refresh, selectControl, sourceControl} = options;
    const document = payload.document;
    let book = document.books.find(value => value.gfId === row.id);
    const pageIndex = Math.min(selectedPages.get(row.id) || 0, Math.max(0, (book?.pages.length || 1) - 1));
    const commit = action => { if (readonly) return; action(); change(); refresh(); };
    const button = (label, title, action, disabled = false) => el("button", {
      type:"button", title, "aria-label":title, disabled:readonly || disabled,
      onclick:() => commit(action)}, label);
    const root = el("div", {class:"gf-spellbook-editor", "data-gf-id":row.id});
    const enabled = el("input", {type:"checkbox", checked:!!settings.gfSpellbooksEnabled,
      disabled:readonly, "aria-label":"Enable GF spellbooks",
      onchange:event => commit(() => {settings.gfSpellbooksEnabled = event.target.checked;})});
    root.append(el("label", {class:"gf-spellbook-toggle"}, enabled, "Enable GF spellbooks",
      infoHelp("Requires Monogamy on and Shared Magic off. A GF without a configured book keeps the normal Magic list. Zero-stock spells remain visible and unusable; a prerequisite must be learned by this GF.")));
    const restore = el("div", {class:"gf-spellbook-actions"});
    for (const reference of references) {
      if (JSON.stringify(reference.book || null) === JSON.stringify(book || null)) continue;
      restore.append(button(`Use ${reference.shortName}`, `Restore ${reference.name} spellbook`, () => {
        document.books = document.books.filter(value => value.gfId !== row.id);
        if (reference.book) document.books.push(structuredClone(reference.book));
        selectedPages.set(row.id, 0);
      }));
    }
    if (restore.childElementCount) root.append(restore);
    if (!book) {
      root.append(el("p", {}, "This GF uses the normal Magic list."),
        button("Create spellbook", "Create spellbook for this GF", () => {
          document.books.push({gfId:row.id, pages:[[]]}); selectedPages.set(row.id, 0);
        }));
      return root;
    }
    const pages = book.pages;
    const page = pages[pageIndex];
    const movePage = offset => {
      [pages[pageIndex], pages[pageIndex + offset]] = [pages[pageIndex + offset], pages[pageIndex]];
      selectedPages.set(row.id, pageIndex + offset);
    };
    const pageSelect = selectControl(pageIndex, pages.map((_, id) => ({id, name:`Page ${id + 1}`})), value => {
      selectedPages.set(row.id, Number(value)); refresh();
    });
    pageSelect.setAttribute("aria-label", "Spellbook page");
    // Navigation remains usable in a read-only source.
    pageSelect.disabled = false;
    root.append(el("div", {class:"gf-spellbook-actions"}, pageSelect,
      button("←", "Move page earlier", () => movePage(-1), pageIndex === 0),
      button("→", "Move page later", () => movePage(1), pageIndex === pages.length - 1),
      button("+ Page", "Add spellbook page", () => {pages.push([]);selectedPages.set(row.id,pages.length - 1);}, pages.length >= payload.limits.maxPages),
      button("− Page", "Remove spellbook page", () => {pages.splice(pageIndex,1);selectedPages.set(row.id,Math.max(0,pageIndex - 1));}, pages.length === 1)));
    const used = new Set(pages.flat().map(slot => slot.magicId));
    const allowedSpells = magics.filter(value => payload.magicIds.includes(value.id));
    const allowedAbilities = abilities.filter(value => payload.abilityIds.includes(value.id));
    const table = el("div", {class:"gf-spellbook-slots"});
    page.forEach((slot, index) => {
      const sourceAt = reference => reference.book?.pages[pageIndex]?.[index];
      const referenced = (control, key, apply, format) => sourceControl(control, () => slot[key],
        undefined, references.filter(value => value.shortName !== "V").map(value => ({
          name:value.name, shortName:value.shortName, value:sourceAt(value)?.[key]
        })).filter(value => value.value !== undefined), value => commit(() => apply(value)), format);
      const spellChoices = allowedSpells.filter(value => value.id === slot.magicId || !used.has(value.id));
      const spell = selectControl(slot.magicId, spellChoices, value => commit(() => {slot.magicId = Number(value);}));
      spell.disabled = readonly;spell.setAttribute("aria-label", `Spell ${index + 1}`);
      const ability = selectControl(slot.abilityId ?? "", [{id:"",name:"None"}, ...allowedAbilities], value => commit(() => {slot.abilityId = value === "" ? null : Number(value);}));
      ability.disabled = readonly;
      const abilitySelect = ability.matches("select") ? ability : ability.querySelector("select");
      abilitySelect.disabled = readonly;abilitySelect.setAttribute("aria-label", `Required ability ${index + 1}`);
      const move = offset => {[page[index],page[index + offset]] = [page[index + offset],page[index]];};
      const target = selectControl(pageIndex, pages.map((entry,id) => ({id,name:`Page ${id+1}`})).filter(value => value.id === pageIndex || pages[value.id].length < payload.limits.slotsPerPage), value => commit(() => {
        const [entry] = page.splice(index,1);pages[Number(value)].push(entry);selectedPages.set(row.id,Number(value));
      }));
      target.disabled = readonly;target.setAttribute("aria-label", `Move spell ${index + 1} to page`);
      table.append(el("div", {class:"gf-spellbook-slot", "data-slot":index},
        el("span", {class:"gf-spellbook-slot-number"}, String(index + 1)),
        el("label", {}, "Spell", referenced(spell,"magicId",value=>{slot.magicId=Number(value);},value=>allowedSpells.find(entry=>entry.id===value)?.name || value)),
        el("label", {}, "Required ability", referenced(ability,"abilityId",value=>{slot.abilityId=value;},value=>value===null?"None":allowedAbilities.find(entry=>entry.id===value)?.name || value)),
        el("div", {class:"gf-spellbook-actions"},
          button("↑", `Move spell ${index + 1} earlier`, () => move(-1), index === 0),
          button("↓", `Move spell ${index + 1} later`, () => move(1), index === page.length - 1),
          target, button("×", `Remove spell ${index + 1}`, () => page.splice(index,1)))));
    });
    const available = allowedSpells.find(value => !used.has(value.id));
    root.append(detailSection({title:`PAGE ${pageIndex + 1}`, body:table}),
      button("+ Spell", "Add spell to this page", () => page.push({magicId:available.id,abilityId:null}),
        page.length >= payload.limits.slotsPerPage || !available),
      button("Remove spellbook", "Remove spellbook for this GF", () => {document.books = document.books.filter(value=>value.gfId!==row.id);}));
    return root;
  };
  return {render};
})();
