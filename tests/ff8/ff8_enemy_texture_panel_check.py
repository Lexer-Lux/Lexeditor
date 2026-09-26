"""An enemy's own texture pages stand in the enemy's own panel.

Lexer: "why is clicking the thumbnail taking me to a page with textures. that
info, specific to the enemy, should just be in the details panel!!! if i open
the model viewer on an enemy it should show me the enemy!!!" and "why is the
thumbnail preview thing on the other side of the header."

The panel used to open with the shared "No image" box on the right of the
heading, and both the box and the model preview led to the Textures page. This
renders the real Enemies page from the installed game and checks what a reader
gets now: the enemy's first texture page as the heading's own picture, on the
left with the record; a TEXTURES section in the panel; and a preview that shows
the enemy's pages where the reader already is.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(r"C:\RDR2Mod\tools\reverse-engineering")))

from plugins.ff8.plugin import FF8Session  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from tests.shared.verify_panel_layout_visual_46 import (  # noqa: E402
    browser_session, close_browser, screenshot, wait_eval,
)


def main() -> int:
    project = tempfile.TemporaryDirectory(prefix="lexeditor-ff8-enemy-textures-",
                                          ignore_cleanup_errors=True)
    profile = browser = cdp = None
    try:
        profile, browser, cdp = browser_session()
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project.name}) as session:
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 120)
            # Pick an enemy whose battle model has texture pages, using the same
            # first-match lookup the panel uses for the enemy's model.
            with_model = cdp.eval("""(()=>{const byEnemy=new Map();
              for(const row of state.data.models?.rows||[]){const id=Number(row.enemyId);
                if(Number.isFinite(id)&&!byEnemy.has(id))byEnemy.set(id,row);}
              const enemy=(state.data.enemies.rows||[])
                .find(entry=>(byEnemy.get(Number(entry.id))?.tims||[]).length);
              if(!enemy)return null;state.selected.enemies=enemy.id;navigate('enemies');
              return enemy.id})()""")
            assert with_model is not None, "no enemy in the installed data has a model"
            # The detail pane rebuilds after the selection, so wait for the
            # chosen enemy's own panel rather than the one before it.
            wait_eval(cdp, "(()=>{const panel=document.querySelector('.enemy-detail');"
                           "if(!panel)return false;"
                           f"if(Number(state.selected.enemies)!=={with_model})return false;"
                           "return panel.querySelector('.lex-detail-panel-icon')!==null})()", 30)
            wait_eval(cdp, "document.querySelector('.enemy-detail .lex-detail-section-title')!==null", 30)
            rendered = cdp.eval("""(()=>{const panel=document.querySelector('.enemy-detail'),
              icon=panel.querySelector('.lex-detail-panel-icon'),title=panel.querySelector('.lex-detail-panel-title'),
              image=icon?.querySelector('img'),
              sections=[...panel.querySelectorAll('.lex-detail-section-title')].map(node=>node.textContent.trim()),
              cards=panel.querySelectorAll('.lex-detail-section .lex-icon-slot').length,
              links=panel.querySelectorAll('.lex-detail-section .lex-hoverable').length;
              return {iconImage:!!image,imageSource:image?image.getAttribute('src'):'',
                iconLeft:icon?Math.round(icon.getBoundingClientRect().left):null,
                titleLeft:title?Math.round(title.getBoundingClientRect().left):null,
                sections,cards,links,tab:state.tab}})()""")
            assert rendered["iconImage"], rendered
            assert "battle" in rendered["imageSource"] and "texture.png" in rendered["imageSource"], rendered
            assert rendered["iconLeft"] < rendered["titleLeft"], rendered
            # The section's own question mark rides inside its title element.
            assert any(name.startswith("TEXTURES") for name in rendered["sections"]), rendered
            assert rendered["cards"] >= 1, rendered
            assert rendered["links"] == 0, ("a panel card still leaves for another page", rendered)

            # The heading picture is the model preview trigger, and what it opens
            # is the enemy's own pages where the reader already stands.
            cdp.eval("document.querySelector('.enemy-detail .lex-detail-panel-icon').click()")
            wait_eval(cdp, "document.querySelector('.lex-model-preview-drawer')!==null", 15)
            drawer = cdp.eval("""(()=>{const drawer=document.querySelector('.lex-model-preview-drawer');
              return {text:drawer.innerText.slice(0,120),cards:drawer.querySelectorAll('.lex-icon-slot').length,
                links:drawer.querySelectorAll('.lex-hoverable').length,tab:state.tab}})()""")
            assert drawer["cards"] >= 1 and drawer["links"] == 0, drawer
            assert "Texture 1" in drawer["text"], drawer
            assert drawer["tab"] == "enemies", drawer
            image = screenshot(cdp, "ff8-enemy-textures.png")
            print(json.dumps({"enemy": with_model, "rendered": rendered, "drawer": drawer,
                              "screenshot": str(image)}))
        return 0
    finally:
        if profile:
            close_browser(profile, browser, cdp)
        project.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
