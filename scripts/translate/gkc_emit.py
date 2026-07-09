# -*- coding: utf-8 -*-
"""Assemble LLM (Opus) block translations for an author into translations_pages.jsonl.
Usage: gkc_emit.py <author> <tasks_dir> <out_dir> [--vault]

Reads data/<tasks_dir>/*.json (source blocks) + data/<out_dir>/<label>.NNN.jsonl
(IT blocks, index-aligned) -> content-addressed block cache sha1(en)->it.
Then for every content page under content/testi/<author>/** whose blocks are (at
least partly) covered, build the IT body by block replacement and UPSERT it into
data/translations_pages.jsonl (keyed by rel; existing Sayers entries preserved).
Untranslated blocks are left as EN (miss) and counted. With --vault also writes
the vault .it.md siblings for fully-covered atoms.

Because the cache is content-addressed, part_NN fragments, chapters and the full
work share blocks -> work IT == sum of fragment IT, by construction.
"""
import os, re, sys, glob, json, hashlib
sys.path.insert(0, os.path.dirname(__file__))
from sbtrans import clean_body, split_blocks, has_prose

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CONTENT = os.path.join(ROOT, "content")
DATA = os.path.join(ROOT, "data")
PAGE_STORE = os.path.join(DATA, "translations_pages.jsonl")
FM_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", re.S)
QSWITCH_RE = re.compile(r'<div class="qlang-switch"[^>]*></div>\s*\n?')
QSPLIT_RE = re.compile(r'\n?\s*<span class="qlang-split"[^>]*></span>.*$', re.S)

def sha(s): return hashlib.sha1(s.encode("utf-8")).hexdigest()

def strip_qlang(body):
    return QSPLIT_RE.sub("", QSWITCH_RE.sub("", body))

def parse(path):
    raw = open(path, encoding="utf-8").read()
    m = FM_RE.match(raw)
    if not m:
        return None, strip_qlang(raw)
    tm = re.search(r'(?m)^title:\s*"?(.*?)"?\s*$', m.group(1))
    return (tm.group(1) if tm else None), strip_qlang(m.group(2))

def load_cache(tasks_dir, out_dir):
    cache, problems = {}, []
    for tf in sorted(glob.glob(os.path.join(tasks_dir, "*.json"))):
        t = json.load(open(tf, encoding="utf-8"))
        label, blocks = t["doc"], t["blocks"]
        its = {}
        for of in sorted(glob.glob(os.path.join(out_dir, f"{label}.*.jsonl"))):
            for ln in open(of, encoding="utf-8"):
                ln = ln.strip()
                if ln:
                    r = json.loads(ln)
                    its[r["i"]] = r["it"]
        miss = [i for i in range(len(blocks)) if i not in its]
        if miss:
            problems.append(f"{label}: {len(miss)}/{len(blocks)} missing")
        for i, b in enumerate(blocks):
            if i in its and its[i].strip():
                cache[sha(b)] = its[i]
    return cache, problems

def translate_body(body, cache, stats):
    out = []
    for part in split_blocks(clean_body(body)):
        p = part.strip()
        if not p or p.startswith("<nav") or not has_prose(p):
            out.append(part); continue
        it = cache.get(sha(p))
        if it is None:
            stats["miss"] += 1; out.append(part)
        else:
            stats["hit"] += 1; out.append(it)
    return "".join(out)

def main():
    author = sys.argv[1]
    tasks_dir = os.path.join(DATA, sys.argv[2])
    out_dir = os.path.join(DATA, sys.argv[3])
    do_vault = "--vault" in sys.argv
    cache, problems = load_cache(tasks_dir, out_dir)
    print(f"block cache: {len(cache)} entries | task problems: {len(problems)}")
    for p in problems[:20]:
        print("  ", p)

    # load existing store keyed by rel
    store = {}
    if os.path.exists(PAGE_STORE):
        for ln in open(PAGE_STORE, encoding="utf-8"):
            ln = ln.strip()
            if ln:
                r = json.loads(ln); store[r["rel"]] = r

    stats = {"hit": 0, "miss": 0}
    pages = [p for p in glob.glob(os.path.join(CONTENT, "testi", author, "**", "*.md"), recursive=True)
             if not p.endswith(".it.md")]
    upserted = 0
    for path in pages:
        title, body = parse(path)
        body_it = translate_body(body, cache, {"hit": 0, "miss": 0})  # per-page probe below
        # recompute with global stats
        st = {"hit": 0, "miss": 0}
        body_it = translate_body(body, cache, st)
        if st["hit"] == 0:
            continue  # page has no translated block yet — skip (stays EN-only)
        stats["hit"] += st["hit"]; stats["miss"] += st["miss"]
        rel = os.path.relpath(path, CONTENT).replace("\\", "/")
        title_it = cache.get(sha(title)) if title else None
        store[rel] = {"rel": rel, "kind": "testi", "title_it": title_it, "body_it": body_it}
        upserted += 1

    with open(PAGE_STORE, "w", encoding="utf-8") as fh:
        for rel in sorted(store):
            fh.write(json.dumps(store[rel], ensure_ascii=False) + "\n")
    print(f"pages upserted: {upserted} | store total: {len(store)} | blocks hit {stats['hit']} miss {stats['miss']}")

    if do_vault:
        VROOT = r"E:/giovanni/Dropbox/insegnamento/Wiligelmo/SubjectBrain/English/Authors"
        vbase = os.path.join(VROOT, author.capitalize(), "Atomized")
        n = 0
        for p in glob.glob(os.path.join(vbase, "**", "*.md"), recursive=True):
            if p.endswith(".it.md"):
                continue
            raw = open(p, encoding="utf-8").read()
            st = {"hit": 0, "miss": 0}
            out = translate_body(raw, cache, st)
            if st["hit"] == 0:
                continue
            if not out.endswith("\n"):
                out += "\n"
            open(p[:-3] + ".it.md", "w", encoding="utf-8", newline="\n").write(out)
            n += 1
        print(f"vault siblings written: {n}")

if __name__ == "__main__":
    main()
