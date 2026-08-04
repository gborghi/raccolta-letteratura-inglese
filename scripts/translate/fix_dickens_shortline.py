# -*- coding: utf-8 -*-
"""Rescue Dickens atoms that REJECTed, without re-running the model.

Two recurring, un-retryable failures make an atom unpublishable (the emitter skips any page whose
EN/IT prose-block counts differ, or whose IT carries a wikilink target that names no concept note):

  1. has_prose short-line asymmetry. The block guard requires a >=3-letter word. A curt English
     reply "Yes." (3 letters) is a prose block, but its faithful "Sì." (2 letters) is NOT -> the IT
     side loses a block (25 EN vs 24 IT). Cure: a per-block manual override that stays faithful AND
     carries a >=3-letter word (same fix used by hand for The Flying Inn: "But-." -> "Però...»").

  2. glued mask code. The model drops the pipe and fuses the opaque code onto the Italian word:
     [[L01|summer]] -> [[L01estate]], so unmask_links can't restore it and validate() sees an
     invented target 'L01estate'. Cure: a literal token replacement over the cached IT
     ([[L01estate]] -> [[Summer|estate]]) -- pure markup repair, no re-translation.

Every OTHER block comes straight from the shared Tower cache (read-only -- we never write the cache
file while the main batch may be appending), so this is instant and only writes each <atom>.it.md.

Usage:  python3 fix_dickens_shortline.py [--write]
Add an entry to REPAIRS per rescued atom.
"""
import os, sys, json, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dickens_tower as dt
from sbtrans import clean_body, split_blocks, has_prose

WRITE = "--write" in sys.argv

# One entry per rescued atom.
#   corrections: {exact stripped EN block -> faithful IT literal}  (short-line rescues)
#   linkfix:     {bad token substring -> correct [[Target|label]]} applied to every cached IT block
REPAIRS = {
    "Authors/Dickens/Atomized/Oliver_Twist/Chapter_08/part_02.md": {
        # Oliver confirming he is going to London; echo the verb so "Sì" isn't a bare 2-letter block.
        "corrections": {"“Yes.”": "«Sì, ci vado.»"},
    },
    "Authors/Dickens/Atomized/Oliver_Twist/Chapter_37/part_03.md": {
        # Monks confirming "the time, night." A terse affirmation; "esatto" keeps it >=3 letters.
        "corrections": {"“Yes.”": "«Sì, esatto.»"},
    },
    "Authors/Dickens/Atomized/Oliver_Twist/Chapter_38/part_01.md": {
        # Model glued the codes onto the words; restore the masked targets Summer/Storm/River.
        "linkfix": {
            "[[L01estate]]": "[[Summer|estate]]",
            "[[L02tempesta]]": "[[Storm|tempesta]]",
            "[[L03fiume]]": "[[River|fiume]]",
        },
    },
    "Authors/Dickens/Atomized/Oliver_Twist/Chapter_42/part_02.md": {
        # REJECTed 33 vs 32 during the run (a block's first sample came back non-prose), but the
        # cache now holds a prose IT for every block -> rebuilds clean from cache, no override.
    },
    "Authors/Dickens/Atomized/Oliver_Twist/Chapter_47/part_02.md": {
        # Recovered after a fabrication FAIL; re-translation left two identical "Yes." (Noah
        # confirming to Fagin) as bare "Sì." -> both dropped (56 vs 54). Same faithful confirmation
        # for both occurrences, as Dickens repeats the word verbatim.
        "corrections": {"“Yes.”": "«Sì, esatto.»"},
    },
    # ---- Great Expectations short-line rescues (IT one block short; curt reply lost >=3-letter word)
    "Authors/Dickens/Atomized/Great_Expectations/Chapter_02/part_01.md": {
        # Pip to Joe, who says Mrs Joe is out looking for him: an incredulous echo. 26 vs 25.
        "corrections": {"“Is she?”": "\"Davvero?\""},
    },
    "Authors/Dickens/Atomized/Great_Expectations/Chapter_03.md": {
        # The convict pointing to his struck cheek ("Not here?"/"Yes, there!"). 48 vs 47.
        "corrections": {"“Yes, there!”": "\"Sì, proprio lì!\""},
    },
    "Authors/Dickens/Atomized/Great_Expectations/Chapter_22/part_01.md": {
        # Two bare replies in Herbert's account of Miss Havisham. 37 vs 35.
        "corrections": {"“Indeed?”": "\"Davvero?\"", "“Yes.”": "\"Sì, esatto.\""},
    },
    "Authors/Dickens/Atomized/Great_Expectations/Chapter_22/part_03.md": {
        # "do you mean ... the young fellow?" / "Yes; to you." emphatic. 39 vs 38.
        "corrections": {"“Yes; to you.”": "\"Sì, proprio a te.\""},
    },
    "Authors/Dickens/Atomized/Great_Expectations/Chapter_29/part_02.md": {
        # Pip's reluctant admission that he read with the tutor's father. 36 vs 35.
        "corrections": {"“Yes.”": "\"Sì, è così.\""},
    },
    "Authors/Dickens/Atomized/Great_Expectations/Chapter_40/part_01.md": {
        # Emphatic "Yes. Oh yes." confirming he saw the man. 21 vs 20.
        "corrections": {"“Yes. Oh yes.”": "\"Sì. Oh, sì davvero.\""},
    },
    "Authors/Dickens/Atomized/Great_Expectations/Chapter_49/part_02.md": {
        # Answer to "Is she married?" — echo the verb to keep a >=3-letter word. 34 vs 33.
        "corrections": {"“Yes.”": "\"Sì, è sposata.\""},
    },
    "Authors/Dickens/Atomized/Great_Expectations/Chapter_57/part_03.md": {
        # "Him as sent the bank-notes, Pip?" / "Yes." — echo "him". 27 vs 26.
        "corrections": {"“Yes.”": "\"Sì, proprio lui.\""},
    },
}


