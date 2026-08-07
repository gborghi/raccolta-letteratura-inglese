#!/usr/bin/env python3
"""Ripara le foglie EN che contengono anche la sezione successiva.

Due difetti distinti, entrambi lasciati dall'atomizzatore e censiti da
check_leaf_overlap.py:

1.  SOVRAPPOSIZIONE. La foglia N e' stata scritta come "sezione N + sezione N+1".
    Il testo in eccesso e' identico, riga per riga, alla testa della foglia N+1:
    lo si taglia via. Riguarda solo The_Waste_Land e Ash-Wednesday.

2.  CODA ESTRANEA. L'ultima foglia di un'opera si porta dietro l'inizio dell'opera
    seguente -- di solito la sua sola intestazione. Qui non c'e' una foglia successiva
    con cui confrontarsi, quindi il punto di taglio e' dichiarato a mano nella tabella
    TAILS: la prima riga del blocco estraneo, verbatim. Un taglio puo' anche essere una
    scissione (`split`): il blocco non e' spazzatura ma un'unita' a se' -- le Note del
    Waste Land sono di Eliot, non di un curatore -- e allora diventa una foglia sua.

Il taglio lavora sulle righe grezze, non sul corpo normalizzato, cosi' i due spazi
finali che in markdown fanno l'a-capo forzato restano dove sono.

Uso:
    python3 fix_leaf_overlap.py            # dry-run: dice cosa taglierebbe
    python3 fix_leaf_overlap.py --write
"""

import argparse
import io
import os
import re

import check_leaf_overlap as chk
import dickens_tower as dt

# rel della foglia -> (prima riga del blocco estraneo, nome della nuova foglia o None)
# None = il blocco e' solo l'intestazione dell'opera successiva, si butta.
TAILS = {
    "Authors/Eliot/Long/The_Hollow_Men/Section_05_part_v.md": (
        "[[Ash-Wednesday|ASH-WEDNESDAY]]",
        None,
    ),
    "Authors/Eliot/Long/Ash-Wednesday/Section_06_vi.md": (
        "[[Ariel|ARIEL]] [[Poems|POEMS]]",
        None,
    ),
    "Authors/Eliot/Long/The_Waste_Land/Section_05_v_what_the_thunder_said.md": (
        "Notes on the Waste Land",
        "Section_06_notes_on_the_waste_land.md",
    ),
}


def split_head(text):
    """(frontmatter+H1, resto). Il frontmatter va copiato verbatim, mai riscritto."""
    head = ""
    rest = text
    if rest.startswith("---") and "\n---\n" in rest:
        fm, rest = rest.split("\n---\n", 1)
        head = fm + "\n---\n"
    m = re.match(r"(\s*#[^\n]*\n)", rest)
    if m:
        head += m.group(1)
        rest = rest[m.end():]
    return head, rest


def cut_after_body_line(text, keep):
    """Taglia il testo dopo la keep-esima riga non vuota del corpo.

    Restituisce (testa+corpo_tenuto, coda_tagliata). keep==0 non taglia nulla.
    """
    head, rest = split_head(text)
    lines = rest.split("\n")
    seen = 0
    for i, l in enumerate(lines):
        if l.strip():
            seen += 1
            if seen == keep:
                kept = "\n".join(lines[: i + 1]).rstrip("\n") + "\n"
                tail = "\n".join(lines[i + 1:]).strip("\n")
                return head + kept, tail
    return text, ""


def cut_at_marker(text, marker):
    """Taglia il testo alla prima riga uguale a marker. (tenuto, coda)."""
    head, rest = split_head(text)
    lines = rest.split("\n")
    for i, l in enumerate(lines):
        if l.strip() == marker:
            kept = "\n".join(lines[:i]).rstrip("\n") + "\n"
            tail = "\n".join(lines[i:]).strip("\n")
            return head + kept, tail
    return text, ""


def do_overlaps(vault, write):
    n = 0
    for _author, rel, d in chk.walk_works(vault):
        secs = chk.units(d)
        if len(secs) < 2:
            continue
        B = [chk.body(os.path.join(d, s)) for s in secs]
        for i in range(len(secs) - 1):
            k = chk.overlap(B[i], B[i + 1])
            if not k:
                continue
            p = os.path.join(d, secs[i])
            text = io.open(p, encoding="utf-8").read()
            kept, tail = cut_after_body_line(text, len(B[i]) - k)
            if not tail:
                print("!! %s: taglio non riuscito" % os.path.join(rel, secs[i]))
                continue
            print("%-62s -%4d righe (%d -> %d)"
                  % (os.path.join(rel, secs[i]), k, len(B[i]), len(B[i]) - k))
            if write:
                io.open(p, "w", encoding="utf-8").write(kept)
            n += 1
    return n


def do_tails(vault, write):
    n = 0
    for rel, (marker, newname) in sorted(TAILS.items()):
        p = os.path.join(vault, rel)
        if not os.path.exists(p):
            print("!! manca %s" % rel)
            continue
        text = io.open(p, encoding="utf-8").read()
        kept, tail = cut_at_marker(text, marker)
        if not tail:
            print("== %s: coda gia' assente" % rel)
            continue
        verb = "scissa in %s" % newname if newname else "eliminata"
        print("%-62s coda %d righe, %s"
              % (rel, len(tail.split("\n")), verb))
        if write:
            io.open(p, "w", encoding="utf-8").write(kept)
            if newname:
                head, _ = split_head(text)
                fm = head.split("\n---\n")[0] + "\n---\n" if "\n---\n" in head else ""
                title = marker
                out = os.path.join(os.path.dirname(p), newname)
                io.open(out, "w", encoding="utf-8").write(
                    "%s\n# %s\n\n%s\n" % (fm, title, tail))
        n += 1
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    print("--- sovrapposizioni ---")
    a = do_overlaps(dt.VAULT_ROOT, args.write)
    print("--- code estranee ---")
    b = do_tails(dt.VAULT_ROOT, args.write)
    print("\nfoglie toccate: %d sovrapposte, %d con coda%s"
          % (a, b, "" if args.write else "  (DRY-RUN: nulla scritto)"))


if __name__ == "__main__":
    main()
