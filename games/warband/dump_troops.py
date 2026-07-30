#!/usr/bin/env python3
"""
Lexeditor -- Warband troop dump (first slice)

Reads ModuleSystem/module_troops.py and lists EVERY troop, including the ones
TaleWorlds commented out, so cut content can actually be looked at.

This is deliberately a plain script rather than a GUI. It gets Lexer the thing
he asked for -- seeing the cut content -- without waiting on a UI framework
decision. The parser here is the part a GUI would reuse.

Usage:
    python Lexeditor\\dump_troops.py            -> writes Lexeditor\\troops.tsv
    python Lexeditor\\dump_troops.py --cut       -> only commented-out troops
    python Lexeditor\\dump_troops.py --faction fac_undeads

Run with the system Python 3 (the module system needs 2.7, this does not).
"""

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import paths  # noqa: E402  -- game-specific locations live here

TROOPS_PY = os.path.join(paths.MODULE_SYSTEM, "module_troops.py")

# A troop entry starts with ["id","Singular","Plural", ... and runs until the
# bracket depth returns to zero. Entries may be commented out with any number
# of leading '#' characters, on every line of the entry.
ENTRY_START = re.compile(r'^\s*(#*)\s*\[\s*"([^"]+)"\s*,\s*"([^"]*)"\s*,\s*"([^"]*)"\s*,')

LEVEL_RE = re.compile(r'level\((\d+)\)')
FAC_RE = re.compile(r'\b(fac_[a-z0-9_]+)\b')


def strip_comment_markers(line):
    """Remove leading whitespace and '#' markers, keep the rest verbatim."""
    return re.sub(r'^\s*#+\s?', '', line)


def depth_delta(text):
    """Net bracket depth change, ignoring brackets inside string literals."""
    depth = 0
    in_str = False
    quote = ''
    prev = ''
    for ch in text:
        if in_str:
            if ch == quote and prev != '\\':
                in_str = False
        elif ch in '"\'':
            in_str = True
            quote = ch
        elif ch == '[':
            depth += 1
        elif ch == ']':
            depth -= 1
        prev = ch
    return depth


def parse_troops(path):
    """Find every troop entry.

    Deliberately does NOT rely on bracket balance to find the end of an entry.
    An earlier version did, and a single unbalanced bracket anywhere caused the
    scanner to swallow following entries silently -- it lost
    black_khergit_guard that way. For surveying cut content, silently missing
    rows is the worst possible failure, so instead each entry simply runs from
    its own start line to the line before the next entry start. That cannot skip
    anything, at the cost of occasionally including a trailing comment.
    """
    with open(path, 'r', errors='replace') as fh:
        lines = fh.readlines()

    starts = []
    for idx, line in enumerate(lines):
        m = ENTRY_START.match(line)
        if m:
            starts.append((idx, m))

    troops = []
    for n, (i, m) in enumerate(starts):
        end = starts[n + 1][0] if n + 1 < len(starts) else len(lines)

        commented = bool(m.group(1))
        tid, singular, plural = m.group(2), m.group(3), m.group(4)

        body = ' '.join(strip_comment_markers(l).rstrip('\n')
                        for l in lines[i:end])

        lvl = LEVEL_RE.search(body)
        facs = FAC_RE.findall(body)

        troops.append({
            'line': i + 1,
            'status': 'CUT' if commented else 'active',
            'id': tid,
            'name': singular,
            'plural': plural,
            'level': lvl.group(1) if lvl else '',
            'faction': facs[0] if facs else '',
            'flags': ' '.join(sorted(set(re.findall(r'\btf_[a-z0-9_]+', body)))),
        })

    return troops


def main():
    ap = argparse.ArgumentParser(description="Dump Warband troops, cut ones included.")
    ap.add_argument('--cut', action='store_true', help='only commented-out (cut) troops')
    ap.add_argument('--faction', help='filter by faction, e.g. fac_undeads')
    ap.add_argument('--out', default=os.path.join(paths.OUT_DIR, 'troops.tsv'))
    args = ap.parse_args()

    if not os.path.isfile(TROOPS_PY):
        sys.exit("Could not find %s" % os.path.normpath(TROOPS_PY))

    troops = parse_troops(TROOPS_PY)

    if args.cut:
        troops = [t for t in troops if t['status'] == 'CUT']
    if args.faction:
        troops = [t for t in troops if t['faction'] == args.faction]

    cols = ['status', 'id', 'name', 'level', 'faction', 'line', 'flags']
    with open(args.out, 'w') as fh:
        fh.write('\t'.join(cols) + '\n')
        for t in troops:
            fh.write('\t'.join(str(t[c]) for c in cols) + '\n')

    total = len(troops)
    cut = sum(1 for t in troops if t['status'] == 'CUT')
    print("Parsed %s" % os.path.normpath(TROOPS_PY))
    print("  %d troops listed (%d cut / commented out)" % (total, cut))
    print("  written to %s" % args.out)

    if cut:
        print("\nCut troops:")
        for t in troops:
            if t['status'] == 'CUT':
                print("  %-24s %-28s lvl %-3s %s"
                      % (t['id'], t['name'], t['level'] or '?', t['faction'] or ''))


if __name__ == '__main__':
    main()
