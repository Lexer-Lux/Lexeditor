"""The dead-space probe measures visible content through boxless wrappers."""
import pytest

from test_shared_ui_feedback import page
from verify_no_dead_space import PROBE


@pytest.mark.parametrize('wrapper,expected_gap', [
    ('display:contents',20),
    ('display:none',None),
    ('display:contents;visibility:hidden',None),
    ('width:0;height:0;overflow:hidden',None),
])
def test_probe_distinguishes_boxless_layout_from_hidden_content(page,wrapper,expected_gap):
    page.evaluate('''style=>{
      const main=document.querySelector('main');
      main.style.cssText='position:relative;height:300px;width:500px;padding:0;border:0;margin:0';
      const outer=document.createElement('div');outer.style.cssText=style;
      const nested=document.createElement('div');nested.style.display='contents';
      const painted=document.createElement('div');
      painted.style.cssText='position:absolute;left:0;bottom:20px;width:100px;height:30px;background:red';
      painted.textContent='Visible content';
      nested.append(painted);outer.append(nested);main.replaceChildren(outer);
    }''',wrapper)
    result=page.evaluate(PROBE)
    if expected_gap is None:
        assert result['lowest']==result['top'],result
    else:
        assert result['bottom']-result['lowest']==expected_gap,result
