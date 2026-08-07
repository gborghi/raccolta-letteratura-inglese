# -*- coding: utf-8 -*-
"""Repair Italian-side marker artifacts in vault .it.md siblings, using the emitter's EXACT
block model (sbtrans.split_blocks / clean_body / has_prose, same as gkc_emit_vault.prose_parts):

  1. STRAY HEADING  — Tower prepended '#'/'##' to a block whose EN counterpart is plain prose
     (e.g. EN 'CHAPTER I\\nGOING AWAY'  ->  IT '# CAPITOLO I\\nALLONTANANDOSI'). Renders a giant
     H1 mid-chapter and diverges from the English page. Fix: strip the leading '#{1,6}\\s*' from the
     block's first line. Count-preserving; only applied where index-aligned EN block is NOT a heading.

  1b. EATEN EMPHASIS — the dominant shape of the same defect: Tower ATE a leading '_' and emitted
     '#' in its place, so EN '_Lady Susan Vernon to Mr. Vernon._' came back as
     '#Lady Susan Vernon e il signor Vernon_' — an orphaned trailing '_' left dangling. Where the
     index-aligned EN block is whole-block emphasis ('_...._'), the fix RESTORES THE PAIR
     ('#X_' -> '_X_') instead of merely stripping the '#'. Same safety gate as (1).

  2. DUPLICATE HEADING — the heading-translation pass left TWO near-identical title heading blocks
     back-to-back (one curated, one garbled Tower leftover), so IT has one prose block too many and
     gkc_emit_vault silently skips the whole page. Fix: drop the second of a consecutive
     near-duplicate heading pair until the IT prose-block count matches EN.

Safety: an atom is written only if the edit does NOT increase its EN/IT prose-count distance; a
structural dedupe is accepted only when it lands the count EXACTLY on EN's. Atoms still mismatched
after repair (paragraph blank-splits / dropped blocks — need retranslation) are printed as a queue
and left untouched.

  python repair_dickens_it_headings.py                        # DRY RUN, Dickens (default)
  python repair_dickens_it_headings.py --author Austen        # DRY RUN, one author
  python repair_dickens_it_headings.py --author Austen,Poe    # DRY RUN, several
  python repair_dickens_it_headings.py --all                  # DRY RUN, every author dir
  python repair_dickens_it_headings.py --author Austen --write # apply
  extra: --samples N (print N before/after diffs per author)  --list-mismatch (full queue)
"""
import os, sys, re, glob, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sbtrans import clean_body, split_blocks, has_prose

AUTHORS_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                           "..", "..", "..", "VaultEnglish", "Authors"))
DEFAULT_AUTHORS = ["Dickens"]
FM_RE = re.compile(r"^(---\r?\n.*?\r?\n---\r?\n?)(.*)$", re.S)
HEAD_RE = re.compile(r"^\s*#{1,6}\s*")
# Tower sometimes marked every line of a run, not only the block's first: a three-line
# EN heading run came back as '#La notte...\n#Il villaggio...\n#Il grido...'. HEAD_RE
# only reaches the first one. Stripping the rest is safe exactly where the STRIP branch
# runs (the aligned EN block is known not to be a heading, so no line of it is one) and
# cannot move a block boundary, since blocks split on blank lines.
MIDLINE_GLUED_RE = re.compile(r"^([ \t]*)#{1,6}(?=[^#\s])", re.M)
# the corruption signature: a '#' run GLUED to the line's first word (no space after it).
# NB deliberately excludes '# Real Heading' (space) and '#graph/...' style tag lines never occur
# under Authors/ — those live in the vault's 'Knowledge Graph/' tree, outside this BASE.
# GLUED0 is column-0-anchored (the baseline census grep); GLUED_RE also catches the indented
# variant '    #Uno… due… tre…' that verse/blockquote atoms carry — same defect, same fix.
GLUED0_RE = re.compile(r"^#{1,6}[^#\s]", re.M)
GLUED_RE = re.compile(r"^[ \t]*#{1,6}[^#\s]", re.M)
# whole-block emphasis: '_...._' with no doubled underscore at either edge (not '__bold__')
EMPH_RE = re.compile(r"^_(?!_)(?P<inner>.+?)(?<!_)_$", re.S)
WS_RE = re.compile(r"^(\s*)(.*?)(\s*)$", re.S)


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


