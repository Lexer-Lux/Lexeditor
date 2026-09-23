"use strict";
  function renderDashboard(){
    $("#toolbar").replaceChildren();
    const problems=state.dashboard.problems;
    $("#main").replaceChildren(detailPanel({className:"lex-information-panel",icon:LexeditorUI.infoIcon(),title:"Information",meta:"Plugin and path health, mod manuals, and the build log",body:[
      LexeditorUI.detailSection({title:"STATUS",body:problems.length
        ?problems.map(problem=>LexeditorUI.notice({tone:"warning",message:problem}))
        :[LexeditorUI.detailNote("All configured paths found.")]}),
      LexeditorUI.detailSection({title:"MOD MANUALS",body:[LexeditorUI.actionRow(el("button",{type:"button",onclick:()=>navigate("manuals")},"Read installed mod manuals"))]}),
      LexeditorUI.detailSection({title:"LOG",body:[LexeditorUI.logView(state.build.lines.join("")||"No save or build has run in this session.")]}),
      LexeditorUI.modLoaderSection({
        loader:"Warband loads a module folder chosen in its own launcher. There is no separate mod loader.",
        output:"Lexeditor builds a saved module folder under the game's Modules directory; the launcher lists it as its own entry.",
        order:"Only one module runs at a time, so modules do not stack or conflict. Combining changes means building them into one module.",
        safety:"The Native module and the installed game files are never written. A build only ever creates or updates its own module folder.",
        removal:"Pick a different module in the launcher, and delete the generated module folder to remove it entirely.",
      }),
    ]}));
  }
