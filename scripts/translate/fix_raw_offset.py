#!/usr/bin/env python3
"""Toglie dalle foglie EN il testo dell'opera successiva, entrato per uno sfalsamento della _raw.

L'ingestione ha scritto il file grezzo N come "unita' N + unita' N+1". Dove una foglia del
vault e' stata costruita 1:1 da un file grezzo, si e' portata dietro l'errore: ogni poesia
compare due volte sul sito, in fondo alla precedente e poi al posto suo. Riguarda Eliot
(86 foglie) e Conan Doyle (4); l'ordine dei file grezzi e' quello alfabetico del prefisso
numerico, che e' anche l'ordine del libro.

Il punto di taglio non e' un'euristica: e' la coda della foglia che coincide, riga per riga
(a wikilink neutralizzati), con la testa del file grezzo successivo. In tutti i casi censiti
cade su un confine di blocco, quindi si taglia a blocchi interi.

La traduzione va tagliata insieme all'originale, o resta piu' lunga della sua fonte. Se il
.it.md ha lo stesso numero di blocchi dell'EN, gli si tolgono gli stessi blocchi finali; se
non li ha -- la traduzione ha unito o spezzato blocchi -- non c'e' corrispondenza da tagliare
e il file viene rimosso, cosi' la coda dell'autore lo ritraduce sulla sorgente ormai pulita.

Uso:
    python3 fix_raw_offset.py                    # dry-run
    python3 fix_raw_offset.py --write
"""

import argparse
import collections
import io
import os
import re

import dickens_tower as dt

WL = re.compile(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]")
AUTHORS = ("Eliot", "Conan_Doyle")
SUBTREES = ("Long", "Plays", "Poems", "Atomized")


def norm(text):
    """Righe di contenuto, senza frontmatter/H1 e con i wikilink ridotti al loro alias.

    I grezzi non hanno wikilink, le foglie si': il confronto va fatto sul testo nudo.
    """
    if text.startswith("---") and "\n---\n" in text:
        text = text.split("\n---\n", 1)[1]
    text = re.sub(r"^#[^\n]*\n", "", text.lstrip(), count=1)
    out = []
    for l in text.split("\n"):
        s = re.sub(r"\s+", " ", WL.sub(r"\1", l).replace(" ", " ")).strip()
        if s:
            out.append(s)
    return out


def tail_overlap(a, b):
    """Quante righe finali di a sono l'inizio di b."""
    n = 0
    for k in range(1, min(len(a), len(b)) + 1):
        if a[-k:] == b[:k]:
            n = k
    return n


def blocks_for_lines(text, k):
    """Quanti blocchi finali di text contengono esattamente k righe di contenuto.

    None se k non cade su un confine di blocco -- in quel caso non si taglia niente.
    """
    blocks = dt.prose_blocks(text)
    seen = 0
    for i in range(len(blocks) - 1, -1, -1):
        seen += len([x for x in blocks[i].split("\n") if x.strip()])
        if seen == k:
            return len(blocks) - i
        if seen > k:
            return None
    return None


def drop_tail_blocks(text, nblocks):
    """text senza i suoi ultimi nblocks blocchi."""
    blocks = dt.prose_blocks(text)
    first_removed = blocks[len(blocks) - nblocks]
    i = text.rfind(first_removed)
    if i <= 0:
        return None
    return text[:i].rstrip("\n") + "\n"


def contaminated(vault):
    """(percorso foglia, righe di troppo, nome del grezzo da cui vengono)."""
    root = os.path.join(vault, "Authors")
    for a in AUTHORS:
        rawd = os.path.join(root, a, "_raw")
        if not os.path.isdir(rawd):
            continue
        files = sorted(f for f in os.listdir(rawd) if f.endswith(".md"))
        R = {}
        for f in files:
            R[f] = norm(io.open(os.path.join(rawd, f), encoding="utf-8", errors="replace").read())
        offset = {}
        for x, y in zip(files, files[1:]):
            k = tail_overlap(R[x], R[y])
            if k:
                offset[x] = (y, k)

        byname = collections.defaultdict(list)
        for sub in SUBTREES:
            base = os.path.join(root, a, sub)
            if not os.path.isdir(base):
                continue
            for dp, _dn, fn in os.walk(base):
                for f in fn:
                    if f.endswith(".md") and not f.endswith(".it.md"):
                        byname[f].append(os.path.join(dp, f))

        for f, (nxt, k) in sorted(offset.items()):
            for p in byname.get(f, []):
                L = norm(io.open(p, encoding="utf-8").read())
                if len(L) > k and L[-k:] == R[nxt][:k]:
                    yield p, k, nxt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    cut = skipped = it_cut = it_removed = it_absent = 0
    for p, k, nxt in contaminated(dt.VAULT_ROOT):
        rel = os.path.relpath(p, dt.VAULT_ROOT)
        en = io.open(p, encoding="utf-8").read()
        nb = blocks_for_lines(en, k)
        if nb is None:
            print("!! %-72s  -%d righe: taglio fuori dai blocchi, saltato" % (rel, k))
            skipped += 1
            continue
        new_en = drop_tail_blocks(en, nb)
        if new_en is None:
            print("!! %-72s  blocco finale non ritrovato, saltato" % rel)
            skipped += 1
            continue

        itp = p[:-3] + ".it.md"
        note = "(nessuna traduzione)"
        new_it = None
        if os.path.exists(itp):
            it = io.open(itp, encoding="utf-8").read()
            if len(dt.prose_blocks(it)) == len(dt.prose_blocks(en)):
                new_it = drop_tail_blocks(it, nb)
                note = "it: -%d blocchi" % nb if new_it else "it: taglio fallito"
            else:
                note = "it: blocchi disallineati -> rimosso, da ritradurre"
        else:
            it_absent += 1

        print("%-72s -%3d righe / -%d blocchi  <- %s  %s" % (rel, k, nb, nxt, note))
        cut += 1
        if args.write:
            io.open(p, "w", encoding="utf-8").write(new_en)
            if os.path.exists(itp):
                if new_it:
                    io.open(itp, "w", encoding="utf-8").write(new_it)
                    it_cut += 1
                else:
                    os.remove(itp)
                    it_removed += 1
        elif os.path.exists(itp):
            if new_it:
                it_cut += 1
            else:
                it_removed += 1

    print("\nfoglie tagliate: %d (saltate %d) | .it.md tagliati: %d, rimossi: %d, assenti: %d%s"
          % (cut, skipped, it_cut, it_removed, it_absent,
             "" if args.write else "   (DRY-RUN: nulla scritto)"))


if __name__ == "__main__":
    main()
