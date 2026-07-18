# -*- coding: utf-8 -*-
"""Translate the Opus-filter-blocked Chesterton atoms via local Tower (no output filter).

Reuses gkc_tower_sensitive.py wholesale (Chesterton brief, masking, cache, validation, linkfix
queue) but points its TSV at the list of atoms the hosted Opus agents could not render because the
content filter aborted them. Same cache (gkc_tower_cache.jsonl) and linkfix (gkc_tower_linkfix.jsonl)
as the rest of the sensitive Chesterton corpus.

Usage: python3 run_blocked_tower.py [--dry-run] [--limit N]
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gkc_tower_sensitive as g

g.TSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chesterton_blocked_by_filter.tsv")
g.main()