def is_glued(part):
    """True when this block carries the corruption signature on its FIRST line."""
    return bool(GLUED_RE.match(clean_body(part).strip()))


def is_emph_block(part):
    """True when this (EN) block is wholly wrapped in '_..._' emphasis."""
    return bool(EMPH_RE.match(clean_body(part).strip()))


def restore_emph(part):
    """'#Lady Susan alla signora Johnson_'  ->  '_Lady Susan alla signora Johnson_'.

    Replaces the eaten leading '_' and re-pairs the orphaned trailing one (adding it back when
    Tower ate that too). Leading/trailing block whitespace is preserved verbatim."""
    lead, core, trail = WS_RE.match(part).groups()
    inner = HEAD_RE.sub("", core, count=1)
    if inner.endswith("_") and not inner.endswith("__"):
        inner = inner[:-1].rstrip()
    if not inner:
        return part
    if inner.startswith("_"):                       # already emphasised — just drop the marker
        return lead + inner + trail
    return lead + "_" + inner + "_" + trail


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
    """Return (new_it_body, stats, resolved_bool, en_n, it_n_final).

    stats keys: stray / emph (edits made), stray_glued / emph_glued (of which carried the
    GLUED_RE signature), dedup, glued0 / glued (occurrences before, col-0 / indent-tolerant),
    rep0 / rep (occurrences actually removed), skip_count / skip_enhead / skip_midblock (glued
    occurrences left behind, by reason), samples (list of (kind, en_block, before, after))."""
    parts = split_blocks(it_body)                       # [block, sep, block, sep, ...] preserved
    en_prose = prose_list(en_body)
    target = len(en_prose)
    st = {k: 0 for k in ("stray", "emph", "emph_orphan", "stray_glued", "emph_glued", "dedup",
                         "glued0", "glued", "rep0", "rep",
                         "skip_count", "skip_enhead", "skip_midblock")}
    st["samples"] = []
    st["glued0"] = len(GLUED0_RE.findall(it_body))
    st["glued"] = len(GLUED_RE.findall(it_body))

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
                st["dedup"] += 1
                changed = True
                break

    # ---- pass 2: fix stray '#' where index-aligned EN block is NOT a heading (count-matched only) ----
    pidx = prose_idx(parts)
    if len(pidx) == target:
        for k, i in enumerate(pidx):
            head = is_heading(parts[i])
            # A block whose FIRST line was already repaired can still carry marked lines
            # below it, so the block's first line is not the only way in.
            if not head and not MIDLINE_GLUED_RE.search(parts[i]):
                continue
            glued = is_glued(parts[i])
            if en_prose[k].lstrip().startswith("#"):    # EN is a real heading -> IT's is legit
                st["skip_enhead"] += 1 if glued else 0
                continue
            if head and is_emph_block(en_prose[k]):
                new, kind, key = restore_emph(parts[i]), "EMPH", "emph"
                if parts[i].rstrip().endswith("_"):     # orphaned trailing '_' left by Tower
                    st["emph_orphan"] += 1
            else:
                new = MIDLINE_GLUED_RE.sub(r"\1", HEAD_RE.sub("", parts[i], count=1))
                kind, key = "STRIP", "stray"
            if new != parts[i]:
                if len(st["samples"]) < 4:
                    st["samples"].append((kind, clean_body(en_prose[k]).strip(),
                                          parts[i].strip(), new.strip()))
                parts[i] = new
                st[key] += 1
                st[key + "_glued"] += 1 if glued else 0

    new_body = "".join(parts)
    it_n = len(prose_list(new_body))
    # residual glued occurrences, attributed to a reason
    left = len(GLUED_RE.findall(new_body))
    st["rep0"] = st["glued0"] - len(GLUED0_RE.findall(new_body))
    st["rep"] = st["glued"] - left
    if it_n != target:
        st["skip_count"] = left                         # pass 2 never ran / could not run
        st["skip_enhead"] = 0
    else:
        st["skip_midblock"] = max(0, left - st["skip_enhead"])
    resolved = (it_n == target)
    return new_body, st, resolved, target, it_n


