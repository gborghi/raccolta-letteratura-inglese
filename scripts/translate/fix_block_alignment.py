# -*- coding: utf-8 -*-
"""Riallinea i blocchi di una traduzione al suo inglese, muovendo solo righe vuote.

`emit_vault_units.py` pubblica un'unita' solo se EN e IT hanno lo stesso numero di blocchi,
e quando non l'hanno la scarta **in silenzio**: la traduzione esiste, e' giusta, e non arriva
sul sito. Quasi sempre la causa non e' testo perso ma una riga vuota di troppo o in meno --
il modello ha reso due paragrafi inglesi come due righe consecutive, o ha spezzato in due un
paragrafo solo.

Qui non si aggiunge e non si toglie un carattere di testo: si apre o si chiude una riga vuota.
A ogni passo si provano *tutte* le mosse possibili, si riallinea l'intero file per ognuna e si
tiene quella di costo minimo; poi si ricomincia, finche' i conteggi combaciano.

Il costo di un blocco e' `|log(len_it / (1.12 * len_en))|`: l'italiano e' mediamente un ottavo
piu' lungo dell'inglese, ed e' l'unico invariante che si abbia fra due lingue. Il punto va
guardato sull'INTERO file, mai sul solo blocco sospetto: un blocco corto che segue (una
battuta di due parole, l'intestazione di un capitolo) sparisce dentro il rumore del rapporto
locale, e la diagnosi dice "blocco saltato" dove il blocco c'e'.

    python3 fix_block_alignment.py <path.it.md> [...]           # dry-run, mostra i tagli
    python3 fix_block_alignment.py --author Dickens             # cerca da se' le unita' rotte
    python3 fix_block_alignment.py --author Dickens --write
"""
import argparse
import glob
import io
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import emit_vault_units as ev  # noqa: E402

EXP = 1.12
# Un blocco spaiato costa piu' di qualunque errore di lunghezza plausibile, cosi' la ricerca
# non "paga" mai un disallineamento in cambio di due blocchi di lunghezza piu' simile.
UNPAIRED = 3.0
MAX_STEPS = 200

# La sola lunghezza non basta a scegliere dove aprire. Dove la traduzione ha conservato gli
# a-capo tipografici dell'inglese, un blocco e' pieno di newline che cadono in mezzo a una
# frase, e il costo puo' benissimo preferirne una: "...con un'espressione piu' pensierosa |
# e affabile." Un confine di paragrafo si riconosce invece dai due lati -- la riga prima
# chiude una frase, la riga dopo ne apre una.
END_OK = ".!?…:;»”\"')]_*"
START_OK = "«“\"'_*#[—-("


def cost(it, en):
    return abs(math.log(max(len(it), 1) / (EXP * max(len(en), 1))))


def total(bi, be):
    n = min(len(bi), len(be))
    return (sum(cost(bi[i], be[i]) for i in range(n))
            + UNPAIRED * abs(len(bi) - len(be)))


def is_boundary(a, b, wrap):
    """Se questa newline puo' essere un confine di paragrafo, a giudicare dai due lati.

    `wrap` e' la riga piu' lunga del blocco: dove il testo e' mandato a capo a mano, le righe
    sono tutte larghe uguali, e una riga molto piu' corta e' un titolo -- che non finisce con
    un punto e che il solo criterio della punteggiatura scarterebbe.
    """
    a, b = a.rstrip(), b.lstrip()
    if not a or not b:
        return False
    c = b[0]
    if not (c.isupper() or c.isdigit() or c in START_OK):
        return False
    last = a.split("\n")[-1].strip()
    return a[-1] in END_OK or len(last) <= 0.6 * wrap


def step_split(body, be):
    """Apre una newline interna in riga vuota. -> (corpo, descrizione) oppure None."""
    bi = ev.blocks(body)
    best = None
    for k, blk in enumerate(bi):
        off = 0
        wrap = max(len(l.strip()) for l in blk.split("\n"))
        for line in blk.split("\n")[:-1]:
            off += len(line) + 1
            a, b = blk[:off].rstrip("\n"), blk[off:]
            if not a.strip() or not b.strip():
                continue
            if not is_boundary(a, b, wrap):
                continue
            s = total(bi[:k] + [a, b] + bi[k + 1:], be)
            if best is None or s < best[0]:
                best = (s, k, a, b)
    if best is None:
        return None
    _, k, a, b = best
    if body.count(bi[k]) != 1:
        return None
    return (body.replace(bi[k], a + "\n\n" + b, 1),
            "apro   %3d: ...%s || %s..." % (k, _tail(a), _head(b)))


def step_join(body, be):
    """Chiude la riga vuota fra due blocchi. -> (corpo, descrizione) oppure None."""
    bi = ev.blocks(body)
    best = None
    for k in range(len(bi) - 1):
        s = total(bi[:k] + [bi[k] + "\n" + bi[k + 1]] + bi[k + 2:], be)
        if best is None or s < best[0]:
            best = (s, k)
    if best is None:
        return None
    _, k = best
    old = bi[k] + "\n\n" + bi[k + 1]
    if body.count(old) != 1:
        return None
    return (body.replace(old, bi[k] + "\n" + bi[k + 1], 1),
            "chiudo %3d: ...%s || %s..." % (k, _tail(bi[k]), _head(bi[k + 1])))


def _tail(s):
    return s[-45:].replace("\n", "\\n")


def _head(s):
    return s[:45].replace("\n", "\\n")


def fix(path, write):
    en_path = path[:-6] + ".md"
    if not os.path.exists(en_path):
        print("!! %s: manca l'inglese" % path)
        return False
    raw = io.open(path, encoding="utf-8").read()
    body = ev.body_of(path)
    head = raw[:len(raw) - len(body)]
    be = ev.blocks(ev.body_of(en_path))
    rel = os.path.relpath(path, ev.VAULT_AUTHORS)
    print("== %s  EN %d IT %d" % (rel, len(be), len(ev.blocks(body))))
    for _ in range(MAX_STEPS):
        n = len(ev.blocks(body))
        if n == len(be):
            break
        r = (step_split if n < len(be) else step_join)(body, be)
        if r is None:
            print("   ! nessuna mossa possibile")
            break
        body, what = r
        print("   " + what)
    ok = len(ev.blocks(body)) == len(be)
    print("   -> IT %d %s" % (len(ev.blocks(body)), "OK" if ok else "NON RISOLTO"))
    if write and ok:
        io.open(path, "w", encoding="utf-8", newline="").write(head + body)
    return ok


def broken_units(author):
    """Le unita' dell'autore che emit_vault_units scarterebbe."""
    folder, base = ev.author_dir(author)
    out = []
    for sub in ev.SUBS:
        root = os.path.join(base, sub)
        if not os.path.isdir(root):
            continue
        for p in sorted(glob.glob(os.path.join(root, "**", "*.it.md"), recursive=True)):
            relU = os.path.relpath(p, root).replace(os.sep, "/")
            if any(seg.startswith("_") for seg in relU.split("/")):
                continue
            en = p[:-6] + ".md"
            if os.path.exists(en) and len(ev.blocks(ev.body_of(en))) != len(ev.blocks(ev.body_of(p))):
                out.append(p)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--author", default=None)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    paths = list(a.paths)
    if a.author:
        paths += broken_units(a.author)
    if not paths:
        raise SystemExit(__doc__)
    ok = sum(fix(p, a.write) for p in paths)
    print("\nrisolte %d su %d%s" % (ok, len(paths), "" if a.write else "  (DRY-RUN: nulla scritto)"))
    return 0 if ok == len(paths) else 1


if __name__ == "__main__":
    raise SystemExit(main())
