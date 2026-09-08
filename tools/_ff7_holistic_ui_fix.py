from pathlib import Path

path=Path(__file__).resolve().parents[1]/'games/ff7/editor.html'
text=path.read_text(encoding='utf-8')
old='''  function growthCurvePreview(row){const values=Array.from({length:98},(_,i)=>growthCurveValue(row,i+2)),min=Math.min(...values),max=Math.max(...values),span=Math.max(1,max-min),points=values.map((value,i)=>`${(i*100/(values.length-1)).toFixed(2)},${(32-(value-min)*30/span).toFixed(2)}`),svg=el("svg",{viewBox:"0 0 100 34",role:"img","aria-label":`${row.name} curve preview`,preserveAspectRatio:"none"},el("title",{},`${row.name}: ${min} to ${max}`),el("polyline",{points:points.join(" "),fill:"none",stroke:"currentColor","stroke-width":"1.2","vector-effect":"non-scaling-stroke"}));return el("div",{},svg,el("small",{},`Level 2–99 preview · ${min} → ${max}`))}\n'''
new='''  function growthCurvePreview(row){const values=Array.from({length:98},(_,i)=>growthCurveValue(row,i+2)),min=Math.min(...values),max=Math.max(...values),span=Math.max(1,max-min),points=values.map((value,i)=>`${(i*100/(values.length-1)).toFixed(2)},${(32-(value-min)*30/span).toFixed(2)}`),ns="http://www.w3.org/2000/svg",svg=document.createElementNS(ns,"svg"),title=document.createElementNS(ns,"title"),line=document.createElementNS(ns,"polyline");svg.setAttribute("viewBox","0 0 100 34");svg.setAttribute("role","img");svg.setAttribute("aria-label",`${row.name} curve preview`);svg.setAttribute("preserveAspectRatio","none");title.textContent=`${row.name}: ${min} to ${max}`;line.setAttribute("points",points.join(" "));line.setAttribute("fill","none");line.setAttribute("stroke","currentColor");line.setAttribute("stroke-width","1.2");line.setAttribute("vector-effect","non-scaling-stroke");svg.append(title,line);return el("div",{},svg,el("small",{},`Level 2–99 preview · ${min} → ${max}`))}\n'''
if new not in text:
    if old not in text: raise SystemExit('growth preview insertion point changed')
    text=text.replace(old,new,1)
path.write_text(text,encoding='utf-8')
