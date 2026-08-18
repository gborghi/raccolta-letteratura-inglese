# -*- coding: utf-8 -*-
"""Upsert translations_pages.jsonl straight from vault (atom.md, atom.it.md) pairs.

gkc_emit_vault.py rebuilds a *content page* by block substitution, which no longer
works for SPA reading pages: preprocess concatenates every atom of a work into one
markdown file behind atom-split markers, so the per-atom block hashes never line up
and each page comes back "partial" (an atom-split <span> counts as an untranslated
block). This emitter skips content/ altogether and keys each entry by the SPA unit
rel that publishUnits() looks up:

    testi/<author>/<sub>/<relU>          (lowercased, relU = path under Authors/<A>/<sub>)

body_it is the IT sibling's body minus frontmatter and minus the leading H1 (the
reader takes the title from data-title, exactly as it does for the EN side).

Usage: emit_vault_units.py <author> [<author> ...]      e.g. emit_vault_units.py coleridge eliot
"""
import os, sys, re, glob, json

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA = os.path.join(ROOT, "data")
PAGE_STORE = os.path.join(DATA, "translations_pages.jsonl")
VAULT_AUTHORS = os.path.abspath(os.path.join(ROOT, "..", "VaultEnglish", "Authors"))
SUBS = ("Atomized", "Plays", "Long", "Poems")
FM_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", re.S)
H1_RE = re.compile(r"^([ \t]*\r?\n)*[ \t]*#[ \t]+[^\n]*\r?\n")


def author_dir(author):
    want = author.replace(" ", "_").lower()
    for d in os.listdir(VAULT_AUTHORS):
        if d.lower() == want:
            return d, os.path.join(VAULT_AUTHORS, d)
    raise SystemExit("autore non trovato nel vault: " + author)


def body_of(path):
    raw = open(path, encoding="utf-8").read()
    m = FM_RE.match(raw)
    return (m.group(2) if m else raw)


def blocks(body):
    return [b for b in re.split(r"\n[ \t]*\n", body.strip()) if b.strip()]


def collect(author):
    """-> (rel, body_it) for every translated leaf, plus counters."""
    folder, base = author_dir(author)
    out, skipped, orphan = [], [], 0
    for sub in SUBS:
        subRoot = os.path.join(base, sub)
        if not os.path.isdir(subRoot):
            continue
        for it_path in sorted(glob.glob(os.path.join(subRoot, "**", "*.it.md"), recursive=True)):
            relU = os.path.relpath(it_path, subRoot).replace(os.sep, "/")
            if any(seg.startswith("_") for seg in relU.split("/")):
                continue
            en_path = it_path[:-6] + ".md"
            if not os.path.exists(en_path):
                orphan += 1
                continue
            en, it = body_of(en_path), body_of(it_path)
            # Same block count on both sides or the two panes drift apart; a
            # mismatch means the .it.md was written against a stale EN atom.
            if len(blocks(en)) != len(blocks(it)):
                skipped.append(relU)
                continue
            body_it = H1_RE.sub("", it).rstrip() + "\n"
            rel = "testi/{}/{}/{}".format(folder, sub, relU[:-6] + ".md").lower()
            out.append((rel, body_it))
    return out, skipped, orphan


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    store = {}
    if os.path.exists(PAGE_STORE):
        for ln in open(PAGE_STORE, encoding="utf-8"):
            ln = ln.strip()
            if ln:
                r = json.loads(ln)
                store[r["rel"]] = r
    before = len(store)
    for author in sys.argv[1:]:
        rows, skipped, orphan = collect(author)
        new = sum(1 for rel, _ in rows if rel not in store)
        for rel, body_it in rows:
            store[rel] = {"rel": rel, "kind": "testi", "title_it": None, "body_it": body_it}
        print("{}: {} unita' ({} nuove, {} aggiornate) | blocchi disallineati {} | .it.md orfani {}"
              .format(author, len(rows), new, len(rows) - new, len(skipped), orphan))
        for relU in skipped[:20]:
            print("   DISALLINEATO " + relU)
    with open(PAGE_STORE, "w", encoding="utf-8") as fh:
        for rel in sorted(store):
            fh.write(json.dumps(store[rel], ensure_ascii=False) + "\n")
    print("store: {} -> {} pagine".format(before, len(store)))


if __name__ == "__main__":
    main()
