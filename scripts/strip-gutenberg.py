# -*- coding: utf-8 -*-
"""Strip Project Gutenberg licence header/footer from vault atoms.

The atomiser swept PG's legal boilerplate into the vault along with the texts: 49 of the 287 blocks
in Chesterton's Poems/part/part_08.md are the licence tail ("*** END OF THIS PROJECT GUTENBERG
EBOOK POEMS ***", refund clauses, gutenberg.org URLs). It renders on the site as if it were the
author's work, and it makes a translator complete its hard-wrapped fragments.

SCOPE: Atomized/ and Long/ only -- the trees that render.
  - _raw/ is left pristine: it is the archival record of what was actually fetched.
  - Knowledge Graph/Works notes are left alone: there the PG header is PROVENANCE (which edition a
    text came from), not rubbish.

WHAT IS STRIPPED, positionally (keywords alone miss 18 of 49 blocks -- "Produced by Marc D'Hooghe"
and "will be renamed." are ordinary English that is only boilerplate by position):
  - everything from the END/FULL-LICENSE marker to end of file
  - everything from start of file up to and including the START marker
Body text between the markers is never touched.

Usage:
  python3 strip-gutenberg.py            # DRY RUN - report only, writes nothing
  python3 strip-gutenberg.py --apply    # actually rewrite the files
"""
import os, re, sys, glob

# NOTE: this file sits in scripts/, ONE level down -- unlike scripts/translate/*.py which are two.
# Copying their `join(__file__, "..", "..")` idiom here overshoots to SubjectBrain/VaultEnglish and
# silently matches nothing ("0 files") instead of erroring.
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
VAULT = os.path.abspath(os.path.join(ROOT, "..", "VaultEnglish"))
AUTHORS = os.path.join(VAULT, "Authors")
if not os.path.isdir(AUTHORS):                    # fail loudly rather than report a clean "0 files"
    raise SystemExit(f"vault not found: {AUTHORS}")

# BOTH languages, because a previous session TRANSLATED the licence into Italian. Enumerating
# phrasings was a losing game -- "End of the/this Project Gutenberg Etext", "Fine dell'eBook Project
# Gutenberg di X", "Fine di X del Project Gutenberg", "Fine di questo Project Gutenberg Etext di X".
# Miss ONE variant on ONE side and you strip that side only, desyncing the pair and silently
# un-publishing the page. Match structurally instead: a line that OPENS with an end-marker and
# mentions Gutenberg is the boundary, whatever the wording.
START_RE = re.compile(r"^\s*\*{3,}.*\b(?:START OF|INIZIO DI)\b.*PROJECT GUTENBERG.*$", re.I | re.M)
END_RE = re.compile(r"^\s*(?:\*{3,}.*\b(?:END OF|FINE DI)\b.*PROJECT GUTENBERG"
                    # "Fine di/del/dell'eBook/dell'Etext ..." -- d\S* spans the elision. Safe only
                    # because ^ anchors it: real prose mentioning "la fine della sua vita" never
                    # STARTS the line with "Fine d...".
                    r"|(?:End of|Fine\s+d\S*)\b.*?\bGutenberg\b"
                    r"|\*{3,}\s*(?:START:\s*FULL LICENSE|INIZIO:\s*LICENZA COMPLETA)"
                    r").*$", re.I | re.M)


# Project Gutenberg *Australia* uses a different masthead entirely: a metadata block
# ("* A Project Gutenberg of Australia eBook *", eBook No., Edition, ...) followed by licence prose
# ending at the licence URL, after which the real text starts. Cut from the marker to that URL.
# The span is BOUNDED ({0,2000}): an unbounded `.*?` with re.S backtracks catastrophically over a
# 200KB atom and hangs. The real header is ~800 chars.
AUS_RE = re.compile(r"^.*Project Gutenberg of Australia eBook.*$"      # masthead line
                    r"[\s\S]{0,2000}?"                                 # metadata + licence prose
                    r"^.*gutenberg\.net\.au/licence\.html.*$\n?",      # ...ends at the licence URL
                    re.I | re.M)
# The old US masthead: "***The Project Gutenberg Etext of X***" ... "Information on contacting..."
US_HEAD_RE = re.compile(r"^\*{2,}\s*The Project Gutenberg E(?:text|Book) of .*$\n?", re.I | re.M)


def strip(text):
    """Return (new_text, removed_chars). Cuts the PG masthead/header and the licence tail."""
    orig = text
    m = END_RE.search(text)
    if m:
        text = text[:m.start()]
    m = START_RE.search(text)
    if m:
        text = text[m.end():]
    text = AUS_RE.sub("", text)
    text = US_HEAD_RE.sub("", text)
    return text.rstrip() + "\n", len(orig) - len(text)


def main():
    apply = "--apply" in sys.argv
    files = []
    for sub in ("Atomized", "Long"):
        files += glob.glob(os.path.join(AUTHORS, "*", sub, "**", "*.md"), recursive=True)
    hits, removed_total, by_author = [], 0, {}
    for p in sorted(files):
        try:
            t = open(p, encoding="utf-8").read()
        except Exception:
            continue
        # Gate on EVERY pattern strip() knows about -- gating on START/END only meant the
        # PG-Australia mastheads (which match neither) were silently never processed.
        if not (START_RE.search(t) or END_RE.search(t) or AUS_RE.search(t) or US_HEAD_RE.search(t)):
            continue
        new, removed = strip(t)
        if removed <= 0:
            continue
        hits.append((p, removed, len(t)))
        removed_total += removed
        a = os.path.relpath(p, AUTHORS).split(os.sep)[0]
        by_author[a] = by_author.get(a, 0) + 1
        if apply:
            open(p, "w", encoding="utf-8").write(new)

    print(("APPLIED" if apply else "DRY RUN - nothing written") + f": {len(hits)} files, "
          f"{removed_total:,} chars of Gutenberg boilerplate")
    for a, n in sorted(by_author.items(), key=lambda x: -x[1]):
        print(f"  {a:14} {n} files")
    print("\n  largest cuts:")
    for p, removed, total in sorted(hits, key=lambda x: -x[1])[:8]:
        print(f"    -{removed:>6,} chars of {total:>7,}  {os.path.relpath(p, VAULT)}")
    if not apply:
        print("\n  re-run with --apply to write. Undo: git -C VaultEnglish checkout .")


if __name__ == "__main__":
    main()
