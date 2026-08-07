# -*- coding: utf-8 -*-
"""Censisce le foglie tradotte in cui il rientro dell'italiano non e' quello dell'inglese.

Le sorgenti rientrano i versi con lo spazio unificatore U+00A0: e' l'unico che markdown non
riassorbe, e chi traduce a mano riscrive il rientro con lo spazio ASCII senza accorgersene.
Il risultato e' un verso che nella pagina resa torna a filo di margine, in silenzio -- nessuna
guardia di dickens_tower guarda i caratteri iniziali, tutte confrontano righe gia' rstrip-ate.

    python3 check_indent.py [--author X] [--write]

Vale solo per i versi. In prosa la riga italiana non e' la riga inglese -- il testo si
riavvolge diverso -- e confrontare i rientri riga per riga non solo non dice niente, ma
riscriverli sposterebbe il rientro su un capoverso che non c'entra. La prosa e' esclusa.

Confronta solo le coppie EN/IT con lo stesso numero di righe: dove le righe non corrispondono
il rientro non e' confrontabile e il problema e' un altro. Con --write ricopia il rientro
inglese sulla riga italiana -- si tocca solo cio' che precede il testo, mai il testo.
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import leafcheck

VAULT_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(HERE))), "VaultEnglish")
INDENT = " \\t\\u00a0".encode().decode("unicode_escape")
LEAD = re.compile("^[" + INDENT + "]*")


def lines(path):
    t = io.open(path, encoding="utf-8").read()
    if t.startswith("---") and "\n---\n" in t:
        t = t.split("\n---\n", 1)[1]
    return t.split("\n")


def is_verse(path):
    """Vero se il file tiene i suoi a capo: in markdown, due spazi in fondo alla riga.

    E' il segno che opus_atom ha scritto con --verse, ed e' l'unico caso in cui la riga k
    dell'italiano risponde alla riga k dell'inglese.
    """
    body = [l for l in lines(path) if l.strip()]
    if not body:
        return False
    return sum(1 for l in body if l.endswith("  ")) * 2 > len(body)


def reindent(en_path, it_path):
    """Ricopia il rientro EN sulle righe IT. Ritorna quante righe ha cambiato.

    Si allinea sulla coda: il frontmatter italiano puo' essere piu' lungo o piu' corto di
    quello inglese, ma il corpo -- l'unica parte con dei versi -- finisce alla stessa riga.
    """
    en = io.open(en_path, encoding="utf-8").read().split("\n")
    it = io.open(it_path, encoding="utf-8").read().split("\n")
    eb, ib = lines(en_path), lines(it_path)
    out, n = it[:len(it) - len(ib)], 0
    for e, t in zip(en[len(en) - len(eb):], it[len(it) - len(ib):]):
        lead = LEAD.match(e).group(0)
        body = t.lstrip(INDENT)
        new = (lead + body) if body else t
        n += new != t
        out.append(new)
    if n:
        io.open(it_path, "w", encoding="utf-8", newline="\n").write("\n".join(out))
    return n


def check(author=None, write=False):
    bad, seen = [], 0
    authors = [author] if author else sorted(
        d for d in os.listdir(os.path.join(VAULT_ROOT, "Authors"))
        if os.path.isdir(os.path.join(VAULT_ROOT, "Authors", d)))
    for a in authors:
        for _a, rel in leafcheck.walk_leaves(a, VAULT_ROOT):
            en = os.path.join(VAULT_ROOT, rel)
            it = en[:-len(".md")] + ".it.md"
            if not os.path.exists(it):
                continue
            if not is_verse(en):
                continue
            seen += 1
            el, il = lines(en), lines(it)
            if len(el) != len(il):
                continue
            # una riga inglese fatta solo di spazi unificatori e' una riga vuota "spessa":
            # ricopiarla sopra la riga vuota italiana cambierebbe i confini dei blocchi,
            # perche' per prose_blocks quella riga non e' vuota. Si lascia stare, e non si
            # conta -- altrimenti il censimento segnala per sempre cio' che non va toccato.
            diff = [k for k, (e, i) in enumerate(zip(el, il), 1)
                    if e.lstrip(INDENT) and LEAD.match(e).group(0) != LEAD.match(i).group(0)]
            if diff:
                bad.append((rel, reindent(en, it) if write else len(diff)))
    for rel, n in sorted(bad, key=lambda x: -x[1]):
        print("%5d  %s" % (n, rel))
    print("\n%d foglie tradotte esaminate, %d con rientri divergenti%s"
          % (seen, len(bad), " -- riscritte" if write else ""))


if __name__ == "__main__":
    a = sys.argv[1:]
    check(a[a.index("--author") + 1] if "--author" in a else None, "--write" in a)
