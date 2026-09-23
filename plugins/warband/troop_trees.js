/* Upgrade graphs: pure data/layout code shared by the view and regression tests. */
(function (root) {
  'use strict';
  function build(troops, upgrades) {
    const known = new Map(troops.filter(t => t.status !== 'CUT').map(t => [t.id, t]));
    const nodes = new Map(), edges = [], seenEdges = new Set();
    for (const edge of upgrades) {
      if (!edge.fromId || !edge.toId) continue;
      for (const id of [edge.fromId, edge.toId]) {
        if (!nodes.has(id)) nodes.set(id, {...(known.get(id) || {id, name: id, missing: true}), children: [], parents: []});
      }
      const key = JSON.stringify([edge.fromId, edge.toId]);
      if (seenEdges.has(key)) continue;
      seenEdges.add(key); edges.push({from: edge.fromId, to: edge.toId});
      nodes.get(edge.fromId).children.push(edge.toId); nodes.get(edge.toId).parents.push(edge.fromId);
    }
    const visited = new Set(), trees = [];
    for (const start of [...nodes.keys()].sort()) {
      if (visited.has(start)) continue;
      const ids = [], queue = [start]; visited.add(start);
      for (let i = 0; i < queue.length; i++) {
        const id = queue[i], node = nodes.get(id); ids.push(id);
        for (const next of [...node.parents, ...node.children]) if (!visited.has(next)) { visited.add(next); queue.push(next); }
      }
      const group = ids.map(id => nodes.get(id));
      const roots = group.filter(n => !n.parents.length).sort((a,b) => a.id.localeCompare(b.id));
      const factions = [...new Set(group.map(n => n.faction || 'unassigned'))].sort();
      const set = new Set(ids);
      trees.push({id: ids.slice().sort()[0], nodes: group,
        edges: edges.filter(e => set.has(e.from)), roots: roots.map(n => n.id), factions,
        label: roots.length ? roots.map(n => n.name).join(' / ') : `Cyclic group: ${group[0].name}`});
    }
    return trees.sort((a,b) => a.label.localeCompare(b.label));
  }
  function layout(tree) {
    // Collapse strongly-connected components, so malformed/modded cycles never
    // hang the editor or produce an ever-growing depth calculation.
    const byId = new Map(tree.nodes.map(n => [n.id,n]));
    const index = new Map(), low = new Map(), active = new Set(), stack = [], components = [];
    let counter = 0;
    function visit(id) {
      index.set(id,counter); low.set(id,counter++); stack.push(id); active.add(id);
      for (const child of byId.get(id).children) {
        if (!index.has(child)) { visit(child); low.set(id,Math.min(low.get(id),low.get(child))); }
        else if (active.has(child)) low.set(id,Math.min(low.get(id),index.get(child)));
      }
      if (low.get(id) === index.get(id)) {
        const group = []; let next;
        do { next = stack.pop(); active.delete(next); group.push(next); } while (next !== id);
        components.push(group);
      }
    }
    for (const node of tree.nodes) if (!index.has(node.id)) visit(node.id);
    const owner = new Map(); components.forEach((ids,i) => ids.forEach(id => owner.set(id,i)));
    const children = components.map(() => new Set()), indegree = components.map(() => 0), depth = components.map(() => 0);
    let cyclic = components.some(ids => ids.length > 1);
    for (const e of tree.edges) {
      const a=owner.get(e.from), b=owner.get(e.to);
      if (a===b) { cyclic=true; continue; }
      if (!children[a].has(b)) { children[a].add(b); indegree[b]++; }
    }
    const queue=indegree.flatMap((n,i)=>n===0?[i]:[]);
    for (let i=0;i<queue.length;i++) for (const child of children[queue[i]]) {
      depth[child]=Math.max(depth[child],depth[queue[i]]+1);
      if (--indegree[child]===0) queue.push(child);
    }
    const rows = Array.from({length:Math.max(0,...depth)+1},()=>[]);
    for (const node of tree.nodes) rows[depth[owner.get(node.id)]].push(node);
    rows.forEach(row=>row.sort((a,b)=>a.id.localeCompare(b.id)));
    const width=Math.max(400,...rows.map(row=>row.length*190+24)), height=rows.length*105+30;
    const placed=rows.flatMap((row,d)=>row.map((node,i)=>({...node,
      x:width/2+(i-(row.length-1)/2)*190, y:height-65-d*105})));
    return {nodes:placed, edges:tree.edges, width, height, cyclic};
  }
  const api={build,layout};
  if (typeof module !== 'undefined' && module.exports) module.exports=api;
  else root.WarbandTroopTrees=api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
