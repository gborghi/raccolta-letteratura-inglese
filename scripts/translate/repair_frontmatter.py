# -*- coding: utf-8 -*-
"""Restore the YAML frontmatter of translated leaves that lost it, without a model.

Every leaf's first block is its frontmatter, and it must reach the Italian file
BYTE-FOR-BYTE: the tags are graph keys (`archetype/child`, `concept/imprisonment`),
not prose. Two ways it went wrong before the frontmatter-verbatim rule was enforced:

  * the model TRANSLATED the block  -> `archetipo/bambino`, a tag that indexes nothing;
  * the model DROPPED it entirely   -> the older Chesterton/Sayers convention, where the
    Italian file starts straight at the H1 and is two blocks shorter (the frontmatter and
    the blank line after it);
  * the model REPLACED it outright  -> an invented essay heading, e.g.
        # Il pellegrino e la prigione > "La vita e' un viaggio, e noi siamo tutti pellegrini"
    which reads like fabricated Dickens but is only block 0: the real title is block 2
    and every prose block after it aligns and is correctly translated.

All three are repaired from the English block 0 alone -- overwritten when the Italian has
a block in that slot, prepended when it has none -- so none of them needs a retranslation
and the files are recovered instead of costing hours of queue time again. The block counts
decide which: equal means only block 0 moved, two short means the whole frontmatter is
absent, and any other shortfall means prose really is missing, so the atom goes back
through the queue untouched. Every repaired file is re-checked with dickens_tower.validate()
and written only if it comes back clean.

Only `replace` is repaired by default, because it is unambiguously a defect. A missing
frontmatter is NOT: in Sayers (64 files out of 64) and Chesterton (3346 against 89) it is
the convention the whole author was translated under, while in Dickens (121 against 3801
that do carry it) it is the same bug in a milder form. Rewriting thousands of files to a
convention their author never used is not a repair, so `prepend` needs --prepend and is
meant to be run per author.

Usage:
  python3 repair_frontmatter.py                 # dry-run report
  python3 repair_frontmatter.py --write         # repair the 'replace' defects
  python3 repair_frontmatter.py --author Dickens --prepend --write
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import dickens_tower as dt                       # noqa: E402
from leafcheck import VAULT_ROOT, walk_leaves    # noqa: E402
from sbtrans import clean_body, split_blocks     # noqa: E402


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def classify(en_text, it_text):
    """-> (verdict, en_blocks, it_blocks). Verdict is 'ok' | 'replace' | 'prepend' | 'reblock'."""
    en = split_blocks(clean_body(en_text))
    it = split_blocks(clean_body(it_text))
    if not en or not en[0].lstrip().startswith("---"):
        return "ok", en, it                      # no frontmatter to protect
    if it and it[0] == en[0]:
        return "ok", en, it
    if len(it) == len(en):
        return "replace", en, it
    # two blocks short and no frontmatter of its own: the whole block is simply absent
    if len(it) == len(en) - 2 and not (it and it[0].lstrip().startswith("---")):
        return "prepend", en, it
    return "reblock", en, it                     # prose is missing: needs the queue


def repair(verdict, en, it):
    """The Italian text with the English frontmatter restored in block 0."""
    return "".join([en[0]] + (it[1:] if verdict == "replace" else [en[1]] + it))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--author", default=None)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--prepend", action="store_true",
                    help="also restore a frontmatter that is missing altogether")
    a = ap.parse_args()

    wanted = ("replace", "prepend") if a.prepend else ("replace",)
    fixed, rejected, reblock, skipped, scanned = [], [], [], 0, 0
    for _author, rel in walk_leaves(a.author):
        it_path = os.path.join(VAULT_ROOT, rel[:-3] + ".it.md")
        if not os.path.exists(it_path):
            continue
        scanned += 1
        en_text, it_text = _read(os.path.join(VAULT_ROOT, rel)), _read(it_path)
        verdict, en, it = classify(en_text, it_text)
        if verdict == "ok":
            continue
        if verdict == "reblock":
            reblock.append(rel)
            continue
        if verdict not in wanted:
            skipped += 1
            continue
        out = repair(verdict, en, it)
        problems = dt.validate(en_text, out, False)
        if problems:
            rejected.append((rel, problems))
            continue
        if a.write:
            with open(it_path, "w", encoding="utf-8") as fh:
                fh.write(out)
        fixed.append(rel)

    tag = "riparati" if a.write else "riparabili (dry-run)"
    print("foglie tradotte esaminate: %d" % scanned)
    print("%s: %d" % (tag, len(fixed)))
    for rel in fixed[:8]:
        print("   %s" % rel)
    if skipped:
        print("\nfrontmatter assente, non toccati (serve --prepend): %d" % skipped)
    if rejected:
        print("\nriparazione respinta da validate(): %d" % len(rejected))
        for rel, p in rejected[:8]:
            print("   %s -> %s" % (rel, p))
    if reblock:
        print("\nblocchi mancanti, da ritradurre: %d" % len(reblock))
        for rel in reblock[:8]:
            print("   %s" % rel)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
