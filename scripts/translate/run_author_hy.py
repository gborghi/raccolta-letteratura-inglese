# -*- coding: utf-8 -*-
"""Translate ONE author's pending leaf atoms with the HY pipeline.

Reuses run_dickens_hy's proven machinery verbatim -- the few-shot HY _ask patch,
SafeCache, the worker pool, validate(), and the reject-recording to
dickens_rejected.jsonl (so the watcher's retry+Opus rescue covers these atoms
too). The ONLY thing swapped is enumeration: instead of the Dickens
*_atoms.tsv files it walks Authors/<Author>/Atomized and picks every leaf atom
that still lacks a .it.md.

    python3 run_author_hy.py Belloc
    HY_WORKERS=4 python3 run_author_hy.py Conan_Doyle

Env HY_WORKERS / HY_LIMIT behave exactly as in run_dickens_hy.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run_dickens_hy as R          # applies the HY few-shot _ask patch on import
import dickens_tower as dt


CONFLICTED_RE = re.compile(r" \([^()]*conflicted copy \d{4}-\d{2}-\d{2}\)")


def is_leaf_atom(root, f):
    """A source atom the pipeline should translate: a .md that is a LEAF, not an
    aggregate. Excludes *_raw / _index working dirs, the folder-aggregate
    (Work/Work.md, stem == parent dir) and any chapter split further into a
    same-named subfolder (Chapter_07.md next to Chapter_07/part_*.md).

    Dropbox "conflicted copy" duplicates are excluded too: they are byte-identical
    twins of an atom that already has its own .it.md, so translating them burns the
    model on nothing and leaves a second .it.md that assemble_aggregates would then
    have to choose between."""
    if not f.endswith(".md") or f.endswith(".it.md"):
        return False
    if CONFLICTED_RE.search(f):
        return False
    parts = root.split(os.sep)
    if any(p.startswith("_") or p.endswith("_raw") for p in parts):
        return False
    stem = f[:-3]
    if stem == os.path.basename(root):
        return False
    if os.path.isdir(os.path.join(root, stem)):
        return False
    return True


def gather_author(author):
    base = os.path.join(dt.VAULT_ROOT, "Authors", author, "Atomized")
    out = []
    for root, _dirs, files in os.walk(base):
        for f in files:
            if is_leaf_atom(root, f):
                en = os.path.join(root, f)
                if not os.path.exists(en[:-3] + ".it.md"):
                    out.append(en)
    return sorted(out)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: run_author_hy.py <Author>")
        sys.exit(1)
    author = sys.argv[1]
    R.gather_pending = lambda: gather_author(author)
    print(f"### author run: {author}", flush=True)
    R.main()
