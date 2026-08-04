# -*- coding: utf-8 -*-
"""Benchmark one loaded LM Studio model on the 2 Oliver Twist smoke atoms.

Reuses the Dickens pipeline (masking, whole-block translation, unmasking, validation) from
dickens_tower.py, but: (a) points MODEL at a candidate identifier, (b) uses a throwaway cache so
the candidate is actually exercised (not served tower72's cached blocks), and (c) writes outputs to
a scratch dir instead of the vault, so the tower72 reference .it.md files are never touched.

Usage: python3 bench_translate.py <model-identifier> <label>
  e.g. python3 bench_translate.py cand tower9b
"""
import os, sys, time, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dickens_tower as dt

MODEL_ID = sys.argv[1]
LABEL = sys.argv[2]
dt.MODEL = MODEL_ID

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bench_out", LABEL)
os.makedirs(OUT, exist_ok=True)
CACHE = os.path.join(OUT, "cache.jsonl")
if os.path.exists(CACHE):
    os.remove(CACHE)  # fresh every run so the candidate is truly exercised

ATOMS = [
    "Authors/Dickens/Atomized/Oliver_Twist/Chapter_01.md",
    "Authors/Dickens/Atomized/Oliver_Twist/Chapter_02/part_01.md",
]

cache = dt.Cache(CACHE)
print(f"=== {LABEL} (model={MODEL_ID}) ===", flush=True)
t0 = time.time()
total_en = 0
for rel in ATOMS:
    en_path = os.path.join(dt.VAULT_ROOT, rel)
    en_body = open(en_path, encoding="utf-8").read()
    fixups = []
    ta = time.time()
    try:
        it_body = dt.translate_atom(en_path, cache, fixups)
    except Exception as e:
        print(f"  FAIL {rel}: {e}", flush=True)
        continue
    verse = False
    problems = dt.validate(en_body, it_body, verse)
    en_chars = sum(len(b) for b in dt.prose_blocks(en_body))
    total_en += en_chars
    name = rel.replace("/", "__").replace(".md", ".it.md")
    open(os.path.join(OUT, name), "w", encoding="utf-8").write(it_body)
    nmiss = sum(len(f["missing"]) for f in fixups)
    tag = "OK" if not problems else "REJECT: " + "; ".join(problems)
    print(f"  {rel}\n    {tag} | {en_chars} EN chars | {len(dt.prose_blocks(it_body))} IT blocks "
          f"| {nmiss} links need repair | {time.time()-ta:.0f}s", flush=True)
el = (time.time() - t0) / 60
print(f"total: {total_en} EN chars in {el:.1f} min = {total_en/el:,.0f} chars/min", flush=True)
