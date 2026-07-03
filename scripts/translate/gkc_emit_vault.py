# -*- coding: utf-8 -*-
"""Build translations_pages.jsonl from FULL-PAGE vault .it.md siblings (Opus output).

Unlike gkc_emit.py (block .jsonl cache), this sources the block cache directly from
the para-aligned vault (atom.md, atom.it.md) pairs: sha(EN prose block) -> IT block.
Then, exactly like gkc_emit, it walks content/testi/<author>/** and rebuilds each
page's IT body by block replacement, upserting into translations_pages.jsonl
(existing entries for other authors preserved). Aggregate pages (whole work/chapter)
are reconstructed from atom blocks by construction.

Usage: gkc_emit_vault.py <author>        e.g. gkc_emit_vault.py chesterton
"""
import os, sys, re, glob, json, hashlib
sys.path.insert(0, os.path.dirname(__file__))
from sbtrans import clean_body, split_blocks, has_prose

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CONTENT = os.path.join(ROOT, "content")
DATA = os.path.join(ROOT, "data")
PAGE_STORE = os.path.join(DATA, "translations_pages.jsonl")
VAULT_AUTHORS = "E:/giovanni/Dropbox/insegnamento/Wiligelmo/SubjectBrain/English/Authors"
FM_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", re.S)
QSWITCH_RE = re.compile(r'<div class="qlang-switch"[^>]*></div>\s*\n?')
QSPLIT_RE = re.compile(r'\n?\s*<span class="qlang-split"[^>]*></span>.*$', re.S)

def sha(s): return hashlib.sha1(s.encode("utf-8")).hexdigest()

def strip_qlang(body):
    # drop the language-toggle div and everything from the EN/IT split onward,
    # so we only ever see the English body of an already-bilingual page.
    return QSPLIT_RE.sub("", QSWITCH_RE.sub("", body))

def parse(path):
    raw = open(path, encoding="utf-8").read()
    m = FM_RE.match(raw)
    if not m:
        return None, strip_qlang(raw)
    tm = re.search(r'(?m)^title:\s*"?(.*?)"?\s*$', m.group(1))
    return (tm.group(1) if tm else None), strip_qlang(m.group(2))

def prose_parts(body):
    """Ordered (stripped_key, raw_block) for prose blocks (skip nav/blank/non-prose)."""
    out = []
    for part in split_blocks(clean_body(body)):
        p = part.strip()
        if not p or p.startswith("<nav") or not has_prose(p):
            continue
        out.append((p, part))
    return out

def build_cache(author):
    vbase = os.path.join(VAULT_AUTHORS, author.capitalize(), "Atomized")
    cache = {}
    pairs = mism = 0
    for it_path in glob.glob(os.path.join(vbase, "**", "*.it.md"), recursive=True):
        en_path = it_path[:-6] + ".md"
        if not os.path.exists(en_path):
            continue
        _, en_body = parse(en_path)
        _, it_body = parse(it_path)
        ep, ip = prose_parts(en_body), prose_parts(it_body)
        if len(ep) != len(ip):
            mism += 1
            continue
        pairs += 1
        for (ekey, _eraw), (_ikey, iraw) in zip(ep, ip):
            cache.setdefault(sha(ekey), iraw.strip("\n"))
    return cache, pairs, mism

def translate_body(body, cache, st):
    out = []
    for part in split_blocks(clean_body(body)):
        p = part.strip()
        if not p or p.startswith("<nav") or not has_prose(p):
            out.append(part); continue
        it = cache.get(sha(p))
        if it is None:
            st["miss"] += 1; out.append(part)
        else:
            st["hit"] += 1; out.append(it)
    return "".join(out)

def main():
    author = sys.argv[1]
    cache, pairs, mism = build_cache(author)
    print(f"cache blocks={len(cache)} from atom-pairs={pairs} (block-count mismatches skipped={mism})")

    store = {}
    if os.path.exists(PAGE_STORE):
        for ln in open(PAGE_STORE, encoding="utf-8"):
            ln = ln.strip()
            if ln:
                r = json.loads(ln); store[r["rel"]] = r

    pages = [p for p in glob.glob(os.path.join(CONTENT, "testi", author, "**", "*.md"), recursive=True)
             if not p.endswith(".it.md")]
    upserted = full = partial = 0
    tot_hit = tot_miss = 0
    for path in pages:
        title, body = parse(path)
        st = {"hit": 0, "miss": 0}
        body_it = translate_body(body, cache, st)
        if st["hit"] == 0:
            continue
        # Only publish FULLY-translated pages (no EN blocks left) so every IT toggle
        # is complete. Partially-covered pages stay EN-only until their atoms finish.
        if st["miss"] > 0:
            partial += 1
            continue
        tot_hit += st["hit"]
        full += 1
        rel = os.path.relpath(path, CONTENT).replace("\\", "/")
        title_it = cache.get(sha(title.strip())) if title else None
        store[rel] = {"rel": rel, "kind": "testi", "title_it": title_it, "body_it": body_it}
        upserted += 1

    with open(PAGE_STORE, "w", encoding="utf-8") as fh:
        for rel in sorted(store):
            fh.write(json.dumps(store[rel], ensure_ascii=False) + "\n")
    print(f"pages upserted={upserted} (full={full} partial={partial}) | store total={len(store)} | blocks hit={tot_hit} miss={tot_miss}")

if __name__ == "__main__":
    main()
