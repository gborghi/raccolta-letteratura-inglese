# -*- coding: utf-8 -*-
"""Toglie dai versi i numeri di riga di Gutenberg rimasti incollati al testo.

Le edizioni Gutenberg numerano i versi ogni dieci nel margine. Se l'ingestione non separa il
margine dal testo, quel numero finisce in testa al verso -- '10 And went on in sunlight,' --
e da li' in poi e' indistinguibile dalla poesia: si pubblica, si traduce, e nessuna guardia
lo vede, perche' per ogni controllo e' semplicemente una parola in piu'.

    python3 strip_line_numbers.py [--author X] [--write]

Si tocca solo cio' che e' certo: un numero in testa alla riga, multiplo di cinque, seguito da
altro testo, in un file in versi, e almeno due nella stessa OPERA, crescenti. Un verso non
comincia due volte per caso con un numero tondo che sale; un numero isolato, invece, puo'
benissimo essere il testo (una data, un'ora), e resta dov'e'.

La conferma si cerca nell'opera, non nel file: il margine si divide fra le sezioni come cade,
e a 'Death by Water', lunga dieci versi, ne tocca uno solo. Cercandola nel file quella sezione
resterebbe numerata mentre le sorelle e l'aggregato che la contiene sono gia' pulite -- la
disuniformita' peggiore, perche' nasce dalla riparazione.

Si toglie il numero e al piu' UNO spazio ASCII dopo. Non di piu': il rientro del verso e'
scritto con lo spazio unificatore U+00A0, che spesso segue subito il numero, e mangiarlo
sposterebbe il verso a filo di margine -- lo stesso danno che ripara check_indent.
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check_indent as ci
import leafcheck

# Il separatore va enumerato: se lo si scrive (?=\S), lo spazio unificatore conta come
# spazio e la ricerca ripiega su un numero piu' corto pur di far tornare il conto --
# '350\xa0\xa0 Ganga' si legge allora come il numero 35 seguito da '0 Ganga', e il verso
# perderebbe le due cifre di testa restando con uno zero orfano.
NUM = re.compile(r"^(\d{1,4})(?=[ \t ])")


def numbered(lines):
    """Le righe che cominciano con un numero di riga plausibile, come (indice, numero)."""
    out = []
    for k, l in enumerate(lines):
        m = NUM.match(l)
        if not m or int(m.group(1)) % 5:
            continue
        if not l[m.end(1):].strip():
            continue  # numero solo, senza verso dopo: non e' un margine
        out.append((k, int(m.group(1))))
    return out


def scan(path):
    """(righe, colpi) del file, senza deciderne nulla."""
    lines = io.open(path, encoding="utf-8").read().split("\n")
    return lines, numbered(lines)


def rises(hits):
    """Vero se i numeri di un singolo file salgono."""
    return all(a < b for (_, a), (_, b) in zip(hits, hits[1:]))


def strip(path, lines, hits):
    for k, _ in hits:
        lines[k] = NUM.sub("", lines[k])
    io.open(path, "w", encoding="utf-8", newline="\n").write("\n".join(lines))


def walk_en(author, vault):
    """Ogni .md inglese sotto i sottoalberi d'autore: foglie E aggregati.

    L'aggregato non si rigenera dall'inglese -- e' anch'esso una sorgente -- e porta lo
    stesso margine numerico dei figli, quindi va ripulito insieme a loro.
    """
    base = os.path.join(vault, "Authors")
    for name in sorted(os.listdir(base)):
        if author and name != author:
            continue
        for sub in leafcheck.SUBTREES:
            top = os.path.join(base, name, sub)
            if not os.path.isdir(top):
                continue
            for root, _dirs, files in os.walk(top):
                for f in sorted(files):
                    if f.endswith(".md") and not f.endswith(".it.md"):
                        yield os.path.relpath(os.path.join(root, f), vault)


def run(author=None, write=False):
    seen, works = 0, {}
    for rel in walk_en(author, ci.VAULT_ROOT):
        p = os.path.join(ci.VAULT_ROOT, rel)
        if not ci.is_verse(p):
            continue
        seen += 1
        lines, hits = scan(p)
        if hits:
            works.setdefault(os.path.dirname(rel), []).append((rel, p, lines, hits))

    bad = []
    for _work, files in sorted(works.items()):
        # l'opera conferma se in tutto ha almeno due numeri e nessun file li ha calanti.
        # Non si incolonnano i numeri di file diversi: l'aggregato riparte da capo, e
        # una serie unica pretesa fra sezione e aggregato non salirebbe mai.
        if sum(len(h) for _r, _p, _l, h in files) < 2:
            continue
        if not all(rises(h) for _r, _p, _l, h in files):
            continue
        for rel, p, lines, hits in files:
            bad.append((rel, len(hits)))
            if write:
                strip(p, lines, hits)
    for rel, n in sorted(bad, key=lambda x: -x[1]):
        print("%4d  %s" % (n, rel))
    print("\n%d file in versi esaminati, %d con numeri di riga, %d righe%s"
          % (seen, len(bad), sum(n for _, n in bad), " -- ripulite" if write else ""))


if __name__ == "__main__":
    a = sys.argv[1:]
    run(a[a.index("--author") + 1] if "--author" in a else None, "--write" in a)
