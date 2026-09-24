import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from generate_component_usage import shared_dependencies, propagate_usage


def test_private_helpers_aliases_and_cycles():
    graph = shared_dependencies('''
  const page = () => privateFit();
  const privateFit = () => pager();
  const pager = () => page();
  const other = page;
  const unused = () => "pager()";
''')
    found = {'page': set(), 'pager': set(), 'other': {'game'}, 'unused': {'other-game'}}
    propagate_usage(found, graph)
    assert found['page'] == {'game'}
    assert found['pager'] == {'game'}
    assert graph['unused'] == set()


def test_comments_do_not_create_edges():
    graph = shared_dependencies('''
  const page = () => {
    // pager() is not called here.
    /* privateFit() */
    return "nothing";
  };
  const pager = () => 1;
''')
    assert graph['page'] == set()
