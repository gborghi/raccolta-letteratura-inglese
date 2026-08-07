# -*- coding: utf-8 -*-
"""Translate ONE author's pending leaf atoms with the HY pipeline.

Reuses run_dickens_hy's proven machinery verbatim -- the few-shot HY _ask patch,
SafeCache, the worker pool, validate(), and the reject-recording to
dickens_rejected.jsonl (so the watcher's retry+Opus rescue covers these atoms
too). The ONLY thing swapped is enumeration: instead of the Dickens
*_atoms.tsv files it uses leafcheck.walk_leaves -- Atomized/, Long/, Plays/ and
Poems/ -- and picks every leaf atom that still lacks a .it.md.

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
import leafcheck


CONFLICTED_RE = re.compile(r" \([^()]*conflicted copy \d{4}-\d{2}-\d{2}\)")


def gather_author(author):
    """Every pending leaf of the author, across all four content subtrees.

    Enumeration is leafcheck.walk_leaves -- the same walker assemble_aggregates and
    repair_frontmatter use -- so the queue, the assembly and the frontmatter check all
    agree on what a leaf is. It used to walk Atomized/ alone, which left Long/, Plays/
    and Poems/ invisible to the queue: those atoms were never translated and never even
    reported as pending.

    Env HY_SKIP is a regex on the atom path: verse inside a prose author's folder
    (Wilde's The Sphinx) must stay out of HY and go to Opus instead.

    Dropbox "conflicted copy" duplicates are dropped here rather than in leafcheck:
    they are byte-identical twins of an atom that already has its own .it.md, so
    translating them burns the model on nothing and leaves assemble_aggregates with
    two candidates to choose between."""
    skip = re.compile(os.environ["HY_SKIP"]) if os.environ.get("HY_SKIP") else None
    out = []
    for _name, rel in leafcheck.walk_leaves(author, dt.VAULT_ROOT):
        if CONFLICTED_RE.search(os.path.basename(rel)):
            continue
        en = os.path.join(dt.VAULT_ROOT, rel)
        if skip and skip.search(en):
            continue
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
