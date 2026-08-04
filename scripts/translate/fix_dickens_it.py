# -*- coding: utf-8 -*-
"""Post-hoc cleanup sweep over Dickens .it.md siblings (no model, idempotent):
  1. MARKUP: collapse malformed wikilink brackets ( ]]]] / [[[ -> ]] / [[ ) and
     re-space a link glued to the preceding word ( parola[[X]] -> parola [[X]] ).
  2. ELLIPSES: HY adds the '…' character of its own; strip it (restore normal
     punctuation) but ONLY when the EN source block set has no ellipsis of its
     own -- Dickens uses them a handful of times and those must survive.

DRY-RUN by default; --apply to write. Usage: fix_dickens_it.py [--apply]
"""
import os, re, sys, glob

DICK = ("/Users/g.borghi/Library/CloudStorage/Dropbox/insegnamento/Wiligelmo/"
        "SubjectBrain/English/VaultEnglish/Authors/Dickens/Atomized")


def strip_ellipses(s):
    s = s.replace("...", "…")
    s = re.sub(r"\s*…\s*$", ".", s, flags=re.M)
    s = re.sub(r"\s*…\s+(?=[A-ZÀ-Þ\[\"«])", ". ", s)
    s = re.sub(r"\s*…\s*", ", ", s)
    s = re.sub(r"\s+([.,;:!?])", r"\1", s)
    s = re.sub(r",\s*\.", ".", s)
    return s


def fix_markup(s):
    s = re.sub(r"\]\]\]+", "]]", s)          # ]]] / ]]]] -> ]]
    s = re.sub(r"\[\[\[+", "[[", s)          # [[[ -> [[
    s = re.sub(r"(\w)(\[\[[^\]]+\]\])", r"\1 \2", s)   # word[[X]] -> word [[X]]
    return s


def n_ell(s):
    return s.count("…") + s.count("...")


def main():
    apply = "--apply" in sys.argv
    files = glob.glob(os.path.join(DICK, "**/*.it.md"), recursive=True)
    n_markup = n_ell_fixed = n_ell_skipped = n_written = 0
    for it in files:
        s = open(it, encoding="utf-8").read()
        orig = s
        s2 = fix_markup(s)
        if s2 != s:
            n_markup += 1
        s = s2
        # ellipsis, source-aware
        if n_ell(s):
            en = it[:-6] + ".md"
            en_has = os.path.exists(en) and n_ell(open(en, encoding="utf-8").read()) > 0
            if en_has:
                n_ell_skipped += 1
            else:
                s3 = strip_ellipses(s)
                if s3 != s:
                    n_ell_fixed += 1
                s = s3
        if s != orig:
            n_written += 1
            if apply:
                open(it, "w", encoding="utf-8").write(s)
    print(("APPLIED" if apply else "DRY RUN") + f" over {len(files)} .it.md")
    print(f"  markup fixed (brackets/spacing): {n_markup}")
    print(f"  ellipsis stripped (files)      : {n_ell_fixed}")
    print(f"  ellipsis kept (EN has them)    : {n_ell_skipped}")
    print(f"  files changed                  : {n_written}")


if __name__ == "__main__":
    main()
