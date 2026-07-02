# -*- coding: utf-8 -*-
"""Assemble Claude-Fable Sayers translations.
Reads data/fable_tasks/*.json (source blocks) + data/fable_out/<label>.NNN.jsonl
(Italian blocks, index-aligned), builds a block cache sha1(en)->it, then:
  1. rebuilds data/translations_pages.jsonl for ALL Sayers pages (backs up old
     store to translations_pages.nllb.bak.jsonl)
  2. rewrites the 78 vault .it.md siblings in Authors/Sayers/Atomized
Block-level replacement preserves blank-line spacing exactly (split_blocks keeps
separators); nav blocks and non-prose blocks pass through verbatim. Because the
cache is content-addressed, part_NN fragments, chapters and the full-work page
share blocks -> full IT == sum of fragment IT, by construction.
"""
import os, re, sys, glob, json, hashlib
sys.path.insert(0, os.path.dirname(__file__))
from sbtrans import clean_body, split_blocks, has_prose

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CONTENT = os.path.join(ROOT, "content")
DATA = os.path.join(ROOT, "data")
VAULT = r"E:/giovanni/Dropbox/insegnamento/Wiligelmo/SubjectBrain/English/Authors/Sayers/Atomized"
TASKS = os.path.join(DATA, "fable_tasks")
OUT = os.path.join(DATA, "fable_out")
PAGE_STORE = os.path.join(DATA, "translations_pages.jsonl")
FM_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", re.S)

def sha(s): return hashlib.sha1(s.encode("utf-8")).hexdigest()

QSWITCH_RE = re.compile(r'<div class="qlang-switch"[^>]*></div>\s*\n?')
QSPLIT_RE = re.compile(r'\n?\s*<span class="qlang-split"[^>]*></span>.*$', re.S)

def strip_qlang(body):
    """content pages on disk are already bilingual-merged (EN + qlang-split +
    IT). Keep only the EN half: drop the switch placeholder and cut at the
    split marker."""
    return QSPLIT_RE.sub("", QSWITCH_RE.sub("", body))

def parse(path):
    raw = open(path, encoding="utf-8").read()
    m = FM_RE.match(raw)
    if not m:
        return None, strip_qlang(raw)
    tm = re.search(r'(?m)^title:\s*"?(.*?)"?\s*$', m.group(1))
    return (tm.group(1) if tm else None), strip_qlang(m.group(2))

def load_cache():
    cache, problems = {}, []
    for tf in sorted(glob.glob(os.path.join(TASKS, "*.json"))):
        t = json.load(open(tf, encoding="utf-8"))
        label = t["doc"]
        if label == "_meta":
            continue
        blocks = t["blocks"]
        its = {}
        for of in sorted(glob.glob(os.path.join(OUT, f"{label}.*.jsonl"))):
            for ln in open(of, encoding="utf-8"):
                ln = ln.strip()
                if not ln:
                    continue
                r = json.loads(ln)
                its[r["i"]] = r["it"]
        missing = [i for i in range(len(blocks)) if i not in its]
        if missing:
            problems.append(f"{label}: missing indices {missing[:10]}{'...' if len(missing)>10 else ''} ({len(missing)}/{len(blocks)})")
        for i, b in enumerate(blocks):
            if i in its and its[i].strip():
                cache[sha(b)] = its[i]
    return cache, problems

def translate_body(body, cache, stats):
    out = []
    for part in split_blocks(clean_body(body)):
        p = part.strip()
        if not p or p.startswith("<nav") or not has_prose(p):
            out.append(part)
            continue
        it = cache.get(sha(p))
        if it is None:
            stats["miss"] += 1
            out.append(part)
        else:
            stats["hit"] += 1
            out.append(it)
    return "".join(out)

def translate_work_body(body, cache, stats):
    lines = body.split("\n")
    out, i = [], 0
    while i < len(lines):
        if re.match(r"^>\s*\[!abstract\]", lines[i]):
            out.append(lines[i]); j = i + 1; buf = []
            while j < len(lines) and lines[j].startswith(">"):
                buf.append(re.sub(r"^>\s?", "", lines[j])); j += 1
            text = clean_body(" ".join(buf)).strip()
            it = cache.get(sha(text))
            if it is None:
                stats["miss"] += 1
                out.extend(lines[i + 1:j])
            else:
                stats["hit"] += 1
                out.append("> " + it.replace("\n", " "))
            i = j
        else:
            out.append(lines[i]); i += 1
    return "\n".join(out)

def main():
    cache, problems = load_cache()
    print(f"block cache: {len(cache)} entries")
    for p in problems:
        print("PROBLEM:", p)
    if problems and "--force" not in sys.argv:
        print("aborting (use --force to emit anyway)"); sys.exit(1)

    stats = {"hit": 0, "miss": 0}

    # 1. page store
    pages = []
    for p in glob.glob(os.path.join(CONTENT, "testi", "sayers", "**", "*.md"), recursive=True):
        if not p.endswith(".it.md"):
            pages.append(("testi", p))
    for p in glob.glob(os.path.join(CONTENT, "works", "*(sayers).md")):
        pages.append(("work", p))

    if os.path.exists(PAGE_STORE):
        bak = os.path.join(DATA, "translations_pages.nllb.bak.jsonl")
        if not os.path.exists(bak):
            os.replace(PAGE_STORE, bak)
            print(f"backed up old store -> {bak}")
        else:
            os.remove(PAGE_STORE)

    with open(PAGE_STORE, "w", encoding="utf-8") as fh:
        for kind, path in pages:
            title, body = parse(path)
            rel = os.path.relpath(path, CONTENT).replace("\\", "/")
            title_it = cache.get(sha(title)) if title else None
            body_it = (translate_work_body(body, cache, stats) if kind == "work"
                       else translate_body(body, cache, stats))
            fh.write(json.dumps({"rel": rel, "kind": kind,
                                 "title_it": title_it, "body_it": body_it},
                                ensure_ascii=False) + "\n")
    print(f"page store: {len(pages)} pages -> {PAGE_STORE}")

    # 2. vault .it.md siblings
    written = 0
    for p in glob.glob(os.path.join(VAULT, "**", "*.md"), recursive=True):
        if p.endswith(".it.md"):
            continue
        raw = open(p, encoding="utf-8").read()
        out = translate_body(raw, cache, stats)
        if not out.endswith("\n"):
            out += "\n"
        open(p[:-3] + ".it.md", "w", encoding="utf-8", newline="\n").write(out)
        written += 1
    print(f"vault siblings: {written}")
    print(f"blocks hit {stats['hit']} | miss (left EN) {stats['miss']}")

if __name__ == "__main__":
    main()
