"""One-shot rendered visual audit for dense FF7 editor views."""
from __future__ import annotations

import json
from pathlib import Path
import unittest

import verify_ff7_rendered_neutral  # installs the neutral/shared open() harness
import verify_ff7_rendered as target

OUT = target.ROOT / "out/ff7-ui-audit"
GROUPS = (
    "initialState", "characters", "recruits", "growthCurves", "materia",
    "materiaEquipEffects", "playerAttacks", "limitBreaks", "enemyAttacks",
    "enemies", "encounters", "shops", "characterAI", "texts", "exeText",
)
SIZES = ((900, 620), (1200, 800))


class VisualAudit(target.RenderedTests):
    def test_dense_views_fit_and_capture(self):
        self.install()
        self.open()
        OUT.mkdir(parents=True, exist_ok=True)
        report = []
        for width, height in SIZES:
            self.page.set_viewport_size({"width": width, "height": height})
            for group in GROUPS:
                with self.subTest(width=width, group=group):
                    self.navigate(group)
                    self.page.wait_for_timeout(80)
                    metrics = self.page.evaluate("""()=>{
                      const detail=document.querySelector('.ff7-detail');
                      const main=document.querySelector('main');
                      const rect=node=>node?node.getBoundingClientRect():null;
                      const tables=[...document.querySelectorAll('.ff7-concept-table')].map(table=>({
                        label:table.getAttribute('aria-label')||'', clientWidth:table.clientWidth,
                        scrollWidth:table.scrollWidth, left:rect(table)?.left, right:rect(table)?.right
                      }));
                      let overlaps=0, clippedControls=0;
                      for(const row of document.querySelectorAll('.ff7-concept-table .lex-column-list-row')){
                        const cells=[...row.querySelectorAll(':scope > .lex-column-list-cell')].map(rect).filter(Boolean);
                        for(let i=0;i+1<cells.length;i++)if(cells[i].right>cells[i+1].left+1)overlaps++;
                      }
                      for(const control of document.querySelectorAll('.ff7-detail input,.ff7-detail select,.ff7-detail textarea,.ff7-detail button')){
                        const r=rect(control);if(r&&r.width>0&&(r.right>innerWidth+2||r.left<-2))clippedControls++;
                      }
                      return {group:window.state.tab,viewportWidth:innerWidth,viewportHeight:innerHeight,
                        documentWidth:document.documentElement.scrollWidth,documentHeight:document.documentElement.scrollHeight,
                        bodyWidth:document.body.scrollWidth,main:rect(main),detail:rect(detail),tables,overlaps,clippedControls};
                    }""")
                    report.append(metrics)
                    self.assertLessEqual(metrics["documentWidth"], width + 2, metrics)
                    self.assertLessEqual(metrics["bodyWidth"], width + 2, metrics)
                    self.assertLessEqual(metrics["detail"]["right"], width + 2, metrics)
                    self.assertEqual(metrics["overlaps"], 0, metrics)
                    self.assertEqual(metrics["clippedControls"], 0, metrics)
                    self.page.screenshot(path=str(OUT / f"{width}x{height}-{group}.png"))
        (OUT / "metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        self.originals_unchanged()


if __name__ == "__main__":
    unittest.main(verbosity=2)
