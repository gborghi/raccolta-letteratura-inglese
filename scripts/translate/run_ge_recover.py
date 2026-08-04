# -*- coding: utf-8 -*-
"""Recover the 4 Great Expectations atoms that FAILed with 'fabricated output'.

Drives recover_dickens_fails over the GE fail-set without disturbing its canonical Oliver Twist
record. Pass 1 (no --write): re-translate every block, cache the good ones, and report EXACTLY which
block fabricated per atom. Fill CORRECTIONS below with a faithful concise IT for each, then rerun
with --write: cached + corrected blocks combine into a valid .it.md.

Usage:  python3 run_ge_recover.py [--write]
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import recover_dickens_fails as r

r.ATOMS = [
    "Authors/Dickens/Atomized/Great_Expectations/Chapter_17/part_01.md",
    "Authors/Dickens/Atomized/Great_Expectations/Chapter_39/part_04.md",
    "Authors/Dickens/Atomized/Great_Expectations/Chapter_44/part_02.md",
    "Authors/Dickens/Atomized/Great_Expectations/Chapter_52.md",
]

# Filled in pass 2 from the pass-1 report: exact stripped EN block -> faithful concise IT
# (kept under the 2*EN+80 fabrication ceiling).
r.CORRECTIONS = {
}

r.main()
