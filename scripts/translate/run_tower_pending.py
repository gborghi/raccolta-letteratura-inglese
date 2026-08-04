# -*- coding: utf-8 -*-
"""Translate the remaining opus-filter-blocked Chesterton atoms via local Tower.

Same shape as run_blocked_tower.py: reuses gkc_tower_sensitive.py wholesale (Chesterton brief,
masking, shared cache gkc_tower_cache.jsonl, validation, linkfix queue gkc_tower_linkfix.jsonl) but
points its TSV at data/chesterton_tower_pending.tsv (ball_and_cross + manalive atoms the hosted Opus
agents could not render). Resumable: an atom with an existing .it.md is skipped; every block cached.

Usage: python3 run_tower_pending.py [--dry-run] [--limit N]
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gkc_tower_sensitive as g

g.TSV = os.path.join(g.ROOT, "data", "chesterton_tower_pending.tsv")
g.main()
