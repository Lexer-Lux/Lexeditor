// Every piece of visible text on the page that a reader cannot fully read.
//
// Evaluated by tools/visual_snapshot.py in each captured view. A text node is
// a problem when:
//   clipped-y  a box that does not scroll cuts off part of its height;
//   clipped-x  a box that does not scroll cuts off part of its width and does
//              not say so with an ellipsis;
//   tiny       it is drawn smaller than `minimum` CSS pixels.
// Text cut at the edge of a box that scrolls is not a problem: the reader
// scrolls to it. Text entirely outside a box is not drawn at all and is left to
// whatever hid it.
(minimum) => {
  const issues = [];
  const name = element => {
    const parts = [];
    for (let node = element; node && node !== document.body && parts.length < 4; node = node.parentElement) {
      const classes = [...node.classList].filter(c => !/^(active|selected|sel|hover|focus)$/.test(c)).slice(0, 2);
      parts.unshift(node.tagName.toLowerCase() + classes.map(c => "." + c).join(""));
    }
    return parts.join(" > ");
  };
  const clips = value => value === "hidden" || value === "clip";
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const text = walker.currentNode;
    const words = text.textContent.replace(/\s+/g, " ").trim();
    if (!words) continue;
    const element = text.parentElement;
    if (!element || element.closest("script,style,template,svg,option,[hidden],[aria-hidden='true'],.lex-overlay-scrollbar")) continue;
    const style = getComputedStyle(element);
    if (style.visibility !== "visible" || style.color === "rgba(0, 0, 0, 0)" || /transparent/.test(style.color)) continue;
    // Text inside anything fully transparent is not shown - hover-only chrome
    // such as a field's type rail - so it is not text anyone is reading.
    let shown = true;
    for (let node = element; node && node !== document.documentElement; node = node.parentElement) {
      if (Number(getComputedStyle(node).opacity) === 0) { shown = false; break; }
    }
    if (!shown) continue;
    const range = document.createRange();
    range.selectNodeContents(text);
    const rects = [...range.getClientRects()].filter(rect => rect.width > .5 && rect.height > .5);
    if (!rects.length) continue;
    // Fully inside a closed ancestor (display:none higher up gives no rects).
    const size = parseFloat(style.fontSize) || 0;
    if (size && size < minimum) {
      issues.push({kind: "tiny", text: words.slice(0, 60), size: Math.round(size * 10) / 10, where: name(element)});
    }
    let cut = null;
    // An axis stops being checked at the first box that scrolls on it and
    // does not show all of the text: the reader scrolls there, so any box
    // further out cutting the same text is cutting what is scrolled away.
    let reachX = false, reachY = false;
    for (let box = element; box && box !== document.documentElement && !cut; box = box.parentElement) {
      const boxStyle = getComputedStyle(box);
      const scrollsX = /auto|scroll/.test(boxStyle.overflowX), scrollsY = /auto|scroll/.test(boxStyle.overflowY);
      const clipX = clips(boxStyle.overflowX) && !reachX, clipY = clips(boxStyle.overflowY) && !reachY;
      if (!clipX && !clipY && !scrollsX && !scrollsY) continue;
      const outer = box.getBoundingClientRect();
      if (!outer.width || !outer.height) break;
      const left = outer.left + box.clientLeft, top = outer.top + box.clientTop;
      const right = left + box.clientWidth, bottom = top + box.clientHeight;
      if (scrollsX && rects.some(rect => rect.left < left - 1.5 || rect.right > right + 1.5)) reachX = true;
      if (scrollsY && rects.some(rect => rect.top < top - 1.5 || rect.bottom > bottom + 1.5)) reachY = true;
      if (!clipX && !clipY) continue;
      for (const rect of rects) {
        const inside = rect.right > left && rect.left < right && rect.bottom > top && rect.top < bottom;
        if (!inside) continue;
        // Half a pixel of antialiasing is not a clipped letter.
        if (clipY && (rect.top < top - 1.5 || rect.bottom > bottom + 1.5)) {
          cut = {kind: "clipped-y", by: name(box), lost: Math.round(Math.max(top - rect.top, rect.bottom - bottom))};
          break;
        }
        if (clipX && (rect.left < left - 1.5 || rect.right > right + 1.5)) {
          const ellipsis = getComputedStyle(box).textOverflow === "ellipsis" || style.textOverflow === "ellipsis";
          if (!ellipsis) {
            cut = {kind: "clipped-x", by: name(box), lost: Math.round(Math.max(left - rect.left, rect.right - right))};
            break;
          }
        }
      }
    }
    if (cut) issues.push({...cut, text: words.slice(0, 60), where: name(element)});
  }
  return issues;
}
