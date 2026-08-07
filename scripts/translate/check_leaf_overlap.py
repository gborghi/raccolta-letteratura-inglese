#!/usr/bin/env python3
"""Cerca le foglie EN che si sovrappongono alla foglia successiva.

Il difetto che questo script censisce: l'atomizzatore ha emesso, per alcune opere,
la sezione N come "sezione N + sezione N+1". Il testo non e' corrotto -- e' duplicato,
e la duplicazione arriva pari pari nel libro assemblato e quindi sul sito. Si vede solo
confrontando la coda di una foglia con la testa della successiva: se coincidono per k
righe, quelle k righe sono di troppo.

L'euristica e' volutamente letterale (uguaglianza riga per riga sul corpo, senza
frontmatter ne' H1): se due foglie condividono davvero un passo, quel passo e' stato
scritto due volte dalla stessa sorgente e le righe combaciano carattere per carattere.

Uso:
    python3 check_leaf_overlap.py                 # tutto il vault
    python3 check_leaf_overlap.py --author Eliot  # un autore solo
"""

import argparse
import io
import os
import re

import dickens_tower as dt

H1_RE = re.compile(r"^#[^\n]*\n")


def body(path):
    """Il corpo della foglia: senza frontmatter, senza H1, senza righe vuote."""
    t = io.open(path, encoding="utf-8").read()
    if t.startswith("---") and "\n---\n" in t:
        t = t.split("\n---\n", 1)[1]
    t = H1_RE.sub("", t.lstrip(), count=1)
    return [l.rstrip() for l in t.split("\n") if l.strip()]


def overlap(a, b):
    """Quante righe iniziali di b chiudono a. 0 se le due foglie sono disgiunte."""
    n = 0
    for k in range(1, min(len(a), len(b)) + 1):
        if a[-k:] == b[:k]:
            n = k
    return n


def units(work_dir):
    """Le foglie ordinate di una directory-opera: i Section_/Scene_ , non il libro."""
    return sorted(
        f
        for f in os.listdir(work_dir)
        if f.endswith(".md")
        and not f.endswith(".it.md")
        and re.match(r"^(Section|Scene|Chapter|part)_", f)
    )


def walk_works(vault, only_author=None):
    """Ogni directory che contiene foglie numerate, sotto Long/, Plays/, Poems/, Atomized/."""
    root = os.path.join(vault, "Authors")
    for author in sorted(os.listdir(root)):
        if only_author and author != only_author:
            continue
        if not os.path.isdir(os.path.join(root, author)):
            continue
        for sub in ("Long", "Plays", "Poems", "Atomized"):
            base = os.path.join(root, author, sub)
            if not os.path.isdir(base):
                continue
            for dirpath, _dirnames, _files in os.walk(base):
                if units(dirpath):
                    yield author, os.path.relpath(dirpath, vault), dirpath


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--author")
    args = ap.parse_args()

    bad = 0
    for author, rel, d in walk_works(dt.VAULT_ROOT, args.author):
        secs = units(d)
        if len(secs) < 2:
            continue
        B = [body(os.path.join(d, s)) for s in secs]
        hits = [(secs[i], secs[i + 1], overlap(B[i], B[i + 1])) for i in range(len(secs) - 1)]
        hits = [h for h in hits if h[2] > 0]
        if hits:
            bad += 1
            print("%s  (%d foglie)" % (rel, len(secs)))
            for a, b, k in hits:
                print("    %-40s -> %-40s %4d righe duplicate" % (a, b, k))
    print("\nopere con foglie sovrapposte: %d" % bad)


if __name__ == "__main__":
    main()
