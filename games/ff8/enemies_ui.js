/* Compact enemy controls. The host supplies the shared controls, provenance
 * rails and Searcher, so edits still use the normal history/save pipeline. */
window.FF8EnemiesUI = ({el, state, columnList, detailSection, enemyTableSource,
  magicSearchControl, itemSearchControl, numberControl, unitField, infoHelp,
  conceptIcon, hoverable, beginSearcher, searchIcon, navigate, renderEnemies, shell}) => {
  const editable = () => state.activeSource === "mine";
  const tiers = ["low", "medium", "high"];
  const tierLabel = {low:"Low", medium:"Med", high:"High"};
  const previousDefence = new WeakMap();
  const origin = row => () => { state.selected.enemies = row.id; navigate("enemies"); };
  const pairs = (row, kind, title) => {
    // Keep the actual slot objects: the save path serializes row.tables.
    // Spreading each entry into a presentation row silently loses edits.
    const rows = tiers.map(tier => ({tier, entries:row.tables[kind][tier]}));
    const columns = [{key:"tier",label:"Level",render:entry=>tierLabel[entry.tier]},
      ...Array.from({length:4}, (_, slot) => ({key:`entry-${slot}`,
        label:kind === "draw" ? "" : `Slot ${slot + 1}`,
        render:tier => {
          const entry = tier.entries[slot];
          if (!entry) return el("span", {}, "—");
          const read = value => value?.tables[kind][tier.tier]?.[slot];
          const set = value => { if (!editable()) return; entry.valueId = Number(value); renderEnemies(); shell.refresh(); };
          const reference = kind === "draw"
            ? magicSearchControl(entry.valueId, `Select Magic for ${row.name}.`, set, origin(row))
            : itemSearchControl(entry.valueId, `Select the Item for ${row.name}.`, set, origin(row));
          if (!editable()) reference.querySelectorAll("button").forEach(button=>button.disabled=true);
          const count = numberControl(entry.quantity, 0, 255, 1,
            value => { if (editable()) entry.quantity = Math.round(value); },
            {disabled:!editable(),"aria-label":`${title} ${tierLabel[tier.tier]} entry ${slot+1} quantity`});
          const finder = enemyTableSource(reference,row,value=>read(value)?.valueId,set);
          const quantity = enemyTableSource(count,row,value=>read(value)?.quantity,
            value=>{if(editable())entry.quantity=Number(value)});
          return el("div", {class:"enemy-tier-entry", "data-enemy-slot":slot}, finder,
            el("span", {class:"enemy-tier-quantity",title:"Quantity (stored second byte)"},quantity));
        }
      }))];
    const table = columnList({rows,key:entry=>entry.tier,
      class:`ff8-record-list enemy-pair-table enemy-pair-${kind}`,editable:true,
      template:"38px repeat(4,minmax(0,1fr))",columns});
    return detailSection({className:"enemy-table-section enemy-tier-section",title,
      help:infoHelp(kind === "draw"
        ? "Each row is a level tier. All four Draw entries and their stored second bytes are retained in their original order."
        : "Each row is a level tier. Slot order is preserved; edit the item and its quantity together."),
      body:el("div",{class:"enemy-tier-scroll"},table)});
  };
  const defences = (row, kind, title) => {
    const elemental = kind === "elementDefence";
    const names = elemental ? ["Fire","Ice","Thunder","Earth","Poison","Wind","Water","Holy"]
      : state.data.enemyTables.choices.statuses.map(entry=>entry.name);
    const aliases = {Blind:"Darkness",Mute:"Silence","Sub-petrify":"Petrifying"};
    const immunePercent = elemental ? 0 : 155;
    const neutralPercent = elemental ? 100 : 0;
    const isImmune = entry => Number(entry.percent) === immunePercent;
    let remembered = previousDefence.get(row);
    if (!remembered) { remembered = new Map(); previousDefence.set(row,remembered); }
    const tiles = row.tables[kind].map(entry => {
      const name = names[entry.slot] || `Status ${entry.slot+1}`;
      const key = `${kind}:${entry.slot}`;
      if (!isImmune(entry)) remembered.set(key, Number(entry.percent));
      let input, button, tile;
      const sync = () => {
        const immune = isImmune(entry);
        button.setAttribute("aria-pressed", String(immune));
        tile.classList.toggle("is-immune", immune);
        input.disabled = immune || !editable();
        button.disabled = !editable();
      };
      const set = (value, editing=false) => {
        if (!editable()) return;
        const number = Number(value);
        if (!Number.isFinite(number)) return;
        entry.stored = Math.max(0,Math.min(255,Math.round(elemental ? (900-number)/10 : number+100)));
        entry.percent = elemental ? 900-entry.stored*10 : entry.stored-100;
        if (!isImmune(entry)) remembered.set(key,entry.percent);
        // Do not disable the focused input while a multi-digit number is
        // still being typed (e.g. the first '1' in '100' rounds to immunity).
        if (!editing) { input.value=String(entry.percent); sync(); }
        shell.refresh();
      };
      input = numberControl(entry.percent,elemental?-1650:-100,elemental?900:155,elemental?10:1,
        value=>set(value,true), {"aria-label":`${name} ${elemental?"damage taken":"status defence"} percent`});
      input.addEventListener("blur",()=>{input.value=String(entry.percent);sync();});
      const icon = conceptIcon(elemental?"element":"status",aliases[name]||name);
      button = el("button",{type:"button",class:"enemy-defence-toggle",
        "aria-label":`${name} immunity`,title:`${name}: toggle full immunity`,
        onclick:()=>set(isImmune(entry)?(remembered.get(key)??neutralPercent):immunePercent)},
        icon || el("span",{class:"enemy-defence-fallback"},name),
        el("span",{class:"enemy-defence-immune","aria-hidden":"true"},"Immune"));
      tile = el("div",{class:"enemy-defence-tile","data-defence-slot":entry.slot},
        button,unitField(input,"%"));
      sync();
      return enemyTableSource(tile,row,value=>value?.tables[kind][entry.slot]?.percent,
        value=>set(value),value=>`${value}%`);
    });
    return detailSection({className:"enemy-table-section enemy-defence-section",title,
      help:infoHelp(elemental
        ? "Incoming elemental damage: 100% is neutral, 0% is immune, negative values absorb, and above 100% takes extra damage. Click an icon for immunity; click again to restore the previous value."
        : "Status defence is the stored byte minus 100 (-100% to 155%). The immunity shortcut stores 255 (155%); click again to restore the previous value. Named tiles are used where no matching game icon is available."),
      body:el("div",{class:`enemy-defence-grid ${elemental?"enemy-element-defence":"enemy-status-defence"}`},...tiles)});
  };
  const cards = row => {
    const choices = state.data.enemyTables.choices.cards;
    const tiles = row.tables.cards.map(entry => {
      const card = state.data.cards?.rows?.find(value=>Number(value.id)===Number(entry.cardId))
        || choices.find(value=>Number(value.id)===Number(entry.cardId))
        || {id:entry.cardId,name:`Card ${entry.cardId}`};
      const set = value => { if (!editable()) return; entry.cardId=Number(value); renderEnemies(); shell.refresh(); };
      const pick = event => { if (!editable()) return; event.preventDefault();event.stopPropagation();beginSearcher({type:"cards",
        prompt:`Select card entry ${entry.slot+1} for ${row.name}.`,target:()=>navigate("cards"),origin:origin(row),accept:set}); };
      const image = el("img",{src:entry.cardId===255?undefined:`/assets/cards/${entry.cardId}.png`,alt:card.name,
        loading:"lazy",onerror:event=>{event.target.hidden=true;fallback.hidden=false;}});
      const fallback = el("span",{class:"enemy-card-fallback",hidden:entry.cardId!==255},entry.cardId===255?"—":"Art unavailable");
      if (entry.cardId===255) image.hidden=true;
      const portrait = el("button",{type:"button",class:"enemy-card-art",disabled:!editable(),
        "aria-label":`Choose card entry ${entry.slot+1}`,onclick:pick},image,fallback);
      const name = hoverable({class:"enemy-card-name",content:card.name,targetType:"cards",
        targetId:entry.cardId,targetLabel:card.name,
        activate:()=>{if(entry.cardId!==255){state.selected.cards=Number(entry.cardId);navigate("cards");}}});
      const finder = el("button",{type:"button",class:"ff8-entity-search-button",disabled:!editable(),
        "aria-label":`Replace card entry ${entry.slot+1}`,title:"Choose card",onclick:pick},searchIcon());
      const empty = el("button",{type:"button",class:"enemy-card-clear",disabled:!editable(),title:"No card / immune",
        "aria-label":`Clear card entry ${entry.slot+1}`,onclick:()=>set(255)},"×");
      const control = el("div",{class:"enemy-card-choice","data-card-slot":entry.slot},portrait,
        el("div",{class:"enemy-card-caption"},name,finder),empty);
      return enemyTableSource(control,row,value=>value?.tables.cards[entry.slot]?.cardId,set,
        value=>choices.find(choice=>Number(choice.id)===Number(value))?.name||String(value));
    });
    return detailSection({className:"enemy-table-section enemy-card-section",title:"CARDS",
      body:el("div",{class:"enemy-card-grid"},...tiles)});
  };
  return {pairs,defences,cards};
};
