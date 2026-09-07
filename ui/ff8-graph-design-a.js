"use strict";
/* Approved graph design A (#299). Keep the formula on the actual curve while
   typesetting powers/fractions as math instead of squeezing outlined SVG text. */
(() => {
  const STYLE_ID = "lex-ff8-graph-design-a-style";
  if (!document.getElementById(STYLE_ID)) {
    const link = document.createElement("link");
    link.id = STYLE_ID;
    link.rel = "stylesheet";
    link.href = "/shared/ff8-graph-design-a.css";
    document.head.append(link);
  }

  const precedence = {"=":1, "+":2, "-":2, "*":3, "/":3, "^":4};
  const normalize = text => String(text || "")
    .replaceAll("−", "-")
    .replaceAll("·", "*")
    .replaceAll("×", "*")
    .replaceAll("⌊", "floor(")
    .replaceAll("⌋", ")")
    .replace(/²/g, "^2");

  function tokenize(source) {
    const text = normalize(source);
    const tokens = [];
    const matcher = /\s*([A-Za-z_][A-Za-z0-9_]*|\d+(?:\.\d+)?|[()+\-*/^=,])\s*/gy;
    let offset = 0;
    while (offset < text.length) {
      matcher.lastIndex = offset;
      const match = matcher.exec(text);
      if (!match || match.index !== offset) throw new Error(`Unsupported formula token at ${offset}`);
      tokens.push(match[1]);
      offset = matcher.lastIndex;
    }
    return tokens;
  }

  function parseFormula(source) {
    const tokens = tokenize(source);
    let index = 0;
    const peek = () => tokens[index];
    const take = expected => {
      const token = tokens[index++];
      if (expected && token !== expected) throw new Error(`Expected ${expected}, got ${token}`);
      return token;
    };
    const primary = () => {
      const token = take();
      if (token === "-") return {kind:"unary", op:"-", value:primary()};
      if (token === "(") {
        const value = expression(0);
        take(")");
        return value;
      }
      if (/^\d/.test(token)) return {kind:"number", value:token};
      if (/^[A-Za-z_]/.test(token)) {
        if (peek() !== "(") return {kind:"identifier", value:token};
        take("(");
        const args = [];
        if (peek() !== ")") {
          for (;;) {
            args.push(expression(0));
            if (peek() !== ",") break;
            take(",");
          }
        }
        take(")");
        return {kind:"call", name:token, args};
      }
      throw new Error(`Unexpected token ${token}`);
    };
    const expression = minimum => {
      let left = primary();
      for (;;) {
        const op = peek();
        const rank = precedence[op] || 0;
        if (rank < minimum || !rank) break;
        take();
        const right = expression(rank + (op === "^" ? 0 : 1));
        left = {kind:"binary", op, left, right};
      }
      return left;
    };
    const result = expression(0);
    if (index !== tokens.length) throw new Error(`Unexpected trailing token ${peek()}`);
    return result;
  }

  const span = (className = "", ...children) => {
    const node = document.createElement("span");
    if (className) node.className = className;
    node.append(...children);
    return node;
  };
  const text = value => document.createTextNode(String(value));

  function mathNode(node, parentRank = 0, side = "") {
    if (node.kind === "number") return text(node.value);
    if (node.kind === "identifier") {
      const key = node.value.toLocaleLowerCase();
      return /^[abcd]$/.test(key)
        ? span(`lex-curve-variable-${key}`, text(node.value))
        : text(node.value);
    }
    if (node.kind === "unary") return span("lex-curve-math-row", text("−"), mathNode(node.value, 5));
    if (node.kind === "call") {
      const children = [text(`${node.name}(`)];
      node.args.forEach((arg, index) => {
        if (index) children.push(text(", "));
        children.push(mathNode(arg, 0));
      });
      children.push(text(")"));
      return span("lex-curve-math-row", ...children);
    }
    if (node.kind !== "binary") return text("");
    if (node.op === "/") {
      return span("lex-curve-math-fraction",
        span("lex-curve-math-numerator", mathNode(node.left, 0)),
        span("lex-curve-math-denominator", mathNode(node.right, 0)));
    }
    if (node.op === "^") {
      const base = mathNode(node.left, precedence["^"], "left");
      const power = document.createElement("sup");
      power.append(mathNode(node.right, 0));
      return span("lex-curve-math-row", base, power);
    }
    const rank = precedence[node.op];
    const symbol = node.op === "*" ? " · " : node.op === "-" ? " − " : ` ${node.op} `;
    const content = span("lex-curve-math-row",
      mathNode(node.left, rank, "left"), text(symbol), mathNode(node.right, rank, "right"));
    const needsParens = rank < parentRank || (side === "right" && rank === parentRank && node.op === "-");
    return needsParens ? span("lex-curve-math-row", text("("), content, text(")")) : content;
  }

  function typeset(source) {
    try {
      return mathNode(parseFormula(source));
    } catch {
      /* A future plugin formula should remain visible even before the parser is
         taught its notation. Preserve it rather than failing the graph. */
      return text(source);
    }
  }

  const pending = new WeakSet();
  const observed = new WeakSet();
  const resizeObserver = new ResizeObserver(entries => {
    for (const entry of entries) schedule(entry.target.closest?.(".ff8-character-curve") || entry.target);
  });

  function position(card) {
    if (!card?.isConnected) return;
    const plot = card.querySelector(".lex-curve-plot");
    const svg = card.querySelector(".lex-curve-svg");
    const line = card.querySelector(".lex-curve-line");
    const source = card.querySelector(".lex-curve-formula")?.textContent?.trim();
    if (!plot || !svg || !line || !source || !line.getAttribute("d")) return;

    let label = plot.querySelector(":scope > .lex-curve-design-a-formula");
    if (!label) {
      label = document.createElement("div");
      label.className = "lex-curve-design-a-formula";
      label.setAttribute("aria-hidden", "true");
      plot.append(label);
    }
    if (label.dataset.formula !== source) {
      label.dataset.formula = source;
      label.replaceChildren(typeset(source));
    }

    let length;
    try { length = line.getTotalLength(); } catch { return; }
    if (!(length > 0) || !svg.getScreenCTM()) return;
    const pointAt = ratio => line.getPointAtLength(length * ratio);
    const toScreen = point => {
      const value = svg.createSVGPoint();
      value.x = point.x; value.y = point.y;
      return value.matrixTransform(svg.getScreenCTM());
    };
    const center = toScreen(pointAt(.5));
    const before = toScreen(pointAt(.47));
    const after = toScreen(pointAt(.53));
    const angle = Math.max(-40, Math.min(40,
      Math.atan2(after.y - before.y, after.x - before.x) * 180 / Math.PI));
    const plotBounds = plot.getBoundingClientRect();
    const svgBounds = svg.getBoundingClientRect();
    label.style.removeProperty("font-size");
    label.style.left = `${center.x - plotBounds.left}px`;
    label.style.top = `${center.y - plotBounds.top}px`;
    label.style.transform = `translate(-50%, calc(-100% - 7px)) rotate(${angle.toFixed(2)}deg)`;

    /* Keep the approved natural weight. Only size gives way when a genuinely
       long equation cannot fit the graph; never letter-space or outline it. */
    const available = Math.max(80, svgBounds.width * .84);
    const width = label.scrollWidth;
    if (width > available) {
      const base = parseFloat(getComputedStyle(label).fontSize) || 10;
      label.style.fontSize = `${Math.max(7.5, base * available / width).toFixed(2)}px`;
    }
    if (!observed.has(card)) {
      observed.add(card);
      resizeObserver.observe(card);
    }
  }

  function schedule(card) {
    if (!card || pending.has(card)) return;
    pending.add(card);
    requestAnimationFrame(() => {
      pending.delete(card);
      position(card);
    });
  }

  function scan(root = document) {
    if (root.matches?.(".ff8-character-curve")) schedule(root);
    root.querySelectorAll?.(".ff8-character-curve").forEach(schedule);
  }

  const observer = new MutationObserver(records => {
    for (const record of records) {
      if (record.type === "attributes") {
        schedule(record.target.closest?.(".ff8-character-curve"));
      } else {
        record.addedNodes.forEach(node => { if (node.nodeType === Node.ELEMENT_NODE) scan(node); });
      }
    }
  });
  observer.observe(document.documentElement, {subtree:true, childList:true, attributes:true, attributeFilter:["d"]});
  scan();
})();
