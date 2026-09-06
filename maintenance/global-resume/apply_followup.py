from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
framework = ROOT / "ui/framework.js"
text = framework.read_text("utf-8")

if "const controlHelp = control =>" not in text:
    needle = "  const infoHelp = (text, attrs = {}) => {\n"
    helper = r'''  // Every interactive control gets a concise native tooltip even when a plugin
  // has no richer ?-marker description. We only derive facts visible in the DOM
  // (label, type, bounds, unit and authored apply requirement); we never guess
  // undocumented gameplay semantics from a field name.
  const controlHelp = control => {
    if (!(control instanceof Element) || !control.matches("button,input,select,textarea,[role='button'],[role='slider'],[role='separator']")) return "";
    const authored = String(control.getAttribute("aria-description") || "").trim();
    if (authored) return authored;
    const explicit = String(control.getAttribute("aria-label") || "").trim();
    const labelNode = control.labels?.[0] || control.closest?.("label");
    const fieldLabel = control.closest?.(".lex-detail-field")?.querySelector?.(".lex-detail-field-label");
    const visible = control.matches("button,[role='button']") ? String(control.textContent || "").trim() : "";
    const placeholder = String(control.getAttribute("placeholder") || "").trim();
    const name = (explicit || labelNode?.textContent || fieldLabel?.textContent || visible || placeholder)
      ?.replace(/\s+/g, " ").trim();
    if (!name) return "";
    let text;
    const type = String(control.getAttribute("type") || "").toLocaleLowerCase();
    if (control.matches("button,[role='button']")) text = name.endsWith(".") ? name : `${name}.`;
    else if (type === "checkbox" || type === "radio") text = `Enable or disable ${name}.`;
    else if (control.tagName === "SELECT") text = `Choose ${name}.`;
    else if (type === "range" || type === "number" || control.getAttribute("role") === "slider") text = `Set ${name}.`;
    else if (control.getAttribute("role") === "separator") text = `Resize ${name}.`;
    else text = `Edit ${name}.`;
    const facts = [];
    const min = control.getAttribute("min") ?? control.getAttribute("aria-valuemin");
    const max = control.getAttribute("max") ?? control.getAttribute("aria-valuemax");
    const step = control.getAttribute("step");
    if (min !== null && max !== null && min !== "" && max !== "") facts.push(`Range: ${min} to ${max}.`);
    else if (min !== null && min !== "") facts.push(`Minimum: ${min}.`);
    else if (max !== null && max !== "") facts.push(`Maximum: ${max}.`);
    if (step && step !== "any" && !["checkbox","radio"].includes(type)) facts.push(`Step: ${step}.`);
    const unit = control.closest?.(".lex-unit-field")?.querySelector?.(".lex-unit")?.textContent?.trim();
    if (unit) facts.push(`Unit: ${unit}.`);
    const apply = control.dataset?.lexApplyRequirement || control.closest?.("[data-lex-apply-requirement]")?.dataset?.lexApplyRequirement;
    if (apply) facts.push(`Apply: ${String(apply).trim()}`);
    return [text, ...facts].join(" ");
  };

  const installControlHelp = (root = document.body) => {
    const annotate = node => {
      if (!(node instanceof Element)) return;
      const controls = [node.matches?.("button,input,select,textarea,[role='button'],[role='slider'],[role='separator']") ? node : null,
        ...node.querySelectorAll?.("button,input,select,textarea,[role='button'],[role='slider'],[role='separator']") || []].filter(Boolean);
      controls.forEach(control => {
        if (control.title) return;
        const text = controlHelp(control);
        if (!text) return;
        control.title = text;
        if (!control.getAttribute("aria-description") && !control.matches("button,[role='button']")) control.setAttribute("aria-description", text);
      });
    };
    annotate(root);
    if (typeof MutationObserver !== "function") return () => {};
    const observer = new MutationObserver(records => records.forEach(record => record.addedNodes.forEach(annotate)));
    observer.observe(root, {childList:true, subtree:true});
    return () => observer.disconnect();
  };

'''
    if needle not in text:
        raise SystemExit("infoHelp insertion point changed")
    text = text.replace(needle, helper + needle, 1)

if "const removeControlHelp = installControlHelp(document.body);" not in text:
    needle = '''    nav.addEventListener("pointerout", event => {\n      const button = event.target.closest?.("button[data-tab]");\n      if (button && !button.contains(event.relatedTarget)) {\n        button.querySelector(".lex-tab-ordinal")?.remove();\n      }\n    });\n\n    return {\n'''
    replacement = '''    nav.addEventListener("pointerout", event => {\n      const button = event.target.closest?.("button[data-tab]");\n      if (button && !button.contains(event.relatedTarget)) {\n        button.querySelector(".lex-tab-ordinal")?.remove();\n      }\n    });\n\n    const removeControlHelp = installControlHelp(document.body);\n    window.addEventListener("pagehide", removeControlHelp, {once:true});\n\n    return {\n'''
    if needle not in text:
        raise SystemExit("mountShell insertion point changed")
    text = text.replace(needle, replacement, 1)

old = "window.LexeditorUI = {element, el: element, newButton, infoHelp, creditsPanel"
new = "window.LexeditorUI = {element, el: element, newButton, infoHelp, controlHelp, installControlHelp, creditsPanel"
if old in text:
    text = text.replace(old, new, 1)
elif new not in text:
    raise SystemExit("LexeditorUI export changed")
framework.write_text(text, "utf-8")

test_path = ROOT / "tests/global_controls_check.py"
test = test_path.read_text("utf-8")
needle = "        assert page.locator('#add').get_attribute('aria-label') == 'Add record'\n"
if "#auto-help" not in test:
    insert = '''        assert page.locator('#add').get_attribute('aria-label') == 'Add record'\n        page.evaluate('LexeditorUI.installControlHelp(document.body)')\n        assert page.locator('#add').get_attribute('title') == 'Add record'\n        page.evaluate("""()=>{const U=LexeditorUI,e=U.el;const wrap=e('label',{},'Opacity',e('input',{id:'auto-help',type:'number',min:0,max:100,step:5}));document.querySelector('#main').append(wrap)}""")\n        page.wait_for_timeout(20)\n        assert page.locator('#auto-help').get_attribute('title') == 'Set Opacity. Range: 0 to 100. Step: 5.'\n'''
    if needle not in test:
        raise SystemExit("control test insertion point changed")
    test = test.replace(needle, insert, 1)
if "'automatic_control_tooltips':'pass'" not in test:
    old = "'settings_save_discard_isolation_and_visible_failure':'pass','history_cancellation_and_failure':'pass',"
    new = "'settings_save_discard_isolation_and_visible_failure':'pass','automatic_control_tooltips':'pass','history_cancellation_and_failure':'pass',"
    if old not in test:
        raise SystemExit("results insertion point changed")
    test = test.replace(old, new, 1)
test_path.write_text(test, "utf-8")
