"""Set the root networking string in a staged source distribution."""
import argparse
import ast
from pathlib import Path


def configure(root, nexus):
    path = Path(root)/'disable_networking.py'
    source = path.read_text('utf-8')
    tree = ast.parse(source)
    assignments = {node.targets[0].id: node for node in tree.body
                   if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)}
    name = 'DO_NOT_EDIT_ANY_PART_OF_THIS_STRING_AND_THEN_PRESS_SAVE_OR_NETWORK_FEATURES_WILL_BE_RE_ENABLED'
    value = ast.literal_eval(assignments['NEXUS_DISABLED_TEXT'].value) if nexus else ''
    node = assignments[name]
    lines = source.splitlines(keepends=True)
    lines[node.lineno-1:node.end_lineno] = [f'{name} = {value!r}\n']
    path.write_text(''.join(lines), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--nexus', action='store_true')
    mode.add_argument('--github', action='store_true')
    args = parser.parse_args()
    configure(args.root, args.nexus)
