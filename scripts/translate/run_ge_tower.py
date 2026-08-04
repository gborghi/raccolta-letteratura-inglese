# -*- coding: utf-8 -*-
"""Translate Great Expectations via local Tower 72B, reusing dickens_tower.py wholesale.

Points dickens_tower's TSV at the Great Expectations leaf-atom list and gives it a work-specific
link-repair queue (so GE's fixups don't mix with Oliver Twist's). The block cache is deliberately
SHARED (content-addressed by sha(EN block)) -- identical boilerplate/phrasing across Dickens works
is reused for free, and it costs nothing when there's no overlap.

Usage: python3 run_ge_tower.py [--dry-run] [--limit N]
Resumable: an atom with an existing .it.md is skipped; every block is cached.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dickens_tower as dt

dt.TSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "great_expectations_atoms.tsv")
dt.FIXUPS_PATH = os.path.join(dt.ROOT, "data", "ge_tower_linkfix.jsonl")
dt.main()
