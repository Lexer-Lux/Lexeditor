"""Apply an exact reviewed transport patch without overwriting the newer Blank Data Map."""
import base64
import gzip
import hashlib
from pathlib import Path
import subprocess


def replace_once(path, old, new):
    p=Path(path); text=p.read_text('utf-8')
    if new in text: return
    assert text.count(old)==1, f'Unreviewed context: {path}: {old[:80]}'
    p.write_text(text.replace(old,new),'utf-8')


if not Path('tests/test_global_followup.py').exists():
    encoded=''.join(Path(f'maintenance/global-followup/part{n}.b64').read_text().strip() for n in range(2))
    encoded=encoded.replace('TKCw9Xlye0rpbTKCw9Xlye0rpb5','TKCw9Xlye0rpb5')
    patch=gzip.decompress(base64.b64decode(encoded,validate=True))
    assert len(patch)==44407
    assert hashlib.sha256(patch).hexdigest()=='bf2727e925e8dbcc198424bc3fb227dfc583393e2ff3dbfb94a7d83ce6fcf397'
    expected={'docs/ADDING_A_GAME.md','docs/SHARED_UI_DESIGN.md','games/blank/editor.html','games/rdr2/editor.html','service_session.py','tests/global_design_review_check.py','tests/test_global_followup.py','tools/generate_credits.py','ui/design-review.css','ui/design-review.js','ui/framework.js'}
    assert {line[6:] for line in patch.decode().splitlines() if line.startswith('+++ b/')}==expected
    p=Path('/tmp/global-followup.patch');p.write_bytes(patch)
    subprocess.run(['git','apply','--check','--exclude=games/blank/editor.html',str(p)],check=True)
    subprocess.run(['git','apply','--exclude=games/blank/editor.html',str(p)],check=True)
    # Preserve the newer Data Map and every other tab; add only the reviewed
    # opt-in design tab and its two resources.
    blank='games/blank/editor.html'
    replace_once(blank,'<link rel="stylesheet" href="/shared/framework.css">','<link rel="stylesheet" href="/shared/framework.css">\n  <link rel="stylesheet" href="/shared/design-review.css">')
    replace_once(blank,'<script src="/shared/framework.js"></script>','<script src="/shared/framework.js"></script>\n  <script src="/shared/design-review.js"></script>')
    replace_once(blank,'function render(){let layout;if(tab===','function render(){let layout;if(tab==="design")layout=LexeditorDesignReview.render();else if(tab===')
    replace_once(blank,'tabs:[{id:"one",label:"1 Panel"}','tabs:[{id:"design",label:"Design Review"},{id:"one",label:"1 Panel"}')
    assert 'function dataMapPanel()' in Path(blank).read_text()

framework='ui/framework.js'
replace_once(framework,'''        return true;
      } finally {
        this.applying = false;
        this.changed(this);
      }
    }
  }

  const installBrowserHistoryGuard''','''        return true;
      } catch (error) {
        // A failed destination must not move the history cursor away from the
        // page that is still visible. Cancellation already returns false above.
        this.index = previous;
        throw error;
      } finally {
        this.applying = false;
        this.changed(this);
      }
    }
  }

  const installBrowserHistoryGuard''')
replace_once(framework,'''      try { await options.save?.(); playThemeSound("save"); }
      finally { setBusy(false); }
''','''      let failure = null;
      try { await options.save?.(); playThemeSound("save"); }
      catch (error) { failure = error; }
      finally { setBusy(false); }
      if (failure) showAlert({title: "Settings save failed",
        message: String(failure.message || failure)});
''')
replace_once(framework,'''      divider.addEventListener("contextmenu", event => {
        event.preventDefault();
        setSizes(defaults, true);
      });''','''      const reset = event => {
        if (event.target.closest?.("button,input,select,textarea,[role=button]")) return;
        event.preventDefault();
        setSizes(defaults, true);
      };
      divider.addEventListener("dblclick", reset);
      divider.addEventListener("contextmenu", reset);''')
