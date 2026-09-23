"use strict";

// Install before editor.js destructures/mounts the shared shell. This extends
// only Palworld's tab list; rendering/action logic lives in build-ui.js.
(() => {
  const mount = LexeditorUI.mountShell;
  LexeditorUI.mountShell = options => {
    if (options?.plugin?.id === "palworld" && Array.isArray(options.tabs)
        && !options.tabs.some(tab => tab.id === "build")) {
      options = {...options, tabs: [...options.tabs, {id: "build", label: "Build"}]};
    }
    return mount(options);
  };
})();
