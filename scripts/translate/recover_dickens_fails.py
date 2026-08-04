# -*- coding: utf-8 -*-
"""Recover Dickens atoms that FAILed with 'fabricated output'.

Tower's failure mode: given some block it stops translating and over-generates (IT > 2*EN+80), so
translate_block raises and translate_atom aborts -- leaving the atom with no .it.md and most blocks
uncached. dickens_tower would just FAIL it again on a re-run (temperature 0 -> same fabrication).

This script re-runs the atom but, on the offending block, does NOT abort: it records the block and
leaves it English, so the run completes and reports EXACTLY which blocks fabricated. You then hand-
translate those (they are few -- one per atom) into CORRECTIONS and re-run: cached + corrected +
freshly-translated blocks combine into a valid .it.md.

Pass 1 (no CORRECTIONS): discover the fabricating blocks.   python3 recover_dickens_fails.py
Pass 2 (CORRECTIONS filled): write the atoms.               python3 recover_dickens_fails.py --write
The batch is finished, so writing the shared cache here is safe (no concurrent writer).
"""
import os, sys, re, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dickens_tower as dt
from sbtrans import clean_body, split_blocks, has_prose

WRITE = "--write" in sys.argv

ATOMS = [
    "Authors/Dickens/Atomized/Oliver_Twist/Chapter_47/part_02.md",
    "Authors/Dickens/Atomized/Oliver_Twist/Chapter_48/part_01.md",
    "Authors/Dickens/Atomized/Oliver_Twist/Chapter_52/part_03.md",
]

# Filled in pass 2, keyed by exact stripped EN block -> faithful concise IT (kept under the 2*EN+80
# fabrication ceiling). Rhyme/register notes inline.
CORRECTIONS = {
}


def main():
    cache = dt.Cache(dt.CACHE_PATH)
    print(f"cache warm with {len(cache.d)} blocks\n", flush=True)
    all_fab = []
    for rel in ATOMS:
        en_path = os.path.join(dt.VAULT_ROOT, rel)
        body = open(en_path, encoding="utf-8").read()
        verse = "/Poems/" in en_path.replace(os.sep, "/") or "/Long/" in en_path.replace(os.sep, "/")
        parts = split_blocks(clean_body(body))
        bp = dt.boilerplate_mask(parts)
        out, fab, gaps = [], [], []
        idx = 0
        for k, part in enumerate(parts):
            s = part.strip()
            if not s or s.startswith("<nav") or s.startswith("---") or not has_prose(s) or bp[k]:
                out.append(part)
                continue
            idx += 1
            if s in CORRECTIONS:
                it = CORRECTIONS[s]
            else:
                it = cache.get(s)
                if it is None:
                    try:
                        it, missing = dt.translate_block(s, verse)
                        cache.put(s, it)
                    except RuntimeError as e:
                        fab.append((idx, len(s), s))
                        out.append(part)     # leave English; flagged below
                        continue
            lead = part[:len(part) - len(part.lstrip())]
            trail = part[len(part.rstrip()):]
            qm = re.match(r"(>+\s*)", s)
            if qm and not it.startswith(">"):
                it = qm.group(1) + it
            out.append(lead + it.strip() + trail)
        it_body = "".join(out)
        problems = dt.validate(body, it_body, verse=verse)
        print(f"##### {rel} #####")
        print(f"  prose blocks: {len(dt.prose_blocks(body))} | fabricated: {len(fab)}")
        for i, ln, s in fab:
            print(f"  ⚠ FABRICATED block [{i}] ({ln}c):\n      {s!r}")
            all_fab.append((rel, s))
        print(f"  VALIDATION: {problems or 'OK'}")
        if WRITE and not problems and not fab:
            open(en_path[:-3] + ".it.md", "w", encoding="utf-8").write(it_body)
            print(f"  WROTE {en_path[:-3]}.it.md")
        elif WRITE:
            print("  NOT written (fabrication unresolved or validation failed)")
        print()
    if all_fab:
        print("=== blocks needing a hand translation in CORRECTIONS ===")
        for rel, s in all_fab:
            print(f"[{os.path.basename(os.path.dirname(rel))}/{os.path.basename(rel)}] {s!r}")


if __name__ == "__main__":
    main()
