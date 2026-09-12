from pathlib import Path

visual_path = Path('.github/scripts/ui_visual_acceptance.py')
visual = visual_path.read_text(encoding='utf-8')
old_comment = '''            # string (name + range endpoints) rotated in the graph margin.
            page.evaluate("navigate('graphs')"); page.wait_for_timeout(180)
'''
new_comment = '''            # The Y-axis name stays vertical while the range endpoints sit
            # horizontally in the left graph margin.
            page.evaluate("navigate('graphs')"); page.wait_for_timeout(180)
'''
if visual.count(old_comment) != 1:
    raise RuntimeError(f'graph comment anchor count: {visual.count(old_comment)}')
visual = visual.replace(old_comment, new_comment, 1)
old_assertions = '''            for node in (y_name, axis_top, axis_bottom):
                assert node.evaluate("e=>getComputedStyle(e).writingMode").startswith('vertical'), (width, 'right-axis text is not vertical', node.get_attribute('class'))
            for node in (axis_top, axis_bottom, y_name):
                nb = node.bounding_box(); assert nb['x'] + nb['width'] >= svg_box['x'] + svg_box['width'] - 2, (width, 'right-axis text is not in right margin', node.get_attribute('class'), nb, svg_box)
'''
new_assertions = '''            assert y_name.evaluate("e=>getComputedStyle(e).writingMode").startswith('vertical'), (width, 'y-axis name is not vertical')
            for node in (axis_top, axis_bottom):
                assert node.evaluate("e=>getComputedStyle(e).writingMode") == 'horizontal-tb', (width, 'y-scale number is not horizontal', node.get_attribute('class'))
            for node in (axis_top, axis_bottom, y_name):
                nb = node.bounding_box(); assert nb['x'] <= svg_box['x'] + 2, (width, 'y-axis text is not in left margin', node.get_attribute('class'), nb, svg_box)
'''
if visual.count(old_assertions) != 1:
    raise RuntimeError(f'graph assertion anchor count: {visual.count(old_assertions)}')
visual_path.write_text(visual.replace(old_assertions, new_assertions, 1), encoding='utf-8')

workflow_path = Path('.github/workflows/ff7r-checks.yml')
workflow = workflow_path.read_text(encoding='utf-8')
old_dependency = '        run: python -m pip install pytest Pillow==12.3.0 texfury==1.6.2\n'
new_dependency = '        run: python -m pip install pytest Pillow==12.3.0 texfury==1.6.2 cryptography\n'
if workflow.count(old_dependency) != 1:
    raise RuntimeError(f'FF7R dependency anchor count: {workflow.count(old_dependency)}')
workflow_path.write_text(workflow.replace(old_dependency, new_dependency, 1), encoding='utf-8')
