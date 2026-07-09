# -*- coding: utf-8 -*-
"""Prep Chesterton (or any author) works for block-level LLM translation.
Usage: gkc_prep.py <author> <tasks_dir> [work_slug ...]
  no work_slugs -> all works under content/testi/<author>/atomized/*

One task file per CHAPTER master doc (content/testi/<author>/atomized/<work>/<chapter>.md),
excluding the full-work container (<work>.md) and the paragraph fragments in
<chapter>/part_NN.md subdirs. Blocks are content-addressed (sha1) and deduped
GLOBALLY across the run, so a fragment/part reuses its chapter's translated
block -> work IT == sum of fragment IT, by construction (same as Sayers).

Task file: data/<tasks_dir>/<work>__<chapter>.json = {"doc","work","chapter","blocks":[...]}
Residue (blocks only found in parts / container / vault) -> one _residue task.
"""
import os, re, sys, glob, json, hashlib
sys.path.insert(0, os.path.dirname(__file__))
from sbtrans import clean_body, split_blocks, has_prose

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CONTENT = os.path.join(ROOT, "content")

def sha(s): return hashlib.sha1(s.encode("utf-8")).hexdigest()
FM_RE = re.compile(r"^---\r?\n.*?\r?\n---\r?\n?", re.S)

def prose_blocks(body):
    out = []
    for part in split_blocks(clean_body(FM_RE.sub("", body, count=1))):
        p = part.strip()
        if p and not p.startswith("<nav") and has_prose(p):
            out.append(p)
    return out

def main():
    author = sys.argv[1]
    tasks_dir = os.path.join(ROOT, "data", sys.argv[2])
    want = set(sys.argv[3:])
    os.makedirs(tasks_dir, exist_ok=True)
    abase = os.path.join(CONTENT, "testi", author, "atomized")
    works = sorted(w for w in os.listdir(abase)
                   if os.path.isdir(os.path.join(abase, w)) and (not want or w in want))

    seen = {}          # sha -> 1 (global dedup)
    ntasks = ndup = 0
    for w in works:
        wd = os.path.join(abase, w)
        # chapter master docs: atomized/<w>/*.md except the container <w>.md
        chapters = sorted(p for p in glob.glob(os.path.join(wd, "*.md"))
                          if not p.endswith(".it.md")
                          and os.path.splitext(os.path.basename(p))[0] != w)
        for cp in chapters:
            body = open(cp, encoding="utf-8").read()
            blocks = []
            for b in prose_blocks(body):
                h = sha(b)
                if h in seen:
                    ndup += 1
                    continue
                seen[h] = 1
                blocks.append(b)
            if not blocks:
                continue
            chap = os.path.splitext(os.path.basename(cp))[0]
            label = f"{w}__{chap}"
            json.dump({"doc": label, "work": w, "chapter": chap, "blocks": blocks},
                      open(os.path.join(tasks_dir, f"{label}.json"), "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
            ntasks += 1

    # residue: any block in container/parts (and vault later) not yet seen
    residue = []
    for w in works:
        for p in glob.glob(os.path.join(abase, w, "**", "*.md"), recursive=True):
            if p.endswith(".it.md"):
                continue
            for b in prose_blocks(open(p, encoding="utf-8").read()):
                h = sha(b)
                if h not in seen:
                    seen[h] = 1
                    residue.append(b)
    if residue:
        # chunk residue into task files of <=120 blocks each
        for i in range(0, len(residue), 120):
            json.dump({"doc": f"_residue_{i//120:03d}", "work": "_residue",
                       "chapter": "", "blocks": residue[i:i+120]},
                      open(os.path.join(tasks_dir, f"_residue_{i//120:03d}.json"), "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)

    total_chars = sum(len(b) for b in [b for w in works for cp in [] for b in []]) # noop
    print(f"works: {len(works)} | chapter tasks: {ntasks} | dup-skipped: {ndup} "
          f"| residue blocks: {len(residue)} | unique blocks: {len(seen)}")
    print(f"tasks dir: {tasks_dir}")

if __name__ == "__main__":
    main()
