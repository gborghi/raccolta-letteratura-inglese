# -*- coding: utf-8 -*-
"""Tell leaf atoms from aggregate ones in VaultEnglish/Authors/*/Atomized/.

Atomization is redundant on purpose: the same text exists at up to three levels.

    Work/Work.md              whole book        <- aggregate
    Work/Chapter_NN.md        whole chapter     <- aggregate IF Work/Chapter_NN/ exists
    Work/Chapter_NN/part_M.md the actual atom   <- leaf

Only leaves get a .it.md. A chapter file with no sibling directory is itself the
leaf (Conan Doyle's works and some Austen chapters are atomized that way), so the
rule has to be structural, not name-based.

Importable (is_leaf) and runnable:  python3 leafcheck.py [--author NAME]
"""
import os, sys, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT_ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", "VaultEnglish"))


def is_leaf(rel, vault=VAULT_ROOT):
    """rel is 'Authors/<Name>/Atomized/.../x.md' relative to the vault root."""
    if not rel.endswith(".md") or rel.endswith(".it.md"):
        return False
    path = os.path.join(vault, rel)
    stem = path[:-3]
    # 1. a sibling directory holding the splits -> this file is their aggregate
    if os.path.isdir(stem):
        return False
    # 2. Work/Work.md: the whole book, when the work dir holds anything else
    parent = os.path.dirname(path)
    if os.path.basename(stem) == os.path.basename(parent):
        for e in os.listdir(parent):
            if e.endswith(".md") and not e.endswith(".it.md") and \
                    os.path.join(parent, e) != path:
                return False
            if os.path.isdir(os.path.join(parent, e)):
                return False
    return True


def walk_leaves(author=None, vault=VAULT_ROOT):
    base = os.path.join(vault, "Authors")
    for name in sorted(os.listdir(base)):
        if author and name != author:
            continue
        atom = os.path.join(base, name, "Atomized")
        if not os.path.isdir(atom):
            continue
        for root, _dirs, files in os.walk(atom):
            for f in files:
                if not f.endswith(".md") or f.endswith(".it.md"):
                    continue
                rel = os.path.relpath(os.path.join(root, f), vault)
                if is_leaf(rel, vault):
                    yield name, rel


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--author", default=None)
    a = ap.parse_args()
    from collections import Counter
    tot, todo = Counter(), Counter()
    for name, rel in walk_leaves(a.author):
        tot[name] += 1
        if not os.path.exists(os.path.join(VAULT_ROOT, rel[:-3] + ".it.md")):
            todo[name] += 1
    print("%-14s %8s %8s %7s" % ("autore", "foglie", "da fare", "%"))
    for name in sorted(tot, key=lambda k: -todo[k]):
        pct = 100.0 * (tot[name] - todo[name]) / tot[name]
        print("%-14s %8d %8d %6.1f%%" % (name, tot[name], todo[name], pct))
    print("%-14s %8d %8d" % ("TOTALE", sum(tot.values()), sum(todo.values())))


if __name__ == "__main__":
    raise SystemExit(main())
