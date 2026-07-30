#!/usr/bin/env python3
"""
Lexeditor -- mod feature-list extractor

Most big Warband mods ship an in-game manual (info_pages.txt) describing their
own features, written by the author. That is a far better answer to "what does
this mod do" than diffing, which only shows changed numbers with no labels.

This dumps any module's info pages into readable text.

Usage:
    python Lexeditor\\dump_infopages.py "<path to module folder>"
    python Lexeditor\\dump_infopages.py --list      list installed modules

Example:
    python Lexeditor\\dump_infopages.py BannerPage
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths  # noqa: E402  -- game-specific locations live here

MODULES_DIR = paths.MODULES_DIR
HERE = paths.OUT_DIR


def unescape(text):
    """Warband stores strings with underscores for spaces and ^ for newline."""
    return text.replace('_', ' ').replace('^', '\n')


def parse_info_pages(path):
    with open(path, 'r', errors='replace') as fh:
        lines = [l.rstrip('\n') for l in fh]

    # Line 0: "infopagesfile version 1", line 1: count, then one page per line:
    #   ip_<id> <Title> <body...>
    pages = []
    for line in lines[2:]:
        if not line.strip():
            continue
        parts = line.split(' ', 2)
        if len(parts) < 3 or not parts[0].startswith('ip_'):
            continue
        pages.append({
            'id': parts[0],
            'title': unescape(parts[1]),
            'body': unescape(parts[2]),
        })
    return pages


def resolve_module(name):
    if os.path.isdir(name):
        return name
    candidate = os.path.join(MODULES_DIR, name)
    if os.path.isdir(candidate):
        return candidate
    return None


def main():
    ap = argparse.ArgumentParser(description="Dump a Warband module's in-game manual.")
    ap.add_argument('module', nargs='?', help='module folder name or full path')
    ap.add_argument('--list', action='store_true', help='list installed modules')
    ap.add_argument('--out', help='output file (default Lexeditor/<module>_features.txt)')
    args = ap.parse_args()

    if args.list or not args.module:
        if not os.path.isdir(MODULES_DIR):
            sys.exit("Modules folder not found: %s" % MODULES_DIR)
        print("Installed modules:")
        for d in sorted(os.listdir(MODULES_DIR)):
            full = os.path.join(MODULES_DIR, d)
            if os.path.isdir(full):
                has = os.path.isfile(os.path.join(full, 'info_pages.txt'))
                print("  %-28s %s" % (d, "has a manual" if has else ""))
        return

    mod = resolve_module(args.module)
    if not mod:
        sys.exit("Could not find module: %s" % args.module)

    ip = os.path.join(mod, 'info_pages.txt')
    if not os.path.isfile(ip):
        sys.exit("%s has no info_pages.txt (no in-game manual to extract)." % mod)

    pages = parse_info_pages(ip)
    name = os.path.basename(mod.rstrip('\\/'))
    out = args.out or os.path.join(HERE, '%s_features.txt' % name.replace(' ', '_'))

    with open(out, 'w', errors='replace') as fh:
        fh.write("=" * 78 + "\n")
        fh.write("%s -- in-game manual, extracted\n" % name)
        fh.write("Written by the mod's own author. %d pages.\n" % len(pages))
        fh.write("=" * 78 + "\n\n")
        for p in sorted(pages, key=lambda x: x['title']):
            fh.write("-" * 78 + "\n")
            fh.write("%s   [%s]\n" % (p['title'], p['id']))
            fh.write("-" * 78 + "\n")
            fh.write(p['body'].strip() + "\n\n")

    print("Extracted %d pages from %s" % (len(pages), name))
    print("  -> %s" % out)
    print("\nPage titles:")
    for p in sorted(pages, key=lambda x: x['title']):
        print("  %s" % p['title'])


if __name__ == '__main__':
    main()
