"use strict";
(() => {
  const shared = LexeditorUI.showAlert;
  if (typeof shared !== "function") return;
  LexeditorUI.showAlert = (first, second) => {
    if (first && typeof first === "object" && !Array.isArray(first)) return shared(first);
    return shared({
      title: String(second || "Bannerlord"),
      message: String(first ?? ""),
    });
  };
})();
