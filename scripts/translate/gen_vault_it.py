# -*- coding: utf-8 -*-
"""Write Italian ".it.md" sibling atoms into the Obsidian vault next to each
English Sayers atom (Authors/Sayers/Atomized/**), for reading in Obsidian.
Reuses the content-addressed segment cache (data/trans_seg_it.jsonl); any
uncached sentence is translated with nllb600 (venv). Vault atoms are clean
"# Title\\n\\n<body>" (no nav/frontmatter).
Run with the vault_topics venv python (needs ctranslate2 + transformers).
"""
import os, re, sys, glob
sys.path.insert(0, os.path.dirname(__file__))
import translate_sayers as T
from translate_sayers_nllb import build_translator, translate_batch

VAULT = r"E:/giovanni/Dropbox/insegnamento/Wiligelmo/SubjectBrain/English/Authors/Sayers/Atomized"

def split_title_body(raw):
    lines = raw.split("\n")
    ti = next((i for i, l in enumerate(lines) if l.startswith("# ")), None)
    if ti is None:
        return None, raw
    title = lines[ti][2:].strip()
    body = "\n".join(lines[ti + 1:]).lstrip("\n")
    return title, body

def main():
    cache = T.Cache(T.SEG_STORE)
    atoms = [p for p in glob.glob(os.path.join(VAULT, "**", "*.md"), recursive=True)
             if not p.endswith(".it.md")]
    print(f"vault Sayers atoms: {len(atoms)}", flush=True)

    seg = set()
    for p in atoms:
        raw = open(p, encoding="utf-8").read()
        title, body = split_title_body(raw)
        if title:
            seg.add(title)
        for b in T.split_blocks(T.clean_body(body)):
            if not b.strip() or b.lstrip().startswith("<nav"):
                continue
            for s in T.split_sentences(b):
                if T.has_prose(s):
                    seg.add(s.strip())
    todo = [s for s in seg if cache.get(s) is None]
    print(f"segments {len(seg)} | uncached to translate: {len(todo)}", flush=True)
    if todo:
        tr, tok = build_translator()
        for i in range(0, len(todo), 64):
            chunk = todo[i:i + 64]
            for s, it in zip(chunk, translate_batch(tr, tok, chunk)):
                cache.put(s, it)
        print("translated misses", flush=True)

    written = 0
    for p in atoms:
        raw = open(p, encoding="utf-8").read()
        title, body = split_title_body(raw)
        title_it = (cache.get(title) or title) if title else None
        body_it = T.reassemble_testi(body, cache)
        out = (f"# {title_it}\n\n" if title_it else "") + body_it.lstrip("\n")
        if not out.endswith("\n"):
            out += "\n"
        open(p[:-3] + ".it.md", "w", encoding="utf-8", newline="\n").write(out)
        written += 1
    print(f"wrote {written} vault .it.md siblings", flush=True)

if __name__ == "__main__":
    main()
