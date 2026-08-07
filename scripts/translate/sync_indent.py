# -*- coding: utf-8 -*-
"""Ricopia il rientro dell'inglese sull'italiano, riga per riga, in un workdir di opus_verse.

Il rientro di un verso e' una scelta del poeta, non della lingua: le venticinque colonne
davanti a "In that open field" reggono la pagina e vanno rispettate. Ma contare gli spazi
a mano mentre si traduce e' il modo piu' facile di sbagliarli, e nessuna guardia di
opus_verse li controlla -- le righe sono confrontate dopo rstrip, non lstrip.

E non sono spazi: le sorgenti rientrano con lo spazio unificatore U+00A0, l'unico che
markdown non riassorbe. Un rientro riscritto a mano con lo spazio ASCII sparisce nella
pagina resa, in silenzio e senza che niente lo segnali -- e' proprio il caso che questo
script esiste per chiudere.

    python3 sync_indent.py <workdir> [--write]

Tocca solo le righe che hanno gia' del testo: una riga vuota resta vuota.
"""
import io
import os
import re
import sys

# scritto come escape: uno spazio unificatore incollato in chiaro e' indistinguibile da
# uno spazio normale in ogni diff e in ogni grep -- ed e' proprio l'errore che ripara
INDENT = " \t\u00a0"
LEAD = re.compile("^[ \\t\\u00a0]*")


def sync(workdir, write):
    for f in sorted(os.listdir(workdir)):
        if not f.endswith(".it.txt"):
            continue
        en_path = os.path.join(workdir, f[:-len(".it.txt")] + ".en.txt")
        if not os.path.exists(en_path):
            continue
        en = io.open(en_path, encoding="utf-8").read().split("\n")
        it = io.open(os.path.join(workdir, f), encoding="utf-8").read().split("\n")
        if len(en) != len(it):
            print("%s: %d righe IT vs %d EN, salto" % (f, len(it), len(en)))
            continue
        out, n = [], 0
        for e, t in zip(en, it):
            lead = LEAD.match(e).group(0)
            body = t.lstrip(INDENT)
            new = (lead + body) if body else t
            n += new != t
            out.append(new)
        if n and write:
            io.open(os.path.join(workdir, f), "w", encoding="utf-8",
                    newline="\n").write("\n".join(out))
        print("%s: %d righe rientrate%s" % (f, n, "" if write else " (dry-run)"))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[5])
        sys.exit(1)
    sync(sys.argv[1], "--write" in sys.argv)
