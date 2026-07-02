# -*- coding: utf-8 -*-
"""Prep for Claude-Fable retranslation of Sayers.
Collect UNIQUE prose blocks (paragraphs) from all Sayers pages (content testi +
work abstracts + vault atoms + titles), grouped by master document so each
translation agent sees the whole document as context. Blocks are content-
addressed (sha1), so part_NN fragments and the full-work page reuse the same
translated block -> full == sum of fragments, by construction.

Output: one JSON task file per master doc in TASKS_DIR:
  {"doc": "<label>", "blocks": ["<en block>", ...]}
plus meta.json task with all unique titles + abstract lines.
"""
import os, re, sys, glob, json, hashlib
sys.path.insert(0, os.path.dirname(__file__))
from sbtrans import clean_body, split_blocks, has_prose

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CONTENT = os.path.join(ROOT, "content")
VAULT = r"E:/giovanni/Dropbox/insegnamento/Wiligelmo/SubjectBrain/English/Authors/Sayers/Atomized"
TASKS_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "data", "fable_tasks")
FM_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", re.S)

def sha(s): return hashlib.sha1(s.encode("utf-8")).hexdigest()

def parse(path):
    raw = open(path, encoding="utf-8").read()
    m = FM_RE.match(raw)
    if not m:
        return None, raw
    tm = re.search(r'(?m)^title:\s*"?(.*?)"?\s*$', m.group(1))
    return (tm.group(1) if tm else None), m.group(2)

def prose_blocks(body):
    out = []
    for part in split_blocks(clean_body(body)):
        p = part.strip()
        if not p or p.startswith("<nav") or not has_prose(p):
            continue
        out.append(p)
    return out

def main():
    os.makedirs(TASKS_DIR, exist_ok=True)
    # master docs: 14 chapter pages + lost_tools essay page (they contain every
    # block that parts and the full-work page reuse)
    masters = sorted(
        p for p in glob.glob(os.path.join(CONTENT, "testi", "sayers", "atomized", "*", "*.md"))
        if not p.endswith(".it.md") and os.path.basename(os.path.dirname(p)) != "part"
    )
    masters += [os.path.join(CONTENT, "testi", "sayers", "atomized",
                             "the_lost_tools_of_learning", "the_lost_tools_of_learning.md")]
    # the full-book page is NOT a master (union of chapters); drop it
    masters = [p for p in masters if not p.endswith("the_mind_of_the_maker.md")
               or "atomized" not in p.replace("\\", "/").split("/")[-2]]
    masters = sorted(set(p for p in masters
                         if not os.path.basename(p) == "the_mind_of_the_maker.md"))

    seen = {}          # sha -> block  (dedup across docs)
    ntasks = 0
    for p in masters:
        _, body = parse(p)
        blocks = []
        for b in prose_blocks(body):
            h = sha(b)
            if h in seen:
                continue
            seen[h] = b
            blocks.append(b)
        if not blocks:
            continue
        label = os.path.splitext(os.path.basename(p))[0]
        json.dump({"doc": label, "blocks": blocks},
                  open(os.path.join(TASKS_DIR, f"{label}.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        ntasks += 1
        print(f"task {label}: {len(blocks)} blocks, {sum(len(b) for b in blocks)} chars")

    # coverage check: every prose block of EVERY page (content testi + full-work
    # + parts + work pages' bodies-not-needed + vault atoms) must be in seen;
    # leftovers go into a residue task.
    residue = []
    all_pages = [p for p in glob.glob(os.path.join(CONTENT, "testi", "sayers", "**", "*.md"),
                                      recursive=True) if not p.endswith(".it.md")]
    all_pages += [p for p in glob.glob(os.path.join(VAULT, "**", "*.md"), recursive=True)
                  if not p.endswith(".it.md")]
    for p in all_pages:
        _, body = parse(p)
        if body is None:
            body = open(p, encoding="utf-8").read()
        for b in prose_blocks(body):
            # vault atoms: strip leading "# Title" heading line from block compare
            h = sha(b)
            if h not in seen:
                seen[h] = b
                residue.append(b)
    # titles + work abstracts
    titles = set()
    for p in all_pages + glob.glob(os.path.join(CONTENT, "works", "*(sayers).md")):
        t, _ = parse(p)
        if t:
            titles.add(t)
        raw = open(p, encoding="utf-8").read()
        m = re.search(r"^# (.+)$", raw, re.M)
        if m and os.path.dirname(p).replace("\\", "/").endswith("Atomized") or True:
            pass
    abstracts = []
    for p in glob.glob(os.path.join(CONTENT, "works", "*(sayers).md")):
        t, body = parse(p)
        if t:
            titles.add(t)
        lines = body.split("\n")
        i = 0
        while i < len(lines):
            if re.match(r"^>\s*\[!abstract\]", lines[i]):
                j = i + 1; buf = []
                while j < len(lines) and lines[j].startswith(">"):
                    buf.append(re.sub(r"^>\s?", "", lines[j])); j += 1
                abstracts.append(clean_body(" ".join(buf)).strip())
                i = j
            else:
                i += 1
    # vault atom H1 titles
    for p in glob.glob(os.path.join(VAULT, "**", "*.md"), recursive=True):
        if p.endswith(".it.md"):
            continue
        m = re.search(r"^# (.+)$", open(p, encoding="utf-8").read(), re.M)
        if m:
            titles.add(m.group(1).strip())

    json.dump({"doc": "_meta", "titles": sorted(titles), "abstracts": abstracts,
               "residue": residue},
              open(os.path.join(TASKS_DIR, "_meta.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"\n{ntasks} doc tasks | unique blocks {len(seen)} | residue {len(residue)} "
          f"| titles {len(titles)} | abstracts {len(abstracts)}")
    print(f"tasks dir: {TASKS_DIR}")

if __name__ == "__main__":
    main()
