# -*- coding: utf-8 -*-
"""Re-atomise Chesterton's The Everlasting Man correctly.

The stock atomiser (atomize_prose.atomize_novel) mis-handles this book: its table of contents has
no "Contents" header, so the TOC's two "PART ..." lines inflate kw_count>=3 and the real chapters --
marked as a bare roman numeral on one line then an ALL-CAPS title on the next -- get discarded. The
result was 3 mangled units with Part II sorted before Part I.

Rather than patch the 660-line shared parser (16 other authors), this builds the correct `units`
list for THIS file only and reuses process_work's exact writing path via monkeypatch. Zero change to
atomize_prose.py on disk. Structure produced: 18 flat chapters (Introduction, Part I's I-VIII,
Part II's I-VI, Conclusion, Appendix I & II) in reading order, matching the Emma/manalive convention.

Usage:
  python3 reatomize-everlasting-man.py            # DRY RUN -> writes to a temp dir, reports, keeps vault untouched
  python3 reatomize-everlasting-man.py --apply    # rewrite the real vault atoms (force)
"""
import os, sys, re, importlib.util, tempfile, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.abspath(os.path.join(HERE, "..", "..", "VaultEnglish"))
AP_PATH = os.path.join(VAULT, "graphify-out", "lit", "atomize_prose.py")
RAW = os.path.join(VAULT, "Authors", "Chesterton", "_raw", "everlasting_man.md")

spec = importlib.util.spec_from_file_location("atomize_prose", AP_PATH)
ap = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(ap)
except SystemExit:
    pass

# Section headers that begin a chapter (PART is special: a grouping label, skipped below).
# "PREFA?RATORY NOTE" carries the source's own typo ("PREFARATORY").
PART_RE = re.compile(r"^(PART\s+[IVXLC]+|INTRODUCTION|CONCLUSION|APPENDIX\s+[IVXLC]+"
                     r"|PREFA?RATORY\s+NOTE)\b", re.I)
ROMAN_LINE_RE = re.compile(r"^[IVXLC]{1,6}\.?$")
# The body's first real section is the Prefatory Note (or Introduction). Its ALL-CAPS standalone
# form distinguishes it from the title-case TOC entry ("  Prefatory Note").
BODY_START_RE = re.compile(r"^(PREFA?RATORY\s+NOTE|INTRODUCTION)$")


def plain(s):
    """De-wikilink a title for display: [[Cave|CAVE]] -> CAVE, [[Faith]] -> Faith."""
    s = re.sub(r"\[\[[^\]|]+\|([^\]]+)\]\]", r"\1", s)
    s = re.sub(r"\[\[([^\]]+)\]\]", r"\1", s)
    return s.strip()


def titlecase(s):
    # ALL-CAPS chapter titles -> Title Case; keep short words lower where natural is overkill,
    # a simple .title() reads fine for these headings.
    return plain(s).title() if plain(s).isupper() else plain(s)


def _is_chapter_marker(L, j):
    """A bare-roman line j is a chapter marker if the next non-blank line is an ALL-CAPS title."""
    nxt = next((L[k].strip() for k in range(j + 1, min(j + 5, len(L))) if L[k].strip()), "")
    p = plain(nxt)
    return bool(p) and p == p.upper() and len(p) > 3


def build_units(full_text):
    """Return the correct chapter units in reading order."""
    lines = full_text.split("\n")

    # The real body begins at the first STANDALONE all-caps section header (Prefatory Note, else
    # Introduction). The table of contents lists them title-cased and indented ("  Prefatory Note"),
    # so an exact all-caps match skips the whole TOC unambiguously -- no fragile length heuristic.
    body_start = next((i for i, l in enumerate(lines) if BODY_START_RE.match(l.strip().upper())), 0)

    bounds = []  # (line, title)
    i = body_start
    while i < len(lines):
        s = lines[i].strip()
        m = PART_RE.match(s)
        if m:
            kw = m.group(0).upper()
            if kw.startswith("PART"):
                i += 1
                continue                       # a PART header is a grouping label, not its own chapter
            bounds.append((i, plain(s)))       # INTRODUCTION / CONCLUSION / APPENDIX are chapters
            i += 1
            continue
        if ROMAN_LINE_RE.match(s) and _is_chapter_marker(lines, i):
            j = next(k for k in range(i + 1, len(lines)) if lines[k].strip())
            bounds.append((i, titlecase(lines[j].strip())))
            i = j + 1
            continue
        i += 1

    if os.environ.get("EV_DEBUG"):
        for li, t in bounds:
            print(f"    boundary L{li:>5}: {t}")

    # A chapter that is the last of its Part carries the next Part's divider at its tail:
    #   "\n\nPART II\n\nOn the Man Called Christ\n\n* * *\n"
    # Trim that trailing grouping label so it doesn't dangle after the prose.
    TAIL_DIVIDER = re.compile(
        r"\n\s*PART\s+[IVXLC]+[^\n]*\n(?:\s*[^\n]{0,60}\n)?\s*\*\s*\*\s*\*\s*$", re.I)

    units = []
    for k, (li, title) in enumerate(bounds):
        end = bounds[k + 1][0] if k + 1 < len(bounds) else len(lines)
        seg = "\n".join(lines[li:end]).strip("\n")
        seg = TAIL_DIVIDER.sub("", seg).rstrip() + "\n"
        units.append({"kind": "chapter", "num": k + 1, "title": title, "text": seg.strip("\n"), "line": li})
    return units


def run(apply):
    full = open(RAW, encoding="utf-8").read()
    full = ap.strip_gutenberg_tail(full)
    units = build_units(full)

    # coverage: every non-frontmatter character must land in some unit
    covered = sum(len(u["text"]) for u in units)
    print(f"units: {len(units)} | coverage {covered}/{len(full)} = {100*covered/len(full):.1f}% of full text")
    for u in units:
        print(f"  Chapter_{u['num']:02d}  L{u['line']:>5}  {len(u['text']):>7} chars  {u['title'][:50]}")

    # force process_work down the novel path with OUR units
    orig = ap.atomize_novel
    ap.atomize_novel = lambda title, ft, od, slug, _u=units: (_u if slug == "everlasting_man" else orig(title, ft, od, slug))

    if apply:
        target_root = VAULT
    else:
        target_root = tempfile.mkdtemp(prefix="ev_dryrun_")
        # process_work writes under ROOT/Authors/... ; point ap.ROOT at the temp tree
    real_root = ap.ROOT
    ap.ROOT = target_root
    try:
        res = ap.process_work("Chesterton", RAW, force=True)
    finally:
        ap.ROOT = real_root
        ap.atomize_novel = orig

    out_dir = os.path.join(target_root, "Authors", "Chesterton", "Atomized", "everlasting_man")
    print(f"\nprocess_work -> {res}")
    print(f"wrote to: {out_dir}")
    idx = os.path.join(out_dir, "_index.tsv")
    if os.path.exists(idx):
        rows = [r.split("\t") for r in open(idx, encoding="utf-8").read().splitlines()]
        from collections import Counter
        print("  _index.tsv kinds:", dict(Counter(r[0] for r in rows)))
        print("  chapters:")
        for r in rows:
            if r[0] == "chapter":
                print(f"     {r[1]}")
    if not apply:
        print(f"\nDRY RUN. Inspect {out_dir}, then re-run with --apply. (temp dir not auto-deleted)")


if __name__ == "__main__":
    run("--apply" in sys.argv)
