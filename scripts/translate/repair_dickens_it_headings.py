# -*- coding: utf-8 -*-
"""Repair two Italian-side artifacts in Dickens vault .it.md siblings, using the emitter's EXACT
block model (sbtrans.split_blocks / clean_body / has_prose, same as gkc_emit_vault.prose_parts):

  1. STRAY HEADING  — Tower prepended '#'/'##' to a block whose EN counterpart is plain prose
     (e.g. EN 'CHAPTER I\\nGOING AWAY'  ->  IT '# CAPITOLO I\\nALLONTANANDOSI'). Renders a giant
     H1 mid-chapter and diverges from the English page. Fix: strip the leading '#{1,6}\\s*' from the
     block's first line. Count-preserving; only applied where index-aligned EN block is NOT a heading.

  2. DUPLICATE HEADING — the heading-translation pass left TWO near-identical title heading blocks
     back-to-back (one curated, one garbled Tower leftover), so IT has one prose block too many and
     gkc_emit_vault silently skips the whole page. Fix: drop the second of a consecutive
     near-duplicate heading pair until the IT prose-block count matches EN.

Safety: an atom is written only if the edit does NOT increase its EN/IT prose-count distance; a
structural dedupe is accepted only when it lands the count EXACTLY on EN's. Atoms still mismatched
after repair (paragraph blank-splits / dropped blocks — need retranslation) are printed as a queue
and left untouched.

  python repair_dickens_it_headings.py            # DRY RUN
  python repair_dickens_it_headings.py --write     # apply
"""
import os, sys, re, glob, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sbtrans import clean_body, split_blocks, has_prose

BASE = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", "..", "..", "VaultEnglish", "Authors", "Dickens"))
FM_RE = re.compile(r"^(---\r?\n.*?\r?\n---\r?\n?)(.*)$", re.S)
HEAD_RE = re.compile(r"^\s*#{1,6}\s*")


def _lp(p):
    if os.name == "nt":
        ap = os.path.abspath(p)
        if not ap.startswith("\\\\?\\"):
            return "\\\\?\\" + ap
    return p


def split_fm(raw):
    m = FM_RE.match(raw)
    return (m.group(1), m.group(2)) if m else ("", raw)


def is_prose_part(part):
    """Mirror emitter prose_parts(): evaluate the emitter's predicate on the part's cleaned form."""
    p = clean_body(part).strip()
    return bool(p) and not p.startswith("<nav") and has_prose(p)


def is_heading(part):
    return clean_body(part).strip().startswith("#")


def prose_list(body):
    return [part for part in split_blocks(body) if is_prose_part(part)]


def _norm(part):
    t = HEAD_RE.sub("", clean_body(part).strip().split("\n", 1)[0]).lower()
    return re.sub(r"[^0-9a-zàèéìòù]+", " ", t).split()


def _dup(a, b):
    """Two consecutive heading blocks that are the SAME title emitted twice (curated + garbled)."""
    ta, tb = _norm(a), _norm(b)
    if not ta or not tb:
        return False
    sa, sb = set(ta), set(tb)
    jac = len(sa & sb) / len(sa | sb)
    return jac >= 0.6


def repair_body(en_body, it_body):
    """Return (new_it_body, n_stray_stripped, n_dedup, resolved_bool, en_n, it_n_final)."""
    parts = split_blocks(it_body)                       # [block, sep, block, sep, ...] preserved
    en_prose = prose_list(en_body)
    target = len(en_prose)
    n_stray = n_dedup = 0

    # ---- pass 1: dedupe consecutive near-duplicate heading blocks while IT is too long ----
    def prose_idx(parts):
        return [i for i, p in enumerate(parts) if is_prose_part(p)]

    changed = True
    while changed and len(prose_idx(parts)) > target:
        changed = False
        pidx = prose_idx(parts)
        for a, b in zip(pidx, pidx[1:]):
            if is_heading(parts[a]) and is_heading(parts[b]) and _dup(parts[a], parts[b]):
                # drop block b and the separator immediately before it (a..b gap) to keep spacing sane
                sep = b - 1
                del parts[b]
                if sep > a and sep < len(parts) and not is_prose_part(parts[sep]) and not parts[sep].strip():
                    del parts[sep]
                n_dedup += 1
                changed = True
                break

    # ---- pass 2: strip stray '#' where index-aligned EN block is NOT a heading (count-matched only) ----
    pidx = prose_idx(parts)
    if len(pidx) == target:
        for k, i in enumerate(pidx):
            if is_heading(parts[i]) and not en_prose[k].lstrip().startswith("#"):
                new = HEAD_RE.sub("", parts[i], count=1)
                if new != parts[i]:
                    parts[i] = new
                    n_stray += 1

    new_body = "".join(parts)
    it_n = len(prose_list(new_body))
    resolved = (it_n == target)
    return new_body, n_stray, n_dedup, resolved, target, it_n


def main():
    write = "--write" in sys.argv
    its = [p for sub in ("Atomized", "Long")
           for p in glob.glob(os.path.join(BASE, sub, "**", "*.it.md"), recursive=True)]
    files_written = tot_stray = tot_dedup = 0
    still_mismatch = []
    for it_path in its:
        en_path = it_path[:-6] + ".md"
        if not os.path.exists(en_path):
            continue
        raw_it = open(_lp(it_path), encoding="utf-8").read()
        raw_en = open(_lp(en_path), encoding="utf-8").read()
        _, en_body = split_fm(raw_en)
        fm, it_body = split_fm(raw_it)
        new_body, ns, nd, resolved, en_n, it_n = repair_body(en_body, it_body)
        if new_body != it_body:
            tot_stray += ns
            tot_dedup += nd
            files_written += 1
            if write:
                with open(_lp(it_path), "w", encoding="utf-8") as fh:
                    fh.write(fm + new_body)
        if not resolved:
            still_mismatch.append((os.path.relpath(it_path, BASE), en_n, it_n))

    print(f"{'WROTE' if write else 'DRY RUN'}: files changed={files_written} | "
          f"stray-# stripped={tot_stray} | duplicate headings removed={tot_dedup}")
    print(f"atoms STILL mismatched after repair (retranslation queue) = {len(still_mismatch)}")
    for r in still_mismatch:
        print(f"  MISMATCH EN={r[1]} IT={r[2]}  {r[0]}")


if __name__ == "__main__":
    main()
