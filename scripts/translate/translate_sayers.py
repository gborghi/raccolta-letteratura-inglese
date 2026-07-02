# -*- coding: utf-8 -*-
"""Translate all Sayers content pages EN->IT with tower, resumable.
Output:
  data/trans_seg_it.jsonl   content-addressed sentence cache (shared, dedups
                            full-work vs chapters vs fragments)
  data/translations_pages.jsonl  per-page {rel, title_it, body_it}
Run:  <venv-or-any>python translate_sayers.py
"""
import os, re, sys, glob, json, time
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(__file__))
from sbtrans import (tower, Cache, clean_body, split_blocks, split_sentences,
                     has_prose)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CONTENT = os.path.join(ROOT, "content")
DATA = os.path.join(ROOT, "data")
SEG_STORE = os.path.join(DATA, "trans_seg_it.jsonl")
PAGE_STORE = os.path.join(DATA, "translations_pages.jsonl")
FM_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", re.S)

def parse(path):
    raw = open(path, encoding="utf-8").read()
    m = FM_RE.match(raw)
    if not m:
        return {}, raw, raw
    fm_text, body = m.group(1), m.group(2)
    tm = re.search(r'(?m)^title:\s*"?(.*?)"?\s*$', fm_text)
    title = tm.group(1) if tm else None
    return {"title": title, "fm": fm_text}, body, raw

def gather():
    pages = []
    for p in glob.glob(os.path.join(CONTENT, "testi", "sayers", "**", "*.md"), recursive=True):
        if p.endswith(".it.md"):
            continue
        pages.append(("testi", os.path.relpath(p, CONTENT).replace("\\", "/"), p))
    for p in glob.glob(os.path.join(CONTENT, "works", "*(sayers).md")):
        pages.append(("work", os.path.relpath(p, CONTENT).replace("\\", "/"), p))
    return pages

def body_sentences(kind, body):
    """Yield translatable source strings for a body."""
    if kind == "work":
        # translate ONLY the [!abstract] callout lines; keep byline/Connections EN
        out = []
        lines = body.split("\n")
        i = 0
        while i < len(lines):
            if re.match(r"^>\s*\[!abstract\]", lines[i]):
                j = i + 1
                buf = []
                while j < len(lines) and lines[j].startswith(">"):
                    buf.append(re.sub(r"^>\s?", "", lines[j]))
                    j += 1
                text = clean_body(" ".join(buf)).strip()
                for s in split_sentences(text):
                    if has_prose(s):
                        out.append(s.strip())
                i = j
            else:
                i += 1
        return out
    # testi: all prose sentences outside nav
    out = []
    for b in split_blocks(clean_body(body)):
        if not b.strip() or b.lstrip().startswith("<nav"):
            continue
        for s in split_sentences(b):
            if has_prose(s):
                out.append(s.strip())
    return out

def reassemble_testi(body, cache):
    body = clean_body(body)
    parts = split_blocks(body)
    out = []
    for part in parts:
        if not part.strip():
            out.append(part); continue
        if part.lstrip().startswith("<nav"):
            out.append(part); continue
        lead = re.match(r"^(\s*(?:>+\s*)?)", part).group(1)
        sents = split_sentences(part.strip())
        new = []
        for s in sents:
            k = s.strip()
            new.append(cache.get(k) if (has_prose(k) and cache.get(k)) else s)
        out.append(lead + " ".join(new))
    return "".join(out)

def reassemble_work(body, cache):
    lines = body.split("\n")
    out = []
    i = 0
    while i < len(lines):
        if re.match(r"^>\s*\[!abstract\]", lines[i]):
            out.append(lines[i]); j = i + 1; buf = []
            while j < len(lines) and lines[j].startswith(">"):
                buf.append(re.sub(r"^>\s?", "", lines[j])); j += 1
            text = clean_body(" ".join(buf)).strip()
            it = " ".join(cache.get(s.strip()) or s for s in split_sentences(text))
            out.append("> " + it)
            i = j
        else:
            out.append(lines[i]); i += 1
    return "\n".join(out)

def main():
    os.makedirs(DATA, exist_ok=True)
    cache = Cache(SEG_STORE)
    pages = gather()
    print(f"Sayers pages: {len(pages)}", flush=True)

    # collect unique source strings (sentences + titles)
    segset, titles = set(), {}
    for kind, rel, path in pages:
        meta, body, _ = parse(path)
        if meta.get("title"):
            titles[rel] = meta["title"]
            segset.add(meta["title"])
        for s in body_sentences(kind, body):
            segset.add(s)
    todo = [s for s in segset if cache.get(s) is None]
    print(f"unique segments: {len(segset)} | to translate: {len(todo)}", flush=True)

    t0 = time.time(); done = 0
    def work(s):
        try:
            return s, tower(s)
        except Exception as e:
            return s, None
    with ThreadPoolExecutor(max_workers=3) as ex:
        for s, it in ex.map(work, todo):
            done += 1
            if it is not None:
                cache.put(s, it)
            if done % 25 == 0:
                el = time.time() - t0
                print(f"  {done}/{len(todo)}  {el/done:.1f}s/seg  eta {el/done*(len(todo)-done)/3600:.1f}h", flush=True)

    # emit per-page store
    done_rel = set()
    if os.path.exists(PAGE_STORE):
        for ln in open(PAGE_STORE, encoding="utf-8"):
            if ln.strip():
                done_rel.add(json.loads(ln)["rel"])
    with open(PAGE_STORE, "a", encoding="utf-8") as fh:
        for kind, rel, path in pages:
            if rel in done_rel:
                continue
            meta, body, _ = parse(path)
            title_it = cache.get(meta["title"]) if meta.get("title") else None
            body_it = reassemble_work(body, cache) if kind == "work" else reassemble_testi(body, cache)
            fh.write(json.dumps({"rel": rel, "kind": kind,
                                 "title_it": title_it, "body_it": body_it},
                                ensure_ascii=False) + "\n")
    print(f"DONE. {len(pages)} pages emitted to {PAGE_STORE}", flush=True)

if __name__ == "__main__":
    main()