def parse_authors(argv):
    names = []
    for i, a in enumerate(argv):
        if a == "--author" and i + 1 < len(argv):
            names += [x.strip() for x in argv[i + 1].split(",") if x.strip()]
        elif a.startswith("--author="):
            names += [x.strip() for x in a.split("=", 1)[1].split(",") if x.strip()]
    if "--all" in argv:
        names += sorted(d for d in os.listdir(AUTHORS_DIR)
                        if os.path.isdir(os.path.join(AUTHORS_DIR, d)) and not d.startswith("."))
    seen, out = set(), []
    for n in (names or DEFAULT_AUTHORS):
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def run_author(author, write, nsamples, list_mismatch):
    base = os.path.join(AUTHORS_DIR, author)
    if not os.path.isdir(base):
        print(f"!! no such author dir: {base}")
        return None
    its = [p for sub in ("Atomized", "Long")
           for p in glob.glob(os.path.join(base, sub, "**", "*.it.md"), recursive=True)]
    agg = {k: 0 for k in ("files", "glued0", "glued", "rep0", "rep", "stray", "emph",
                          "emph_orphan", "stray_glued", "emph_glued", "dedup",
                          "skip_count", "skip_enhead", "skip_midblock")}
    still_mismatch, samples = [], []
    for it_path in sorted(its):
        en_path = it_path[:-6] + ".md"
        if not os.path.exists(en_path):
            continue
        raw_it = open(_lp(it_path), encoding="utf-8").read()
        raw_en = open(_lp(en_path), encoding="utf-8").read()
        _, en_body = split_fm(raw_en)
        fm, it_body = split_fm(raw_it)
        new_body, st, resolved, en_n, it_n = repair_body(en_body, it_body)
        g0 = st["glued"]
        for k in ("glued0", "glued", "rep0", "rep", "stray", "emph", "emph_orphan",
                  "stray_glued", "emph_glued", "dedup",
                  "skip_count", "skip_enhead", "skip_midblock"):
            agg[k] += st[k]
        if new_body != it_body:
            agg["files"] += 1
            if len(samples) < nsamples:
                for s in st["samples"]:
                    if len(samples) < nsamples:
                        samples.append((os.path.relpath(it_path, AUTHORS_DIR),) + s)
            if write:
                with open(_lp(it_path), "w", encoding="utf-8") as fh:
                    fh.write(fm + new_body)
        if not resolved:
            still_mismatch.append((os.path.relpath(it_path, base), en_n, it_n, g0))

    rep = agg["rep"]
    skip = agg["glued"] - rep
    print(f"\n=== {author} === {'WROTE' if write else 'DRY RUN'}")
    print(f"  .it.md scanned         : {len(its)}")
    print(f"  glued-# occurrences    : {agg['glued']}  "
          f"(col-0 {agg['glued0']} + indented {agg['glued'] - agg['glued0']})")
    print(f"  files changed          : {agg['files']}")
    print(f"  restored _..._         : {agg['emph']}   (of which glued-#: {agg['emph_glued']}; "
          f"orphan trailing _ {agg['emph_orphan']}, both _ eaten {agg['emph'] - agg['emph_orphan']})")
    print(f"  stripped stray #       : {agg['stray']}   (of which glued-#: {agg['stray_glued']})")
    print(f"  duplicate headings cut : {agg['dedup']}")
    print(f"  glued-# repaired       : {rep}  (col-0 {agg['rep0']})")
    print(f"  glued-# SKIPPED        : {skip}  "
          f"[count-divergence {agg['skip_count']} | EN-is-heading {agg['skip_enhead']} | "
          f"mid-block {agg['skip_midblock']}]")
    print(f"  atoms still mismatched : {len(still_mismatch)} "
          f"(carrying {sum(m[3] for m in still_mismatch)} glued-#)")
    for r in (still_mismatch if list_mismatch else still_mismatch[:10]):
        print(f"    MISMATCH EN={r[1]} IT={r[2]} glued={r[3]}  {r[0]}")
    if not list_mismatch and len(still_mismatch) > 10:
        print(f"    ... +{len(still_mismatch) - 10} more (use --list-mismatch)")
    for s in samples:
        print(f"  [{s[1]}] {s[0]}")
        print(f"      EN : {s[2][:110]}")
        print(f"      -  : {s[3][:110]}")
        print(f"      +  : {s[4][:110]}")
    agg["author"] = author
    agg["repaired"] = rep
    agg["skipped"] = skip
    agg["mismatch_files"] = len(still_mismatch)
    agg["mismatch_glued"] = sum(m[3] for m in still_mismatch)
    return agg


