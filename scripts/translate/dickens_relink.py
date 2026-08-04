# -*- coding: utf-8 -*-
"""Reattach [[Target|label]] wikilinks onto a PLAIN Italian translation.

Used with translators that strip markup (e.g. TranslateGemma): translate the
block plain, then map each EN link onto its Italian rendering here. Two tiers:
  1. verbatim  -- the label appears unchanged in the IT text (proper names,
     loanwords). Wrap the first unused occurrence.
  2. concept   -- the label is a common word that got translated. Translate the
     label alone (translate_word) and find that Italian word in the IT text.
Unresolved links are returned as `missing` (they feed the existing repair queue,
exactly like Tower/HY).
"""
import re

# \n excluded from both groups: see the note in dickens_tower.py -- an unclosed [[ in a
# truncated H1 otherwise swallows the next real link and fakes an "invented target" reject.
WIKILINK_RE = re.compile(r"\[\[([^\]|\n]+)(?:\|([^\]\n]*))?\]\]")


def strip_markup(en_block: str) -> str:
    """[[Target|label]] -> label ; [[Target]] -> Target."""
    return WIKILINK_RE.sub(lambda m: (m.group(2) or m.group(1)), en_block)


def _wrap(target, shown):
    return ("[[%s]]" % target) if shown == target else ("[[%s|%s]]" % (target, shown))


def reattach_links(en_block: str, it_text: str, translate_word):
    """Return (it_with_links, missing_targets). `translate_word(str)->str`
    translates one label in isolation (cached by the caller ideally)."""
    links = [(m.group(1), m.group(2) or m.group(1))
             for m in WIKILINK_RE.finditer(en_block)]
    used = []            # start offsets already consumed
    missing = []
    for target, label in links:
        placed = False
        # tier 1: verbatim (case-insensitive)
        for mm in re.finditer(re.escape(label), it_text, re.I):
            if mm.start() in used:
                continue
            used.append(mm.start())
            it_text = it_text[:mm.start()] + _wrap(target, mm.group(0)) + it_text[mm.end():]
            placed = True
            break
        if placed:
            continue
        # tier 2: translate the label, find the Italian word (word-boundary)
        itw = (translate_word(label) or "").strip()
        if itw:
            for mm in re.finditer(r"\b" + re.escape(itw), it_text, re.I):
                if mm.start() in used:
                    continue
                used.append(mm.start())
                it_text = it_text[:mm.start()] + _wrap(target, mm.group(0)) + it_text[mm.end():]
                placed = True
                break
        if not placed:
            missing.append(target)
    return it_text, missing
