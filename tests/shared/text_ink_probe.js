// A glyph paints its ink inside its advance box, unless the game's own face is
// bolder than its metrics admit. A DOM Range measures the advance box, so ink
// that hangs outside it is invisible to an element-rect sweep - which is how a
// bold game font kept losing the side of its first letter while every check
// reported nothing. Canvas TextMetrics exposes the real ink box; compare it
// with the box that clips the text.
//
// Horizontal only, and only for a text run on one line: a wrapped run has more
// than one rect, so its ink box no longer describes any single line. Wrapped
// text is the layout sweep's business.
(() => {
  const bad = [];
  const measure = document.createElement("canvas").getContext("2d");

  // Each ancestor that can cut the text off. A roomy inner clip does not
  // guarantee that an outer one leaves the glyphs visible.
  const clipBoxes = node => {
    const boxes=[];
    let containingBlock=null;
    for (let step = node; step; step = step.parentElement) {
      if(containingBlock&&step!==containingBlock)continue;
      containingBlock=null;
      const cs = getComputedStyle(step);
      if (cs.display === "inline" || cs.display === "contents") continue;
      // Scrolling can reveal what an outer container hides, but it cannot
      // restore ink already lost to an inner non-scrolling clip.
      if (/auto|scroll/.test(cs.overflowX)) break;
      // A screen-reader-only box is one pixel square and clipped away on
      // purpose: nothing there is meant to be read on screen.
      if (step.clientWidth <= 2 || step.clientHeight <= 2) break;
      if (/hidden|clip/.test(cs.overflowX)) boxes.push(step);
      // Absolutely positioned text escapes intermediate boxes before its
      // containing block. That block can still be clipped by outer ancestors.
      if(cs.position==='fixed'&&!step.offsetParent)break;
      if(cs.position==='absolute'||cs.position==='fixed')containingBlock=step.offsetParent;
    }
    return boxes;
  };

  for (const node of document.querySelectorAll("*")) {
    const runs = [...node.childNodes].filter(child =>
      child.nodeType === 3 && child.textContent.trim());
    if (!runs.length) continue;
    const cs = getComputedStyle(node);
    if (cs.display === "none" || cs.visibility !== "visible") continue;
    if (node.closest("svg,script,style,option,canvas,textarea")) continue;
    // An ellipsis is a signalled truncation: the reader can see the text was
    // shortened, so it is not this defect.
    if (cs.textOverflow === "ellipsis" && cs.whiteSpace !== "normal"
        && node.scrollWidth > node.clientWidth + 1) continue;
    const clips = clipBoxes(node);
    if (!clips.length) continue;
    measure.font = `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
    if ("letterSpacing" in measure) measure.letterSpacing = cs.letterSpacing;
    for (const run of runs) {
      const value = run.textContent.replace(/\s+/g, " ").trim();
      const metrics = measure.measureText(value);
      const range = document.createRange();
      range.selectNodeContents(run);
      const boxes = [...range.getClientRects()].filter(r => r.width && r.height);
      if (boxes.length !== 1) continue;
      const r = boxes[0];
      // Canvas substitutes a face it cannot resolve, and the substituted
      // advance width is not the rendered one - so its ink box means nothing
      // here. Compare the two advances and drop the run when they disagree.
      if (Math.abs(metrics.width - r.width) > 1) continue;
      const inkLeft = r.left - metrics.actualBoundingBoxLeft;
      const inkRight = r.left + metrics.actualBoundingBoxRight;
      for (const box of clips) {
        const rect = box.getBoundingClientRect();
        const scaleX = box.offsetWidth ? rect.width / box.offsetWidth : 1;
        const left = rect.left + box.clientLeft * scaleX;
        const right = left + box.clientWidth * scaleX;
        const overLeft = left - inkLeft;
        const overRight = inkRight - right;
        // Under three quarters of a device-independent pixel the ink is
        // antialiased across the edge rather than lost, so it is not a cut.
        if (overLeft > 0.75 || overRight > 0.75) {
          bad.push({text:value.slice(0, 60), cls:String(node.className).slice(0, 60),
            tag:node.tagName, clippedBy:String(box.className || box.tagName).slice(0, 60),
            inkLeft:Math.round(inkLeft * 10) / 10, boxLeft:Math.round(left * 10) / 10,
            inkRight:Math.round(inkRight * 10) / 10, boxRight:Math.round(right * 10) / 10,
            overLeft:Math.round(overLeft * 10) / 10, overRight:Math.round(overRight * 10) / 10});
          break;
        }
      }
    }
  }
  return JSON.stringify(bad.slice(0, 100));
})()