def main():
    write = "--write" in sys.argv
    list_mismatch = "--list-mismatch" in sys.argv
    nsamples = 0
    for i, a in enumerate(sys.argv):
        if a == "--samples" and i + 1 < len(sys.argv):
            nsamples = int(sys.argv[i + 1])
        elif a.startswith("--samples="):
            nsamples = int(a.split("=", 1)[1])
    rows = [r for r in (run_author(a, write, nsamples, list_mismatch)
                        for a in parse_authors(sys.argv)) if r]

    print("\n" + "=" * 104)
    print(f"{'author':<14}{'files':>7}{'glued0':>8}{'glued':>8}{'restored_':>11}{'stripped#':>11}"
          f"{'repaired':>10}{'skipped':>9}{'mismatch':>10}")
    tot = {k: 0 for k in ("files", "glued0", "glued", "emph_glued", "stray_glued",
                          "repaired", "rep0", "skipped", "mismatch_files")}
    for r in rows:
        print(f"{r['author']:<14}{r['files']:>7}{r['glued0']:>8}{r['glued']:>8}"
              f"{r['emph_glued']:>11}{r['stray_glued']:>11}{r['repaired']:>10}"
              f"{r['skipped']:>9}{r['mismatch_files']:>10}")
        for k in tot:
            tot[k] += r[k]
    print("-" * 104)
    print(f"{'TOTAL':<14}{tot['files']:>7}{tot['glued0']:>8}{tot['glued']:>8}"
          f"{tot['emph_glued']:>11}{tot['stray_glued']:>11}{tot['repaired']:>10}"
          f"{tot['skipped']:>9}{tot['mismatch_files']:>10}")
    print(f"reconcile (indent-tolerant): repaired {tot['repaired']} + skipped {tot['skipped']} = "
          f"{tot['repaired'] + tot['skipped']}  vs glued-# found {tot['glued']}  "
          f"(delta {tot['repaired'] + tot['skipped'] - tot['glued']})")
    print(f"reconcile (col-0 census)   : repaired {tot['rep0']} + skipped "
          f"{tot['glued0'] - tot['rep0']} = {tot['glued0']}  vs glued-# found {tot['glued0']}")
    print(f"edit-split check           : restored_ {tot['emph_glued']} + stripped# "
          f"{tot['stray_glued']} = {tot['emph_glued'] + tot['stray_glued']}  vs repaired "
          f"{tot['repaired']}  (delta {tot['emph_glued'] + tot['stray_glued'] - tot['repaired']})")
    if not write:
        print("DRY RUN — nothing written. Re-run with --write to apply.")


if __name__ == "__main__":
    main()
