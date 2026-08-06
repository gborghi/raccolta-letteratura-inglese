# -*- coding: utf-8 -*-
"""Riassembla con --force SOLO le opere elencate in aggregati_da_riforzare.txt (task #14).

    python3 force_reassemble.py                # dry-run: dice cosa farebbe
    python3 force_reassemble.py --write        # scrive davvero

Perche' un driver invece di assemble_aggregates.py --force --author X: il CLI filtra per
AUTORE, non per opera, quindi rifarebbe tutti gli aggregati dell'autore. Sui Dickens sarebbero
tutti e non i 13 in lista. Qui si riusa assemble() -- la funzione autorevole, ricorsione
depth-first e memoizzazione comprese -- e si filtra soltanto cosa darle in pasto.

Chesterton non e' in lista e non deve entrarci: i suoi 162 aggregati non sono assemblati dalle
foglie, furono tradotti dal modello a blocco unico. Rifarli e' decisione editoriale, non
riparazione. Il driver si rifiuta di toccarli anche se qualcuno li aggiungesse al file.

Guardia: --force a code VIVE tronca in silenzio (assemble() controlla che il figlio esista,
non che sia completo). Lo script esce se trova una coda di traduzione in esecuzione.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# lo script vive in scripts/translate/handoff/: il modulo sta un livello sopra
TRANSLATE = os.path.dirname(HERE)
sys.path.insert(0, TRANSLATE)

import assemble_aggregates as A          # noqa: E402
from leafcheck import VAULT_ROOT         # noqa: E402

LISTA = os.path.join(HERE, "aggregati_da_riforzare.txt")
VIETATI = ("Chesterton",)


def opere():
    """Le righe VaultEnglish/Authors/... del file di lista, come path assoluti."""
    out = []
    for ln in open(LISTA, encoding="utf-8"):
        ln = ln.strip()
        if not ln.startswith("VaultEnglish/Authors/"):
            continue
        rel = ln[len("VaultEnglish/"):]
        autore = rel.split("/")[1]
        if autore in VIETATI:
            sys.exit("RIFIUTO: %s e' in lista ma non va riassemblato (%s)" % (rel, autore))
        p = os.path.join(VAULT_ROOT, rel)
        if not os.path.isdir(p):
            sys.exit("MANCA la cartella dell'opera: %s" % p)
        out.append(p)
    return out


def code_vive():
    """PID delle code di traduzione ancora in esecuzione."""
    try:
        ps = subprocess.run(["ps", "-axo", "pid=,command="],
                            capture_output=True, text=True).stdout
    except OSError:
        return ["ps non disponibile: verifica a mano"]
    # elencarli per nome e' fragile: la coda tails gira come finish_tails.py e il primo
    # elenco che avevo scritto la mancava, cioe' la guardia avrebbe lasciato passare
    # proprio la coda che stava scrivendo le foglie di queste opere.
    vive = []
    for ln in ps.splitlines():
        if any(k in ln for k in ("run_author_hy", "run_dickens_hy", "rerun_atoms",
                                 "finish_tails", "run_dickens_all", "_hy.py",
                                 "_tower.py", "retranslate_rejected")):
            vive.append(ln.strip()[:110])
    return vive


def main():
    write = "--write" in sys.argv[1:]

    vive = code_vive()
    if vive and write:
        print("CODE ANCORA VIVE -- non scrivo: assemblare mentre le foglie vengono scritte")
        print("produce un aggregato troncato in silenzio.")
        for v in vive:
            print("   " + v)
        return 1
    if vive:
        print("nota: %d code vive, questo e' solo un dry-run\n" % len(vive))

    radici = opere()
    print("opere in lista: %d" % len(radici))

    bersagli = [p for p in A.walk_aggregates()
                if any(p.startswith(r + os.sep) or p[:-3] == r for r in radici)]
    print("aggregati dentro quelle opere: %d\n" % len(bersagli))

    stats = {"built": [], "incomplete": [], "no_title": [], "texts": {}, "seen": {}}
    for p in bersagli:
        A.assemble(p, stats, write, True)

    tag = "riscritti" if write else "da riscrivere (dry-run)"
    print("aggregati %s: %d" % (tag, len(stats["built"])))
    for rel, n, k in stats["built"]:
        print("   %s  (%d B da %d figli)" % (rel, n, k))
    if stats["incomplete"]:
        print("\nbloccati da figli non tradotti: %d" % len(stats["incomplete"]))
        for rel, miss, tot in stats["incomplete"]:
            print("   %s  (%d/%d figli senza .it.md)" % (rel, miss, tot))
    if stats["no_title"]:
        print("\nsenza titolo derivabile dai figli: %d" % len(stats["no_title"]))
        for rel in stats["no_title"]:
            print("   %s" % rel)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
