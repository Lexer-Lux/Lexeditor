/* Factory kept independent of the editor's page state. The host supplies its
 * existing list/detail, typed controls, provenance, and history helpers. */
window.FF8CardsUI = ({el, state, rowOf, filtered, showPaged, sharedDetail,
  detailSection, detailField, numberControl, selectControl, sourceControl,
  referenceValues, infoHelp, shell, noteFieldEdit, subtabBar, detailPanel,
  recordId, columnList, conceptIcon, ensureFieldDetail}) => {
  // The card's own four sides, in the order Triple Triad draws them.
  const sides = ["top", "left", "right", "bottom"];
  const fields = [...sides, "element", "power"];
  const labels = {top:"Top", bottom:"Bottom", left:"Left", right:"Right", element:"Element", power:"Selection power"};
  const clone = value => JSON.parse(JSON.stringify(value));
  let mode = "cards";
  const playerView = {query:"",page:0,selected:null};
  const rank = value => Number(value) === 10 ? "A" : String(value);
  const elementOptions = () => state.data.cards.elements || [];
  const elementName = value => elementOptions()
    .find(entry => Number(entry.id) === Number(value))?.name || "";
  const elementIcon = value => Number(value) ? el("img", {
    src:`/assets/card-elements/${Number(value)}.png`,alt:elementName(value)}) : null;

  // The card itself is the control. Every rank on it can be typed into and the
  // element corner opens its own list, so the values are edited where they are
  // read instead of only in a column of boxes beside the picture.
  const preview = (row, refresh) => {
    const update = (field, value) => {
      if(state.activeSource!=="mine")return;
      if (field === "element") {
        if (!elementOptions().some(entry => Number(entry.id) === Number(value))) return;
        row[field] = Number(value);
      } else {
        const limit = field === "power" ? 255 : 10;
        row[field] = Math.max(0, Math.min(limit, Number(value) || 0));
      }
      noteFieldEdit("cards", {field});
      refresh();
    };
    const rankButton = side => el("button", {
      type: "button",
      disabled:state.activeSource!=="mine",
      title: `${labels[side]}: click to change`,
      "aria-label": `${labels[side]}, currently ${rank(row[side])}`,
      onclick: () => update(side, (Number(row[side]) % 10) + 1),
      oncontextmenu: event => {event.preventDefault();update(side, Number(row[side]) <= 1 ? 10 : Number(row[side]) - 1);},
    }, rank(row[side]));
    let card;
    const picker=LexeditorUI.choicePopover({label:"Choose card element",
      boundary:()=>card,
      choices:elementOptions().map(entry=>({value:entry.id,label:entry.name,icon:elementIcon(entry.id)})),
      select:value=>update("element",value)});
    const none = Number(row.element) === 0;
    const element = el("button", {
      type:"button",
      class:none ? "lex-card-corner-empty" : "",
      disabled:state.activeSource !== "mine",
      title:none ? "Add element" : `Change ${elementName(row.element)}`,
      "aria-label":none ? "Add element" : `Change ${elementName(row.element)}`,
      onclick:()=>picker.openFor(element),
    }, none ? "+" : elementIcon(row.element));
    card=LexeditorUI.statCard({image:`/assets/cards/${row.id}.png`,
      ranks:sides.map(rankButton),corner:element});
    return card;
  };

  const renameCard = (row, value) => {
    row.name = String(value);
    const text = state.data.text.rows.find(entry =>
      entry.source === "exe_card_names" && entry.recordId === row.id);
    if (text) text.value = row.name;
    noteFieldEdit("cards", {field: "name"});
  };

  const detail = (row, prefs) => {
    const vanilla = rowOf(state.vanilla, "cards", row.id);
    const refresh = () => render();
    const properties = fields.map(field => {
      const update = value => {row[field] = Number(value);noteFieldEdit("cards", {field});};
      const options = elementOptions().map(entry => ({value: entry.id, name: entry.name}));
      const control = field === "element"
        ? selectControl(row[field], options, update)
        : numberControl(row[field], 0, field === "power" ? 255 : 10, 1, update,
          {"aria-label": `${row.name} ${labels[field]}`});
      const format = value => field === "element"
        ? options.find(entry => entry.value === Number(value))?.name || value
        : Number(value) === 10 && field !== "power" ? "A" : value;
      return detailField({label: labels[field].toUpperCase(),
        pin:prefs?.pinButton(field,labels[field]),
        help: infoHelp(field === "power"
          ? "When you lose, the opponent prefers a card with a higher selection power."
          : field === "element" ? "The card's element under the Elemental rule."
          : "The value on this side of the card. Ten appears as A in Triple Triad."),
        control: sourceControl(control, () => row[field], vanilla[field],
          referenceValues("cards", row.id, value => value?.[field]), update, format)});
    });
    // No NAME property. The name is the heading, and the heading is typed into
    // directly, so a card no longer carries its own name twice.
    return detailPanel({
      // The card beside what it holds: the shared panel's own layout, asked for
      // by name rather than restyled from here.
      bodyLayout: "beside",
      className: "lex-detail detail ff8-card-detail",
      title: row.name,
      renameRecord: value => {renameCard(row, value);shell.refresh();},
      renameLabel: "Card name",
      identity: el("span", {class: "lex-pinnable-property"}, prefs?.pinButton("id", "ID"), recordId(row.id)),
      body: [
        detailSection({title: "PREVIEW", body: [preview(row, refresh)]}),
        detailSection({title: "CARD", body: properties}),
      ],
    });
  };

  const renderCards = () => showPaged("cards", filtered("cards", ["id", "name"]), [
    {key: "id", label: "ID"},
    // The name is edited in the table as well as in the heading: a rename is
    // the one edit you want without leaving the list you are scanning.
    {key: "name", label: "Card",
      edit: (row, value) => {renameCard(row, value);shell.refresh();}},
    ...fields.map(field => ({key: field, label: labels[field], pinned: false, numeric: true}))
  ], detail, "74px minmax(240px,1fr)", {}, false);
  let render = () => null;
  // Only areas that really have a card player are listed. Finding them reads
  // every area's script once per install, so the list says how far along it is.
  let playerAreas = null, playerAreasPolling = false;
  const loadPlayerAreas = async () => {
    if (playerAreasPolling) return;
    playerAreasPolling = true;
    try {
      while (true) {
        const response = await fetch("/api/card-players");
        playerAreas = await response.json();
        if (state.tab === "cards" && mode === "players") render();
        if (playerAreas.ready || playerAreas.error) break;
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
    } catch (error) {
      playerAreas = {ready:false, error:error.message || String(error), keys:[]};
      if (state.tab === "cards" && mode === "players") render();
    } finally { playerAreasPolling = false; }
  };
  const renderPlayers = () => {
    if (!playerAreas?.ready) {
      if (!playerAreas?.error) loadPlayerAreas();
      const text = playerAreas?.error ? `Could not find card players: ${playerAreas.error}`
        : `Finding card players… ${playerAreas?.scanned || 0} of ${playerAreas?.total || "?"} areas read`;
      return detailPanel({className:"ff8-card-player-detail",title:"Card players",body:[el("p",{},text)]});
    }
    const groups=new Map();
    for(const entry of playerAreas.players||[]){
      const key=`${entry.map}:${entry.entity}`;
      if(!groups.has(key))groups.set(key,{key,map:entry.map,entity:entry.entity,calls:[]});
      groups.get(key).calls.push(entry.id);
    }
    const known=new Map((state.data.characters?.rows||[]).map(row=>[row.name.toLowerCase(),row.name]));
    const query=playerView.query.toLowerCase();
    // A deck is what the game actually selects, and one deck is shared by
    // several opponents. The scan already read every CARDGAME call, so the
    // deck each opponent names is known without loading a single area here.
    const deckOfCall=new Map();
    for(const entry of playerAreas.players||[]){
      if(entry.deckMode!=="literal"||entry.deckId===null||entry.deckId===undefined)continue;
      deckOfCall.set(`${entry.map}:${entry.entity}`,Number(entry.deckId));
    }
    const deckMembers=new Map();
    for(const entry of groups.values()){
      const deck=deckOfCall.get(entry.key);
      if(deck===undefined)continue;
      if(!deckMembers.has(deck))deckMembers.set(deck,[]);
      deckMembers.get(deck).push(entry.key);
    }
    const players=[...groups.values()].map(entry=>({...entry,
      name:known.get(entry.entity.toLowerCase())||entry.entity,
      deck:deckOfCall.get(entry.key)}));
    const byKey=new Map(players.map(row=>[row.key,row]));
    const rows=players.filter(row=>`${row.name} ${row.map}`.toLowerCase().includes(query));
    const help=[
      "Selects the opponent's deck, not a single card. The deck list itself is not editable.",
      "The card rules you bring from previous regions. The game uses these when it offers to mix rules.",
      "The card rules used in this opponent's region. These are separate from the rules you bring with you.",
      "Percentage chance, from 0 to 100, that this opponent uses an available rare card.",
      "The gameplay effect of this argument has not been verified. Its original value is retained.",
      "The gameplay effect of this argument has not been verified. Its original value is retained.",
      "The gameplay effect of this argument has not been verified. Its original value is retained."];
    const detail=entry=>{
      const map=state.data.fields.rows.find(row=>row.key===entry.map);
      if(!map)return detailPanel({title:entry.name,body:[LexeditorUI.detailNote('Location data is unavailable.')]});
      if(!map._loaded&&!map._loading&&!map._error)
        queueMicrotask(async()=>{await ensureFieldDetail(map);if(state.tab==='cards'&&mode==='players')render()});
      const body=[detailField({label:'Location',control:LexeditorUI.readonlyField(map.name)}),
        detailField({label:'Map file',control:LexeditorUI.readonlyField(map.key)})];
      if(map._error)body.push(LexeditorUI.detailNote(`Could not load opponent: ${map._error}`));
      else if(!map._loaded)body.push(LexeditorUI.detailNote('Loading opponent settings…'));
      else {
        const calls=(map.players||[]).filter(player=>player.entity===entry.entity);
        if(calls.length>1)body.push(LexeditorUI.detailNote('This opponent has more than one card-game setup. The game script decides which setup is used.'));
        calls.forEach((player,index)=>{
          const fields=(player.params||[]).map(param=>{
            const before=state.vanilla?.fields?.rows?.find(row=>row.key===map.key)?.players?.find(row=>row.id===player.id)?.params?.find(row=>row.id===param.id);
            const update=value=>{param.value=Number(value);noteFieldEdit('fields',{field:param.name});shell.refresh()};
            const variable=param.mode==='variable',maximum=!variable&&param.id===3?100:0xFFFFFF;
            const input=numberControl(param.value,0,maximum,1,update,{'aria-label':`${entry.name} ${param.name}`});
            input.disabled=!param.editable||state.activeSource!=='mine';
            return detailField({label:param.name+(variable?' variable':''),dataType:'INT',min:0,max:maximum,
              help:infoHelp(help[param.id]+(variable?' Holds a game-variable reference; changing it selects a different variable.':'')),
              control:sourceControl(input,()=>param.value,before?.value,[],update)});
          });
          body.push(calls.length===1?LexeditorUI.stack({fill:false},...fields):detailSection({title:`Setup ${index+1}`,body:fields}));
        });
        // Which other opponents play the same deck. Editing a deck means
        // editing every script that names it, and no other screen shows that.
        const deck=deckOfCall.get(entry.key);
        if(deck!==undefined){
          const others=(deckMembers.get(deck)||[]).filter(key=>key!==entry.key)
            .map(key=>byKey.get(key)).filter(Boolean);
          body.push(detailSection({title:`ALSO USES DECK ${deck}`,
            help:infoHelp(`The deck number this opponent's CARDGAME call names. Several opponents can name the same deck, and the game reads that deck's own card list.`
              +` The card list of a deck is not stored in the files this editor reads, so it cannot be shown or edited here.`
              +` Each opponent below has its own CARDGAME call; select one to edit the values its script passes.`),
            body:others.length
              ?LexeditorUI.stack({fill:false},...others.map(other=>
                  el("button",{type:"button",style:"text-align:left",
                    onclick:()=>{playerView.selected=other.key;playerView.page=0;render()}},
                    `${other.name} · ${other.map}`)))
              :LexeditorUI.detailNote(`No other CARDGAME call in the game data names deck ${deck}.`)}));
        }
      }
      return detailPanel({title:entry.name,body});
    };
    return LexeditorUI.pagedListDetail({rows,key:row=>row.key,selected:playerView.selected,
      page:playerView.page,pageSize:40,noun:'players',maxBarrels:1,slots:true,fit:{minRowHeight:28},
      className:'ff8-card-players',splitKey:'ff8-card-players',rowsKey:'ff8-card-players',
      search:{key:'ff8-card-players',value:playerView.query,label:'Search card players',change:value=>{playerView.query=value;playerView.page=0;render()}},
      sync:next=>Object.assign(playerView,next),change:next=>{Object.assign(playerView,next);render()},
      master:({rows,selected,select})=>columnList({rows,key:row=>row.key,selected,select,
        columns:[{key:'name',label:'Player',help:'Character name when known, else the game identifier.'},
          {key:'deck',label:'Deck',help:'The deck number this opponent names, or a dash when the script passes a savemap variable instead of a number.',
            render:row=>row.deck===undefined?"—":String(row.deck)}]}),detail,
      emptyDetail:()=>detailPanel({title:'Card players',body:[LexeditorUI.detailNote('No players match this search.')]})});
  };
  render = () => {
    if (state.tab !== "cards") return null;
    const toolbar=document.querySelector('#toolbar');toolbar.replaceChildren();toolbar.hidden=true;
    const root = LexeditorUI.stack(
      subtabBar({
        flush: true,
        label: "Cards views",
        active: mode,
        tabs: [{id: "cards", label: "CARDS"}, {id: "players", label: "PLAYERS"}],
        change: value => {mode = value;render();},
      }),
      mode === "players" ? renderPlayers() : renderCards());
    document.querySelector("#main")?.replaceChildren(root);
    shell.refresh();
    return root;
  };
  return {
    render,
    edits: () => state.data.cards.rows.flatMap(row => {
      const base = state.base.cards.find(value => value.id === row.id);
      return fields.filter(field => row[field] !== base[field])
        .map(field => ({id: row.id, field, value: row[field]}));
    })
  };
};

/* Issue #93 extension. The main FF8 editor already loads this module on every
 * page, so the spellbook editor can attach to the existing GF detail surface
 * without duplicating the 300KB host document or creating a second GF editor. */
(() => {
  const PANEL_CLASS = "lexeditor-gf-spellbook";
  const clone = value => JSON.parse(JSON.stringify(value));
  const request = async (url, options) => {
    const response = await fetch(url, options);
    const payload = await response.json();
    if (!response.ok || payload?.error) throw new Error(payload?.error || `HTTP ${response.status}`);
    return payload;
  };
  const button = (text, onClick, title="") => {
    const value = document.createElement("button");
    value.type = "button";
    value.textContent = text;
    value.title = title;
    value.addEventListener("click", onClick);
    return value;
  };
  const select = (options, selected, onChange, emptyLabel=null) => {
    const value = document.createElement("select");
    if (emptyLabel !== null) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = emptyLabel;
      value.append(option);
    }
    options.forEach(row => {
      const option = document.createElement("option");
      option.value = String(row.id);
      option.textContent = `${row.id} — ${row.name}`;
      option.selected = Number(selected) === Number(row.id);
      value.append(option);
    });
    value.addEventListener("change", () => onChange(value.value === "" ? null : Number(value.value)));
    return value;
  };
  const mount = async () => {
    const host = document.querySelector("#gf-detail[data-gf]");
    if (!host || host.querySelector(`.${PANEL_CLASS}`)) return;
    const gfId = Number(host.dataset.gf);
    if (!Number.isInteger(gfId) || gfId < 0 || gfId > 15) return;
    const marker = LexeditorUI.stack({fill:false});
    marker.classList.add(PANEL_CLASS);
    marker.dataset.gf = String(gfId);
    marker.textContent = "Loading GF spellbook…";
    const abilitiesPanel=host.querySelector('[data-gf-panel="abilities"]');
    if(!abilitiesPanel)return;
    const parts=LexeditorUI.sectionParts(abilitiesPanel);
    const abilitiesContent=parts.content.querySelector(':scope > [data-gf-abilities]') || parts.content;
    parts.title?.remove();
    let spellbookReady=false;
    const tabbed=LexeditorUI.tabbedPanel({label:'GF abilities and spellbook',active:'abilities',tabs:[{id:'abilities',label:'ABILITIES'},{id:'spellbook',label:'SPELLBOOK',attrs:{'aria-disabled':'true'}}],content:[abilitiesContent,marker],change:id=>{
      if(id==='spellbook'&&!spellbookReady)return;
      abilitiesContent.hidden=id!=='abilities';marker.hidden=id!=='spellbook';
      tabs.querySelectorAll('[role="tab"]').forEach((tab,index)=>{const active=index===(id==='abilities'?0:1);tab.tabIndex=active?0:-1;tab.classList.toggle('active',active);tab.setAttribute('aria-selected',String(active));});
    }});
    const tabs=tabbed.querySelector('[role="tablist"]');
    const spellTab=tabs.querySelectorAll('button')[1];
    const spellHelp=LexeditorUI.infoHelp("Choose and order this GF's Magic pages. To unlock this tab, open Tweaks → Gameplay and enable GF Spellbooks and Monogamy, with Shared Party Magic Inventory off. This does not change the GF's learnable abilities.");
    spellHelp.addEventListener('click',event=>event.stopPropagation());
    spellHelp.addEventListener('keydown',event=>event.stopPropagation());
    spellTab?.append(spellHelp);
    marker.hidden=true;
    host.lexReplacePanel(abilitiesPanel,tabbed);
    try {
      const payload = await request("/api/kernel?section=3&dataset=current");
      if (!marker.isConnected || Number(host.dataset.gf) !== gfId) return;
      const gf = payload.rows?.find(row => Number(row.id) === gfId);
      if (!gf) throw new Error(`GF ${gfId} is unavailable`);
      const meta = payload.spellbook || {};
      // Respect edits made on Tweaks before Save as well as saved settings.
      const currentSettings=typeof state!=='undefined'?state.data?.settings:null;
      const enabled=currentSettings?.gfSpellbooksEnabled??meta.enabled;
      const runtimeActive=currentSettings?currentSettings.singleGf&&!currentSettings.sharedMagicInventory:meta.runtimeActive!==false;
      if (!enabled) {
        marker.replaceChildren(LexeditorUI.detailNote("Enable GF Spellbooks on the Tweaks page."));
        return;
      }
      if (!runtimeActive) {
        marker.replaceChildren(LexeditorUI.detailNote("GF Spellbooks needs Monogamy on and Shared Party Magic Inventory off. Set these on Tweaks."));
        return;
      }
      spellbookReady=true;
      spellTab?.setAttribute('aria-disabled','false');
      const magic = meta.magicOptions || [];
      const abilities = meta.abilityOptions || [];
      const drafts = window.ff8SpellbookDrafts ||= new Map();
      let pages = clone(drafts.get(gfId) ?? gf.spellbook?.pages ?? []);
      marker.replaceChildren();
      const toolbar = LexeditorUI.actionRow();
      const body = LexeditorUI.stack({fill:false});
      const status = LexeditorUI.detailNote("");
      const setDirty = () => { drafts.set(gfId,pages); status.textContent = "Unsaved spellbook changes"; window.dispatchEvent(new Event("ff8-spellbook-changed")); };
      const usedMagic = (except=null) => new Set(pages.flatMap(page => page).filter(slot => slot !== except).map(slot => slot.magicId));
      const draw = () => {
        toolbar.replaceChildren();
        body.replaceChildren();
        if (!pages.length) {
          toolbar.append(button("ADD PAGE", () => {pages=[[]];setDirty();draw();}));
        } else {
          toolbar.append(
            button("ADD PAGE", () => {if(pages.length < (meta.maxPages||8)){pages.push([]);setDirty();draw();}}, "Maximum eight pages"),
            button("CLEAR PAGES", () => {pages=[];setDirty();draw();})
          );
          pages.forEach((page, pageIndex) => {
            const card = LexeditorUI.detailSection({title:`PAGE ${pageIndex+1}`});
            const cardBody=LexeditorUI.sectionParts(card).content;
            const head = LexeditorUI.actionRow();
            const pageActions = LexeditorUI.actionRow();
            pageActions.append(
              button("↑",()=>{if(pageIndex){[pages[pageIndex-1],pages[pageIndex]]=[pages[pageIndex],pages[pageIndex-1]];setDirty();draw();}},"Move page earlier"),
              button("↓",()=>{if(pageIndex<pages.length-1){[pages[pageIndex+1],pages[pageIndex]]=[pages[pageIndex],pages[pageIndex+1]];setDirty();draw();}},"Move page later"),
              button("REMOVE PAGE",()=>{pages.splice(pageIndex,1);setDirty();draw();})
            );
            head.append(pageActions);
            cardBody.append(head);
            const spellRows=[];
            page.forEach((slot, slotIndex) => {
              const spellChoices = magic.map(entry => ({...entry}));
              const magicSelect = select(spellChoices,slot.magicId,value=>{
                if(value===null)return;
                if(usedMagic(slot).has(value)){status.textContent="A spell can appear only once in this GF's book.";magicSelect.value=String(slot.magicId);return;}
                slot.magicId=value;setDirty();draw();
              });
              const abilitySelect = select(abilities,slot.abilityId,value=>{slot.abilityId=value;setDirty();},"No learned-ability requirement");
              const actions = LexeditorUI.actionRow();
              actions.append(
                button("↑",()=>{if(slotIndex){[page[slotIndex-1],page[slotIndex]]=[page[slotIndex],page[slotIndex-1]];setDirty();draw();}},"Move spell earlier"),
                button("↓",()=>{if(slotIndex<page.length-1){[page[slotIndex+1],page[slotIndex]]=[page[slotIndex],page[slotIndex+1]];setDirty();draw();}},"Move spell later"),
                button("×",()=>{page.splice(slotIndex,1);setDirty();draw();},"Remove spell")
              );
              magicSelect.setAttribute("aria-label",`Spell ${slotIndex+1}`);
              abilitySelect.setAttribute("aria-label",`Required ability for spell ${slotIndex+1}`);
              spellRows.push({id:slotIndex,magicSelect,abilitySelect,actions});
            });
            cardBody.append(LexeditorUI.columnList({rows:spellRows,key:row=>row.id,editable:true,
              template:"minmax(0,1fr) minmax(0,1fr) auto",columns:[
                {key:"magic",label:"Magic",render:row=>row.magicSelect},
                {key:"ability",label:"Required ability",render:row=>row.abilitySelect},
                {key:"actions",label:"",render:row=>row.actions}
              ]}));
            if (page.length < (meta.slotsPerPage||4)) {
              cardBody.append(button("ADD SPELL",()=>{
                const used=usedMagic();const first=magic.find(entry=>!used.has(Number(entry.id)));
                if(!first){status.textContent="No unused spells remain.";return;}
                page.push({magicId:Number(first.id),abilityId:null});setDirty();draw();
              }));
            }
            body.append(card);
          });
        }
        const save = button("SAVE SPELLBOOK", async () => {
          save.disabled = true;
          status.textContent = "Saving…";
          try {
            await request("/api/kernel/save", {
              method:"POST", headers:{"Content-Type":"application/json"},
              body:JSON.stringify({section:3,edits:[{id:gfId,field:"__spellbook",value:pages.length?pages:null}]})
            });
            drafts.delete(gfId);status.textContent="Spellbook saved.";
            window.dispatchEvent(new Event("ff8-spellbook-changed"));
          } catch(error) {status.textContent=error.message;}
          finally {save.disabled=false;}
        });
        toolbar.append(save);
      };
      marker.append(toolbar,body,status);
      draw();
    } catch (error) {
      marker.textContent = `Spellbook unavailable: ${error.message}`;
    }
  };
  const observer = new MutationObserver(() => queueMicrotask(mount));
  const start = () => {observer.observe(document.body,{childList:true,subtree:true});mount();};
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded",start,{once:true});
  else start();
})();
