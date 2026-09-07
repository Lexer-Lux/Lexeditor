/* Factory kept independent of the editor's page state. The host supplies its
 * existing list/detail, typed controls, provenance, and history helpers. */
window.FF8CardsUI = ({el, state, rowOf, filtered, showPaged, sharedDetail,
  detailSection, detailField, numberControl, selectControl, sourceControl,
  referenceValues, infoHelp, shell, noteFieldEdit}) => {
  const fields = ["top", "bottom", "left", "right", "element", "power"];
  const labels = {top:"Top", bottom:"Bottom", left:"Left", right:"Right", element:"Element", power:"Selection power"};
  const clone = value => JSON.parse(JSON.stringify(value));
  let mode = "cards", playerMap = "", playerData = null, playerBase = null,
      playerLoading = false, playerError = "", playerStatus = "";
  if (!document.getElementById("ff8-card-redesign-style")) {
    const style = document.createElement("style");
    style.id = "ff8-card-redesign-style";
    style.textContent = `
      .ff8-card-root{display:grid;grid-template-rows:auto minmax(0,1fr);height:100%;min-height:0}
      .ff8-card-tabs{display:flex;gap:8px;margin:0 0 10px}.ff8-card-tabs button[aria-pressed="true"]{font-weight:800;text-decoration:underline}
      .ff8-card-preview{position:relative;width:min(260px,72vw);aspect-ratio:3/4;margin:3px auto 10px;overflow:hidden;border-radius:8px;background:#111;box-shadow:0 0 0 1px rgba(180,200,240,.35)}
      .ff8-card-preview img{width:100%;height:100%;display:block;object-fit:cover;image-rendering:auto}
      .ff8-card-rank{position:absolute;font:800 21px/1 var(--ui-font,Arial,sans-serif);text-shadow:0 1px 2px #000,0 0 3px #000;color:#fff;min-width:24px;text-align:center}
      .ff8-card-rank.top{top:8px;left:50%;transform:translateX(-50%)}.ff8-card-rank.right{right:8px;top:50%;transform:translateY(-50%)}
      .ff8-card-rank.bottom{bottom:8px;left:50%;transform:translateX(-50%)}.ff8-card-rank.left{left:8px;top:50%;transform:translateY(-50%)}
      .ff8-card-element{position:absolute;right:8px;bottom:8px;padding:3px 6px;border-radius:999px;background:rgba(0,0,0,.72);font-size:11px;font-weight:700}
      .ff8-card-player-toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:10px}.ff8-card-player-toolbar select{min-width:min(430px,75vw)}
      .ff8-card-player{border:1px solid rgba(160,180,215,.28);border-radius:7px;padding:9px;margin:8px 0}.ff8-card-player h4{margin:0 0 7px}
      .ff8-card-player-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:8px}.ff8-card-player-field{display:grid;gap:3px;font-size:11px}.ff8-card-player-field input{width:100%}
      .ff8-card-player-mode{opacity:.72;font-size:10px}
    `;
    document.head.append(style);
  }
  const rank = value => Number(value) === 10 ? "A" : String(value);
  const preview = row => {
    const options = state.data.cards.elements || [];
    const element = options.find(entry => Number(entry.id) === Number(row.element));
    return el("div",{class:"ff8-card-preview"},
      el("img",{src:`/assets/cards/${row.id}.png`,alt:`${row.name} card artwork`}),
      ...["top","right","bottom","left"].map(side=>el("span",{class:`ff8-card-rank ${side}`},rank(row[side]))),
      element && Number(row.element) !== 255 ? el("span",{class:"ff8-card-element",title:"Element"},element.name) : null);
  };
  const detail = (row, prefs) => {
    const vanilla = rowOf(state.vanilla, "cards", row.id);
    const properties = fields.map(field => {
      const update = value => {row[field] = Number(value);noteFieldEdit("cards", {field});};
      const options = state.data.cards.elements.map(entry => ({value:entry.id, name:entry.name}));
      const control = field === "element"
        ? selectControl(row[field], options, update)
        : numberControl(row[field], 0, field === "power" ? 255 : 10, 1, update,
          {"aria-label":`${row.name} ${labels[field]}`});
      const format = value => field === "element"
        ? options.find(entry => entry.value === Number(value))?.name || value
        : Number(value) === 10 && field !== "power" ? "A" : value;
      return detailField({label:labels[field].toUpperCase(),
        help:infoHelp(field === "power"
          ? "When you lose, the opponent prefers a card with a higher selection power."
          : field === "element" ? "The card's element under the Elemental rule."
          : "The value on this side of the card. Ten appears as A in Triple Triad."),
        control:sourceControl(control,()=>row[field],vanilla[field],
          referenceValues("cards",row.id,value=>value?.[field]),update,format)});
    });
    const name = el("input", {type:"text",value:row.name,"aria-label":"Card name",oninput:event=>{
      row.name=event.target.value;
      const text=state.data.text.rows.find(value=>value.source==="exe_card_names"&&value.recordId===row.id);
      if(text)text.value=row.name;
      shell.refresh();
    }});
    properties.unshift(detailField({label:"NAME",control:sourceControl(name,()=>row.name,vanilla.name,
      referenceValues("cards",row.id,value=>value?.name),value=>{
        row.name=String(value);
        const text=state.data.text.rows.find(entry=>entry.source==="exe_card_names"&&entry.recordId===row.id);
        if(text)text.value=row.name;
      })}));
    return sharedDetail(row,prefs,[
      detailSection({title:"PREVIEW",body:[preview(row)]}),
      detailSection({title:"CARD",body:properties})
    ]);
  };
  const renderCards = () => showPaged("cards",filtered("cards",["id","name"]),[
    {key:"id",label:"ID"},{key:"name",label:"Card"},
    ...fields.map(field=>({key:field,label:labels[field],pinned:false,numeric:true}))
  ],detail,"74px minmax(240px,1fr)",{},false);
  let render = () => null;
  const loadPlayerMap = async key => {
    if (!key || playerLoading) return;
    playerLoading=true;playerError="";playerStatus="";
    try {
      const response=await fetch(`/api/field?map=${encodeURIComponent(key)}&dataset=current`);
      const payload=await response.json();
      if(!response.ok||payload.error)throw new Error(payload.error||`HTTP ${response.status}`);
      if(playerMap!==key)return;
      playerData=payload;playerBase=clone(payload);
    } catch(error) {if(playerMap===key)playerError=error.message;}
    finally {playerLoading=false;if(state.tab==="cards")render();}
  };
  const savePlayers = async () => {
    if(!playerData||!playerBase)return;
    const edits=[];
    for(const player of playerData.players||[])for(const param of player.params||[]){
      const before=playerBase.players?.[player.id]?.params?.[param.id];
      if(before&&Number(before.value)!==Number(param.value))edits.push({map:playerData.key,player:player.id,param:param.id,value:Number(param.value)});
    }
    if(!edits.length){playerStatus="No player changes to save.";render();return;}
    try {
      const response=await fetch("/api/field/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({edits})});
      const payload=await response.json();
      if(!response.ok||payload.error)throw new Error(payload.error||`HTTP ${response.status}`);
      playerBase=clone(playerData);playerStatus=`Saved ${edits.length} CARDGAME parameter change${edits.length===1?"":"s"}.`;
    } catch(error) {playerStatus=error.message;}
    render();
  };
  const renderPlayers = () => {
    const maps=state.data.fields?.rows||[];
    if(!playerMap&&maps.length)playerMap=maps[0].key;
    if(playerMap&&!playerData&&!playerLoading)queueMicrotask(()=>loadPlayerMap(playerMap));
    const selector=el("select",{value:playerMap,onchange:event=>{
      playerMap=event.target.value;playerData=null;playerBase=null;playerError="";playerStatus="";render();
    }},...maps.map(row=>el("option",{value:row.key,selected:row.key===playerMap},`${row.name} — ${row.key}`)));
    const toolbar=el("div",{class:"ff8-card-player-toolbar"},
      el("strong",{},"FIELD"),selector,
      playerData?el("button",{type:"button",onclick:savePlayers},"SAVE PLAYERS"):null);
    let content;
    if(playerLoading)content=el("div",{},"Loading field card players…");
    else if(playerError)content=el("div",{},`Players unavailable: ${playerError}`);
    else if(!playerData)content=el("div",{},"Choose a field to inspect its Triple Triad opponents.");
    else if(!(playerData.players||[]).length)content=el("div",{},"This field has no CARDGAME calls.");
    else content=el("div",{},...(playerData.players||[]).map(player=>el("section",{class:"ff8-card-player"},
      el("h4",{},`${player.entity} :: ${player.script}`),
      el("div",{class:"ff8-card-player-grid"},...player.params.map(param=>el("label",{class:"ff8-card-player-field"},
        el("span",{},param.name),
        el("input",{type:"number",min:0,max:16777215,step:1,value:param.value,disabled:!param.editable,oninput:event=>{param.value=Number(event.target.value);playerStatus="Unsaved player changes";}}),
        el("span",{class:"ff8-card-player-mode"},param.mode==="variable"?`savemap variable ${param.value}`:param.mode)))))));
    return el("div",{},toolbar,
      el("p",{class:"muted"},"NPC card-player data comes from the seven fixed-size values immediately before field opcode CARDGAME (0x13A). Variable pushes remain variables; Lexeditor changes only their stored value."),
      content,el("div",{class:"ff8-card-player-mode"},playerStatus));
  };
  render = () => {
    if(state.tab!=="cards")return null;
    const root=el("div",{class:"ff8-card-root"},
      el("div",{class:"ff8-card-tabs"},
        el("button",{type:"button","aria-pressed":mode==="cards",onclick:()=>{mode="cards";render();}},"CARDS"),
        el("button",{type:"button","aria-pressed":mode==="players",onclick:()=>{mode="players";render();}},"PLAYERS")),
      mode==="players"?renderPlayers():renderCards());
    document.querySelector("#main")?.replaceChildren(root);
    shell.refresh();
    return root;
  };
  return {
    render,
    edits:()=>state.data.cards.rows.flatMap(row=>{
      const base=state.base.cards.find(value=>value.id===row.id);
      return fields.filter(field=>row[field]!==base[field])
        .map(field=>({id:row.id,field,value:row[field]}));
    })
  };
};

/* Issue #93 extension. The main FF8 editor already loads this module on every
 * page, so the spellbook editor can attach to the existing GF detail surface
 * without duplicating the 300KB host document or creating a second GF editor. */
(() => {
  const STYLE_ID = "lexeditor-gf-spellbook-style";
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
  const ensureStyle = () => {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = `
      .${PANEL_CLASS}{margin-top:14px;padding:12px;border:1px solid var(--border,#52627c);border-radius:8px;background:rgba(0,0,0,.12)}
      .${PANEL_CLASS} h3{margin:0 0 5px;font-size:14px;letter-spacing:.05em}
      .${PANEL_CLASS} .lex-spell-note{opacity:.78;font-size:12px;margin:0 0 10px}
      .${PANEL_CLASS} .lex-spell-toolbar,.${PANEL_CLASS} .lex-spell-page-head,.${PANEL_CLASS} .lex-spell-row{display:flex;gap:7px;align-items:center;flex-wrap:wrap}
      .${PANEL_CLASS} .lex-spell-toolbar{margin:8px 0}
      .${PANEL_CLASS} .lex-spell-page{padding:8px;margin:8px 0;border:1px solid rgba(160,180,215,.28);border-radius:6px}
      .${PANEL_CLASS} .lex-spell-page-head{justify-content:space-between;margin-bottom:6px;font-size:12px;font-weight:700}
      .${PANEL_CLASS} .lex-spell-row{display:grid;grid-template-columns:28px minmax(150px,1fr) minmax(160px,1fr) auto;margin:5px 0}
      .${PANEL_CLASS} select{min-width:0;width:100%}
      .${PANEL_CLASS} button{white-space:nowrap}
      .${PANEL_CLASS} .lex-spell-status{font-size:12px;min-height:1.3em}
      @media(max-width:760px){.${PANEL_CLASS} .lex-spell-row{grid-template-columns:28px 1fr}.${PANEL_CLASS} .lex-spell-row select{grid-column:2}.${PANEL_CLASS} .lex-spell-actions{grid-column:2}}
    `;
    document.head.append(style);
  };
  const mount = async () => {
    const host = document.querySelector("#gf-detail[data-gf]");
    if (!host || host.querySelector(`.${PANEL_CLASS}`)) return;
    const gfId = Number(host.dataset.gf);
    if (!Number.isInteger(gfId) || gfId < 0 || gfId > 15) return;
    const marker = document.createElement("div");
    marker.className = PANEL_CLASS;
    marker.dataset.gf = String(gfId);
    marker.textContent = "Loading GF spellbook…";
    host.append(marker);
    ensureStyle();
    try {
      const payload = await request("/api/kernel?section=3&dataset=current");
      if (!marker.isConnected || Number(host.dataset.gf) !== gfId) return;
      const gf = payload.rows?.find(row => Number(row.id) === gfId);
      if (!gf) throw new Error(`GF ${gfId} is unavailable`);
      const meta = payload.spellbook || {};
      const magic = meta.magicOptions || [];
      const abilities = meta.abilityOptions || [];
      let pages = clone(gf.spellbook?.pages || []);
      let dirty = false;
      marker.replaceChildren();
      const title = document.createElement("h3");
      title.textContent = "SPELLBOOK";
      const note = document.createElement("p");
      note.className = "lex-spell-note";
      note.textContent = "Ordered Magic pages for this GF. Zero-stock spells remain visible but disabled in battle. Optional requirements use abilities learned by this GF. Runtime requires Single GF and Shared Magic off.";
      const toolbar = document.createElement("div");
      toolbar.className = "lex-spell-toolbar";
      const body = document.createElement("div");
      const status = document.createElement("div");
      status.className = "lex-spell-status";
      const setDirty = () => { dirty = true; status.textContent = "Unsaved spellbook changes"; };
      const usedMagic = (except=null) => new Set(pages.flatMap(page => page).filter(slot => slot !== except).map(slot => slot.magicId));
      const draw = () => {
        toolbar.replaceChildren();
        body.replaceChildren();
        if (!pages.length) {
          toolbar.append(button("ENABLE SPELLBOOK", () => {pages=[[]];setDirty();draw();}));
          const empty = document.createElement("div");
          empty.className = "lex-spell-note";
          empty.textContent = "No custom book: FF8 uses its native Magic stock list.";
          body.append(empty);
        } else {
          toolbar.append(
            button("ADD PAGE", () => {if(pages.length < (meta.maxPages||8)){pages.push([]);setDirty();draw();}}, "Maximum eight pages"),
            button("DISABLE", () => {pages=[];setDirty();draw();})
          );
          pages.forEach((page, pageIndex) => {
            const card = document.createElement("div");
            card.className = "lex-spell-page";
            const head = document.createElement("div");
            head.className = "lex-spell-page-head";
            const name = document.createElement("span");
            name.textContent = `PAGE ${pageIndex+1}`;
            const pageActions = document.createElement("span");
            pageActions.append(
              button("↑",()=>{if(pageIndex){[pages[pageIndex-1],pages[pageIndex]]=[pages[pageIndex],pages[pageIndex-1]];setDirty();draw();}},"Move page earlier"),
              button("↓",()=>{if(pageIndex<pages.length-1){[pages[pageIndex+1],pages[pageIndex]]=[pages[pageIndex],pages[pageIndex+1]];setDirty();draw();}},"Move page later"),
              button("REMOVE PAGE",()=>{pages.splice(pageIndex,1);setDirty();draw();})
            );
            head.append(name,pageActions);
            card.append(head);
            page.forEach((slot, slotIndex) => {
              const row = document.createElement("div");
              row.className = "lex-spell-row";
              const index = document.createElement("span");
              index.textContent = String(slotIndex+1);
              const spellChoices = magic.map(entry => ({...entry}));
              const magicSelect = select(spellChoices,slot.magicId,value=>{
                if(value===null)return;
                if(usedMagic(slot).has(value)){status.textContent="A spell can appear only once in this GF's book.";magicSelect.value=String(slot.magicId);return;}
                slot.magicId=value;setDirty();draw();
              });
              const abilitySelect = select(abilities,slot.abilityId,value=>{slot.abilityId=value;setDirty();},"No learned-ability requirement");
              const actions = document.createElement("span");
              actions.className = "lex-spell-actions";
              actions.append(
                button("↑",()=>{if(slotIndex){[page[slotIndex-1],page[slotIndex]]=[page[slotIndex],page[slotIndex-1]];setDirty();draw();}},"Move spell earlier"),
                button("↓",()=>{if(slotIndex<page.length-1){[page[slotIndex+1],page[slotIndex]]=[page[slotIndex],page[slotIndex+1]];setDirty();draw();}},"Move spell later"),
                button("×",()=>{page.splice(slotIndex,1);setDirty();draw();},"Remove spell")
              );
              row.append(index,magicSelect,abilitySelect,actions);
              card.append(row);
            });
            if (page.length < (meta.slotsPerPage||4)) {
              card.append(button("ADD SPELL",()=>{
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
            dirty=false;status.textContent="Spellbook saved. Save Gameplay settings too if you changed Single GF / Shared Magic.";
          } catch(error) {status.textContent=error.message;}
          finally {save.disabled=false;}
        });
        toolbar.append(save);
      };
      marker.append(title,note,toolbar,body,status);
      draw();
      window.addEventListener("beforeunload", event => {if(dirty){event.preventDefault();event.returnValue="";}}, {once:true});
    } catch (error) {
      marker.textContent = `Spellbook unavailable: ${error.message}`;
    }
  };
  const observer = new MutationObserver(() => queueMicrotask(mount));
  const start = () => {observer.observe(document.body,{childList:true,subtree:true});mount();};
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded",start,{once:true});
  else start();
})();