def load_cache():
    d = {}
    if os.path.exists(dt.CACHE_PATH):
        for ln in open(dt.CACHE_PATH, encoding="utf-8"):
            ln = ln.strip()
            if ln:
                r = json.loads(ln)
                d[r["h"]] = r["it"]
    return d


def rescue(rel, spec, cache):
    corrections = spec.get("corrections", {})
    linkfix = spec.get("linkfix", {})
    en_path = os.path.join(dt.VAULT_ROOT, rel)
    body = open(en_path, encoding="utf-8").read()
    verse = "/Poems/" in en_path.replace(os.sep, "/") or "/Long/" in en_path.replace(os.sep, "/")
    parts = split_blocks(clean_body(body))
    bp = dt.boilerplate_mask(parts)

    out, applied, gaps = [], [], []
    for k, part in enumerate(parts):
        s = part.strip()
        # YAML frontmatter (some atoms carry a tags block) trips has_prose on words like "tags",
        # but must never be translated: pass it verbatim. It stays identical on both sides, so
        # prose_blocks counts it equally and preprocess strips it at render time either way.
        if not s or s.startswith("<nav") or s.startswith("---") or not has_prose(s) or bp[k]:
            out.append(part)
            continue
        if s in corrections:
            it = corrections[s]
            applied.append(("correction", s[:50], it))
        else:
            it = cache.get(dt.sha(s))
            if it is None:
                gaps.append(s[:60])
                out.append(part)
                continue
            for bad, good in linkfix.items():
                if bad in it:
                    it = it.replace(bad, good)
                    applied.append(("linkfix", bad, good))
        lead = part[:len(part) - len(part.lstrip())]
        trail = part[len(part.rstrip()):]
        qm = re.match(r"(>+\s*)", s)
        if qm and not it.startswith(">"):
            it = qm.group(1) + it
        out.append(lead + it.strip() + trail)

    it_body = "".join(out)
    print(f"\n########## {rel} ##########")
    en_pb, it_pb = dt.prose_blocks(body), dt.prose_blocks(it_body)
    print(f"EN prose blocks: {len(en_pb)} | IT prose blocks: {len(it_pb)}")
    for kind, a, b in applied:
        print(f"  ✎ [{kind}] {a!r} -> {b!r}")
    if gaps:
        print(f"  ⚠ {len(gaps)} blocks NOT in cache (left English):")
        for g in gaps:
            print(f"     {g!r}")
    stray = re.findall(r"\[\[L\d{2}[^\]]*\]\]", it_body)
    if stray:
        print(f"  ⚠ stray mask codes remain: {stray}")
    problems = dt.validate(body, it_body, verse=verse)
    print("VALIDATION:", problems or "OK")

    ok = not problems and not gaps and not stray
    if WRITE and ok:
        open(en_path[:-3] + ".it.md", "w", encoding="utf-8").write(it_body)
        print("WROTE", en_path[:-3] + ".it.md")
    elif WRITE:
        print("NOT written (validation failed / cache gaps / stray codes)")
    return ok


def main():
    cache = load_cache()
    results = {rel: rescue(rel, spec, cache) for rel, spec in REPAIRS.items()}
    print("\n=== summary ===")
    for rel, ok in results.items():
        print(f"  {'OK ' if ok else 'FAIL'} {rel}")


if __name__ == "__main__":
    main()
