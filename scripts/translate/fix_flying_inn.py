# -*- coding: utf-8 -*-
"""Re-translate The Flying Inn ch.12 part_02 (the Vegetarian song) as VERSE, with hand fixes.

The atom is a comic ballad translated line-by-line (rhyme intentionally not preserved). Applies:
  - manual corrections to a few blocks the model got slightly wrong (gender/subject/word-order),
  - a faithful fix for the interrupted line "But-." -> "Pero..." so it keeps a >=3-letter word
    (else has_prose drops it and the EN/IT block count diverges 55 vs 54).
Local cache so re-runs are instant. Pass --write to write the .it.md once it validates 55==55.
"""
import sys, os, re, json, hashlib
sys.path.insert(0, os.path.abspath('.'))
import dickens_tower as dt
from sbtrans import clean_body, split_blocks, has_prose

WRITE = "--write" in sys.argv
F = os.path.join(dt.VAULT_ROOT, "Authors/Chesterton/Atomized/The_Flying_Inn/"
                 "Chapter_12_VEGETARIANISM_IN_THE_FOREST/part_02.md")
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run_logs", "flying_inn_cache.jsonl")

# Hand corrections, keyed by the exact (clean_body) English block. Rhyme deliberately dropped;
# these fix clear sense/grammar slips + keep the interrupted line countable.
CORRECTIONS = {
    'That I had, upon a fork;': 'Che avevo, su una forchetta;',
    'He offered them grass instead of bread,': 'Egli offrì loro erba invece di pane,',
    '“Black Lord Foulon the Frenchmen slew,': '“I Francesi uccisero il nero Lord Foulon,',
    'But–.”': 'Però...»',
}

def sha(s): return hashlib.sha1(s.encode("utf-8")).hexdigest()
cache = {}
if os.path.exists(CACHE):
    for l in open(CACHE, encoding="utf-8"):
        if l.strip():
            r = json.loads(l); cache[r["h"]] = r["it"]
cfh = open(CACHE, "a", encoding="utf-8")

body = open(F, encoding="utf-8").read()
parts = split_blocks(clean_body(body))
bp = dt.boilerplate_mask(parts)

out, pairs = [], []
for k, part in enumerate(parts):
    s = part.strip()
    if not s or s.startswith("<nav") or not has_prose(s) or bp[k]:
        out.append(part); continue
    if s in CORRECTIONS:
        it = CORRECTIONS[s]
    else:
        h = sha(s)
        it = cache.get(h)
        if it is None:
            it, _ = dt.translate_block(s, verse=True)
            it = it.strip()
            cfh.write(json.dumps({"h": h, "en": s, "it": it}, ensure_ascii=False) + "\n"); cfh.flush()
    lead = part[:len(part) - len(part.lstrip())]
    trail = part[len(part.rstrip()):]
    qm = re.match(r"(>+\s*)", s)
    if qm and not it.startswith(">"):
        it = qm.group(1) + it
    out.append(lead + it.strip() + trail)
    pairs.append((s, it.strip(), has_prose(it.strip())))

it_body = "".join(out)
en_pb, it_pb = dt.prose_blocks(body), dt.prose_blocks(it_body)
print(f"EN prose blocks: {len(en_pb)} | IT prose blocks: {len(it_pb)}")
for en, it, ok in pairs:
    if not ok or en in CORRECTIONS:
        print(f"{'⚠' if not ok else '✎'} {en!r}\n   -> {it!r}")
problems = dt.validate(body, it_body, verse=True)
print("VALIDATION:", problems or "OK")
if WRITE and not problems:
    open(F[:-3] + ".it.md", "w", encoding="utf-8").write(it_body)
    print("WROTE", F[:-3] + ".it.md")
elif WRITE:
    print("NOT written (validation failed)")
