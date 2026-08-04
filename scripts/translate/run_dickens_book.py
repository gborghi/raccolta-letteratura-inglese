# -*- coding: utf-8 -*-
"""Translate ONE Dickens work via local Tower 72B, reusing dickens_tower.py wholesale.

Parametrised by the env var DICKENS_WORK (the Atomized/ subdir name, e.g. A_Tale_of_Two_Cities).
Points dickens_tower's TSV at that work's leaf-atom list (<work_lower>_atoms.tsv, produced by
gen_dickens_tsv.py) and gives it a work-specific link-repair queue so books don't cross-contaminate.
The block cache is deliberately SHARED across all Dickens works (content-addressed by sha(EN block)):
identical boilerplate/phrasing is reused for free, and it costs nothing when there's no overlap.

Resumable: an atom with an existing .it.md is skipped; every block is cached. Any --dry-run/--limit
args pass straight through to dickens_tower.main().
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dickens_tower as dt

work = os.environ.get("DICKENS_WORK", "").strip()
if not work:
    sys.exit("DICKENS_WORK env var is required (e.g. A_Tale_of_Two_Cities)")

HERE = os.path.dirname(os.path.abspath(__file__))
tsv = os.path.join(HERE, work.lower() + "_atoms.tsv")
if not os.path.exists(tsv):
    sys.exit(f"no TSV for {work}: expected {tsv} (run gen_dickens_tsv.py {work})")

dt.TSV = tsv
dt.FIXUPS_PATH = os.path.join(dt.ROOT, "data", f"{work.lower()}_tower_linkfix.jsonl")
print(f"### WORK {work} | TSV {os.path.basename(tsv)} | linkfix {os.path.basename(dt.FIXUPS_PATH)}",
      flush=True)
dt.main()
