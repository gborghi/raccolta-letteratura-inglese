#!/usr/bin/env python3
"""Rifa' il file-libro EN concatenando le sue foglie.

Serve dopo fix_leaf_overlap: se le foglie erano duplicate, il libro costruito su di esse
lo e' rimasto, e la duplicazione non si vede piu' confrontando le foglie fra loro -- si
vede solo confrontando il libro con la loro somma.

Il libro EN non ha frontmatter e non ha gli H1 delle sezioni: e' l'H1 del titolo, l'eventuale
preambolo (la riga "ASH-WEDNESDAY 1930" e simili, che sta nel libro e in nessuna foglia) e
poi il testo di seguito. Il preambolo si riconosce come tutto cio' che nel libro precede la
prima riga della prima foglia, e va conservato: non appartiene a nessuna sezione.

Uso:
    python3 assemble_en_book.py Authors/Eliot/Long/The_Waste_Land          # dry-run
    python3 assemble_en_book.py Authors/Eliot/Long/The_Waste_Land --write
"""

import argparse
import io
import os
import re
import sys

import check_leaf_overlap as chk
import dickens_tower as dt


def leaf_body_raw(path):
    """Il corpo della foglia con la spaziatura intatta: senza frontmatter e senza H1."""
    t = io.open(path, encoding="utf-8").read()
    if t.startswith("---") and "\n---\n" in t:
        t = t.split("\n---\n", 1)[1]
    t = re.sub(r"^\s*#[^\n]*\n", "", t.lstrip(), count=1)
    return t.strip("\n")


def rebuild(work_dir, write=False):
    name = os.path.basename(work_dir)
    book = os.path.join(work_dir, name + ".md")
    if not os.path.exists(book):
        print("!! nessun file-libro in %s" % work_dir)
        return False
    secs = chk.units(work_dir)
    if not secs:
        print("!! nessuna foglia in %s" % work_dir)
        return False

    old = io.open(book, encoding="utf-8").read()
    first_leaf = chk.body(os.path.join(work_dir, secs[0]))
    if not first_leaf:
        print("!! prima foglia vuota in %s" % work_dir)
        return False

    # testa del libro = tutto cio' che precede la prima riga della prima foglia
    lines = old.split("\n")
    start = None
    for i, l in enumerate(lines):
        if l.strip() == first_leaf[0]:
            start = i
            break
    if start is None:
        print("!! %s: la prima riga della prima foglia non compare nel libro" % name)
        return False
    head = lines[:start]
    # un "## I" in coda alla testa e' l'intestazione della prima sezione: il numerale sta
    # gia' nella prima riga della foglia, e gli altri libri Long/ non hanno intestazioni
    # di sezione. Toglierlo e' cio' che rende i libri uniformi fra loro.
    while head and (not head[-1].strip() or head[-1].lstrip().startswith("##")):
        head.pop()
    head = "\n".join(head).rstrip("\n")

    body = "\n\n".join(leaf_body_raw(os.path.join(work_dir, s)) for s in secs)
    new = head + "\n\n" + body + "\n"

    a, b = len(chk.body(book)), len(sum((chk.body(os.path.join(work_dir, s)) for s in secs), []))
    print("%-40s libro %d -> %d righe (foglie %d, testa %d righe)"
          % (name, a, len(new.split("\n")), b, len(head.split("\n"))))
    if write:
        io.open(book, "w", encoding="utf-8").write(new)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("works", nargs="+", help="rel della directory-opera nel vault")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    ok = True
    for w in args.works:
        ok &= rebuild(os.path.join(dt.VAULT_ROOT, w), args.write)
    if not args.write:
        print("(DRY-RUN: nulla scritto)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
