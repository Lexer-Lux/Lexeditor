/* Factory kept independent of the editor's page state. The host supplies its
 * existing list/detail, typed controls, provenance, and history helpers. */
window.FF8CardsUI = ({el, state, rowOf, filtered, showPaged, sharedDetail,
  detailSection, detailField, numberControl, selectControl, sourceControl,
  referenceValues, infoHelp, shell, noteFieldEdit}) => {
  const fields = ["top", "bottom", "left", "right", "element", "power"];
  const labels = {top:"Top", bottom:"Bottom", left:"Left", right:"Right", element:"Element", power:"Selection power"};
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
    return sharedDetail(row,prefs,[detailSection({title:"CARD",body:properties})]);
  };
  return {
    render:()=>showPaged("cards",filtered("cards",["id","name"]),[
      {key:"id",label:"ID"},{key:"name",label:"Card"},
      ...fields.map(field=>({key:field,label:labels[field],pinned:false,numeric:true}))
    ],detail,"74px minmax(240px,1fr)"),
    edits:()=>state.data.cards.rows.flatMap(row=>{
      const base=state.base.cards.find(value=>value.id===row.id);
      return fields.filter(field=>row[field]!==base[field])
        .map(field=>({id:row.id,field,value:row[field]}));
    })
  };
};
